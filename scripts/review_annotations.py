# ============================================================
# scripts/review_annotations.py
# Visual annotation review script.
#
# Draws bounding boxes on a random sample of labelled images
# using OpenCV, so you can visually verify boxes are correct
# before committing to training.
#
# Run BEFORE training, after annotating 30–50 pilot images.
#
# Usage:
#   python scripts/review_annotations.py
#   python scripts/review_annotations.py --split train --n 50
#   python scripts/review_annotations.py --split val --save
# ============================================================

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_config, get_class_names

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# Colour palette (BGR) — one per class
_PALETTE = [
    (0, 200, 255),   # amber
    (50, 220, 50),   # green
    (80, 80, 255),   # coral-red
    (255, 180, 0),   # blue-gold
    (200, 80, 200),  # magenta
]


def _colour(class_id: int) -> tuple[int, int, int]:
    return _PALETTE[class_id % len(_PALETTE)]


def draw_labels_on_image(
    image_path: Path,
    label_path: Path,
    class_names: list[str],
) -> "np.ndarray | None":  # type: ignore[name-defined]
    """Return a BGR image with bounding boxes drawn from a YOLO label file."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        print("[ERROR] OpenCV not installed. pip install opencv-python-headless")
        sys.exit(1)

    img = cv2.imread(str(image_path))
    if img is None:
        print(f"  [SKIP] Cannot read: {image_path.name}")
        return None

    h, w = img.shape[:2]

    if not label_path.exists():
        # No label file — draw a red "NO LABEL" banner
        cv2.putText(img, "NO LABEL FILE", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2, cv2.LINE_AA)
        return img

    lines = label_path.read_text(encoding="utf-8").strip().splitlines()
    if not lines:
        cv2.putText(img, "EMPTY LABEL (background)", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 180, 0), 2, cv2.LINE_AA)
        return img

    for line in lines:
        parts = line.strip().split()
        if len(parts) != 5:
            continue
        try:
            cls = int(parts[0])
            xc, yc, bw, bh = (float(v) for v in parts[1:])
        except ValueError:
            continue

        # Convert normalised coords to pixel coords
        x1 = int((xc - bw / 2) * w)
        y1 = int((yc - bh / 2) * h)
        x2 = int((xc + bw / 2) * w)
        y2 = int((yc + bh / 2) * h)

        colour = _colour(cls)
        cv2.rectangle(img, (x1, y1), (x2, y2), colour, 2)

        name = class_names[cls] if 0 <= cls < len(class_names) else f"UNKNOWN_ID_{cls}"
        label = f"[{cls}] {name}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(img, (x1, y1 - th - 8), (x1 + tw + 4, y1), colour, cv2.FILLED)
        cv2.putText(img, label, (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

    # Filename overlay at bottom
    cv2.putText(img, image_path.name, (4, h - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1, cv2.LINE_AA)
    return img


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Visually review annotated images with bounding boxes overlaid."
    )
    parser.add_argument("--split", choices=["train", "val", "test", "all"], default="train")
    parser.add_argument("--n", type=int, default=30, help="Number of images to review (default: 30).")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--save", action="store_true",
        help="Save reviewed images to results/annotation_review/ instead of displaying them.",
    )
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config" / "settings.yaml"))
    args = parser.parse_args()

    try:
        import cv2
    except ImportError:
        print("[ERROR] OpenCV not installed. pip install opencv-python-headless")
        sys.exit(1)

    cfg = load_config(args.config)
    class_names = get_class_names(cfg)
    images_root = Path(cfg["paths"]["images_dir"])
    labels_root = Path(cfg["paths"]["labels_dir"])

    # Collect images from the requested split(s)
    splits = ["train", "val", "test"] if args.split == "all" else [args.split]
    candidates: list[tuple[str, Path]] = []
    for split in splits:
        split_dir = images_root / split
        if split_dir.exists():
            for p in split_dir.iterdir():
                if p.suffix.lower() in IMAGE_EXTENSIONS:
                    candidates.append((split, p))

    if not candidates:
        print(f"\n[INFO] No images found in: {[str(images_root/s) for s in splits]}")
        print("  Add images and labels first.")
        return

    random.seed(args.seed)
    sample = random.sample(candidates, min(args.n, len(candidates)))

    print(f"\n  Reviewing {len(sample)} of {len(candidates)} images from split(s): {splits}")
    print(f"  Classes: {class_names}")

    if args.save:
        out_dir = Path(cfg["paths"]["results_dir"]) / "annotation_review"
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"  Saving to: {out_dir}")

    for split, img_path in sample:
        lbl_path = labels_root / split / (img_path.stem + ".txt")
        annotated = draw_labels_on_image(img_path, lbl_path, class_names)
        if annotated is None:
            continue

        if args.save:
            out = out_dir / f"{split}_{img_path.name}"
            cv2.imwrite(str(out), annotated)
        else:
            cv2.imshow(f"Review: {split}/{img_path.name}  (press any key, Q to quit)", annotated)
            key = cv2.waitKey(0) & 0xFF
            cv2.destroyAllWindows()
            if key == ord("q"):
                print("  Review stopped by user.")
                break

    if args.save:
        print(f"\n  Saved {len(sample)} reviewed images to: {out_dir}")
    print("\n  Done.")


if __name__ == "__main__":
    main()
