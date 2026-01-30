# backend/app.py

from flask import Flask, request, jsonify
from flask_cors import CORS
import io
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import (
    IMAGES_ROOT,
    ANNOTATIONS_ROOT,
    MAX_CONTENT_LENGTH,
    ALLOWED_SPLITS,
    DEBUG
)

from services.validation_service import run_autocheck
from services.yolo_service import run_yolo_on_folder
from services.coco_service import build_coco_from_detections
from services.upload_service import handle_dataset_upload

# --------------------------------------------------
# App setup
# --------------------------------------------------

app = Flask(__name__)
CORS(app)

app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# --------------------------------------------------
# Logging (Production-grade)
# --------------------------------------------------

logger = logging.getLogger("india_annotate")
logger.setLevel(logging.INFO)

handler = RotatingFileHandler(
    "backend.log",
    maxBytes=5_000_000,
    backupCount=3
)
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s"
)
handler.setFormatter(formatter)
logger.addHandler(handler)

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
# Routes
# --------------------------------------------------

@app.route("/", methods=["GET"])
def home():
    return ok(message="IndiaAnnotate API running")


@app.route("/health", methods=["GET"])
def health():
    return ok({"uptime": "ok"}, "healthy")

# --------------------------------------------------
# DATASET UPLOAD (ADD-1)
# --------------------------------------------------

@app.route("/upload-dataset", methods=["POST"])
def upload_dataset():
    try:
        if "file" not in request.files:
            return err("Dataset ZIP required", 400)

        file = request.files["file"]
        result = handle_dataset_upload(file)

        logger.info(f"Dataset uploaded | session={result['session_id']}")

        return ok(
            {
                "session_id": result["session_id"],
                "dataset_path": result["dataset_path"]
            },
            "Dataset uploaded successfully"
        )

    except Exception:
        logger.exception("Upload dataset crashed")
        return err("Internal server error", 500)

# --------------------------------------------------
# VALIDATE COCO JSON (ADD-2 + ADD-4)
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
                    "current_stage": report.get("crowd_flow", {}).get("current_stage")
                }
            },
            "Validation completed"
        )

    except Exception:
        logger.exception("Validate endpoint crashed")
        return err("Internal server error", 500)

# --------------------------------------------------
# AUTO-ANNOTATE (ADD-3 + ADD-4)
# --------------------------------------------------

@app.route("/auto-annotate", methods=["POST"])
def auto_annotate():
    try:
        data = request.get_json(silent=True) or {}
        split = data.get("split", "test")

        if split not in ALLOWED_SPLITS:
            return err("Invalid split. Use train/val/test.", 400)

        images_dir = IMAGES_ROOT / split
        if not images_dir.exists():
            return err(f"Images folder not found: {split}", 400)

        logger.info(f"Auto-annotation started | split={split}")

        # 1️⃣ YOLO inference
        yolo_result = run_yolo_on_folder(str(images_dir))
        if yolo_result.get("status") != "success":
            return err("YOLO inference failed", 500)

        # 2️⃣ Build COCO
        coco_json = build_coco_from_detections(
            detections_per_image=yolo_result["detections"],
            categories=yolo_result["categories"],
            images_root=str(IMAGES_ROOT)
        )

        # 3️⃣ Save annotations
        out_path = ANNOTATIONS_ROOT / f"auto_annotations_{split}.json"
        out_path.write_text(json.dumps(coco_json, indent=2), encoding="utf-8")

        # 4️⃣ Validate generated dataset
        validation_report = run_autocheck(
            io.StringIO(json.dumps(coco_json))
        )

        logger.info(f"Auto-annotation completed | split={split}")

        return ok(
            {
                "annotations_file": str(out_path),
                "validation_report": validation_report,
                "india_specific": {
                    "dataset": "Indian Driving Dataset (IDD)",
                    "objects": [
                        "car", "bus", "truck",
                        "autorickshaw", "motorcycle",
                        "traffic_sign", "pedestrian"
                    ]
                }
            },
            "Auto-annotation completed"
        )

    except Exception:
        logger.exception("Auto-annotate crashed")
        return err("Internal server error", 500)

# --------------------------------------------------
# Run server
# --------------------------------------------------

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=DEBUG
    )
