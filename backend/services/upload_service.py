# backend/services/upload_service.py

import zipfile
import uuid
import shutil
from pathlib import Path
from config import SESSIONS_ROOT, ALLOWED_IMAGE_EXTS


def handle_dataset_upload(zip_file):
    session_id = str(uuid.uuid4())

    # Create proper session directory structure
    session_dir = SESSIONS_ROOT / session_id
    images_dir = session_dir / "images"
    annotations_dir = session_dir / "annotations"
    review_dir = session_dir / "review"
    extract_dir = session_dir / "_extract"  # temp extraction folder

    images_dir.mkdir(parents=True, exist_ok=True)
    annotations_dir.mkdir(parents=True, exist_ok=True)
    review_dir.mkdir(parents=True, exist_ok=True)
    extract_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded zip inside session
    zip_path = session_dir / zip_file.filename
    zip_file.save(str(zip_path))

    # Validate the zip before extracting
    if not zipfile.is_zipfile(str(zip_path)):
        shutil.rmtree(str(session_dir))
        raise ValueError("Uploaded file is not a valid ZIP archive")

    # Extract into isolated temp folder
    with zipfile.ZipFile(str(zip_path), "r") as z:
        # Security: reject paths with ".." to prevent zip-slip attacks
        for member in z.namelist():
            if ".." in member or member.startswith("/"):
                shutil.rmtree(str(session_dir))
                raise ValueError(f"Unsafe path in ZIP: {member}")
        z.extractall(str(extract_dir))

    # Remove the uploaded zip to save space
    zip_path.unlink(missing_ok=True)

    image_count = 0
    annotation_count = 0

    # Walk extracted files and move them into proper subfolders
    for p in extract_dir.rglob("*"):
        if not p.is_file():
            continue

        suffix = p.suffix.lower()

        if suffix in ALLOWED_IMAGE_EXTS:
            dest = _unique_dest(images_dir, p.name)
            shutil.move(str(p), str(dest))
            image_count += 1

        elif suffix == ".json":
            dest = _unique_dest(annotations_dir, p.name)
            shutil.move(str(p), str(dest))
            annotation_count += 1

    # Cleanup temp extraction folder
    shutil.rmtree(str(extract_dir), ignore_errors=True)

    if image_count == 0:
        shutil.rmtree(str(session_dir))
        raise ValueError(
            "No valid images found in ZIP. "
            f"Supported formats: {', '.join(ALLOWED_IMAGE_EXTS)}"
        )

    return {
        "session_id": session_id,
        "images_dir": str(images_dir),
        "annotations_dir": str(annotations_dir),
        "image_count": image_count,
        "annotation_count": annotation_count,
    }


def _unique_dest(folder: Path, filename: str) -> Path:
    """
    Return a unique destination path inside `folder`.
    If a file with the same name already exists, append a counter suffix.
    Example: image.jpg -> image_1.jpg -> image_2.jpg
    """
    dest = folder / filename
    if not dest.exists():
        return dest

    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 1
    while True:
        candidate = folder / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1