# 🌿 Western Ghats Endangered Animal Detection
### AI-Based Wildlife Detection & Monitoring for Tamil Nadu & Kerala Region

> **Academic Prototype Disclaimer**: This project is an educational and research prototype developed for wildlife monitoring demonstration.
> It is **not** a validated anti-poaching or field-enforcement system. All conservation statuses are aligned with the official [IUCN Red List](https://www.iucnredlist.org/).

---

## 📌 Table of Contents
1. [Project Overview](#1-project-overview)
2. [Target Endangered & Vulnerable Species](#2-target-endangered--vulnerable-species)
3. [Small-Dataset Optimization Strategy](#3-small-dataset-optimization-strategy)
4. [Project Structure](#4-project-structure)
5. [Installation (Windows)](#5-installation-windows)
6. [Adding Images (Now & In The Future)](#6-adding-images-now--in-the-future)
7. [Validation & Training](#7-validation--training)
8. [Evaluation & CLI Inference](#8-evaluation--cli-inference)
9. [Streamlit Web Application](#9-streamlit-web-application)
10. [References & Authoritative Sources](#10-references--authoritative-sources)

---

## 1. Project Overview

The **Western Ghats biodiversity hotspot** spanning **Tamil Nadu and Kerala** is home to some of the world's most endangered and endemic fauna. This project delivers a specialized computer-vision detection pipeline designed to:

- Detect and classify 10 focal Western Ghats species with high precision.
- Train effectively even with **minimal initial training sets (5–20 images per species)** using domain-calibrated transfer learning and aggressive data augmentations.
- Seamlessly ingest new field photos, camera-trap captures, or PDF extracts in the future using an automated ingestion tool (`scripts/add_images.py`).
- Present detection results with **percentage confidence scores** and **interactive IUCN conservation profile cards** in both web and CLI interfaces.

---

## 2. Target Endangered & Vulnerable Species

| Class ID | Species Common Name | Scientific Name | IUCN Status | Key Western Ghats Reserves (TN / Kerala) |
|:---:|:---|:---|:---:|:---|
| `0` | **Nilgiri Tahr** | *Nilgiritragus hylocrius* | `EN` (Endangered) | Eravikulam, Nilgiri Hills, Anamalai |
| `1` | **Lion-Tailed Macaque** | *Macaca silenus* | `EN` (Endangered) | Silent Valley, Anamalai, Kalakad-Mundanthurai |
| `2` | **Nilgiri Langur** | *Semnopithecus johnii* | `VU` (Vulnerable) | Nilgiris, Anamalai, Periyar |
| `3` | **Malabar Civet** | *Viverra civettina* | `CR` (Critically Endangered) | Kerala lowland forests (critically rare) |
| `4` | **Gaur (Indian Bison)** | *Bos gaurus* | `VU` (Vulnerable) | Mudumalai, Wayanad, Parambikulam |
| `5` | **Bengal Tiger** | *Panthera tigris tigris* | `EN` (Endangered) | Mudumalai, Anamalai, Wayanad, KMTR |
| `6` | **Sloth Bear** | *Melursus ursinus* | `VU` (Vulnerable) | Mudumalai, Anamalai, Grizzled Giant Squirrel WS |
| `7` | **Asian Elephant** | *Elephas maximus* | `EN` (Endangered) | Nilgiri Biosphere, Wayanad, Periyar |
| `8` | **Nilgiri Marten** | *Martes gwatkinsii* | `VU` (Vulnerable) | High-elevation shola-grassland (>1000m) |
| `9` | **Anaimalai Flying Frog** | *Rhacophorus pseudomalabaricus* | `EN` (Endangered) | Anaimalai Hills / Valparai rainforest patches |

---

## 3. Small-Dataset Optimization Strategy

Because sightings of rare endemic animals like the *Malabar Civet* or *Nilgiri Marten* are sparse, standard large-scale training strategies would overfit. This project incorporates specific optimizations:

1. **Backbone Transfer Learning**: Initializes from `yolov8s.pt` to leverage pre-learned visual priors (edges, silhouettes, natural textures).
2. **Aggressive Augmentations**:
   - HSV color jitter (`hsv_h: 0.02`, `hsv_s: 0.8`, `hsv_v: 0.5`) to simulate varying rainforest canopies and lighting.
   - Scale (`0.6`) and rotation (`15°`) variations to handle varying camera distances.
   - MixUp (`0.1`) and horizontal flipping (`0.5`).
3. **Mosaic Scheduling**: Employs mosaic multi-crop synthesis during the main training phase, disabling it during the final 20 epochs (`close_mosaic: 20`) for sharp bounding-box convergence.
4. **Stable Convergence**: Batch size set to `8`, initial learning rate `0.001`, warmup over 5 epochs, with early stopping patience of 30 epochs.

---

## 4. Project Structure

```
ML/
├── app/
│   └── app.py                  # Streamlit web app with IUCN species cards & % confidence
├── config/
│   └── settings.yaml           # Central configuration: 10 species, IUCN profiles, hyperparameters
├── data/
│   ├── dataset.yaml            # YOLO dataset specification
│   ├── metadata.csv            # Attribution, source URLs, licenses, and splits
│   ├── images/
│   │   ├── train/              # Training images
│   │   ├── val/                # Validation images
│   │   └── test/               # Test images
│   ├── labels/
│   │   ├── train/              # YOLO .txt labels
│   │   ├── val/
│   │   └── test/
│   └── raw/                    # Staged unannotated images awaiting labeling
├── scripts/
│   ├── add_images.py           # Automated tool to ingest new images (labelled or raw)
│   ├── fetch_images.py         # Research-grade iNaturalist downloader filtered to India
│   ├── validate_dataset.py     # Comprehensive dataset integrity & bounding-box validator
│   ├── train.py                # Transfer learning training script (optimized for small data)
│   ├── evaluate.py             # Precision, Recall, mAP evaluation
│   └── infer.py                # CLI inference tool with % confidence & IUCN tags
├── src/
│   ├── config.py               # YAML config loader and metadata accessors
│   ├── inference.py            # YOLO inference + status overlay
│   └── video_processor.py      # Frame-by-frame OpenCV video processing
├── runs/                       # Training experiments and saved checkpoints
├── results/                    # Inference outputs (images, videos, CSV/JSON)
└── README.md
```

---

## 5. Installation (Windows)

```powershell
# 1. Activate your virtual environment
cd "C:\Users\admin\OneDrive\Desktop\ML"
venv\Scripts\activate

# 2. Verify dependencies
python -c "import ultralytics, streamlit, cv2, yaml; print('All core packages ready!')"
```

---

## 6. Adding Images (Now & In The Future)

The project includes `scripts/add_images.py` to seamlessly ingest images without manual filename or directory management. It automatically detects duplicates via MD5 hashing and updates `data/metadata.csv`.

### Mode A: Adding Labelled Pairs (Image + YOLO .txt)
Use this when you already have bounding box annotations:
```powershell
python scripts/add_images.py `
  --source path\to\your_images `
  --species nilgiri_tahr `
  --mode labelled `
  --split train
```

### Mode B: Adding Raw Photos for Future Labeling
Use this to stage unannotated photos into `data/raw/<species>/`:
```powershell
python scripts/add_images.py `
  --source path\to\raw_photos `
  --species lion_tailed_macaque `
  --mode raw
```

### Fetching Research-Grade Field Photos via iNaturalist
You can also download Creative Commons observations filtered strictly to India:
```powershell
python scripts/fetch_images.py --species nilgiri_tahr --max-images 20
```

---

## 7. Validation & Training

### 1. Validate Dataset Integrity
Before launching training, always verify label coordinates and formatting:
```powershell
python scripts/validate_dataset.py
```

### 2. Run Training
```powershell
# Automatically uses small-dataset hyperparameters from config/settings.yaml
python scripts/train.py

# Or customize on the fly:
python scripts/train.py --epochs 150 --batch 8 --device cpu
```

Once completed, the best model weights will be saved to:
`runs/train/<experiment_name>/weights/best.pt`. Update `trained_checkpoint` in `config/settings.yaml` to make it active.

---

## 8. Evaluation & CLI Inference

### Evaluation
```powershell
python scripts/evaluate.py --split val
```

### Command-Line Inference
Run inference directly from PowerShell with percentage confidence and IUCN tags:
```powershell
# Test on an image
python scripts/infer.py --source path\to\photo.jpg

# Test on a video file
python scripts/infer.py --source path\to\wildlife_video.mp4 --conf 0.35
```

---

## 9. Streamlit Web Application

Launch the interactive monitoring dashboard:
```powershell
streamlit run app/app.py
```

### Key UI Features:
- **Photo Upload**: Real-time detection with side-by-side comparison, bounding boxes, percentage confidence (e.g. `87.3%`), and raw scores.
- **IUCN Conservation Cards**: Color-coded badges (`CR`, `EN`, `VU`) with scientific names, Western Ghats habitat distribution, and conservation descriptions.
- **Video Processing**: Frame-by-frame processing with progress indicators, detection summaries, and downloadable annotated MP4 videos.
- **Export Options**: Export detection results as annotated imagery, CSV tables, or JSON structures.
- **About Tab**: Complete species catalog, small-dataset architecture explanation, and workflow guidance.

---

## 10. References & Authoritative Sources

- **IUCN Red List of Threatened Species**: https://www.iucnredlist.org/
- **Wildlife Institute of India (WII)**: https://www.wii.gov.in/
- **Kerala Forest and Wildlife Department**: https://forest.kerala.gov.in/
- **Tamil Nadu Forest Department**: https://www.forests.tn.gov.in/
- **iNaturalist Open Data Initiative**: https://www.inaturalist.org/
- **Ultralytics YOLOv8**: https://docs.ultralytics.com/
