# backend/app.py

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import io
import json
import shutil
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import (
    SESSIONS_ROOT,
    IMAGES_ROOT,
    ANNOTATIONS_ROOT,
    MAX_CONTENT_LENGTH,
    ALLOWED_SPLITS,
    DEBUG,
)

from services.validation_service import run_autocheck
from services.yolo_service import run_yolo_for_session
from services.coco_service import build_coco_from_detections
from services.upload_service import handle_dataset_upload

# --------------------------------------------------
# App setup
# --------------------------------------------------

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# --------------------------------------------------
# Logging (Production-grade)
# --------------------------------------------------

logger = logging.getLogger("india_annotate")
logger.setLevel(logging.INFO)

handler = RotatingFileHandler(
    "backend.log",
    maxBytes=5_000_000,
    backupCount=3,
)
formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# Also log to console in development
if DEBUG:
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

logger.info("IndiaAnnotate backend started")

# --------------------------------------------------
# Response helpers
# --------------------------------------------------


def ok(data=None, message="ok", code=200):
    payload = {"status": "success", "message": message}
    if data is not None:
        payload.update(data)
    return jsonify(payload), code


def err(message="error", code=400):
    return jsonify({"status": "error", "message": message}), code


# --------------------------------------------------
# Routes — Health
# --------------------------------------------------


@app.route("/", methods=["GET"])
def home():
    return ok(message="IndiaAnnotate API running")


@app.route("/health", methods=["GET"])
def health():
    return ok({"uptime": "ok"}, "healthy")


# --------------------------------------------------
# DATASET UPLOAD
# --------------------------------------------------


@app.route("/upload-dataset", methods=["POST"])
def upload_dataset():
    try:
        if "file" not in request.files:
            return err("Dataset ZIP required", 400)

        file = request.files["file"]

        if not file.filename:
            return err("Empty filename", 400)

        if not file.filename.lower().endswith(".zip"):
            return err("Only .zip files are supported", 400)

        result = handle_dataset_upload(file)

        logger.info(
            f"Dataset uploaded | session={result['session_id']} "
            f"| images={result['image_count']} "
            f"| annotations={result['annotation_count']}"
        )

        return ok(
            {
                "session_id": result["session_id"],
                "image_count": result["image_count"],
                "annotation_count": result["annotation_count"],
            },
            f"Dataset uploaded: {result['image_count']} images found",
        )

    except ValueError as e:
        logger.warning(f"Upload rejected: {e}")
        return err(str(e), 400)
    except Exception:
        logger.exception("Upload dataset crashed")
        return err("Internal server error", 500)


# --------------------------------------------------
# SESSION STATUS
# --------------------------------------------------


@app.route("/session/<session_id>/status", methods=["GET"])
def session_status(session_id):
    """
    Returns the current state of a session:
    image count, whether annotations exist, and whether they are validated.
    """
    try:
        session_dir = SESSIONS_ROOT / session_id

        if not session_dir.exists():
            return err("Session not found", 404)

        images_dir = session_dir / "images"
        annotations_dir = session_dir / "annotations"

        image_files = [
            p for p in images_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        ] if images_dir.exists() else []

        annotation_files = list(annotations_dir.glob("*.json")) if annotations_dir.exists() else []

        has_auto_annotations = (annotations_dir / "auto_annotations.json").exists()

        return ok(
            {
                "session_id": session_id,
                "image_count": len(image_files),
                "annotation_files": [f.name for f in annotation_files],
                "has_auto_annotations": has_auto_annotations,
                "ready_for_annotation": len(image_files) > 0,
            },
            "Session found",
        )

    except Exception:
        logger.exception("Session status crashed")
        return err("Internal server error", 500)


# --------------------------------------------------
# VALIDATE COCO JSON
# --------------------------------------------------


@app.route("/validate", methods=["POST"])
def validate_dataset():
    try:
        if "file" not in request.files:
            return err("No file uploaded", 400)

        file = request.files["file"]
        if not file.filename.strip():
            return err("Empty filename", 400)

        report = run_autocheck(file)

        if report.get("status") != "success":
            logger.warning("Validation failed")
            return err(report.get("message", "Validation failed"), 400)

        logger.info("Validation completed")

        return ok(
            {
                "report": report,
                "human_review": {
                    "requires_human_review": report.get("requires_human_review"),
                    "review_status": report.get("review_status"),
                    "current_stage": report.get("crowd_flow", {}).get("current_stage"),
                },
            },
            "Validation completed",
        )

    except Exception:
        logger.exception("Validate endpoint crashed")
        return err("Internal server error", 500)


