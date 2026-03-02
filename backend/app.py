# backend/app.py  — v1.2
# New: Auth endpoints, Image serving, Annotator save, Reviewer queue, Approve/Reject

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
    ALLOWED_IMAGE_EXTS,
)

from services.validation_service import run_autocheck
from services.yolo_service import run_yolo_for_session
from services.coco_service import build_coco_from_detections
from services.upload_service import handle_dataset_upload
from services.auth_service import (
    register_user, login_user, logout_user,
    get_token_from_request, verify_token,
    require_auth, require_role, seed_default_users,
)

# --------------------------------------------------
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

logger = logging.getLogger("india_annotate")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler("backend.log", maxBytes=5_000_000, backupCount=3)
formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
if DEBUG:
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

logger.info("IndiaAnnotate backend v1.2 started")
seed_default_users()

# --------------------------------------------------
def ok(data=None, message="ok", code=200):
    payload = {"status": "success", "message": message}
    if data is not None:
        payload.update(data)
    return jsonify(payload), code

def err(message="error", code=400):
    return jsonify({"status": "error", "message": message}), code

# ==================================================
# HEALTH
# ==================================================

@app.route("/", methods=["GET"])
def home():
    return ok(message="IndiaAnnotate API v1.2")

@app.route("/health", methods=["GET"])
def health():
    return ok({"uptime": "ok"}, "healthy")

# ==================================================
# AUTH
# ==================================================

@app.route("/auth/register", methods=["POST"])
def auth_register():
    try:
        data = request.get_json(silent=True) or {}
        result = register_user(
            data.get("username", "").strip(),
            data.get("password", ""),
            data.get("role", "annotator"),
        )
        if not result["ok"]:
            return err(result["message"], 400)
        logger.info(f"Registered: {result['username']} role={result['role']}")
        return ok({"username": result["username"], "role": result["role"]}, "Registered", 201)
    except Exception:
        logger.exception("Register crashed")
        return err("Internal server error", 500)


@app.route("/auth/login", methods=["POST"])
def auth_login():
    try:
        data = request.get_json(silent=True) or {}
        result = login_user(data.get("username", "").strip(), data.get("password", ""))
        if not result["ok"]:
            return err(result["message"], 401)
        logger.info(f"Login: {result['username']}")
        return ok({"token": result["token"], "username": result["username"], "role": result["role"]}, "Login successful")
    except Exception:
        logger.exception("Login crashed")
        return err("Internal server error", 500)


@app.route("/auth/logout", methods=["POST"])
@require_auth
def auth_logout():
    logout_user(get_token_from_request())
    return ok(message="Logged out")


@app.route("/auth/me", methods=["GET"])
@require_auth
def auth_me():
    return ok({"username": request.current_user["username"], "role": request.current_user["role"]})

# ==================================================
# UPLOAD DATASET
# ==================================================

@app.route("/upload-dataset", methods=["POST"])
@require_auth
def upload_dataset():
    try:
        if "file" not in request.files:
            return err("Dataset ZIP required", 400)
        file = request.files["file"]
        if not file.filename or not file.filename.lower().endswith(".zip"):
            return err("Only .zip files are supported", 400)

        result = handle_dataset_upload(file)
        uploader = request.current_user["username"]

        meta_path = SESSIONS_ROOT / result["session_id"] / "meta.json"
        meta_path.write_text(json.dumps({
            "uploaded_by": uploader,
            "status": "uploaded",
            "review_notes": "",
            "reviewed_by": None,
        }, indent=2), encoding="utf-8")

        logger.info(f"Upload | session={result['session_id']} | user={uploader}")
        return ok({"session_id": result["session_id"], "image_count": result["image_count"], "annotation_count": result["annotation_count"]}, f"Uploaded: {result['image_count']} images")
    except ValueError as e:
        return err(str(e), 400)
    except Exception:
        logger.exception("Upload crashed")
        return err("Internal server error", 500)

# ==================================================
# SESSION STATUS
# ==================================================

