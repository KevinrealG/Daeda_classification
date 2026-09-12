(function () {
  const STORAGE_KEY = 'aquavigia_geo_records';
  const API_URL = 'https://example.com/api/locations';

  function readLocalRecords() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (error) {
      console.warn('No se pudieron cargar los registros locales:', error);
      return [];
    }
  }

  function writeLocalRecords(records) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(records));
  }

  function normalizeRecord(record) {
    return {
      id: record.id || Date.now() + Math.random(),
      lat: Number(record.lat),
      lng: Number(record.lng),
      source: record.source || 'manual',
      timestamp: record.timestamp || new Date().toISOString(),
      riskLevel: record.riskLevel || 'sin-datos',
      virusPresent: Boolean(record.virusPresent),
      riskPercent: Number(record.riskPercent || 0),
      larvaPercent: Number(record.larvaPercent || 0),
      analysisStatus: record.analysisStatus || 'sin-datos',
      imageName: record.imageName || 'sin-imagen'
    };
  }

  function saveToExternalServer(record) {
    if (!window.fetch) return Promise.resolve({ ok: false });
    return fetch(API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(normalizeRecord(record))
    }).catch(() => ({ ok: false }));
  }

  function addRecord(record) {
    const normalized = normalizeRecord(record);
    const existing = readLocalRecords();
    const updated = [...existing, normalized];
    writeLocalRecords(updated);
    saveToExternalServer(normalized);
    return normalized;
  }

  function getRecords() {
    return readLocalRecords().map(normalizeRecord);
  }

  function clearRecords() {
    writeLocalRecords([]);
  }

  window.AquavigiaStorage = {
    STORAGE_KEY,
    addRecord,
    getRecords,
    clearRecords,
    saveToExternalServer
  };
})();
