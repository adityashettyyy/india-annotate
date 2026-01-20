# backend/services/detector.py

from pathlib import Path
from ultralytics import YOLO

# ------------------------------------------------------------------
# Load YOLO model ONCE globally (production-safe)
# ------------------------------------------------------------------

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "idd_yolo.pt"

if not MODEL_PATH.exists():
    raise FileNotFoundError(f"YOLO model missing at: {MODEL_PATH}")

print(f"[YOLO] Loading single-image model from: {MODEL_PATH}")

_MODEL = YOLO(str(MODEL_PATH))   # <-- REPLACES torch.hub.load
_MODEL.conf = 0.25               # default confidence


def detect_image(image_path: str, conf: float = 0.25):
    """
    Run YOLO inference on a single image.

    Returns:
    {
      "status": "success",
      "image_path": "...",
      "detections": [
         {
           "category_id": 3,
           "category_name": "car",
           "bbox": [x, y, w, h],
           "score": 0.82
         }
      ]
    }
    """

    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    model = _MODEL
    model.conf = conf

    results = model(image_path, verbose=False)[0]

    detections = []

    for box in results.boxes:
        cls = int(box.cls)
        x1, y1, x2, y2 = box.xyxy[0].tolist()

        w = x2 - x1
        h = y2 - y1

        detections.append({
            "category_id": cls + 1,                 # COCO-style indexing
            "category_name": model.names[cls],
            "bbox": [float(x1), float(y1), float(w), float(h)],
            "score": float(box.conf)
        })

    return {
        "status": "success",
        "image_path": image_path,
        "detections": detections
    }