@app.route("/session/<session_id>/status", methods=["GET"])
@require_auth
def session_status(session_id):
    try:
        session_dir = SESSIONS_ROOT / session_id
        if not session_dir.exists():
            return err("Session not found", 404)

        images_dir = session_dir / "images"
        ann_dir    = session_dir / "annotations"
        meta_path  = session_dir / "meta.json"

        image_files = [p for p in images_dir.rglob("*") if p.is_file() and p.suffix.lower() in ALLOWED_IMAGE_EXTS] if images_dir.exists() else []
        annotation_files = list(ann_dir.glob("*.json")) if ann_dir.exists() else []
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}

        return ok({
            "session_id": session_id,
            "image_count": len(image_files),
            "image_names": [f.name for f in image_files],
            "annotation_files": [f.name for f in annotation_files],
            "has_auto_annotations": (ann_dir / "auto_annotations.json").exists(),
            "has_manual_annotations": (ann_dir / "manual_annotations.json").exists(),
            "status": meta.get("status", "unknown"),
            "uploaded_by": meta.get("uploaded_by"),
            "reviewed_by": meta.get("reviewed_by"),
            "review_notes": meta.get("review_notes", ""),
        })
    except Exception:
        logger.exception("Session status crashed")
        return err("Internal server error", 500)

# ==================================================
# IMAGE SERVING
# ==================================================

@app.route("/session/<session_id>/images", methods=["GET"])
@require_auth
def list_session_images(session_id):
    try:
        session_dir = SESSIONS_ROOT / session_id
        if not session_dir.exists():
            return err("Session not found", 404)

        images_dir = session_dir / "images"
        images = []
        if images_dir.exists():
            images = [
                {"filename": p.name, "url": f"/session/{session_id}/image/{p.name}", "size_bytes": p.stat().st_size}
                for p in sorted(images_dir.iterdir())
                if p.is_file() and p.suffix.lower() in ALLOWED_IMAGE_EXTS
            ]
        return ok({"images": images, "count": len(images)})
    except Exception:
        logger.exception("List images crashed")
        return err("Internal server error", 500)


@app.route("/session/<session_id>/image/<filename>", methods=["GET"])
@require_auth
def serve_session_image(session_id, filename):
    try:
        images_dir = (SESSIONS_ROOT / session_id / "images").resolve()
        img_path   = (images_dir / filename).resolve()

        if not str(img_path).startswith(str(images_dir)):
            return err("Invalid filename", 400)
        if not img_path.exists():
            return err("Image not found", 404)

        mime_map = {".jpg":"image/jpeg",".jpeg":"image/jpeg",".png":"image/png",".bmp":"image/bmp",".webp":"image/webp"}
        return send_file(str(img_path), mimetype=mime_map.get(img_path.suffix.lower(), "application/octet-stream"))
    except Exception:
        logger.exception("Serve image crashed")
        return err("Internal server error", 500)

# ==================================================
# ANNOTATIONS — load / save
# ==================================================

@app.route("/session/<session_id>/annotations/current", methods=["GET"])
@require_auth
def get_current_annotations(session_id):
    try:
        ann_dir = SESSIONS_ROOT / session_id / "annotations"
        manual  = ann_dir / "manual_annotations.json"
        auto    = ann_dir / "auto_annotations.json"

        if manual.exists():
            data, source = json.loads(manual.read_text()), "manual"
        elif auto.exists():
            data, source = json.loads(auto.read_text()), "auto"
        else:
            data, source = {"images":[],"annotations":[],"categories":[]}, "empty"

        return ok({"annotations": data, "source": source})
    except Exception:
        logger.exception("Get annotations crashed")
        return err("Internal server error", 500)


