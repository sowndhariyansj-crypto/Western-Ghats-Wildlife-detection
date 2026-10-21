# ============================================================
# scripts/validate_dataset.py
# Dataset validation script for the Animal Detection project.
#
# Checks:
#   - Image readability (not corrupt)
#   - Matching label files
#   - YOLO label format (5 values per line, class_id in range,
#     bbox coords in [0, 1])
#   - Missing labels and images without labels
#   - Class ID distribution (class counts per split)
#   - Summary report
#
# Usage:
#   python scripts/validate_dataset.py
#   python scripts/validate_dataset.py --split train
#   python scripts/validate_dataset.py --split val --verbose
# ============================================================

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import NamedTuple

# --------------- ensure project root is on sys.path ---------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Safe Windows stdout encoding
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.config import load_config, get_class_names

# Try importing PIL for image validation; fall back gracefully.
try:
    from PIL import Image as PILImage
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


# ──────────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────────

class ValidationResult(NamedTuple):
    split: str
    total_images: int
    valid_images: int
    corrupt_images: list[str]
    images_missing_labels: list[str]
    labels_missing_images: list[str]
    invalid_label_lines: list[str]     # formatted error strings
    class_counts: dict[int, int]       # class_id → count of bounding boxes
    warnings: list[str]


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _collect_images(images_dir: Path) -> list[Path]:
    """Return all image files under images_dir (non-recursive for one split)."""
    return [p for p in images_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS]


def _label_path_for_image(image_path: Path, labels_dir: Path) -> Path:
    """Return the expected label .txt path for a given image."""
    return labels_dir / image_path.with_suffix(".txt").name


def _check_image(image_path: Path) -> bool:
    """Return True if the image can be opened and is not corrupt."""
    if not _PIL_AVAILABLE:
        # Cannot validate without PIL; assume OK but warn.
        return True
    try:
        with PILImage.open(image_path) as img:
            img.verify()          # checks headers
        # Re-open to load pixel data (verify() leaves file in unknown state)
        with PILImage.open(image_path) as img:
            img.load()
        return True
    except Exception:
        return False


def _validate_label_file(
    label_path: Path,
    num_classes: int,
    verbose: bool = False,
) -> tuple[list[str], dict[int, int]]:
    """Validate a single YOLO label file.

    Returns:
        errors: list of human-readable error strings
        class_counts: dict mapping class_id → number of boxes
    """
    errors: list[str] = []
    class_counts: dict[int, int] = {}

    try:
        lines = label_path.read_text(encoding="utf-8").strip().splitlines()
    except Exception as exc:
        return [f"  ✗ Cannot read {label_path.name}: {exc}"], {}

    if not lines:
        return [], {}  # Empty label file = background / no animals (allowed)

    for line_no, raw_line in enumerate(lines, start=1):
        parts = raw_line.strip().split()

        if len(parts) != 5:
            errors.append(
                f"  ✗ {label_path.name}:{line_no} — expected 5 values, got {len(parts)}: '{raw_line}'"
            )
            continue

        try:
            class_id = int(parts[0])
            x_c, y_c, w, h = (float(v) for v in parts[1:])
        except ValueError:
            errors.append(
                f"  ✗ {label_path.name}:{line_no} — non-numeric value: '{raw_line}'"
            )
            continue

        if class_id < 0 or class_id >= num_classes:
            errors.append(
                f"  ✗ {label_path.name}:{line_no} — class_id {class_id} out of range "
                f"[0, {num_classes - 1}] (dataset.yaml defines {num_classes} class(es))"
            )

        for name, val in [("x_center", x_c), ("y_center", y_c), ("width", w), ("height", h)]:
            if not (0.0 <= val <= 1.0):
                errors.append(
                    f"  ✗ {label_path.name}:{line_no} — {name}={val:.4f} is outside [0, 1]"
                )

        if w <= 0 or h <= 0:
            errors.append(
                f"  ✗ {label_path.name}:{line_no} — width or height is zero/negative: w={w}, h={h}"
            )

        class_counts[class_id] = class_counts.get(class_id, 0) + 1

    return errors, class_counts


# ──────────────────────────────────────────────────────────────────
# Main validation logic
# ──────────────────────────────────────────────────────────────────

