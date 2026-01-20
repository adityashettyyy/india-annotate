from flask import Flask, request, jsonify
from flask_cors import CORS
import io
import json

from config import IMAGES_ROOT, ANNOTATIONS_ROOT
from services.validation_service import run_autocheck
from services.yolo_service import run_yolo_on_folder
from services.coco_service import build_coco_from_detections

app = Flask(__name__)
CORS(app)

# Security: limit upload size (50MB)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  

# Allowed dataset splits
ALLOWED_SPLITS = {"train", "val", "test"}

def api_error(msg, code=400):
    return jsonify({"status": "error", "message": msg}), code


@app.route("/")
def home():
    return jsonify({"message": "IndiaAnnotate API is running"}), 200


# -----------------------------
# VALIDATE COCO JSON
# -----------------------------
@app.route("/validate", methods=["POST"])
def validate_dataset():
    try:
        if "file" not in request.files:
            return api_error("No file uploaded.", 400)

        file = request.files["file"]

        if file.filename.strip() == "":
            return api_error("Empty filename.", 400)

        report = run_autocheck(file)
        return jsonify(report), 200

    except Exception as e:
        return api_error(f"Server error: {str(e)}", 500)


# -----------------------------
# AUTO-ANNOTATE IMAGES
# -----------------------------
@app.route("/auto-annotate", methods=["POST"])
def auto_annotate():
    try:
        data = request.get_json(silent=True) or {}
        split = data.get("split", "test")

        # Security check
        if split not in ALLOWED_SPLITS:
            return api_error("Invalid split. Use train/val/test.", 400)

        images_dir = IMAGES_ROOT / split

        if not images_dir.exists():
            return api_error(f"Images folder not found: {images_dir}", 400)

        # 1) Run YOLO
        yolo_result = run_yolo_on_folder(str(images_dir))

        if yolo_result["status"] != "success":
            return api_error("YOLO inference failed.", 500)

        detections = yolo_result["detections"]
        categories = yolo_result["categories"]

        # 2) Build COCO JSON
        coco_json = build_coco_from_detections(
            detections_per_image=detections,
            categories=categories,
            images_root=str(IMAGES_ROOT)
        )

        # 3) Save file
        out_path = ANNOTATIONS_ROOT / f"auto_annotations_{split}.json"
        out_path.write_text(json.dumps(coco_json, indent=2), encoding="utf-8")

        # 4) Validate generated file
        json_file_like = io.StringIO(json.dumps(coco_json))
        validation_report = run_autocheck(json_file_like)

        return jsonify({
            "status": "success",
            "message": "Auto-annotation completed successfully.",
            "annotations_file": str(out_path),
            "validation_report": validation_report
        }), 200

    except Exception as e:
        return api_error(f"Auto-annotation failed: {str(e)}", 500)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