@app.route("/session/<session_id>/save-annotations", methods=["POST"])
@require_auth
def save_annotations(session_id):
    try:
        session_dir = SESSIONS_ROOT / session_id
        if not session_dir.exists():
            return err("Session not found", 404)

        coco_data = request.get_json(silent=True)
        if not coco_data or not all(k in coco_data for k in ("images","annotations","categories")):
            return err("Invalid COCO format", 400)

        ann_dir = session_dir / "annotations"
        ann_dir.mkdir(exist_ok=True)
        (ann_dir / "manual_annotations.json").write_text(json.dumps(coco_data, indent=2), encoding="utf-8")

        meta_path = session_dir / "meta.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        meta["status"] = "annotating"
        meta["last_annotated_by"] = request.current_user["username"]
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        logger.info(f"Annotations saved | session={session_id}")
        return ok({"annotation_count": len(coco_data.get("annotations",[]))}, "Saved")
    except Exception:
        logger.exception("Save annotations crashed")
        return err("Internal server error", 500)


@app.route("/session/<session_id>/submit-for-review", methods=["POST"])
@require_auth
def submit_for_review(session_id):
    try:
        session_dir = SESSIONS_ROOT / session_id
        if not session_dir.exists():
            return err("Session not found", 404)

        ann_dir = session_dir / "annotations"
        if not (ann_dir / "manual_annotations.json").exists() and not (ann_dir / "auto_annotations.json").exists():
            return err("No annotations to submit", 400)

        meta_path = session_dir / "meta.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        meta["status"] = "pending_review"
        meta["submitted_by"] = request.current_user["username"]
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        logger.info(f"Submitted for review | session={session_id}")
        return ok(message="Submitted for review")
    except Exception:
        logger.exception("Submit crashed")
        return err("Internal server error", 500)

# ==================================================
# REVIEWER
# ==================================================

@app.route("/review/queue", methods=["GET"])
@require_role("reviewer", "admin")
def review_queue():
    try:
        queue = []
        for session_dir in SESSIONS_ROOT.iterdir():
            if not session_dir.is_dir():
                continue
            meta_path = session_dir / "meta.json"
            if not meta_path.exists():
                continue
            meta = json.loads(meta_path.read_text())
            if meta.get("status") != "pending_review":
                continue

            images_dir = session_dir / "images"
            image_count = len([p for p in images_dir.rglob("*") if p.is_file() and p.suffix.lower() in ALLOWED_IMAGE_EXTS]) if images_dir.exists() else 0
            ann_dir = session_dir / "annotations"
            manual = ann_dir / "manual_annotations.json"
            auto   = ann_dir / "auto_annotations.json"
            if manual.exists():
                ann_data, ann_source = json.loads(manual.read_text()), "manual"
            elif auto.exists():
                ann_data, ann_source = json.loads(auto.read_text()), "auto"
            else:
                ann_data, ann_source = {"annotations":[]}, "none"

            queue.append({
                "session_id": session_dir.name,
                "uploaded_by": meta.get("uploaded_by","unknown"),
                "submitted_by": meta.get("submitted_by","unknown"),
                "image_count": image_count,
                "annotation_count": len(ann_data.get("annotations",[])),
                "annotation_source": ann_source,
            })

        return ok({"queue": queue, "count": len(queue)})
    except Exception:
        logger.exception("Review queue crashed")
        return err("Internal server error", 500)


@app.route("/session/<session_id>/approve", methods=["POST"])
@require_role("reviewer", "admin")
def approve_session(session_id):
    try:
        session_dir = SESSIONS_ROOT / session_id
        if not session_dir.exists():
            return err("Session not found", 404)
        data  = request.get_json(silent=True) or {}
        notes = data.get("notes","").strip()
        meta_path = session_dir / "meta.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        meta.update({"status":"approved","reviewed_by":request.current_user["username"],"review_notes":notes})
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        logger.info(f"APPROVED | session={session_id}")
        return ok(message="Approved — ready for training")
    except Exception:
        logger.exception("Approve crashed")
        return err("Internal server error", 500)