def validate_split(
    split: str,
    images_dir: Path,
    labels_dir: Path,
    num_classes: int,
    verbose: bool = False,
) -> ValidationResult:
    """Run all validation checks on one dataset split.

    Args:
        split: Name of the split ("train", "val", or "test").
        images_dir: Path to images/<split>/.
        labels_dir: Path to labels/<split>/.
        num_classes: Number of classes defined in dataset.yaml.
        verbose: If True, print individual file errors.

    Returns:
        A ValidationResult summary.
    """
    if not images_dir.exists():
        print(f"  [SKIP] Images directory does not exist: {images_dir}")
        return ValidationResult(
            split=split,
            total_images=0,
            valid_images=0,
            corrupt_images=[],
            images_missing_labels=[],
            labels_missing_images=[],
            invalid_label_lines=[],
            class_counts={},
            warnings=[f"Images directory not found: {images_dir}"],
        )

    image_files = _collect_images(images_dir)
    if not image_files:
        print(f"  [SKIP] No images found in: {images_dir}")
        return ValidationResult(
            split=split,
            total_images=0,
            valid_images=0,
            corrupt_images=[],
            images_missing_labels=[],
            labels_missing_images=[],
            invalid_label_lines=[],
            class_counts={},
            warnings=[f"No images found in: {images_dir}"],
        )

    corrupt_images: list[str] = []
    images_missing_labels: list[str] = []
    all_label_errors: list[str] = []
    aggregate_class_counts: dict[int, int] = {}
    valid_images = 0

    for img_path in sorted(image_files):
        # --- Image integrity ---
        if not _check_image(img_path):
            corrupt_images.append(img_path.name)
            continue
        valid_images += 1

        # --- Matching label file ---
        lbl_path = _label_path_for_image(img_path, labels_dir)
        if not lbl_path.exists():
            images_missing_labels.append(img_path.name)
            continue

        # --- Label format ---
        errors, counts = _validate_label_file(lbl_path, num_classes, verbose)
        all_label_errors.extend(errors)
        for cls_id, cnt in counts.items():
            aggregate_class_counts[cls_id] = aggregate_class_counts.get(cls_id, 0) + cnt

    # --- Labels without images ---
    if labels_dir.exists():
        label_files = list(labels_dir.glob("*.txt"))
        image_stems = {p.stem for p in image_files}
        labels_missing_images = [
            lf.name for lf in label_files if lf.stem not in image_stems
        ]
    else:
        labels_missing_images = []

    # --- Warnings ---
    warnings: list[str] = []
    if not _PIL_AVAILABLE:
        warnings.append(
            "Pillow is not installed — image corruption checks were skipped. "
            "Install with: pip install Pillow"
        )

    return ValidationResult(
        split=split,
        total_images=len(image_files),
        valid_images=valid_images,
        corrupt_images=corrupt_images,
        images_missing_labels=images_missing_labels,
        labels_missing_images=labels_missing_images,
        invalid_label_lines=all_label_errors,
        class_counts=aggregate_class_counts,
        warnings=warnings,
    )


def print_result(result: ValidationResult, class_names: list[str], verbose: bool) -> None:
    """Pretty-print a ValidationResult to stdout."""
    split = result.split.upper()
    ok_mark = "[OK]"
    fail_mark = "[FAIL]"
    warn_mark = "[WARN]"

    print(f"\n{'-' * 60}")
    print(f"  SPLIT: {split}")
    print(f"{'-' * 60}")
    print(f"  Total images    : {result.total_images}")
    print(f"  Valid images    : {result.valid_images}")
    print(f"  Corrupt images  : {len(result.corrupt_images)}")
    print(f"  Missing labels  : {len(result.images_missing_labels)}")
    print(f"  Orphan labels   : {len(result.labels_missing_images)}")
    print(f"  Label errors    : {len(result.invalid_label_lines)}")

    if result.class_counts:
        print("\n  Class distribution (bounding boxes):")
        for cls_id, cnt in sorted(result.class_counts.items()):
            name = class_names[cls_id] if cls_id < len(class_names) else f"UNKNOWN_ID_{cls_id}"
            print(f"    [{cls_id}] {name:<30} {cnt:>6} boxes")
    else:
        print("\n  Class distribution : (no labelled boxes found)")

    if result.warnings:
        for w in result.warnings:
            print(f"\n  {warn_mark}  {w}")

    if verbose:
        if result.corrupt_images:
            print("\n  Corrupt images:")
            for f in result.corrupt_images:
                print(f"    {fail_mark} {f}")
        if result.images_missing_labels:
            print("\n  Images missing label files:")
            for f in result.images_missing_labels:
                print(f"    {fail_mark} {f}")
        if result.labels_missing_images:
            print("\n  Label files without matching images:")
            for f in result.labels_missing_images:
                print(f"    {warn_mark}  {f}")
        if result.invalid_label_lines:
            print("\n  Label format errors:")
            for e in result.invalid_label_lines:
                print(e)

    issues = (
        len(result.corrupt_images)
        + len(result.images_missing_labels)
        + len(result.invalid_label_lines)
    )
    status = f"  {ok_mark} No issues found." if issues == 0 else f"  {fail_mark} {issues} issue(s) found."
    print(f"\n{status}")


# ──────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate the animal detection dataset (images + YOLO labels)."
    )
    parser.add_argument(
        "--split",
        choices=["train", "val", "test", "all"],
        default="all",
        help="Which split to validate (default: all).",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print per-file errors in addition to the summary.",
    )
    parser.add_argument(
        "--config",
        default=str(PROJECT_ROOT / "config" / "settings.yaml"),
        help="Path to settings.yaml.",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  ANIMAL DETECTION - DATASET VALIDATION")
    print("=" * 60)

    try:
        cfg = load_config(args.config)
    except FileNotFoundError as exc:
        print(f"\n[ERROR] {exc}")
        sys.exit(1)

    class_names = get_class_names(cfg)
    num_classes = len(class_names)
    data_dir = Path(cfg["paths"]["data_dir"])
    images_root = Path(cfg["paths"]["images_dir"])
    labels_root = Path(cfg["paths"]["labels_dir"])

    print(f"\n  Config           : {args.config}")
    print(f"  Data directory   : {data_dir}")
    print(f"  Number of classes: {num_classes}")
    print(f"  Classes          : {class_names}")

    splits = ["train", "val", "test"] if args.split == "all" else [args.split]

    any_issues = False
    for split in splits:
        result = validate_split(
            split=split,
            images_dir=images_root / split,
            labels_dir=labels_root / split,
            num_classes=num_classes,
            verbose=args.verbose,
        )
        print_result(result, class_names, args.verbose)

        if (
            result.corrupt_images
            or result.images_missing_labels
            or result.invalid_label_lines
        ):
            any_issues = True

    print(f"\n{'=' * 60}")
    if any_issues:
        print("  Overall: Issues detected — fix them before training.")
    elif all(r == 0 for r in [0]):  # placeholder — real check above
        print("  Overall: All checked splits passed validation.")
    else:
        print("  Overall: All checked splits passed validation.")
    print("=" * 60)


if __name__ == "__main__":
    main()
