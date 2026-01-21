# backend/config.py

from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATASET_ROOT = PROJECT_ROOT / "dataset"
IMAGES_ROOT = DATASET_ROOT / "images"
ANNOTATIONS_ROOT = DATASET_ROOT / "annotations"
ANNOTATIONS_ROOT.mkdir(parents=True, exist_ok=True)

MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB

ALLOWED_SPLITS = {"train", "val", "test"}

ENV = os.getenv("FLASK_ENV", "production")
DEBUG = ENV != "production"
