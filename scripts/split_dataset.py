# ============================================================
# scripts/split_dataset.py
# Assign images to train / val / test splits correctly.
#
# KEY RULE (anti-leakage):
#   Images must be grouped by observation_id (or photographer)
#   and ENTIRE GROUPS assigned to a single split.
#   Burst shots from the same session must NEVER straddle splits.
#
# This script reads metadata.csv (which must have an
# observation_id column), groups by observation_id, shuffles
# groups, then assigns:
#   70% of groups → train
#   20% of groups → val
#   10% of groups → test
#
# It MOVES images and labels into the correct subfolders and
# updates the 'split' column in metadata.csv.
#
# Usage:
#   # Dry-run (just show what would be moved):
#   python scripts/split_dataset.py --dry-run
#
#   # Execute the split:
#   python scripts/split_dataset.py
#
#   # Custom ratios:
#   python scripts/split_dataset.py --train 0.75 --val 0.15 --test 0.10
#
# IMPORTANT:
#   Run this ONCE after collecting all images.
#   Re-running after partial training will change splits, which
#   invalidates comparisons. If you add images later, add them
#   only to the training split or run a fresh split on all data.
# ============================================================

from __future__ import annotations

import argparse
import collections
import csv
import os
import random
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_config

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _load_metadata(metadata_path: Path) -> list[dict[str, str]]:
    """Load metadata.csv rows that are not comments or headers."""
    rows = []
    with open(metadata_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            fn = (row.get("filename") or "").strip()
            if fn and not fn.startswith("#"):
                rows.append(row)
    return rows


def _save_metadata(metadata_path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(metadata_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_split(
    cfg: dict,
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    seed: int,
    dry_run: bool,
) -> None:
    data_dir = Path(cfg["paths"]["data_dir"])
    images_root = Path(cfg["paths"]["images_dir"])
    labels_root = Path(cfg["paths"]["labels_dir"])
    metadata_path = data_dir / "metadata.csv"

    if not metadata_path.exists():
        print("\n[ERROR] metadata.csv not found.")
        print("  Fill it in for every image you download, then re-run this script.")
        sys.exit(1)

    rows = _load_metadata(metadata_path)
    if not rows:
        print("\n[ERROR] metadata.csv has no data rows.")
        sys.exit(1)

    # ── Group by observation_id (fall back to photographer if missing) ──
    groups: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    for row in rows:
        obs_id = (row.get("observation_id") or "").strip()
        photographer = (row.get("photographer") or "").strip()
        group_key = obs_id if obs_id else (photographer if photographer else row["filename"])
        groups[group_key].append(row)

    group_keys = sorted(groups.keys())
    random.seed(seed)
    random.shuffle(group_keys)

    n = len(group_keys)
    n_train = max(1, round(n * train_ratio))
    n_val   = max(1, round(n * val_ratio))
    n_test  = max(0, n - n_train - n_val)

    split_map: dict[str, str] = {}  # filename → split
    for i, key in enumerate(group_keys):
        if i < n_train:
            sp = "train"
        elif i < n_train + n_val:
            sp = "val"
        else:
            sp = "test"
        for row in groups[key]:
            split_map[row["filename"]] = sp

    print(f"\n{'='*60}")
    print("  DATASET SPLIT PLAN")
    print(f"{'='*60}")
    print(f"  Total observation groups : {n}")
    print(f"  Train groups             : {n_train}  ({train_ratio:.0%})")
    print(f"  Val groups               : {n_val}    ({val_ratio:.0%})")
    print(f"  Test groups              : {n_test}   ({test_ratio:.0%})")
    print(f"  Seed                     : {seed}")
    if dry_run:
        print("\n  DRY-RUN MODE — no files will be moved.")

    # ── Move files ───────────────────────────────────────────────
    move_log: list[str] = []
    errors: list[str] = []

    for filename, split in split_map.items():
        # Locate the image (could be in any existing split folder or root)
        src_img: Path | None = None
        search_dirs = [images_root] + [images_root / s for s in ["train", "val", "test", "unassigned"]]
        for d in search_dirs:
            candidate = d / filename
            if candidate.is_file():
                src_img = candidate
                break

        if src_img is None:
            errors.append(f"  Image not found: {filename}")
            continue

        dst_img = images_root / split / filename
        dst_lbl = labels_root / split / (Path(filename).stem + ".txt")

        # Source label
        src_lbl = labels_root / src_img.parent.name / (src_img.stem + ".txt")
        if not src_lbl.exists():
            # Try same directory as image
            src_lbl_alt = src_img.parent.parent.parent / "labels" / src_img.parent.name / (src_img.stem + ".txt")
            if not src_lbl_alt.exists():
                src_lbl = None  # background image — label intentionally absent
            else:
                src_lbl = src_lbl_alt

        move_log.append(f"  {src_img}  →  {dst_img}")
        if src_lbl:
            move_log.append(f"  {src_lbl}  →  {dst_lbl}")

        if not dry_run:
            dst_img.parent.mkdir(parents=True, exist_ok=True)
            dst_lbl.parent.mkdir(parents=True, exist_ok=True)
            if src_img != dst_img:
                shutil.move(str(src_img), str(dst_img))
            if src_lbl and src_lbl != dst_lbl:
                shutil.move(str(src_lbl), str(dst_lbl))

    # Print log
    if move_log:
        print(f"\n  Files to move ({len(split_map)}):")
        for line in move_log[:40]:
            print(line)
        if len(move_log) > 40:
            print(f"  ... and {len(move_log)-40} more")

    if errors:
        print(f"\n  WARNINGS ({len(errors)} files not found):")
        for e in errors:
            print(e)

    # ── Update metadata.csv ──────────────────────────────────────
    if not dry_run:
        for row in rows:
            row["split"] = split_map.get(row["filename"], row.get("split", "unassigned"))
        _save_metadata(metadata_path, rows)
        print(f"\n  ✓ metadata.csv updated with split assignments.")

    print(f"\n{'='*60}")
    if dry_run:
        print("  Dry-run complete. Re-run without --dry-run to apply.")
    else:
        print("  Split complete. Run: python scripts/check_dataset.py")
    print("="*60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Assign images to train/val/test splits grouped by observation_id."
    )
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config" / "settings.yaml"))
    parser.add_argument("--train", type=float, default=0.70, help="Train ratio (default 0.70).")
    parser.add_argument("--val",   type=float, default=0.20, help="Val ratio (default 0.20).")
    parser.add_argument("--test",  type=float, default=0.10, help="Test ratio (default 0.10).")
    parser.add_argument("--seed",  type=int,   default=42)
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be moved without actually moving files.")
    args = parser.parse_args()

    total = args.train + args.val + args.test
    if abs(total - 1.0) > 0.001:
        print(f"[ERROR] Ratios must sum to 1.0, got {total:.3f}")
        sys.exit(1)

    cfg = load_config(args.config)
    run_split(cfg, args.train, args.val, args.test, args.seed, args.dry_run)


if __name__ == "__main__":
    main()
