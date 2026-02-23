# backend/services/yolo_service.py

from pathlib import Path
from PIL import Image
from ultralytics import YOLO
from config import SESSIONS_ROOT

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "idd_yolo.pt"

if not MODEL_PATH.exists():
    raise FileNotFoundError(f"YOLO model missing at: {MODEL_PATH}")

_MODEL = YOLO(str(MODEL_PATH))

SUPPORTED_IMG_EXTS = {
    ".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif"
}


def run_yolo_for_session(session_id: str, conf: float = 0.25, use_gpu: bool = False):

    session_dir = SESSIONS_ROOT / session_id
    images_folder = session_dir / "images"
    annotations_folder = session_dir / "annotations"

    if not images_folder.exists():
        raise FileNotFoundError(f"Images not found for session: {session_id}")

    model = _MODEL
    if use_gpu:
        try:
            model.to("cuda")
        except:
            pass

    image_paths = [
        p for p in images_folder.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_IMG_EXTS
    ]

    if not image_paths:
        raise RuntimeError("No images found in session.")

    categories = [
        {
            "id": i + 1,
            "name": name,
            "supercategory": "object"
        }
        for i, name in model.names.items()
    ]

    detections = []

    for img_path in image_paths:
        results = model(str(img_path), conf=conf, verbose=False)[0]

        with Image.open(img_path) as im:
            width, height = im.size

        objects = []
        for box in results.boxes:
            cls = int(box.cls)
            x1, y1, x2, y2 = box.xyxy[0].tolist()

            w = x2 - x1
            h = y2 - y1

            objects.append({
                "category_id": cls + 1,
                "category_name": model.names[cls],
                "bbox": [float(x1), float(y1), float(w), float(h)],
                "score": float(box.conf)
            })

        detections.append({
            "image_path": str(img_path),
            "width": width,
            "height": height,
            "objects": objects
        })

    return {
        "status": "success",
        "session_id": session_id,
        "detections": detections,
        "categories": categories
    }