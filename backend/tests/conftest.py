# backend/tests/conftest.py

import io
import json
from pathlib import Path
import pytest

# A tiny valid COCO sample for tests
@pytest.fixture
def sample_coco_json():
    data = {
        "images": [
            {
                "id": 1,
                "file_name": "test.jpg",
                "width": 640,
                "height": 480
            }
        ],
        "annotations": [
            {
                "id": 1,
                "image_id": 1,
                "category_id": 1,
                "bbox": [10, 10, 100, 100],
                "area": 10000,
                "iscrowd": 0,
                "segmentation": []
            }
        ],
        "categories": [
            {"id": 1, "name": "person", "supercategory": "object"}
        ]
    }
    return io.StringIO(json.dumps(data))
