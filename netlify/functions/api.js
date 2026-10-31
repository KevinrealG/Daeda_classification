// netlify/functions/api.js
// Equivalente Serverless en Netlify de server.py + aquavigia.db
// Persiste las tablas 'users' y 'reports' en Netlify Blobs (o memoria de instancia) con hash PBKDF2-SHA256

const crypto = require("crypto");

const INITIAL_USERS = [
  { id: 1, name: "Kevin Sossa (Admin Salud Pública)", email: "admin@aquavigia.co", passwordHash: hashPw("admin123"), role: "admin", municipio: "Cartagena de Indias (Bolívar)", createdAt: "2026-10-01T08:00:00Z" },
  { id: 2, name: "Coordinación DADIS Cartagena", email: "dadis@cartagena.gov.co", passwordHash: hashPw("dadis2026"), role: "admin", municipio: "Cartagena de Indias (Bolívar)", createdAt: "2026-10-05T09:30:00Z" },
  { id: 3, name: "María Fernanda Gómez (Monitora)", email: "maria@comunidad.co", passwordHash: hashPw("user123"), role: "user", municipio: "Cartagena de Indias (Bolívar)", createdAt: "2026-10-12T14:15:00Z" },
  { id: 4, name: "Carlos Andrés Pérez (Ciudadano)", email: "carlos@correo.co", passwordHash: hashPw("user123"), role: "user", municipio: "Barranquilla (Atlántico)", createdAt: "2026-10-18T11:20:00Z" }
];

const INITIAL_REPORTS = [
  { id: "AV-1001", userEmail: "maria@comunidad.co", lat: 10.3952, lng: -75.4795, municipio: "Cartagena de Indias (Bolívar)", sector: "Olaya Herrera - Sector Central", depositType: "Balde / Recipiente plástico", riskLevel: "alto", virusPresent: true, riskPercent: 96.2, larvaPercent: 96.9, larvaBoxesCount: 11, yoloPreNmsCount: 28, analysisStatus: "virus-detectado", timestamp: "2026-10-21T14:20:00.000Z" },
  { id: "AV-1002", userEmail: "maria@comunidad.co", lat: 10.3821, lng: -75.4680, municipio: "Cartagena de Indias (Bolívar)", sector: "El Pozón", depositType: "Llanta a la intemperie", riskLevel: "alto", virusPresent: true, riskPercent: 94.8, larvaPercent: 92.4, larvaBoxesCount: 7, yoloPreNmsCount: 19, analysisStatus: "virus-detectado", timestamp: "2026-10-21T16:45:00.000Z" },
  { id: "AV-1003", userEmail: "admin@aquavigia.co", lat: 10.3884, lng: -75.4962, municipio: "Cartagena de Indias (Bolívar)", sector: "El Bosque", depositType: "Tanque / Alberca de agua", riskLevel: "alto", virusPresent: false, riskPercent: 95.8, larvaPercent: 6.6, larvaBoxesCount: 0, yoloPreNmsCount: 2, analysisStatus: "riesgo-detectado", timestamp: "2026-10-22T09:15:00.000Z" },
  { id: "AV-1004", userEmail: "admin@aquavigia.co", lat: 10.4236, lng: -75.5478, municipio: "Cartagena de Indias (Bolívar)", sector: "Getsemaní", depositType: "Recipiente agua limpia / Control", riskLevel: "bajo", virusPresent: false, riskPercent: 4.4, larvaPercent: 2.1, larvaBoxesCount: 0, yoloPreNmsCount: 0, analysisStatus: "sin-riesgo", timestamp: "2026-10-22T11:30:00.000Z" },
  { id: "AV-1005", userEmail: "carlos@correo.co", lat: 10.9685, lng: -74.7813, municipio: "Barranquilla (Atlántico)", sector: "Rebolo", depositType: "Charco / Canal de aguas lluvias", riskLevel: "alto", virusPresent: true, riskPercent: 93.1, larvaPercent: 91.5, larvaBoxesCount: 6, yoloPreNmsCount: 17, analysisStatus: "virus-detectado", timestamp: "2026-10-22T13:10:00.000Z" },
  { id: "AV-1006", userEmail: "carlos@correo.co", lat: 3.4516, lng: -76.5320, municipio: "Cali (Valle del Cauca)", sector: "Aguablanca", depositType: "Tanque / Alberca de agua", riskLevel: "alto", virusPresent: false, riskPercent: 91.2, larvaPercent: 8.4, larvaBoxesCount: 0, yoloPreNmsCount: 1, analysisStatus: "riesgo-detectado", timestamp: "2026-10-22T15:05:00.000Z" }
];

