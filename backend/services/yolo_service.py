# backend/services/yolo_service.py

from pathlib import Path
from PIL import Image
from ultralytics import YOLO

# ---------------------------------------------------------
# Load YOLO model ONCE globally (production-safe)
# ---------------------------------------------------------

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "idd_yolo.pt"

if not MODEL_PATH.exists():
    raise FileNotFoundError(f"YOLO model missing at: {MODEL_PATH}")

print(f"[YOLO] Loading batch model from: {MODEL_PATH}")

_MODEL = YOLO(str(MODEL_PATH))   # <-- clean, safe loader

SUPPORTED_IMG_EXTS = {
    ".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif"
}


def run_yolo_on_folder(folder_path: str, conf: float = 0.25, use_gpu: bool = False):
    """
    Scans all images inside folder recursively and performs YOLO inference.

    RETURNS:
    {
        "status": "success",
        "detections": [...],
        "categories": [...]
    }
    """

    folder = Path(folder_path)
    if not folder.exists():
        raise FileNotFoundError(f"Images folder not found: {folder}")

    # Move model to GPU if requested
    model = _MODEL
    if use_gpu:
        try:
            model.to("cuda")
            print("[YOLO] Running on GPU")
        except Exception as e:
            print(f"[YOLO] GPU unavailable, using CPU: {e}")

    # Find all images recursively
    image_paths = [
        p for p in folder.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_IMG_EXTS
    ]

    if not image_paths:
        raise RuntimeError(f"No images found inside: {folder}")

    print(f"[YOLO] Found {len(image_paths)} images")

    # Build COCO-style categories once
    categories = [
        {
            "id": i + 1,
            "name": name,
            "supercategory": "object"
        }
        for i, name in model.names.items()
    ]

    detections = []

    # Run inference image-by-image
    for idx, img_path in enumerate(image_paths, start=1):

        print(f"[YOLO] Processing {idx}/{len(image_paths)} → {img_path.name}")

        results = model(str(img_path), conf=conf, verbose=False)[0]

        # Read image for width/height
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
        "detections": detections,
        "categories": categories
    }
