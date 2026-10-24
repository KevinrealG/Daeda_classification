#!/usr/bin/env python3
"""
Entrenamiento Oficial Ultralytics YOLOv8 para Detección de Larvas de Aedes aegypti y Focos de Riesgo
Usa las anotaciones generadas automáticamente en ./yolo_dataset/dataset.yaml
"""
from ultralytics import YOLO

def main():
    # Cargar modelo base pre-entrenado YOLOv8 Nano (rápido y ligero para web/móvil)
    model = YOLO("yolov8n.pt")

    # Entrenar sobre el dataset de larvas y focos de riesgo hídrico
    results = model.train(
        data="./yolo_dataset/dataset.yaml",
        epochs=50,
        imgsz=640,
        batch=16,
        patience=12,
        name="aquavigia_yolov8_larvas"
    )

    # Exportar a formatos de producción (PyTorch best.pt, ONNX y TensorFlow.js)
    model.export(format="onnx")
    print("Entrenamiento YOLOv8 finalizado y exportado exitosamente.")

if __name__ == "__main__":
    main()
