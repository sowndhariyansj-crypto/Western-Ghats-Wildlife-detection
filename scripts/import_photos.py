"""
scripts/import_photos.py
Import photos from Desktop/photos folder into the project dataset,
standardize them into JPG format, and automatically generate YOLO label files.
"""

import sys
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ultralytics import YOLO

FOLDER_MAP = {
    "Nilgiri tahr": ("nilgiri_tahr", 0),
    "Lion tailed macaque": ("lion_tailed_macaque", 1),
    "bison": ("gaur", 4),
    "Bengal tiger": ("bengal_tiger", 5),
    "sloth_bear": ("sloth_bear", 6),
    "elephant": ("asian_elephant", 7),
    "nilgiri marten": ("nilgiri_marten", 8),
    "flying frog": ("anaimalai_flying_frog", 9),
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

def main():
    photos_dir = Path(r"C:\Users\admin\OneDrive\Desktop\photos")
    if not photos_dir.exists():
        print(f"Error: {photos_dir} does not exist!")
        return

    train_img_dir = PROJECT_ROOT / "data" / "images" / "train"
    val_img_dir = PROJECT_ROOT / "data" / "images" / "val"
    train_lbl_dir = PROJECT_ROOT / "data" / "labels" / "train"
    val_lbl_dir = PROJECT_ROOT / "data" / "labels" / "val"

    for d in [train_img_dir, val_img_dir, train_lbl_dir, val_lbl_dir]:
        d.mkdir(parents=True, exist_ok=True)

    print("Loading pretrained YOLO model for intelligent bounding box auto-labeling...")
    detector = YOLO("yolov8s.pt")

    imported_count = 0

    for folder_name, (species_name, class_id) in FOLDER_MAP.items():
        src_folder = photos_dir / folder_name
        if not src_folder.exists():
            print(f"[SKIP] Folder not found: {folder_name}")
            continue

        raw_files = [f for f in sorted(src_folder.iterdir()) if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS]
        print(f"\nProcessing {folder_name} ({species_name}, class_id={class_id}): {len(raw_files)} photos found")

        for idx, src_file in enumerate(raw_files, start=1):
            stem = f"{species_name}_{idx:03d}"
            target_name = f"{stem}.jpg"

            # Open image with PIL to convert/save as standard RGB JPEG
            try:
                with Image.open(src_file) as img:
                    img_rgb = img.convert("RGB")
                    img_w, img_h = img_rgb.size

                    # Detect animal bounding box using pretrained YOLO
                    results = detector.predict(img_rgb, verbose=False, conf=0.15)
                    boxes = results[0].boxes if len(results) > 0 else []

                    bbox_found = None
                    if boxes is not None and len(boxes) > 0:
                        # Find the largest bounding box (normalized xywh)
                        best_area = 0.0
                        for box in boxes:
                            # xywhn gives normalized [x_center, y_center, width, height]
                            xywhn = box.xywhn[0].tolist()
                            area = xywhn[2] * xywhn[3]
                            if area > best_area:
                                best_area = area
                                bbox_found = xywhn

                    # Fallback if no box detected or box too tiny
                    if not bbox_found or best_area < 0.05:
                        bbox_found = [0.5, 0.5, 0.85, 0.85]

                    xc, yc, w, h = bbox_found
                    # Clamp values inside [0, 1]
                    xc = max(0.01, min(0.99, xc))
                    yc = max(0.01, min(0.99, yc))
                    w = max(0.02, min(0.98, w))
                    h = max(0.02, min(0.98, h))

                    label_line = f"{class_id} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}\n"

                    # Put into train
                    dst_train_img = train_img_dir / target_name
                    dst_train_lbl = train_lbl_dir / f"{stem}.txt"
                    img_rgb.save(dst_train_img, "JPEG", quality=95)
                    dst_train_lbl.write_text(label_line, encoding="utf-8")

                    # Also put 1 copy in val (or if idx == 1) so val split is populated
                    if idx == 1 or len(raw_files) <= 2:
                        dst_val_img = val_img_dir / target_name
                        dst_val_lbl = val_lbl_dir / f"{stem}.txt"
                        img_rgb.save(dst_val_img, "JPEG", quality=95)
                        dst_val_lbl.write_text(label_line, encoding="utf-8")

                    print(f"  [OK] {src_file.name} -> {target_name} (box: {xc:.2f}, {yc:.2f}, {w:.2f}, {h:.2f})")
                    imported_count += 1
            except Exception as e:
                print(f"  [FAIL] {src_file.name}: {e}")

    print(f"\nSuccessfully imported {imported_count} images with YOLO bounding box labels!")

if __name__ == "__main__":
    main()
