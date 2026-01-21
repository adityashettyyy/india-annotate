# backend/tests/test_yolo.py

from pathlib import Path
import tempfile
from PIL import Image
from services.yolo_service import run_yolo_on_folder

def test_run_yolo_on_empty_folder():
    with tempfile.TemporaryDirectory() as tmp:
        try:
            run_yolo_on_folder(tmp)
            assert False  # should not reach here
        except RuntimeError as e:
            assert "No images found" in str(e)

def test_run_yolo_on_nonexistent_folder():
    try:
        run_yolo_on_folder("/path/does/not/exist")
        assert False
    except FileNotFoundError:
        assert True

def test_run_yolo_on_dummy_image():
    # Create a fake image folder
    with tempfile.TemporaryDirectory() as tmp:
        img_path = Path(tmp) / "test.jpg"

        # Create blank image
        img = Image.new("RGB", (640, 480), color="white")
        img.save(img_path)

        result = run_yolo_on_folder(tmp, conf=0.99)  # high conf → likely 0 detections

        assert result["status"] == "success"
        assert "detections" in result
        assert isinstance(result["detections"], list)
        assert len(result["detections"]) == 1   # one image processed
