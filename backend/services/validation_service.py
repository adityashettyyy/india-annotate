# backend/services/validation_service.py

import json
import os
from jsonschema import validate, ValidationError

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
        return False, f"Schema error at {list(e.path)} → {e.message}"


def run_autocheck(file_obj):
    data, err = _safe_load_json(file_obj)
    if err:
        return {"status": "error", "message": err}

    ok, schema_err = _validate_schema(data)
    if not ok:
        return {"status": "error", "message": schema_err}

    images = data.get("images", [])
    anns = data.get("annotations", [])
    cats = data.get("categories", [])

    # Build category map
    id_to_name = {
        str(c["id"]): c.get("name", f"class_{c['id']}")
        for c in cats
    }

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

    # Coverage stats
    images_annot = {str(a["image_id"]) for a in anns}
    image_ids = {str(img["id"]) for img in images}

    images_with = len(images_annot & image_ids)
    images_without = len(image_ids - images_annot)

    # ---- BETTER QUALITY SCORE (Phase 4 fix) ----
    if num_images == 0:
        quality = 0
    else:
        avg = num_ann / max(1, num_images)
        quality = min(95, int(avg * 10))

    warnings = []
    if images_without > 0:
        warnings.append(f"{images_without} images have no annotations")

    if num_images > 0 and avg < 1:
        warnings.append("Very low annotation density")

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
        "warnings": warnings,
        "notes": ["COCO validated", "Auto-detected objects supported"]
    }
