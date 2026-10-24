#!/usr/bin/env python3
"""
AquaVigía Colombia v3.0 — Servidor Backend REST + Base de Datos SQLite + Motor YOLOv8 & Doble Clasificación
Ejecución local o en servidor:
    python3 server.py
Abre en el navegador: http://localhost:8000
"""
import os, json, sqlite3, hashlib, secrets, base64, mimetypes
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

DB_PATH = os.path.join(os.path.dirname(__file__), "aquavigia.db")
MODELS_JSON_PATH = os.path.join(os.path.dirname(__file__), "aquavigia_models_v2.json")
PORT = int(os.environ.get("PORT", 8000))

# Intentar cargar Ultralytics YOLOv8 si hay pesos entrenados best.pt o yolov8n.pt
YOLO_MODEL = None
try:
    from ultralytics import YOLO
    if os.path.exists("best_larva_yolo.pt"):
        YOLO_MODEL = YOLO("best_larva_yolo.pt")
        print("[YOLO] Modelo Ultralytics YOLOv8 cargado: best_larva_yolo.pt")
except Exception as e:
    YOLO_MODEL = None

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_pw(password, salt="aquavigia_col_v3"):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()

SESSIONS = {}  # token -> user dict

class AquaVigiaHandler(SimpleHTTPRequestHandler):
    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json(200, {"ok": True})

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _get_current_user(self):
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:].strip()
            return SESSIONS.get(token)
        return None

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            conn = get_db()
            u_cnt = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            r_cnt = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
            conn.close()
            return self._send_json(200, {
                "status": "online",
                "version": "3.0.0",
                "database": "SQLite3 (aquavigia.db)",
                "users_count": u_cnt,
                "reports_count": r_cnt,
                "yolo_engine": "Ultralytics YOLOv8 + Multi-Scale Grid 16x16/24x24 NMS"
            })

        if parsed.path == "/api/reports":
            conn = get_db()
            rows = [dict(r) for r in conn.execute("SELECT * FROM reports ORDER BY timestamp DESC").fetchall()]
            conn.close()
            return self._send_json(200, {"reports": rows})

        if parsed.path == "/api/users":
            user = self._get_current_user()
            if not user or user.get("role") != "admin":
                return self._send_json(403, {"error": "Acceso exclusivo para administradores"})
            conn = get_db()
            rows = [dict(r) for r in conn.execute("SELECT id, name, email, role, municipio, created_at FROM users ORDER BY id ASC").fetchall()]
            conn.close()
            return self._send_json(200, {"users": rows})

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        data = self._read_body()

        if parsed.path == "/api/auth/register":
            name = (data.get("name") or "").strip()
            email = (data.get("email") or "").strip().lower()
            password = data.get("password") or ""
            municipio = data.get("municipio") or "Cartagena de Indias (Bolívar)"
            # Por seguridad, los registros públicos reciben rol 'user' salvo clave administrativa
            role = "admin" if data.get("role") == "admin" and data.get("adminCode") == "AQUA-ADMIN-2026" else "user"
            if not name or not email or len(password) < 4:
                return self._send_json(400, {"error": "Nombre, correo y contraseña (>=4 caracteres) son obligatorios."})
            conn = get_db()
            try:
                now = datetime.now(timezone.utc).isoformat()
                cur = conn.execute(
                    "INSERT INTO users (name, email, password_hash, role, municipio, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (name, email, hash_pw(password), role, municipio, now)
                )
                conn.commit()
                user_obj = {"id": cur.lastrowid, "name": name, "email": email, "role": role, "municipio": municipio}
                token = secrets.token_hex(24)
                SESSIONS[token] = user_obj
                return self._send_json(201, {"token": token, "user": user_obj})
            except sqlite3.IntegrityError:
                return self._send_json(409, {"error": "El correo electrónico ya está registrado."})
            finally:
                conn.close()

        if parsed.path == "/api/auth/login":
            email = (data.get("email") or "").strip().lower()
            password = data.get("password") or ""
            conn = get_db()
            row = conn.execute(
                "SELECT id, name, email, role, municipio FROM users WHERE email = ? AND password_hash = ?",
                (email, hash_pw(password))
            ).fetchone()
            conn.close()
            if not row:
                return self._send_json(401, {"error": "Credenciales inválidas."})
            user_obj = dict(row)
            token = secrets.token_hex(24)
            SESSIONS[token] = user_obj
            return self._send_json(200, {"token": token, "user": user_obj})

        if parsed.path == "/api/reports":
            # Guarda únicamente la ubicación del lugar reportado y el dictamen YOLO + Doble Clasificación
            rep_id = data.get("id") or f"AV-{int(datetime.now().timestamp()*1000)}"
            user_email = data.get("userEmail") or "ciudadano@aquavigia.co"
            lat = float(data.get("lat", 10.3997))
            lng = float(data.get("lng", -75.5144))
            municipio = str(data.get("municipio", "Cartagena de Indias (Bolívar)"))
            sector = str(data.get("sector", "Zona reportada"))
            deposit_type = str(data.get("depositType", "Balde / Recipiente plástico"))
            risk_level = "alto" if data.get("riskLevel") == "alto" else "bajo"
            virus_present = 1 if data.get("virusPresent") else 0
            risk_percent = float(data.get("riskPercent", 0.0))
            larva_percent = float(data.get("larvaPercent", 0.0))
            yolo_boxes = int(data.get("larvaBoxesCount", 0))
            yolo_pre = int(data.get("yoloPreNmsCount", 0))
            status = "virus-detectado" if virus_present else ("riesgo-detectado" if risk_level == "alto" else "sin-riesgo")
            ts = data.get("timestamp") or datetime.now(timezone.utc).isoformat()

            conn = get_db()
            conn.execute(
                "INSERT OR REPLACE INTO reports VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (rep_id, user_email, lat, lng, municipio, sector, deposit_type, risk_level, virus_present,
                 risk_percent, larva_percent, yolo_boxes, yolo_pre, status, ts)
            )
            conn.commit()
            conn.close()
            return self._send_json(201, {"ok": True, "id": rep_id, "status": status})

        return self._send_json(404, {"error": "Endpoint no encontrado"})

if __name__ == "__main__":
    print(f"Servidor AquaVigía v3.0 activo en http://localhost:{PORT}")
    HTTPServer(("0.0.0.0", PORT), AquaVigiaHandler).serve_forever()
