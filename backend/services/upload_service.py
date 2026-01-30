import zipfile
import uuid
from pathlib import Path
from config import UPLOAD_ROOT, ALLOWED_IMAGE_EXTS

def handle_dataset_upload(zip_file):
    session_id = str(uuid.uuid4())
    session_dir = UPLOAD_ROOT / session_id
    images_dir = session_dir / "images"
    annotations_dir = session_dir / "annotations"

    images_dir.mkdir(parents=True)
    annotations_dir.mkdir(parents=True)

    zip_path = session_dir / zip_file.filename
    zip_file.save(zip_path)

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(session_dir)

    # Auto-detect structure
    for p in session_dir.rglob("*"):
        if p.suffix.lower() in ALLOWED_IMAGE_EXTS:
            p.rename(images_dir / p.name)
        elif p.suffix.lower() == ".json":
            p.rename(annotations_dir / p.name)

    return {
        "session_id": session_id,
        "images_dir": images_dir,
        "annotations_dir": annotations_dir
    }
