This folder holds all dataset images, labels, and split lists.

FOLDER STRUCTURE
================
data/
├── dataset.yaml          ← YOLO dataset descriptor (edit class names here)
├── images/
│   ├── train/            ← Training images  (.jpg / .png)
│   ├── val/              ← Validation images
│   └── test/             ← Test images (optional but recommended)
├── labels/
│   ├── train/            ← YOLO label files for training images (.txt)
│   ├── val/              ← YOLO label files for validation images
│   └── test/             ← YOLO label files for test images
└── attributions.csv      ← Source and license info for each image

HOW TO ADD YOUR OWN IMAGES
===========================
1. Collect images of each animal species you want to detect.
   - Aim for at least 100–200 varied images per class for a reliable model.
   - A single image is enough to test upload and display, but will NOT
     produce a trained species-recognition model.

2. Avoid near-duplicate images:
   - Keep burst shots, time-lapses, and camera-trap sequences TOGETHER
     in the SAME split (train/val/test) to prevent data leakage.
   - Shuffle at the camera/session level, not the image level.

3. Name images descriptively: nilgiri_tahr_001.jpg, snow_leopard_042.png

4. Record the source and license of every image in attributions.csv.
   Do NOT include images without a compatible license.

HOW TO LABEL (ANNOTATE) IMAGES
================================
Use a free annotation tool such as:
  - LabelImg  (https://github.com/HumanSignal/labelImg)
  - Roboflow Annotate (https://roboflow.com/annotate)
  - CVAT       (https://cvat.ai/)
  - Label Studio (https://labelstud.io/)

Export labels in YOLO format (.txt files).

YOLO LABEL FORMAT
=================
Each image must have a matching .txt file in the labels/ folder with the
same base name. Example: images/train/tahr_001.jpg → labels/train/tahr_001.txt

Each line in the .txt file describes one bounding box:
  <class_id> <x_center> <y_center> <width> <height>

All values are normalised to [0, 1] relative to image width/height.
class_id is the 0-based integer matching the order in dataset.yaml → names.

Example (one animal, class 0, centre of image, half-width/height):
  0 0.5 0.5 0.4 0.6

RECOMMENDED SPLIT RATIOS
=========================
  Train : 70–80 %
  Val   : 10–15 %
  Test  : 10–15 %

Split at the camera/session level, not the image level, to avoid leakage.

WHAT TO DO NEXT
===============
After adding images and labels, run:
  python scripts/validate_dataset.py

Then, to start training:
  python scripts/train.py
