# IndiaAnnotate

### Curated Marketplace for Localized Datasets

---

## Overview

**IndiaAnnotate** is a web-based platform designed to **validate, analyze, and automatically annotate localized image datasets** using the COCO format.

The project addresses a core problem in machine learning pipelines:
**inconsistent, incomplete, and low-quality datasets** reduce model performance.

IndiaAnnotate provides:

* Automated annotation using YOLO
* Dataset validation against COCO standards
* Quality scoring and dataset insights
  All through a clean, easy-to-use interface.

---

## Problem Statement

Most real-world datasets:

* Are poorly annotated
* Contain logical inconsistencies
* Lack quality metrics
* Require expensive manual labeling

IndiaAnnotate solves this by combining **automatic object detection + dataset validation**, making datasets **ML-ready**.

---

## Tech Stack

### Frontend

* **HTML5** – Page structure
* **CSS (TailwindCSS)** – Styling & layout
* **JavaScript** – API interaction & UI logic

### Backend

* **Python**
* **Flask** – REST API
* **Flask-CORS** – Cross-origin support

### Machine Learning

* **YOLOv8 (Ultralytics)** – Object detection
* **IDD-trained YOLO model** (`idd_yolo.pt`)

### Dataset Format

* **COCO JSON**
* **JSON Schema Validation**

---

## Key Features

* COCO dataset validation
* Automatic annotation of raw images
* YOLO-based object detection
* Recursive image scanning (nested folders supported)
* Dataset quality score generation
* Label distribution analysis
* Annotated vs unannotated image detection
* Downloadable validation reports
* Dark / Light mode UI

---

## Project Structure

```
IndiaAnnotate/
│
├── backend/
│   ├── app.py                 # Flask API
│   ├── models/
│   │   └── idd_yolo.pt        # YOLO model weights
│   ├── utils/
│   │   ├── autocheck.py       # Dataset validation logic
│   │   ├── yolo_infer.py      # YOLO inference
│   │   ├── coco_builder.py    # YOLO → COCO conversion
│   │   └── schema.json        # COCO schema
│   └── requirements.txt
│
├── dataset/
│   ├── images/                # Raw images (train / val / test)
│   └── annotations/           # COCO annotation files
│
├── frontend/
│   ├── index.html             # UI
│   ├── script.js              # Client logic
│   └── style.css              # Custom styles
│
└── README.md
```

---

## Backend Workflow

1. **Receive Input**

   * Upload COCO JSON or request auto-annotation

2. **Schema Validation**

   * Validates structure using `schema.json`

3. **Logical Validation**

   * Bounding box checks
   * Category mismatches
   * Missing annotations

4. **Quality Analysis**

   * Annotated vs unannotated images
   * Dataset balance
   * Average annotations per image

5. **Return Result**

   * JSON report with statistics and quality score

---

## Auto-Annotation Workflow

```
Raw Images
   ↓
YOLO Object Detection
   ↓
COCO Annotation Generation
   ↓
Dataset Validation
   ↓
Quality Report
```

---

## Dataset Quality Score

The **quality score (0–100)** is a heuristic metric based on:

* Annotation coverage
* Percentage of annotated images
* Average objects per image
* Label distribution balance
* Structural correctness

Higher score → better dataset usability for ML training.

---

## Annotated vs Unannotated Images

* **Annotated Image**
  → Contains at least one valid bounding box

* **Unannotated Image**
  → YOLO detects no objects or no valid labels

Unannotated images are **not errors**, but they reduce dataset quality.

---

## IDD YOLO Model (`idd_yolo.pt`)

* A YOLOv8 model trained/fine-tuned on **Indian Driving Dataset (IDD)**
* Detects Indian traffic-specific objects:

  * Car, bus, truck, autorickshaw
  * Motorcycle, bicycle
  * Traffic signs, pedestrians, etc.

The model defines the **available categories** dynamically.

---

## API Endpoints

### `GET /`

Health check endpoint

### `POST /validate`

Validates an uploaded COCO JSON file

### `POST /auto-annotate`

Runs YOLO on raw images and generates validated annotations

---

## Setup Instructions

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
python app.py
```

Server runs at:

```
http://127.0.0.1:5000
```

---

### Frontend

```bash
cd frontend
# Open index.html in browser
```

---

## Use Cases

* Curated dataset marketplaces
* ML dataset quality assurance
* Computer vision pipelines
* Academic research
* Traffic & smart city datasets
* Localization-specific AI models

---

## Future Enhancements

* Domain-specific dataset packs
* Multiple YOLO model support
* Dataset versioning
* Annotation correction UI
* Export to YOLO / Pascal VOC
* Cloud deployment (AWS/GCP)
* Active learning feedback loop

---

