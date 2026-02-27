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
    """Load JSON from a file object or StringIO."""
    try:
        # Support both file objects and io.StringIO
        if hasattr(file_obj, "read"):
            content = file_obj.read()
            if isinstance(content, bytes):
                content = content.decode("utf-8")
            return json.loads(content), None
        return None, "Invalid file object"
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON syntax: {str(e)}"
    except Exception as e:
        return None, f"Failed to read file: {str(e)}"


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
    valid_category_ids = {str(c["id"]) for c in categories}

    # -------------------------------------------------
    # Label Distribution + Confidence + Validity
    # -------------------------------------------------
    label_distribution = {}
    confidences = []
    low_confidence_annotations = []
    orphan_annotations = []          # annotations with no matching image
    invalid_category_annotations = []  # annotations referencing missing category

    image_id_set = {str(img["id"]) for img in images}

    for ann in annotations:
        cid = str(ann.get("category_id", ""))
        img_id = str(ann.get("image_id", ""))
        name = id_to_name.get(cid, f"class_{cid}")

        # Track orphan annotations
        if img_id not in image_id_set:
            orphan_annotations.append({
                "annotation_id": ann.get("id"),
                "image_id": ann.get("image_id"),
            })

        # Track invalid categories
        if cid not in valid_category_ids and valid_category_ids:
            invalid_category_annotations.append({
                "annotation_id": ann.get("id"),
                "category_id": ann.get("category_id"),
            })

        # Label distribution
        label_distribution.setdefault(name, {"category_id": cid, "count": 0})
        label_distribution[name]["count"] += 1

        # Confidence (optional field — present in auto-annotated datasets)
        conf = ann.get("score") or ann.get("confidence")
        if conf is not None:
            conf = float(conf)
            confidences.append(conf)
            if conf < confidence_threshold:
                low_confidence_annotations.append({
                    "annotation_id": ann.get("id"),
                    "image_id": ann.get("image_id"),
                    "confidence": round(conf, 3),
                })

    # -------------------------------------------------
    # Coverage Analysis
    # -------------------------------------------------
    image_id_ints = {img["id"] for img in images}
    annotated_image_ids = {ann["image_id"] for ann in annotations}

    unannotated_images = list(image_id_ints - annotated_image_ids)
    images_with_annotations = len(image_id_ints & annotated_image_ids)
    images_without_annotations = len(unannotated_images)

    # -------------------------------------------------
    # Quality Score (explainable heuristic, 0–100)
    # -------------------------------------------------
    if num_images == 0:
        avg_annotations = 0.0
        quality_score = 0
    else:
        avg_annotations = num_annotations / num_images
        # Density score: 0–10 ann/image → maps to 0–70 points
        density_score = min(70, round((avg_annotations / 10) * 70))

        # Coverage score: % images annotated → maps to 0–30 points
        coverage_pct = images_with_annotations / num_images if num_images else 0
        coverage_score = round(coverage_pct * 30)

        quality_score = density_score + coverage_score

    # -------------------------------------------------
    # Confidence Analysis
    # -------------------------------------------------
    avg_confidence = (
        round(sum(confidences) / len(confidences), 3) if confidences else 0.0
    )

    # -------------------------------------------------
    # Human-in-the-Loop Logic
    # -------------------------------------------------
    has_low_conf = bool(low_confidence_annotations)
    has_unannotated = images_without_annotations > 0
    has_orphans = bool(orphan_annotations)
    has_invalid_cats = bool(invalid_category_annotations)

    requires_human_review = has_low_conf or has_unannotated or has_orphans or has_invalid_cats

    if requires_human_review:
        review_status = "pending"
        crowd_flow = {
            "current_stage": "annotator_review",
            "next_stage": "reviewer_approval",
            "assigned_role": "annotator",
        }
    else:
        review_status = "approved"
        crowd_flow = {
            "current_stage": "ready_for_training",
            "next_stage": None,
            "assigned_role": None,
        }

    # -------------------------------------------------
    # Warnings
    # -------------------------------------------------
    warnings = []

    if images_without_annotations > 0:
        warnings.append(
            f"{images_without_annotations} image(s) have no annotations"
        )
    if avg_annotations < 1 and num_images > 0:
        warnings.append("Very low annotation density (< 1 annotation per image)")
    if has_low_conf:
        warnings.append(
            f"{len(low_confidence_annotations)} annotation(s) below confidence threshold ({confidence_threshold})"
        )
    if orphan_annotations:
        warnings.append(
            f"{len(orphan_annotations)} annotation(s) reference image IDs that don't exist"
        )
    if invalid_category_annotations:
        warnings.append(
            f"{len(invalid_category_annotations)} annotation(s) reference undefined category IDs"
        )

    # -------------------------------------------------
    # Final Response
    # -------------------------------------------------
    return {
        "status": "success",

        "summary": {
            "num_images": num_images,
            "num_annotations": num_annotations,
            "num_categories": num_categories,
            "images_with_annotations": images_with_annotations,
            "images_without_annotations": images_without_annotations,
            "estimated_quality_score": quality_score,
            "average_annotations_per_image": round(avg_annotations, 2),
            "average_confidence": avg_confidence,
        },

        "label_distribution": label_distribution,

        # Human Review
        "requires_human_review": requires_human_review,
        "review_status": review_status,
        "confidence_threshold": confidence_threshold,
        "crowd_flow": crowd_flow,

        "review_payload": {
            "unannotated_images": unannotated_images,
            "low_confidence_annotations": low_confidence_annotations,
            "orphan_annotations": orphan_annotations,
            "invalid_category_annotations": invalid_category_annotations,
        },

        "warnings": warnings,
        "notes": [
            "COCO schema validated successfully",
            "Quality score: density (0–70) + coverage (0–30)",
            "Human-in-the-loop pipeline enabled",
            "Confidence field: 'score' or 'confidence' on each annotation",
        ],
    }