@app.route("/session/<session_id>/reject", methods=["POST"])
@require_role("reviewer", "admin")
def reject_session(session_id):
    try:
        session_dir = SESSIONS_ROOT / session_id
        if not session_dir.exists():
            return err("Session not found", 404)
        data  = request.get_json(silent=True) or {}
        notes = data.get("notes","").strip()
        if not notes:
            return err("Rejection notes are required", 400)
        meta_path = session_dir / "meta.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        meta.update({"status":"rejected","reviewed_by":request.current_user["username"],"review_notes":notes})
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        logger.info(f"REJECTED | session={session_id}")
        return ok(message="Rejected")
    except Exception:
        logger.exception("Reject crashed")
        return err("Internal server error", 500)

# ==================================================
# VALIDATE
# ==================================================

@app.route("/validate", methods=["POST"])
@require_auth
def validate_dataset():
    try:
        if "file" not in request.files:
            return err("No file", 400)
        file = request.files["file"]
        if not file.filename.strip():
            return err("Empty filename", 400)
        report = run_autocheck(file)
        if report.get("status") != "success":
            return err(report.get("message","Validation failed"), 400)
        return ok({"report": report, "human_review": {"requires_human_review": report.get("requires_human_review"), "review_status": report.get("review_status")}}, "Validation completed")
    except Exception:
        logger.exception("Validate crashed")
        return err("Internal server error", 500)

# ==================================================
# AUTO-ANNOTATE
# ==================================================

@app.route("/auto-annotate", methods=["POST"])
@require_auth
def auto_annotate():
    try:
        data = request.get_json(silent=True) or {}
        session_id = data.get("session_id")
        conf = max(0.05, min(float(data.get("conf", 0.25)), 0.95))
        if not session_id:
            return err("session_id required", 400)

        session_dir = SESSIONS_ROOT / session_id
        images_dir  = session_dir / "images"
        ann_dir     = session_dir / "annotations"

        if not session_dir.exists():
            return err("Session not found", 404)
        if not images_dir.exists():
            return err("Images folder not found", 400)

        yolo_result = run_yolo_for_session(session_id, conf=conf)
        coco_json   = build_coco_from_detections(yolo_result["detections"], yolo_result["categories"], str(images_dir))
        (ann_dir / "auto_annotations.json").write_text(json.dumps(coco_json, indent=2), encoding="utf-8")
        validation_report = run_autocheck(io.StringIO(json.dumps(coco_json)))

        total_det = sum(len(img["objects"]) for img in yolo_result["detections"])
        return ok({"session_id": session_id, "total_images": len(yolo_result["detections"]), "total_detections": total_det, "validation_report": validation_report}, "Auto-annotation complete")
    except FileNotFoundError as e:
        return err(str(e), 404)
    except RuntimeError as e:
        return err(str(e), 400)
    except Exception:
        logger.exception("Auto-annotate crashed")
        return err("Internal server error", 500)

# ==================================================
# DOWNLOAD / DELETE
# ==================================================

@app.route("/session/<session_id>/download-annotations", methods=["GET"])
@require_auth
def download_annotations(session_id):
    try:
        ann_dir = SESSIONS_ROOT / session_id / "annotations"
        target  = ann_dir / "manual_annotations.json"
        if not target.exists():
            target = ann_dir / "auto_annotations.json"
        if not target.exists():
            return err("No annotations found", 404)
        return send_file(str(target), mimetype="application/json", as_attachment=True, download_name=f"annotations_{session_id[:8]}.json")
    except Exception:
        logger.exception("Download crashed")
        return err("Internal server error", 500)


@app.route("/session/<session_id>", methods=["DELETE"])
@require_auth
def delete_session(session_id):
    try:
        session_dir = SESSIONS_ROOT / session_id
        if not session_dir.exists():
            return err("Session not found", 404)
        meta_path = session_dir / "meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            if request.current_user["role"] != "admin" and meta.get("uploaded_by") != request.current_user["username"]:
                return err("Forbidden", 403)
        shutil.rmtree(str(session_dir))
        return ok(message="Deleted")
    except Exception:
        logger.exception("Delete crashed")
        return err("Internal server error", 500)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=DEBUG)