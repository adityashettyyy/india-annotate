import json
import os
from jsonschema import validate, ValidationError

# ===== Load schema.json safely =====
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.json")

with open(SCHEMA_PATH, "r") as f:
    COCO_SCHEMA = json.load(f)


def _safe_load_json(file_obj):
    try:
        return json.load(file_obj), None
    except Exception as e:
        return None, f"Invalid JSON: {str(e)}"


def _validate_schema(data):
    try:
        validate(instance=data, schema=COCO_SCHEMA)
        return True, None
    except ValidationError as e:
        return False, f"Schema validation failed at {list(e.path)} → {e.message}"


def _build_category_map(categories):
    return {str(cat["id"]): cat.get("name", f"class_{cat['id']}") for cat in categories}


def run_autocheck(file_obj):
    """
    Input: JSON file uploaded via UI
    Output: Summary + label distribution
    """

    # Step 1 — Load JSON
    data, err = _safe_load_json(file_obj)
    if err:
        return {"status": "error", "message": err}

    # Step 2 — Schema validation
    ok, schema_err = _validate_schema(data)
    if not ok:
        return {"status": "error", "message": schema_err}

    images = data.get("images", [])
    anns = data.get("annotations", [])
    cats = data.get("categories", [])

    # Step 3 — Mapping categories
    id_to_name = _build_category_map(cats)

    # Step 4 — Stats
    num_images = len(images)
    num_ann = len(anns)
    num_cat = len(cats)

    # Label distribution
    label_dist = {}
    for a in anns:
        cid = str(a["category_id"])
        name = id_to_name.get(cid, f"class_{cid}")
        label_dist.setdefault(name, {"category_id": cid, "count": 0})
        label_dist[name]["count"] += 1

    # Annotation coverage
    images_annot = {str(a["image_id"]) for a in anns}
    image_ids = {str(img["id"]) for img in images}
    images_with = len(images_annot & image_ids)
    images_without = len(image_ids - images_annot)

    # Step 5 — Quality Score
    if num_images == 0 or num_ann == 0:
        quality = 0
    else:
        avg = num_ann / num_images
        if avg >= 10: quality = 95
        elif avg >= 5: quality = 85
        elif avg >= 2: quality = 70
        else: quality = 50

    # Final Output
    return {
        "status": "success",
        "summary": {
            "num_images": num_images,
            "num_annotations": num_ann,
            "num_categories": num_cat,
            "images_with_annotations": images_with,
            "images_without_annotations": images_without,
            "estimated_quality_score": quality
        },
        "label_distribution": label_dist,
        "notes": ["COCO validated", "Auto-detected objects supported"]
    }
