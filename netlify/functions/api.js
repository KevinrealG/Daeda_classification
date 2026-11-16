const crypto = require("crypto");
const SECRET_KEY = process.env.AQUAVIGIA_SECRET || "aquavigia_colombia_hmac_secret_2026";
function hashPw(pw, salt = "aquavigia_col_v3") {
  return crypto.pbkdf2Sync(String(pw), salt, 100000, 32, "sha256").toString("hex");
}
function signToken(u) {
  const b64 = Buffer.from(JSON.stringify({ ...u, exp: Date.now() + 604800000 }), "utf8").toString("base64url");
  const sig = crypto.createHmac("sha256", SECRET_KEY).update(b64).digest("base64url");
  return `${b64}.${sig}`;
}
function verifyToken(t) {
  if (!t || !t.includes(".")) return null;
  const [b64, sig] = t.split(".");
  if (sig !== crypto.createHmac("sha256", SECRET_KEY).update(b64).digest("base64url")) return null;
  try {
    const p = JSON.parse(Buffer.from(b64, "base64url").toString("utf8"));
    return p.exp && Date.now() > p.exp ? null : p;
  } catch { return null; }
}
function getToken(event) {
  const h = event.headers || {};
  const auth = h.authorization || h.Authorization || "";
  if (auth.startsWith("Bearer ")) return auth.slice(7).trim();
  const m = (h.cookie || h.Cookie || "").match(/(?:^|;\s*)session_token=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}
let memoryDB = {
  users: [
    { id: 1, name: "Kevin Sossa (Admin)", email: "admin@aquavigia.co", passwordHash: hashPw("admin123"), role: "admin", municipio: "Cartagena de Indias (Bolívar)" },
    { id: 2, name: "María Gómez (Monitora)", email: "maria@comunidad.co", passwordHash: hashPw("user123"), role: "user", municipio: "Cartagena de Indias (Bolívar)" }
  ],
  reports: []
};
const res = (code, obj, extra = {}) => ({
  statusCode: code,
  headers: { "Content-Type": "application/json; charset=utf-8", "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "Content-Type, Authorization", "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS", ...extra },
  body: JSON.stringify(obj)
});
exports.handler = async (event) => {
  if (event.httpMethod === "OPTIONS") return res(200, { ok: true });
  const path = (event.path || "/").replace(/^\/\.netlify\/functions\/api/, "").replace(/^\/api/, "") || "/";
  const method = event.httpMethod;
  let data = {};
  if (event.body) { try { data = JSON.parse(event.body); } catch {} }
  const currentUser = verifyToken(getToken(event));

  if (method === "GET" && path === "/auth/me") return res(200, { user: currentUser, authenticated: Boolean(currentUser) });
  if (method === "POST" && path === "/auth/logout") return res(200, { ok: true }, { "Set-Cookie": "session_token=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0" });
  if (method === "POST" && path === "/auth/login") {
    const u = memoryDB.users.find(x => x.email.toLowerCase() === String(data.email || "").trim().toLowerCase() && x.passwordHash === hashPw(data.password || ""));
    if (!u) return res(401, { error: "Credenciales inválidas" });
    const { passwordHash, ...safe } = u;
    const tok = signToken(safe);
    return res(200, { ok: true, token: tok, user: safe }, { "Set-Cookie": `session_token=${encodeURIComponent(tok)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=604800` });
  }
  if (method === "POST" && path === "/auth/register") {
    const email = String(data.email || "").trim().toLowerCase();
    if (!data.name || !email || String(data.password || "").length < 4) return res(400, { error: "Datos incompletos" });
    if (memoryDB.users.some(x => x.email === email)) return res(409, { error: "Correo ya registrado" });
    const u = { id: memoryDB.users.length + 1, name: String(data.name).trim(), email, passwordHash: hashPw(data.password), role: data.role === "admin" ? "admin" : "user", municipio: data.municipio || "Cartagena de Indias (Bolívar)" };
    memoryDB.users.push(u);
    const { passwordHash, ...safe } = u;
    const tok = signToken(safe);
    return res(201, { ok: true, token: tok, user: safe }, { "Set-Cookie": `session_token=${encodeURIComponent(tok)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=604800` });
  }
  if (method === "GET" && path === "/reports") return res(200, { reports: memoryDB.reports });
  if (method === "POST" && path === "/reports") { memoryDB.reports.unshift({ ...data, id: data.id || ("AV-" + Date.now()) }); return res(201, { ok: true }); }
  if (method === "GET" && path === "/users") return res(200, { users: memoryDB.users.map(({ passwordHash, ...u }) => u) });
  return res(404, { error: "Ruta no encontrada: " + path });
};
