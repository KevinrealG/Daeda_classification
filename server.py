#!/usr/bin/env python3
"""
AquaVigía Colombia v3.0 — Backend REST + SQLite + YOLO

Ejecución local:
    python server.py
Abre en el navegador:
    http://127.0.0.1:8000
"""
import hashlib
import hmac
import json
import math
import mimetypes
import os
import re
import secrets
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

DB_PATH = os.path.join(os.path.dirname(__file__), "aquavigia.db")
PORT = int(os.environ.get("PORT", 8000))
HOST = os.environ.get("HOST", "127.0.0.1")
SESSION_TTL_SECONDS = 60 * 60
MAX_REQUEST_BYTES = 1_000_000
PASSWORD_ITERATIONS = 600_000
LEGACY_PASSWORD_SALT = "aquavigia_col_v3"
SECURE_COOKIE = os.environ.get("AQUAVIGIA_COOKIE_SECURE", "0") == "1"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

YOLO_MODEL = None
try:
    from ultralytics import YOLO

    model_path = os.path.join(os.path.dirname(__file__), "best_larva_yolo.pt")
    if os.path.exists(model_path):
        YOLO_MODEL = YOLO(model_path)
        print(f"[YOLO] Modelo Ultralytics cargado: {model_path}")
except ImportError:
    pass


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def hash_pw(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_pw(password, stored_hash):
    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            scheme, iterations, salt_hex, digest_hex = stored_hash.split("$", 3)
            if scheme != "pbkdf2_sha256":
                return False, False
            iterations = int(iterations)
            if iterations < 1 or iterations > PASSWORD_ITERATIONS:
                return False, False
            expected = bytes.fromhex(digest_hex)
            actual = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), iterations
            )
            return hmac.compare_digest(actual, expected), False
        except (ValueError, TypeError):
            return False, False

    legacy_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        LEGACY_PASSWORD_SALT.encode("utf-8"),
        100_000,
    ).hex()
    return hmac.compare_digest(legacy_hash, stored_hash), True


SESSIONS = {}
LOGIN_FAILURES = {}
REGISTRATION_ATTEMPTS = {}


class AquaVigiaHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args, directory=os.path.dirname(os.path.abspath(__file__)), **kwargs
        )

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(self), geolocation=(self)")
        self.send_header(
            "Content-Security-Policy",
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
        )
        super().end_headers()

    def _send_json(self, status, payload, headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status, message):
        return self._send_json(status, {"error": message})

    def _read_body(self):
        raw_length = self.headers.get("Content-Length", "0")
        if not raw_length.isdigit():
            raise ValueError("Longitud de solicitud inválida.")
        length = int(raw_length)
        if length <= 0:
            raise ValueError("Se requiere un cuerpo JSON.")
        if length > MAX_REQUEST_BYTES:
            raise OverflowError("La solicitud supera el tamaño permitido.")
        if "application/json" not in self.headers.get("Content-Type", "").lower():
            raise TypeError("El contenido debe ser JSON.")
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("JSON inválido.") from exc
        if not isinstance(data, dict):
            raise ValueError("El cuerpo JSON debe ser un objeto.")
        return data

    def _request_has_same_origin(self):
        origin = self.headers.get("Origin")
        if not origin:
            return True
        parsed_origin = urlparse(origin)
        return bool(parsed_origin.netloc) and parsed_origin.netloc.lower() == (
            self.headers.get("Host", "").lower()
        )

    def _get_session_token(self):
        cookie = SimpleCookie()
        cookie.load(self.headers.get("Cookie", ""))
        morsel = cookie.get("aquavigia_session")
        return morsel.value if morsel else None

    def _get_current_user(self):
        token = self._get_session_token()
        session = SESSIONS.get(token) if token else None
        if not session:
            return None
        if session["expires_at"] <= time.monotonic():
            SESSIONS.pop(token, None)
            return None
        return session["user"]

    def _require_admin(self):
        user = self._get_current_user()
        if not user:
            self._send_error_json(401, "Inicia sesión para continuar.")
            return None
        if user.get("role") != "admin":
            self._send_error_json(403, "Acceso exclusivo para administradores.")
            return None
        return user

    def _session_cookie(self, token, max_age):
        secure = "; Secure" if SECURE_COOKIE else ""
        return (
            f"aquavigia_session={token}; Path=/; Max-Age={max_age}; "
            f"HttpOnly; SameSite=Strict{secure}"
        )

    def _create_session(self, user):
        token = secrets.token_urlsafe(32)
        SESSIONS[token] = {
            "user": user,
            "expires_at": time.monotonic() + SESSION_TTL_SECONDS,
        }
        return token

    def _login_is_limited(self):
        now = time.monotonic()
        address = self.client_address[0]
        failures = [
            timestamp
            for timestamp in LOGIN_FAILURES.get(address, [])
            if now - timestamp < 15 * 60
        ]
        LOGIN_FAILURES[address] = failures
        return len(failures) >= 5

    def _record_login_failure(self):
        address = self.client_address[0]
        LOGIN_FAILURES.setdefault(address, []).append(time.monotonic())
        if len(LOGIN_FAILURES) > 512:
            cutoff = time.monotonic() - 15 * 60
            for key in list(LOGIN_FAILURES):
                recent = [ts for ts in LOGIN_FAILURES[key] if ts > cutoff]
                if recent:
                    LOGIN_FAILURES[key] = recent
                else:
                    LOGIN_FAILURES.pop(key, None)

    def _registration_is_limited(self):
        now = time.monotonic()
        address = self.client_address[0]
        attempts = [
            timestamp
            for timestamp in REGISTRATION_ATTEMPTS.get(address, [])
            if now - timestamp < 15 * 60
        ]
        if len(attempts) >= 5:
            REGISTRATION_ATTEMPTS[address] = attempts
            return True
        attempts.append(now)
        REGISTRATION_ATTEMPTS[address] = attempts
        return False

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Allow", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            return self._send_json(200, {"status": "online", "version": "3.0.0"})

        if parsed.path == "/api/auth/me":
            user = self._get_current_user()
            if not user:
                return self._send_error_json(401, "No hay una sesión activa.")
            return self._send_json(200, {"user": user})

        if parsed.path == "/api/reports":
            if not self._require_admin():
                return
            with closing(get_db()) as conn:
                rows = [
                    dict(row)
                    for row in conn.execute(
                        "SELECT * FROM reports ORDER BY timestamp DESC"
                    ).fetchall()
                ]
            return self._send_json(200, {"reports": rows})

        if parsed.path == "/api/users":
            if not self._require_admin():
                return
            with closing(get_db()) as conn:
                rows = [
                    dict(row)
                    for row in conn.execute(
                        "SELECT id, name, email, role, municipio, created_at "
                        "FROM users ORDER BY id ASC"
                    ).fetchall()
                ]
            return self._send_json(200, {"users": rows})

        if parsed.path in ("/", "/index.html", "/dashboard.html", "/app-storage.js"):
            return super().do_GET()
        return self._send_error_json(404, "Recurso no encontrado.")

    def do_HEAD(self):
        if urlparse(self.path).path in (
            "/",
            "/index.html",
            "/dashboard.html",
            "/app-storage.js",
        ):
            return super().do_HEAD()
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            return self._send_error_json(404, "Endpoint no encontrado.")
        if not self._request_has_same_origin():
            return self._send_error_json(403, "Origen de solicitud no permitido.")
        try:
            data = self._read_body()
        except OverflowError as exc:
            return self._send_error_json(413, str(exc))
        except TypeError as exc:
            return self._send_error_json(415, str(exc))
        except ValueError as exc:
            return self._send_error_json(400, str(exc))

        if parsed.path == "/api/auth/register":
            return self._register(data)
        if parsed.path == "/api/auth/login":
            return self._login(data)
        if parsed.path == "/api/auth/logout":
            token = self._get_session_token()
            if token:
                SESSIONS.pop(token, None)
            return self._send_json(
                200,
                {"ok": True},
                {"Set-Cookie": self._session_cookie("", 0)},
            )
        if parsed.path == "/api/auth/password":
            return self._change_password(data)
        if parsed.path == "/api/reports":
            return self._create_report(data)
        return self._send_error_json(404, "Endpoint no encontrado.")

    def _register(self, data):
        if self._registration_is_limited():
            return self._send_json(
                429,
                {"error": "Demasiados registros desde esta conexión. Intenta más tarde."},
                {"Retry-After": "900"},
            )
        name = data.get("name")
        email = data.get("email")
        password = data.get("password")
        municipio = data.get("municipio") or "Cartagena de Indias (Bolívar)"
        if not all(isinstance(value, str) for value in (name, email, password, municipio)):
            return self._send_error_json(400, "Los campos de registro deben ser texto.")
        name = name.strip()
        email = email.strip().lower()
        municipio = municipio.strip()
        if (
            not name
            or len(name) > 120
            or len(email) > 254
            or not EMAIL_PATTERN.fullmatch(email)
            or len(password) < 12
            or len(password) > 128
            or not municipio
            or len(municipio) > 120
        ):
            return self._send_error_json(
                400,
                "Revisa nombre, correo, municipio y contraseña (mínimo 12 caracteres).",
            )

        user = None
        try:
            with closing(get_db()) as conn:
                cursor = conn.execute(
                    "INSERT INTO users "
                    "(name, email, password_hash, role, municipio, created_at) "
                    "VALUES (?, ?, ?, 'user', ?, ?)",
                    (
                        name,
                        email,
                        hash_pw(password),
                        municipio,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                conn.commit()
                user = {
                    "id": cursor.lastrowid,
                    "name": name,
                    "email": email,
                    "role": "user",
                    "municipio": municipio,
                }
        except sqlite3.IntegrityError:
            return self._send_error_json(409, "El correo electrónico ya está registrado.")

        token = self._create_session(user)
        return self._send_json(
            201,
            {"user": user},
            {"Set-Cookie": self._session_cookie(token, SESSION_TTL_SECONDS)},
        )

    def _login(self, data):
        if self._login_is_limited():
            return self._send_json(
                429,
                {"error": "Demasiados intentos. Intenta más tarde."},
                {"Retry-After": "900"},
            )
        email = data.get("email")
        password = data.get("password")
        if not isinstance(email, str) or not isinstance(password, str):
            self._record_login_failure()
            return self._send_error_json(401, "Credenciales inválidas.")
        if len(password) > 128:
            self._record_login_failure()
            return self._send_error_json(401, "Credenciales inválidas.")
        email = email.strip().lower()
        with closing(get_db()) as conn:
            row = conn.execute(
                "SELECT id, name, email, password_hash, role, municipio "
                "FROM users WHERE email = ?",
                (email,),
            ).fetchone()
            stored_hash = row["password_hash"] if row else hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                LEGACY_PASSWORD_SALT.encode("utf-8"),
                100_000,
            ).hex()
            valid, is_legacy = verify_pw(password, stored_hash)
            if not row or not valid:
                self._record_login_failure()
                return self._send_error_json(401, "Credenciales inválidas.")
            if is_legacy:
                conn.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (hash_pw(password), row["id"]),
                )
                conn.commit()
            user = {
                "id": row["id"],
                "name": row["name"],
                "email": row["email"],
                "role": row["role"],
                "municipio": row["municipio"],
            }

        LOGIN_FAILURES.pop(self.client_address[0], None)
        token = self._create_session(user)
        return self._send_json(
            200,
            {"user": user},
            {"Set-Cookie": self._session_cookie(token, SESSION_TTL_SECONDS)},
        )

    def _change_password(self, data):
        user = self._get_current_user()
        if not user:
            return self._send_error_json(401, "Inicia sesión para cambiar la contraseña.")
        current_password = data.get("currentPassword")
        new_password = data.get("newPassword")
        if (
            not isinstance(current_password, str)
            or not isinstance(new_password, str)
            or len(current_password) > 128
            or not 12 <= len(new_password) <= 128
        ):
            return self._send_error_json(
                400, "La nueva contraseña debe tener entre 12 y 128 caracteres."
            )

        with closing(get_db()) as conn:
            row = conn.execute(
                "SELECT password_hash FROM users WHERE id = ?", (user["id"],)
            ).fetchone()
            if not row or not verify_pw(current_password, row["password_hash"])[0]:
                return self._send_error_json(401, "La contraseña actual es incorrecta.")
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_pw(new_password), user["id"]),
            )
            conn.commit()

        for token in [
            token
            for token, session in SESSIONS.items()
            if session["user"]["id"] == user["id"]
        ]:
            SESSIONS.pop(token, None)
        return self._send_json(
            200,
            {"ok": True},
            {"Set-Cookie": self._session_cookie("", 0)},
        )

    def _create_report(self, data):
        user = self._get_current_user()
        if not user:
            return self._send_error_json(401, "Inicia sesión para enviar un reporte.")

        try:
            lat = float(data.get("lat"))
            lng = float(data.get("lng"))
            risk_percent = float(data.get("riskPercent", 0))
            larva_percent = float(data.get("larvaPercent", 0))
            yolo_boxes = int(data.get("larvaBoxesCount", 0))
            yolo_pre = int(data.get("yoloPreNmsCount", 0))
        except (TypeError, ValueError, OverflowError):
            return self._send_error_json(400, "Los valores numéricos del reporte no son válidos.")
        if (
            not math.isfinite(lat)
            or not math.isfinite(lng)
            or not -90 <= lat <= 90
            or not -180 <= lng <= 180
            or not math.isfinite(risk_percent)
            or not 0 <= risk_percent <= 100
            or not math.isfinite(larva_percent)
            or not 0 <= larva_percent <= 100
            or not 0 <= yolo_boxes <= 100_000
            or not 0 <= yolo_pre <= 100_000
        ):
            return self._send_error_json(400, "Los valores numéricos del reporte están fuera de rango.")

        def report_text(key, default, limit=120):
            value = data.get(key, default)
            if not isinstance(value, str):
                raise ValueError
            value = value.strip()
            if not value or len(value) > limit:
                raise ValueError
            return value

        try:
            municipio = report_text("municipio", "Cartagena de Indias (Bolívar)")
            sector = report_text("sector", "Zona reportada")
            deposit_type = report_text("depositType", "Balde / Recipiente plástico")
        except ValueError:
            return self._send_error_json(400, "Los campos de texto del reporte no son válidos.")

        rep_id = f"AV-{secrets.token_hex(8)}"
        risk_level = "alto" if data.get("riskLevel") == "alto" else "bajo"
        virus_present = 1 if data.get("virusPresent") is True else 0
        status = (
            "virus-detectado"
            if virus_present
            else ("riesgo-detectado" if risk_level == "alto" else "sin-riesgo")
        )
        timestamp = datetime.now(timezone.utc).isoformat()

        try:
            with closing(get_db()) as conn:
                conn.execute(
                    "INSERT INTO reports "
                    "(id, user_email, lat, lng, municipio, sector, deposit_type, "
                    "risk_level, virus_present, risk_percent, larva_percent, "
                    "yolo_boxes_count, yolo_pre_nms_count, analysis_status, timestamp) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        rep_id,
                        user["email"],
                        lat,
                        lng,
                        municipio,
                        sector,
                        deposit_type,
                        risk_level,
                        virus_present,
                        risk_percent,
                        larva_percent,
                        yolo_boxes,
                        yolo_pre,
                        status,
                        timestamp,
                    ),
                )
                conn.commit()
        except sqlite3.IntegrityError:
            return self._send_error_json(409, "No fue posible guardar el reporte.")
        return self._send_json(201, {"ok": True, "id": rep_id, "status": status})


if __name__ == "__main__":
    mimetypes.add_type("application/javascript", ".js")
    print(f"Servidor AquaVigía v3.0 activo en http://{HOST}:{PORT}")
    HTTPServer((HOST, PORT), AquaVigiaHandler).serve_forever()
