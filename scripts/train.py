# ============================================================
# scripts/train.py
# Training script — Western Ghats Endangered Animal Detection.
#
# Uses Ultralytics YOLOv8 with transfer learning from a pretrained
# checkpoint (yolov8s.pt by default — small model, good for few images).
#
# IMPORTANT:
#   - You must have labelled images in data/images/train/ and
#     data/images/val/ before running this script.
#   - The model trained here is specific to the 10 Western Ghats
#     species defined in data/dataset.yaml.
#   - Training on CPU is slow. Use --device 0 if you have a GPU.
#
# Usage:
#   python scripts/train.py
#   python scripts/train.py --epochs 150 --batch 8 --device 0
#   python scripts/train.py --resume runs/train/exp/weights/last.pt
# ============================================================

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_config, get_class_names


# ──────────────────────────────────────────────────────────────────
# Pre-flight checks
# ──────────────────────────────────────────────────────────────────

def _check_dataset_ready(cfg: dict) -> None:
    """Raise an informative error if train/val images are missing."""
    images_train = Path(cfg["paths"]["images_dir"]) / "train"
    images_val = Path(cfg["paths"]["images_dir"]) / "val"

    def count_images(d: Path) -> int:
        exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        return sum(1 for p in d.iterdir() if p.suffix.lower() in exts) if d.exists() else 0

    n_train = count_images(images_train)
    n_val = count_images(images_val)

    if n_train == 0 or n_val == 0:
        print("\n" + "=" * 60)
        print("  TRAINING CANNOT START — MISSING DATASET")
        print("=" * 60)
        print(f"\n  Training images  : {n_train}  (need ≥ 1, recommend ≥ 10 per class)")
        print(f"  Validation images: {n_val}  (need ≥ 1, recommend ≥ 5 per class)")
        print("\n  What to do next:")
        print("  1. Add your images to data/images/train/ and data/images/val/")
        print("     OR use: python scripts/add_images.py --source <folder> --species <name>")
        print("  2. Add matching YOLO .txt labels to data/labels/train/ and data/labels/val/")
        print("  3. Run: python scripts/validate_dataset.py")
        print("  4. Then: python scripts/train.py")
        print("=" * 60)
        sys.exit(1)

    print(f"\n  Dataset ready: {n_train} train image(s), {n_val} val image(s).")
    if n_train < 10:
        print(
            f"  ⚠  Very few training images ({n_train}). "
            "Augmentation is aggressive — training will still run, "
            "but accuracy may be limited."
        )


# ──────────────────────────────────────────────────────────────────
# Training
# ──────────────────────────────────────────────────────────────────

