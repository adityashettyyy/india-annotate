# backend/utils/helper.py

import os
from pathlib import Path


def list_images_in_folder(folder):
    """
    Returns list of image file paths in a folder.
    Accepts: .jpg, .jpeg, .png
    """
    folder = Path(folder)
    if not folder.exists():
        return []

    exts = [".jpg", ".jpeg", ".png"]

    return [
        str(p) for p in folder.iterdir()
        if p.suffix.lower() in exts
    ]


def ensure_dir(path):
    """
    Create a directory if it does not exist.
    """
    Path(path).mkdir(parents=True, exist_ok=True)


def relative_path(root, full_path):
    """
    Convert absolute path → relative to root folder.
    Example:
       root = dataset/images
       full = dataset/images/test/123.jpg
       output = test/123.jpg
    """
    root = Path(root)
    full_path = Path(full_path)
    return str(full_path.relative_to(root)).replace("\\", "/")
