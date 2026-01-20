# backend/app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import io
import json
from pathlib import Path

from services.validation_service import run_autocheck
from services.yolo_service import run_yolo_on_folder
from services.coco_service import build_coco_from_detections


app = Flask(__name__)
CORS(app)

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_ROOT = PROJECT_ROOT / "dataset"
IMAGES_ROOT = DATASET_ROOT / "images"
ANNOTATIONS_ROOT = DATASET_ROOT / "annotations"
ANNOTATIONS_ROOT.mkdir(parents=True, exist_ok=True)


@app.route("/")
def home():
    return jsonify({"message": "IndiaAnnotate API is running"}), 200


# ----------------------------------------------------------------------
# VALIDATE EXISTING COCO JSON
# ----------------------------------------------------------------------
@app.route("/validate", methods=["POST"])
def validate_dataset():
    try:
        if "file" not in request.files:
            return jsonify({
                "status": "error",
                "message": "No file uploaded."
            }), 400

        file = request.files["file"]

        if file.filename.strip() == "":
            return jsonify({
                "status": "error",
                "message": "Empty filename."
            }), 400

        report = run_autocheck(file)
        return jsonify(report), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Server error: {e}"
        }), 500


# ----------------------------------------------------------------------
# AUTO-ANNOTATE RAW IMAGES USING YOLO → COCO JSON → VALIDATE
# ----------------------------------------------------------------------
@app.route("/auto-annotate", methods=["POST"])
def auto_annotate():
    try:
        data = request.get_json(silent=True) or {}
        split = data.get("split", "test")

        images_dir = IMAGES_ROOT / split

        if not images_dir.exists():
            return jsonify({
                "status": "error",
                "message": f"Images folder not found: {images_dir}"
            }), 400

        # --------------------------------------------------------------
        # 1) RUN YOLO — now returns ONE dict (NOT 2 values)
        # --------------------------------------------------------------
        yolo_result = run_yolo_on_folder(str(images_dir))

        if yolo_result["status"] != "success":
            return jsonify({
                "status": "error",
                "message": f"YOLO failed: {yolo_result.get('message','unknown error')}"
            }), 500

        detections = yolo_result["detections"]
        categories = yolo_result["categories"]

        # --------------------------------------------------------------
        # 2) BUILD COCO JSON
        # --------------------------------------------------------------
        coco_json = build_coco_from_detections(
            detections_per_image=detections,
            categories=categories,
            images_root=str(IMAGES_ROOT)
        )

        # --------------------------------------------------------------
        # 3) SAVE TO FILE
        # --------------------------------------------------------------
        out_path = ANNOTATIONS_ROOT / f"auto_annotations_{split}.json"
        out_path.write_text(json.dumps(coco_json, indent=2), encoding="utf-8")

        # --------------------------------------------------------------
        # 4) VALIDATE THE GENERATED FILE
        # --------------------------------------------------------------
        json_file_like = io.StringIO(json.dumps(coco_json))
        validation_report = run_autocheck(json_file_like)

        return jsonify({
            "status": "success",
            "message": "Auto-annotation completed successfully.",
            "annotations_file": str(out_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "validation_report": validation_report
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Auto-annotation failed: {e}"
        }), 500


# Run server
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
