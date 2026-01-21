# backend/tests/test_validation.py

from services.validation_service import run_autocheck

def test_autocheck_valid(sample_coco_json):
    result = run_autocheck(sample_coco_json)

    assert result["status"] == "success"
    assert "summary" in result
    assert result["summary"]["num_images"] == 1
    assert result["summary"]["num_annotations"] == 1
    assert "label_distribution" in result

def test_autocheck_invalid_json():
    from io import StringIO

    bad_file = StringIO("{ this is not json }")
    result = run_autocheck(bad_file)

    assert result["status"] == "error"
    assert "Invalid JSON" in result["message"]
