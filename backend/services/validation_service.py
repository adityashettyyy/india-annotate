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

    # -------------------------------------------------
    # Basic Counts
    # -------------------------------------------------
    num_images = len(images)
    num_annotations = len(annotations)
    num_categories = len(categories)

    # -------------------------------------------------
    # Category Map
    # -------------------------------------------------
    id_to_name = {
        str(c["id"]): c.get("name", f"class_{c['id']}")
        for c in categories
    }

    # -------------------------------------------------
    # Label Distribution + Confidence Tracking
    # -------------------------------------------------
    label_distribution = {}
    confidences = []
    low_confidence_annotations = []

    for ann in annotations:
        cid = str(ann["category_id"])
        name = id_to_name.get(cid, f"class_{cid}")

        label_distribution.setdefault(
            name, {"category_id": cid, "count": 0}
        )
        label_distribution[name]["count"] += 1

        conf = ann.get("confidence")
        if conf is not None:
            confidences.append(conf)
            if conf < confidence_threshold:
                low_confidence_annotations.append({
                    "annotation_id": ann.get("id"),
                    "image_id": ann.get("image_id"),
                    "confidence": conf
                })

    # -------------------------------------------------
    # Coverage Analysis
    # -------------------------------------------------
    image_ids = {img["id"] for img in images}
    annotated_image_ids = {ann["image_id"] for ann in annotations}

    unannotated_images = list(image_ids - annotated_image_ids)

    images_with_annotations = len(image_ids & annotated_image_ids)
    images_without_annotations = len(unannotated_images)

    # -------------------------------------------------
    # Quality Score (EXPLAINABLE HEURISTIC)
    # -------------------------------------------------
    if num_images == 0:
        avg_annotations = 0
        quality_score = 0
    else:
        avg_annotations = num_annotations / num_images

        # Heuristic scoring (transparent)
        # 0–10 avg anns/image → scale to 0–100
        quality_score = min(
            100,
            round((avg_annotations / 10) * 100)
        )

    # -------------------------------------------------
    # Confidence Analysis
    # -------------------------------------------------
    avg_confidence = (
        sum(confidences) / len(confidences)
        if confidences else 0
    )

    # -------------------------------------------------
    # Human-in-the-Loop Logic ⭐
    # -------------------------------------------------
    requires_human_review = (
        avg_confidence < confidence_threshold
        or images_without_annotations > 0
    )

    if requires_human_review:
        review_status = "pending"
        crowd_flow = {
            "current_stage": "annotator_review",
            "next_stage": "reviewer_approval",
            "assigned_role": "annotator"
        }
    else:
        review_status = "approved"
        crowd_flow = {
            "current_stage": "ready_for_training",
            "next_stage": None,
            "assigned_role": None
        }

    # -------------------------------------------------
    # Warnings
    # -------------------------------------------------
    warnings = []

    if images_without_annotations > 0:
        warnings.append(
            f"{images_without_annotations} images have no annotations"
        )

    if avg_annotations < 1:
        warnings.append("Very low annotation density")

    if avg_confidence < confidence_threshold:
        warnings.append(
            "Low-confidence annotations detected"
        )

    # -------------------------------------------------
    # Final Response
    # -------------------------------------------------
    return {
        "status": "success",

        # Summary
        "summary": {
            "num_images": num_images,
            "num_annotations": num_annotations,
            "num_categories": num_categories,
            "images_with_annotations": images_with_annotations,
            "images_without_annotations": images_without_annotations,
            "estimated_quality_score": quality_score,
            "average_annotations_per_image": round(avg_annotations, 2),
            "average_confidence": round(avg_confidence, 3)
        },

        # Distribution
        "label_distribution": label_distribution,

        # Human Review Payload ⭐
        "requires_human_review": requires_human_review,
        "review_status": review_status,
        "confidence_threshold": confidence_threshold,
        "crowd_flow": crowd_flow,

        "review_payload": {
            "unannotated_images": unannotated_images,
            "low_confidence_annotations": low_confidence_annotations
        },

        # Meta
        "warnings": warnings,
        "notes": [
            "COCO schema validated",
            "Quality score is heuristic-based (density-driven)",
            "Human-in-the-loop pipeline enabled"
        ]
    }
