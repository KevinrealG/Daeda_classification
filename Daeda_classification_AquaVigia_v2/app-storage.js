(function () {
  const STORAGE_KEY = 'aquavigia_geo_records';

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
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(records));
    } catch (error) {
      console.warn('No se pudieron guardar los registros locales:', error);
    }
  }

  function normalizeRecord(record) {
    // Privacidad por diseno: guarda exclusivamente la ubicacion del lugar reportado y el dictamen ambiental
    const riskHigh = record.riskLevel === 'alto' || Boolean(record.riskDetected);
    const hasLarva = Boolean(record.virusPresent || record.larvaDetected);
    return {
      id: record.id || ('AV-' + Date.now() + '-' + Math.floor(Math.random() * 1000)),
      lat: Number(Number(record.lat || 10.3997).toFixed(5)),
      lng: Number(Number(record.lng || -75.5144).toFixed(5)),
      municipio: String(record.municipio || 'Cartagena de Indias (Bolívar)'),
      sector: String(record.sector || 'Zona reportada'),
      depositType: String(record.depositType || 'Recipiente / Agua estancada'),
      timestamp: record.timestamp || new Date().toISOString(),
      riskLevel: riskHigh ? 'alto' : 'bajo',
      virusPresent: hasLarva,
      riskPercent: Number(Number(record.riskPercent || 0).toFixed(1)),
      larvaPercent: Number(Number(record.larvaPercent || 0).toFixed(1)),
      larvaBoxesCount: Number(record.larvaBoxesCount || 0),
      analysisStatus: hasLarva ? 'virus-detectado' : (riskHigh ? 'riesgo-detectado' : 'sin-riesgo')
    };
  }

  function addRecord(record) {
    const normalized = normalizeRecord(record);
    const existing = readLocalRecords();
    const updated = [...existing, normalized];
    writeLocalRecords(updated);
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
    normalizeRecord
  };
})();
