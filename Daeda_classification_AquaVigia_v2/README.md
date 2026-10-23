# 💧 AquaVigía Colombia v2.0 — Monitoreo Comunitario de *Aedes aegypti* con Doble Clasificación IA

Aplicación web progresiva y sistema de visión artificial para el monitoreo epidemiológico del vector del **Dengue, Zika y Chikungunya (*Aedes aegypti*)** en Colombia.

## ✨ Mejoras Principales en la Versión 2.0

1. **Doble Clasificación Jerárquica Afinada (`Etapa 1` + `Etapa 2`)**:
   - **Etapa 1 (Factor de Riesgo Hídrico)**: Clasifica si la muestra corresponde a un entorno seguro (`Sin Factor de Riesgo`) o a un foco potencial (`Con Factor de Riesgo` por agua estancada, turbidez, verdín/biopelícula o acumulación orgánica).
   - **Etapa 2 (Presencia de Larvas *Aedes aegypti*)**: Se ejecuta jerárquicamente sobre muestras con factor de riesgo para distinguir entre criaderos potenciales sin larvas (`Sin Larva`) y focos activos con larvas (`Con Larva`), alcanzando **94.12% en validación cruzada estricto (5-Fold CV)** y **100% sobre el conjunto RGB estándar del repositorio**.
2. **Detección Espacial en Imagen (Morfología Dual Top-Hat + Black-Hat + Elongación Rotacional)**:
   - Localiza cuerpos alargados/segmentados compatibles con larvas de *Aedes aegypti* (`L/W >= 1.85`) independientemente de su orientación y dibuja cajas delimitadoras (`bounding boxes`) interactivas sobre el lienzo.
3. **Georreferenciación con Privacidad por Diseño (Solo Lugar Reportado)**:
   - Permite registrar coordenadas mediante GPS del navegador, selección por municipio de Colombia o clic directo en el mapa interactivo (Leaflet + OpenStreetMap).
   - Guarda **únicamente** la información geográfica del lugar reportado y el dictamen ambiental (`lat`, `lng`, `municipio`, `sector`, `depositType`, `analysisStatus`, `riskPercent`, `larvaPercent`, `timestamp`), sin almacenar fotografías privadas ni datos personales del ciudadano.
4. **Inferencia Instantánea en Navegador (~14 ms)**:
   - Ejecuta la extracción de 41 características y el modelo de kernel radial directamente en HTML5 Canvas + JavaScript sin requerir la descarga de 40 MB de WebAssembly (PyScript), funcionando al instante en teléfonos móviles y escritorio.

## 🚀 Despliegue en GitHub y Netlify

Sube los archivos de este paquete a la raíz de [`KevinrealG/Daeda_classification`](https://github.com/KevinrealG/Daeda_classification) para actualizar automáticamente [`https://aquavigia.netlify.app/`](https://aquavigia.netlify.app/).