def run_training(args: argparse.Namespace) -> None:
    """Configure and launch YOLO training."""
    try:
        from ultralytics import YOLO
    except ImportError:
        print("\n[ERROR] Ultralytics is not installed.")
        print("  Install with: pip install ultralytics")
        sys.exit(1)

    cfg = load_config(args.config)
    _check_dataset_ready(cfg)

    t_cfg = cfg.get("training", {})
    m_cfg = cfg.get("model", {})
    aug_cfg = cfg.get("augmentation", {})

    # ── Resolve parameters (CLI overrides config file) ──────────
    checkpoint    = args.resume or m_cfg.get("pretrained_checkpoint", "yolov8s.pt")
    epochs        = args.epochs or t_cfg.get("epochs", 150)
    batch         = args.batch  or t_cfg.get("batch_size", 8)
    imgsz         = args.imgsz  or t_cfg.get("imgsz", 640)
    device        = args.device or t_cfg.get("device", "cpu")
    workers       = t_cfg.get("workers", 2)
    patience      = t_cfg.get("patience", 30)
    optimizer     = t_cfg.get("optimizer", "AdamW")
    lr0           = t_cfg.get("lr0", 0.001)
    lrf           = t_cfg.get("lrf", 0.01)
    weight_decay  = t_cfg.get("weight_decay", 0.0005)
    warmup_epochs = t_cfg.get("warmup_epochs", 5)
    cos_lr        = t_cfg.get("cos_lr", True)
    save_period   = t_cfg.get("save_period", 10)
    close_mosaic  = t_cfg.get("close_mosaic", 20)  # disable mosaic in last N epochs

    dataset_yaml = Path(cfg["paths"]["dataset_yaml"])
    runs_dir = Path(cfg["paths"]["runs_dir"]) / "train"
    run_name = datetime.now().strftime("exp_%Y%m%d_%H%M%S")

    print("\n" + "=" * 60)
    print("  WESTERN GHATS ANIMAL DETECTION — TRAINING")
    print("=" * 60)
    print(f"  Checkpoint   : {checkpoint}")
    print(f"  Dataset YAML : {dataset_yaml}")
    print(f"  Classes ({len(get_class_names(cfg))}) : {get_class_names(cfg)}")
    print(f"  Epochs       : {epochs}")
    print(f"  Batch size   : {batch}")
    print(f"  Image size   : {imgsz}")
    print(f"  Device       : {device}")
    print(f"  Patience     : {patience}")
    print(f"  Close mosaic : last {close_mosaic} epochs")
    print(f"  Run name     : {run_name}")
    print("=" * 60)

    if args.resume:
        print(f"\n  Resuming training from: {args.resume}")

    model = YOLO(checkpoint)

    results = model.train(
        data=str(dataset_yaml),
        epochs=epochs,
        batch=batch,
        imgsz=imgsz,
        device=device,
        workers=workers,
        patience=patience,
        optimizer=optimizer,
        lr0=lr0,
        lrf=lrf,
        weight_decay=weight_decay,
        warmup_epochs=warmup_epochs,
        cos_lr=cos_lr,
        save_period=save_period,
        close_mosaic=close_mosaic,
        project=str(runs_dir),
        name=run_name,
        exist_ok=False,
        # Augmentation parameters (aggressive for small datasets)
        hsv_h=aug_cfg.get("hsv_h", 0.02),
        hsv_s=aug_cfg.get("hsv_s", 0.8),
        hsv_v=aug_cfg.get("hsv_v", 0.5),
        degrees=aug_cfg.get("degrees", 15.0),
        translate=aug_cfg.get("translate", 0.15),
        scale=aug_cfg.get("scale", 0.6),
        shear=aug_cfg.get("shear", 2.0),
        perspective=aug_cfg.get("perspective", 0.0005),
        flipud=aug_cfg.get("flipud", 0.1),
        fliplr=aug_cfg.get("fliplr", 0.5),
        mosaic=aug_cfg.get("mosaic", 1.0),
        mixup=aug_cfg.get("mixup", 0.1),
        copy_paste=aug_cfg.get("copy_paste", 0.1),
        verbose=True,
    )

    best_weights = runs_dir / run_name / "weights" / "best.pt"
    print("\n" + "=" * 60)
    print("  TRAINING COMPLETE")
    print("=" * 60)
    if best_weights.exists():
        print(f"\n  ✓ Best weights: {best_weights}")
        print("\n  NEXT STEPS:")
        print("  1. Update config/settings.yaml → model.trained_checkpoint:")
        print(f"       trained_checkpoint: \"{best_weights}\"")
        print("  2. Evaluate:")
        print("       python scripts/evaluate.py")
        print("  3. Launch app:")
        print("       streamlit run app/app.py")
        print("  4. Add more images later:")
        print("       python scripts/add_images.py --source <folder> --species <name>")
        print("       python scripts/train.py --resume", best_weights.with_name("last.pt"))
    else:
        print("\n  [WARNING] best.pt not found — check the runs/ directory.")
    print("=" * 60)


# ──────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Train YOLO on the animal detection dataset.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config" / "settings.yaml"))
    parser.add_argument("--epochs", type=int, default=None, help="Number of training epochs.")
    parser.add_argument("--batch", type=int, default=None, help="Batch size.")
    parser.add_argument("--imgsz", type=int, default=None, help="Training image size (pixels).")
    parser.add_argument("--device", default=None, help="Device: 'cpu', '0', '0,1', etc.")
    parser.add_argument(
        "--resume",
        default=None,
        metavar="WEIGHTS",
        help="Resume training from a checkpoint (e.g., runs/train/exp.../weights/last.pt).",
    )
    args = parser.parse_args()
    run_training(args)


if __name__ == "__main__":
    main()
