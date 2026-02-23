# backend/services/upload_service.py

import zipfile
import uuid
from pathlib import Path
from config import SESSIONS_ROOT, ALLOWED_IMAGE_EXTS


def handle_dataset_upload(zip_file):
    session_id = str(uuid.uuid4())

    # 🔥 Create proper session directory
    session_dir = SESSIONS_ROOT / session_id
    images_dir = session_dir / "images"
    annotations_dir = session_dir / "annotations"
    review_dir = session_dir / "review"

    images_dir.mkdir(parents=True, exist_ok=True)
    annotations_dir.mkdir(parents=True, exist_ok=True)
    review_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded zip inside session
    zip_path = session_dir / zip_file.filename
    zip_file.save(zip_path)

    # Extract inside session folder
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(session_dir)

    # Move detected files into correct subfolders
    for p in session_dir.rglob("*"):
        if p.is_file():
            if p.suffix.lower() in ALLOWED_IMAGE_EXTS:
                p.rename(images_dir / p.name)
            elif p.suffix.lower() == ".json":
                p.rename(annotations_dir / p.name)

    return {
        "session_id": session_id,
        "images_dir": str(images_dir),
        "annotations_dir": str(annotations_dir)
    }