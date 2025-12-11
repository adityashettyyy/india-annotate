# backend/utils/detector.py

import torch
from pathlib import Path

# ------------------------
# Load YOLO model only once
# ------------------------

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "idd_yolo.pt"
MODEL = None


def load_model():
    """Load YOLO model only once & reuse."""
    global MODEL

    if MODEL is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"YOLO model not found at: {MODEL_PATH}")

        # Load with Ultralytics YOLO
        print(f"[INFO] Loading YOLO model: {MODEL_PATH}")
        MODEL = torch.hub.load("ultralytics/yolov5", "custom", path=str(MODEL_PATH))
        MODEL.conf = 0.25  # Default confidence threshold

    return MODEL


def detect_image(image_path, conf=0.25):
    """
    Run YOLO inference on an image.

    Returns list of dictionaries:
    [
        {"bbox": [x,y,w,h], "confidence": 0.82, "class_id": 2, "class_name": "car"},
        ...
    ]
    """
    model = load_model()
    model.conf = conf

    results = model(image_path)

    detections = []

    for *xyxy, conf_score, cls_id in results.xyxy[0]:
        x1, y1, x2, y2 = [float(i) for i in xyxy]

        w = x2 - x1
        h = y2 - y1

        detections.append({
            "bbox": [x1, y1, w, h],
            "confidence": float(conf_score),
            "class_id": int(cls_id),
            "class_name": model.names[int(cls_id)]
        })

    return detections