let memoryDB = {
  users: [...INITIAL_USERS],
  reports: [...INITIAL_REPORTS]
};

function hashPw(password, salt = "aquavigia_col_v3") {
  return crypto.pbkdf2Sync(String(password), salt, 100000, 32, "sha256").toString("hex");
}

function jsonResponse(statusCode, bodyObj) {
  return {
    statusCode,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
      "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS"
    },
    body: JSON.stringify(bodyObj)
  };
}

exports.handler = async function (event) {
  if (event.httpMethod === "OPTIONS") {
    return jsonResponse(200, { ok: true });
  }

  const path = event.path.replace(/^\/\.netlify\/functions\/api/, "").replace(/^\/api/, "") || "/";
  const method = event.httpMethod;
  let data = {};
  if (event.body) {
    try { data = JSON.parse(event.body); } catch (e) {}
  }

  if (method === "GET" && path === "/health") {
    return jsonResponse(200, {
      status: "online",
      platform: "Netlify Serverless Functions",
      users_count: memoryDB.users.length,
      reports_count: memoryDB.reports.length
    });
  }

  if (method === "GET" && path === "/reports") {
    return jsonResponse(200, { reports: memoryDB.reports });
  }

  if (method === "POST" && path === "/reports") {
    const rep = {
      id: data.id || ("AV-" + Date.now()),
      userEmail: String(data.userEmail || "ciudadano@aquavigia.co"),
      lat: Number(Number(data.lat || 10.3997).toFixed(5)),
      lng: Number(Number(data.lng || -75.5144).toFixed(5)),
      municipio: String(data.municipio || "Cartagena de Indias (Bolívar)"),
      sector: String(data.sector || "Zona reportada"),
      depositType: String(data.depositType || "Balde / Recipiente plástico"),
      riskLevel: data.riskLevel === "alto" ? "alto" : "bajo",
      virusPresent: Boolean(data.virusPresent),
      riskPercent: Number(Number(data.riskPercent || 0).toFixed(1)),
      larvaPercent: Number(Number(data.larvaPercent || 0).toFixed(1)),
      larvaBoxesCount: Number(data.larvaBoxesCount || 0),
      yoloPreNmsCount: Number(data.yoloPreNmsCount || 0),
      analysisStatus: data.virusPresent ? "virus-detectado" : (data.riskLevel === "alto" ? "riesgo-detectado" : "sin-riesgo"),
      timestamp: data.timestamp || new Date().toISOString()
    };
    memoryDB.reports.push(rep);
    return jsonResponse(201, { ok: true, report: rep });
  }

  if (method === "POST" && path === "/auth/login") {
    const email = String(data.email || "").trim().toLowerCase();
    const pwHash = hashPw(data.password || "");
    const found = memoryDB.users.find(u => u.email.toLowerCase() === email && u.passwordHash === pwHash);
    if (!found) {
      return jsonResponse(401, { error: "Credenciales inválidas" });
    }
    const { passwordHash, ...safeUser } = found;
    return jsonResponse(200, { token: "nf_" + crypto.randomBytes(16).toString("hex"), user: safeUser });
  }

  if (method === "POST" && path === "/auth/register") {
    const name = String(data.name || "").trim();
    const email = String(data.email || "").trim().toLowerCase();
    const password = String(data.password || "");
    const role = data.role === "admin" ? "admin" : "user";
    const municipio = String(data.municipio || "Cartagena de Indias (Bolívar)");
    if (!name || !email || password.length < 4) {
      return jsonResponse(400, { error: "Datos incompletos" });
    }
    if (memoryDB.users.some(u => u.email.toLowerCase() === email)) {
      return jsonResponse(409, { error: "El correo ya está registrado" });
    }
    const newUser = {
      id: memoryDB.users.length + 1,
      name,
      email,
      passwordHash: hashPw(password),
      role,
      municipio,
      createdAt: new Date().toISOString()
    };
    memoryDB.users.push(newUser);
    const { passwordHash, ...safeUser } = newUser;
    return jsonResponse(201, { token: "nf_" + crypto.randomBytes(16).toString("hex"), user: safeUser });
  }

  if (method === "GET" && path === "/users") {
    const safeUsers = memoryDB.users.map(({ passwordHash, ...u }) => u);
    return jsonResponse(200, { users: safeUsers });
  }

  return jsonResponse(404, { error: "Ruta no encontrada: " + path });
};
