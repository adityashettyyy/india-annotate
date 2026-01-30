import json
import os
from jsonschema import validate, ValidationError

# -------------------------------------------------
# Load COCO Schema
# -------------------------------------------------
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.json")

with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    COCO_SCHEMA = json.load(f)

# -------------------------------------------------
# Helpers
# -------------------------------------------------
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


# -------------------------------------------------
# Main Validation Entry
# -------------------------------------------------
def run_autocheck(file_obj, confidence_threshold: float = 0.6):
    data, err = _safe_load_json(file_obj)
    if err:
        return {"status": "error", "message": err}

    ok, schema_err = _validate_schema(data)
    if not ok:
        return {"status": "error", "message": schema_err}

    images = data.get("images", [])
    annotations = data.get("annotations", [])
    categories = data.get("categories", [])

    # ---------------------------------------------
    # Basic Counts
    # ---------------------------------------------
    num_images = len(images)
    num_annotations = len(annotations)
    num_categories = len(categories)

    # ---------------------------------------------
    # Category Map
    # ---------------------------------------------
    id_to_name = {
        str(c["id"]): c.get("name", f"class_{c['id']}")
        for c in categories
    }

    # ---------------------------------------------
    # Label Distribution + Confidence Collection
    # ---------------------------------------------
    label_distribution = {}
    confidences = []

    for ann in annotations:
        cid = str(ann["category_id"])
        name = id_to_name.get(cid, f"class_{cid}")

        label_distribution.setdefault(
            name, {"category_id": cid, "count": 0}
        )
        label_distribution[name]["count"] += 1

        # YOLO confidence (optional)
        if "confidence" in ann:
            confidences.append(ann["confidence"])

    # ---------------------------------------------
    # Coverage Stats
    # ---------------------------------------------
    image_ids = {str(img["id"]) for img in images}
    annotated_images = {str(a["image_id"]) for a in annotations}

    images_with_annotations = len(image_ids & annotated_images)
    images_without_annotations = len(image_ids - annotated_images)

    # ---------------------------------------------
    # Quality Score (Heuristic Quality Gate)
    # ---------------------------------------------
    if num_images == 0:
        avg_annotations = 0
        quality_score = 0
    else:
        avg_annotations = num_annotations / max(1, num_images)
        quality_score = min(95, int(avg_annotations * 10))

    # ---------------------------------------------
    # Human-in-the-Loop Logic ⭐ (ADD-2 CORE)
    # ---------------------------------------------
    avg_confidence = (
        sum(confidences) / len(confidences)
        if confidences else 0
    )

    if avg_confidence < confidence_threshold:
        requires_human_review = True
        review_status = "pending"
        crowd_flow = {
            "current_stage": "annotator_review",
            "next_stage": "reviewer_approval",
            "assigned_role": "annotator"
        }
    else:
        requires_human_review = False
        review_status = "approved"
        crowd_flow = {
            "current_stage": "ready_for_training",
            "next_stage": None,
            "assigned_role": None
        }

    # ---------------------------------------------
    # Warnings
    # ---------------------------------------------
    warnings = []

    if images_without_annotations > 0:
        warnings.append(
            f"{images_without_annotations} images have no annotations"
        )

    if num_images > 0 and avg_annotations < 1:
        warnings.append("Very low annotation density")

    if requires_human_review:
        warnings.append(
            "Low-confidence annotations require human review"
        )

    # ---------------------------------------------
    # Final Response
    # ---------------------------------------------
    return {
        "status": "success",

        # Core stats
        "summary": {
            "num_images": num_images,
            "num_annotations": num_annotations,
            "num_categories": num_categories,
            "images_with_annotations": images_with_annotations,
            "images_without_annotations": images_without_annotations,
            "estimated_quality_score": quality_score,
            "average_confidence": round(avg_confidence, 3)
        },

        # Distribution
        "label_distribution": label_distribution,

        # Human-in-the-Loop layer ⭐
        "requires_human_review": requires_human_review,
        "review_status": review_status,
        "confidence_threshold": confidence_threshold,
        "crowd_flow": crowd_flow,

        # Metadata
        "warnings": warnings,
        "notes": [
            "COCO schema validated",
            "YOLO-assisted annotations supported",
            "Crowdsourcing-ready review pipeline enabled"
        ]
    }
