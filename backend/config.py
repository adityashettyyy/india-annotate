from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_ROOT = PROJECT_ROOT / "dataset"
IMAGES_ROOT = DATASET_ROOT / "images"
ANNOTATIONS_ROOT = DATASET_ROOT / "annotations"
ANNOTATIONS_ROOT.mkdir(parents=True, exist_ok=True)
