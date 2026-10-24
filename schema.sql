CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user', 'admin')),
    municipio TEXT DEFAULT 'Cartagena de Indias (Bolívar)',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    user_email TEXT NOT NULL,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    municipio TEXT NOT NULL,
    sector TEXT NOT NULL,
    deposit_type TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    virus_present INTEGER NOT NULL,
    risk_percent REAL NOT NULL,
    larva_percent REAL NOT NULL,
    yolo_boxes_count INTEGER NOT NULL DEFAULT 0,
    yolo_pre_nms_count INTEGER NOT NULL DEFAULT 0,
    analysis_status TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