# --------------------------------------------------
# AUTO-ANNOTATE (SESSION-BASED)
# --------------------------------------------------


@app.route("/auto-annotate", methods=["POST"])
def auto_annotate():
    try:
        data = request.get_json(silent=True) or {}

        session_id = data.get("session_id")
        conf = float(data.get("conf", 0.25))
        conf = max(0.05, min(conf, 0.95))  # clamp to safe range

        if not session_id:
            return err("session_id is required", 400)

        session_dir = SESSIONS_ROOT / session_id
        images_dir = session_dir / "images"
        annotations_dir = session_dir / "annotations"

        if not session_dir.exists():
            return err("Session not found. Please re-upload your dataset.", 404)

        if not images_dir.exists():
            return err("Session images folder not found", 400)

        logger.info(f"Auto-annotation started | session={session_id} | conf={conf}")

        # 1. YOLO inference
        yolo_result = run_yolo_for_session(session_id, conf=conf)

        # 2. Build COCO JSON
        coco_json = build_coco_from_detections(
            detections_per_image=yolo_result["detections"],
            categories=yolo_result["categories"],
            images_root=str(images_dir),
        )

        # 3. Save annotations inside session
        out_path = annotations_dir / "auto_annotations.json"
        out_path.write_text(json.dumps(coco_json, indent=2), encoding="utf-8")

        # 4. Validate generated dataset
        validation_report = run_autocheck(io.StringIO(json.dumps(coco_json)))

        total_images = len(yolo_result["detections"])
        total_detections = sum(
            len(img["objects"]) for img in yolo_result["detections"]
        )

        logger.info(
            f"Auto-annotation done | session={session_id} "
            f"| images={total_images} | detections={total_detections}"
        )

        return ok(
            {
                "session_id": session_id,
                "annotations_file": "auto_annotations.json",
                "total_images": total_images,
                "total_detections": total_detections,
                "validation_report": validation_report,
            },
            "Auto-annotation completed",
        )

    except FileNotFoundError as e:
        logger.warning(f"Auto-annotate file error: {e}")
        return err(str(e), 404)
    except RuntimeError as e:
        logger.warning(f"Auto-annotate runtime error: {e}")
        return err(str(e), 400)
    except Exception:
        logger.exception("Auto-annotate crashed")
        return err("Internal server error", 500)


# --------------------------------------------------
# DOWNLOAD ANNOTATIONS
# --------------------------------------------------


@app.route("/session/<session_id>/download-annotations", methods=["GET"])
def download_annotations(session_id):
    """
    Download the auto-generated COCO annotation JSON for a session.
    """
    try:
        session_dir = SESSIONS_ROOT / session_id

        if not session_dir.exists():
            return err("Session not found", 404)

        annotations_dir = session_dir / "annotations"
        ann_file = annotations_dir / "auto_annotations.json"

        if not ann_file.exists():
            return err(
                "Annotations not generated yet. Run Auto-Annotate first.", 404
            )

        return send_file(
            str(ann_file),
            mimetype="application/json",
            as_attachment=True,
            download_name=f"annotations_{session_id[:8]}.json",
        )

    except Exception:
        logger.exception("Download annotations crashed")
        return err("Internal server error", 500)


# --------------------------------------------------
# DELETE SESSION (cleanup)
# --------------------------------------------------


@app.route("/session/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    """
    Permanently delete a session and all its files.
    """
    try:
        session_dir = SESSIONS_ROOT / session_id

        if not session_dir.exists():
            return err("Session not found", 404)

        shutil.rmtree(str(session_dir))
        logger.info(f"Session deleted | session={session_id}")

        return ok(message="Session deleted successfully")

    except Exception:
        logger.exception("Delete session crashed")
        return err("Internal server error", 500)


# --------------------------------------------------
# Run server
# --------------------------------------------------

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=DEBUG,
    )