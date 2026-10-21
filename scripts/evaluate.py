# ============================================================
# scripts/evaluate.py
# Model evaluation script for the Animal Detection project.
#
# Reports: precision, recall, mAP@0.5, mAP@0.5:0.95
# per class and overall.  Generates confusion matrix and
# PR curves if supported by the installed Ultralytics version.
#
# NOTE:
#   - A labelled test split (data/images/test/ + data/labels/test/)
#     is required to run meaningful evaluation.
#   - Results are never fabricated — this script only reports
#     metrics from images it actually processes.
#   - FPS figures are hardware-specific. The report will state
#     which device was used.
#
# Usage:
#   python scripts/evaluate.py
#   python scripts/evaluate.py --split val
#   python scripts/evaluate.py --weights runs/train/exp.../weights/best.pt
# ============================================================

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_config, get_class_names, is_trained_model_available


def _check_split_images(cfg: dict, split: str) -> int:
    """Return number of images in the requested split, or 0 if missing."""
    images_dir = Path(cfg["paths"]["images_dir"]) / split
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    if not images_dir.exists():
        return 0
    return sum(1 for p in images_dir.iterdir() if p.suffix.lower() in exts)


def run_evaluation(args: argparse.Namespace) -> None:
    """Run model validation and save evaluation results."""
    try:
        from ultralytics import YOLO
    except ImportError:
        print("\n[ERROR] Ultralytics is not installed.")
        print("  Install with: pip install ultralytics")
        sys.exit(1)

    cfg = load_config(args.config)

    # ── Determine weights ────────────────────────────────────────
    weights = args.weights
    if not weights:
        if not is_trained_model_available(cfg):
            print("\n" + "=" * 60)
            print("  EVALUATION CANNOT PROCEED — NO TRAINED MODEL")
            print("=" * 60)
            print(
                "\n  No user-trained model checkpoint was found.\n"
                "\n  You need to:"
                "\n  1. Add labelled images and run:  python scripts/train.py"
                "\n  2. Then set config/settings.yaml → model.trained_checkpoint"
                "\n     to the path of your best.pt file."
                "\n  3. Re-run:  python scripts/evaluate.py"
                "\n\n  A generic pretrained model (e.g. yolov8n.pt) cannot be"
                "\n  evaluated on your species dataset because it was not trained"
                "\n  on your class labels."
            )
            print("=" * 60)
            sys.exit(1)
        weights = cfg["model"]["trained_checkpoint"]

    weights_path = Path(weights)
    if not weights_path.is_file():
        print(f"\n[ERROR] Weights file not found: {weights_path}")
        sys.exit(1)

    split = args.split
    n_images = _check_split_images(cfg, split)
    if n_images == 0:
        print(f"\n[ERROR] No images found in data/images/{split}/")
        print(f"  Please add labelled '{split}' images before evaluating.")
        sys.exit(1)

    dataset_yaml = Path(cfg["paths"]["dataset_yaml"])
    device = args.device or cfg.get("training", {}).get("device", "cpu")
    imgsz = args.imgsz or cfg.get("model", {}).get("imgsz", 640)
    results_dir = Path(cfg["paths"]["results_dir"]) / "eval"
    results_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("  ANIMAL DETECTION — MODEL EVALUATION")
    print("=" * 60)
    print(f"  Weights      : {weights_path}")
    print(f"  Dataset YAML : {dataset_yaml}")
    print(f"  Split        : {split}  ({n_images} images)")
    print(f"  Classes      : {get_class_names(cfg)}")
    print(f"  Device       : {device}")
    print(f"  Image size   : {imgsz}")
    print("=" * 60)

    model = YOLO(str(weights_path))

    eval_cfg = cfg.get("evaluation", {})
    metrics = model.val(
        data=str(dataset_yaml),
        split=split,
        device=device,
        imgsz=imgsz,
        save_json=eval_cfg.get("save_json", True),
        save_txt=eval_cfg.get("save_txt", True),
        plots=eval_cfg.get("plots", True),
        verbose=True,
    )

    # ── Extract and display key metrics ─────────────────────────
    try:
        results_dict = metrics.results_dict
        mp = results_dict.get("metrics/precision(B)", float("nan"))
        mr = results_dict.get("metrics/recall(B)", float("nan"))
        map50 = results_dict.get("metrics/mAP50(B)", float("nan"))
        map5095 = results_dict.get("metrics/mAP50-95(B)", float("nan"))

        print("\n" + "=" * 60)
        print("  EVALUATION RESULTS")
        print("=" * 60)
        print(f"  Precision  (mP)      : {mp:.4f}")
        print(f"  Recall     (mR)      : {mr:.4f}")
        print(f"  mAP @ 0.5            : {map50:.4f}")
        print(f"  mAP @ 0.5:0.95       : {map5095:.4f}")
        print(f"\n  Device used          : {device}")
        print(
            "\n  NOTE: mAP@0.5 and mAP@0.5:0.95 are the standard object-detection"
            "\n  metrics. Pixel-classification accuracy is NOT reported here because"
            "\n  it is not meaningful for bounding-box detection tasks."
        )
        print(
            "\n  LIMITATIONS TO DOCUMENT:"
            "\n  - Class imbalance may inflate per-class metrics for majority classes."
            "\n  - Small or distant animals may have lower recall."
            "\n  - Performance on camera footage may differ from training photos."
            "\n  - Low-light or motion-blurred images may cause false positives."
        )
        print("=" * 60)

        # Save results to JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_file = results_dir / f"eval_{split}_{timestamp}.json"
        save_data = {
            "timestamp": timestamp,
            "weights": str(weights_path),
            "split": split,
            "device": device,
            "imgsz": imgsz,
            "n_images": n_images,
            "metrics": {
                "precision": round(mp, 6),
                "recall": round(mr, 6),
                "mAP50": round(map50, 6),
                "mAP50-95": round(map5095, 6),
            },
        }
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(save_data, f, indent=2)
        print(f"\n  Results saved to: {out_file}")

    except Exception as exc:
        print(f"\n[WARNING] Could not extract structured metrics: {exc}")
        print("  Check the Ultralytics val/ output directory for plots and results.csv.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a trained YOLO model.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config" / "settings.yaml"))
    parser.add_argument("--weights", default=None, help="Path to .pt weights file.")
    parser.add_argument("--split", choices=["val", "test"], default="test",
                        help="Which split to evaluate on (default: test).")
    parser.add_argument("--device", default=None)
    parser.add_argument("--imgsz", type=int, default=None)
    args = parser.parse_args()
    run_evaluation(args)


if __name__ == "__main__":
    main()
