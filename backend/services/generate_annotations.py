import os
import json
from ultralytics import YOLO
from PIL import Image

IMAGES_DIR = "dataset/images/test"
OUTPUT_JSON = "dataset/annotations/train_annotations.json"

model = YOLO("yolov8s.pt")   # or yolov8n.pt for speed

def generate_coco_json():
    images = []
    annotations = []
    categories = {}
    ann_id = 1
    img_id = 1

    # Walk through nested folders
    for root, dirs, files in os.walk(IMAGES_DIR):
        for file in files:
            if file.lower().endswith((".jpg", ".jpeg", ".png")):

                img_path = os.path.join(root, file)
                img = Image.open(img_path)
                width, height = img.size

                # Add image entry
                images.append({
                    "id": img_id,
                    "file_name": os.path.relpath(img_path, IMAGES_DIR).replace("\\", "/"),
                    "width": width,
                    "height": height
                })

                # Run YOLO detection
                results = model(img_path)[0]

                for box in results.boxes:
                    cls = int(box.cls)
                    x1, y1, x2, y2 = box.xyxy[0]

                    w = float(x2 - x1)
                    h = float(y2 - y1)

                    # Register category
                    if cls not in categories:
                        categories[cls] = {
                            "id": cls + 1,
                            "name": model.names[cls]
                        }

                    # Add annotation
                    annotations.append({
                        "id": ann_id,
                        "image_id": img_id,
                        "category_id": cls + 1,
                        "bbox": [float(x1), float(y1), w, h],
                        "area": float(w * h),
                        "iscrowd": 0,
                        "segmentation": []
                    })
                    ann_id += 1

                img_id += 1

    coco = {
        "images": images,
        "annotations": annotations,
        "categories": list(categories.values())
    }

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(coco, f, indent=2)

    print(f"Saved COCO annotations → {OUTPUT_JSON}")

if __name__ == "__main__":
    generate_coco_json()
