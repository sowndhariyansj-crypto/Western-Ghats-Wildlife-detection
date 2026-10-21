# ============================================================
# scripts/check_dataset.py
# Comprehensive dataset quality-check script.
#
# Based on the dataset plan outlined in the project guide.
# Run this BEFORE training and AFTER any structural changes.
#
# Checks performed:
#   1. Image readability (corrupt files)
#   2. Exact duplicate detection (MD5 hash)
#   3. Cross-split exact-duplicate leakage (same hash in train + val/test)
#   4. Near-duplicate detection (perceptual hash, optional)
#   5. Missing label files
#   6. Label format errors (line count, numeric values)
#   7. Class ID range validation
#   8. Bounding-box coordinate range validation
#   9. Instance counts per class (empty-class detection)
#  10. metadata.csv coverage (every image has a metadata row)
#
# Usage:
#   python scripts/check_dataset.py
#   python scripts/check_dataset.py --near-dup-threshold 8
#   python scripts/check_dataset.py --no-near-dup   (skip perceptual hashing)
#   python scripts/check_dataset.py --verbose
# ============================================================

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import sys
from pathlib import Path
from typing import NamedTuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_config, get_class_names

# ──────────────────────────────────────────────────────────────────
# Optional imports
# ──────────────────────────────────────────────────────────────────

try:
    from PIL import Image as PILImage
    _PIL_OK = True
except ImportError:
    _PIL_OK = False
    print("[WARNING] Pillow not installed — corrupt-image check disabled. pip install Pillow")

try:
    import imagehash
    _HASH_OK = True
except ImportError:
    _HASH_OK = False
    # Not a hard error; near-dup check will be skipped with a warning.

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SPLITS = ["train", "val", "test"]


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def _md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _phash(path: Path) -> str | None:
    """Return perceptual hash string, or None on error."""
    if not _HASH_OK or not _PIL_OK:
        return None
    try:
        with PILImage.open(path) as img:
            return str(imagehash.phash(img))
    except Exception:
        return None


def _is_corrupt(path: Path) -> bool:
    if not _PIL_OK:
        return False
    try:
        with PILImage.open(path) as img:
            img.verify()
        with PILImage.open(path) as img:
            img.load()
        return False
    except Exception:
        return True


def _validate_label(path: Path, num_classes: int) -> list[str]:
    """Return list of error strings for a label file."""
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
    except Exception as exc:
        return [f"Cannot read {path.name}: {exc}"]
    for i, raw in enumerate(lines, 1):
        parts = raw.strip().split()
        if len(parts) != 5:
            errors.append(f"  {path.name}:{i} — expected 5 values, got {len(parts)}: '{raw}'")
            continue
        try:
            cls = int(parts[0])
            coords = [float(v) for v in parts[1:]]
        except ValueError:
            errors.append(f"  {path.name}:{i} — non-numeric: '{raw}'")
            continue
        if not (0 <= cls < num_classes):
            errors.append(f"  {path.name}:{i} — class_id {cls} out of range [0,{num_classes-1}]")
        if any(not (0.0 <= v <= 1.0) for v in coords):
            errors.append(f"  {path.name}:{i} — coords out of [0,1]: {coords}")
        if coords[2] <= 0 or coords[3] <= 0:
            errors.append(f"  {path.name}:{i} — zero/negative width or height")
    return errors


# ──────────────────────────────────────────────────────────────────
# Metadata coverage check
# ──────────────────────────────────────────────────────────────────

def _load_metadata_filenames(metadata_path: Path) -> set[str]:
    """Return set of filenames recorded in metadata.csv."""
    if not metadata_path.exists():
        return set()
    recorded: set[str] = set()
    try:
        with open(metadata_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                fn = (row.get("filename") or "").strip()
                if fn and not fn.startswith("#"):
                    recorded.add(fn)
    except Exception:
        pass
    return recorded


# ──────────────────────────────────────────────────────────────────
# Main check
# ──────────────────────────────────────────────────────────────────

def run_checks(
    data_dir: Path,
    num_classes: int,
    class_names: list[str],
    near_dup_threshold: int,
    skip_near_dup: bool,
    verbose: bool,
) -> bool:
    """Run all checks. Returns True if no blocking issues were found."""

    images_root = data_dir / "images"
    labels_root = data_dir / "labels"
    metadata_path = data_dir / "metadata.csv"

    # ── Collect all images ───────────────────────────────────────
    all_images: dict[str, list[Path]] = {}   # split → paths
    for split in SPLITS:
        d = images_root / split
        if d.exists():
            all_images[split] = sorted(
                p for p in d.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS
            )
        else:
            all_images[split] = []

    total_images = sum(len(v) for v in all_images.values())
    print(f"\n  Total images found  : {total_images}")
    for s, imgs in all_images.items():
        print(f"    {s:<8}: {len(imgs)}")

    if total_images == 0:
        print("\n  [SKIP] No images to check. Add images to data/images/<split>/")
        return True

    # ── Metadata coverage ────────────────────────────────────────
    print(f"\n{'─'*60}")
    print("  CHECK 1: Metadata coverage")
    recorded_filenames = _load_metadata_filenames(metadata_path)
    if not recorded_filenames:
        print("  ⚠  metadata.csv is empty or missing.")
        print("     Fill it in for every image you download (see column guide in the file).")
    else:
        not_in_meta: list[str] = []
        for split, imgs in all_images.items():
            for img in imgs:
                if img.name not in recorded_filenames:
                    not_in_meta.append(f"{split}/{img.name}")
        if not_in_meta:
            print(f"  ✗ {len(not_in_meta)} image(s) not in metadata.csv:")
            if verbose:
                for f in not_in_meta[:20]:
                    print(f"      {f}")
                if len(not_in_meta) > 20:
                    print(f"      ... and {len(not_in_meta)-20} more")
        else:
            print(f"  ✓ All {total_images} images have a metadata row.")

    # ── Corruption + MD5 duplicate + label checks ────────────────
    print(f"\n{'─'*60}")
    print("  CHECK 2–5: Corruption, duplicates, labels")

    md5_map: dict[str, tuple[str, Path]] = {}   # hash → (split, path)
    phash_map: dict[str, list[tuple[str, Path]]] = collections.defaultdict(list)
    corrupt: list[str] = []
    exact_dups: list[str] = []
    cross_split_leaks: list[str] = []
    missing_labels: list[str] = []
    label_errors: list[str] = []
    instance_counts: collections.Counter = collections.Counter()

    for split, imgs in all_images.items():
        for img in imgs:
            # Corruption
            if _is_corrupt(img):
                corrupt.append(f"{split}/{img.name}")
                continue

            # MD5
            h = _md5(img)
            if h in md5_map:
                prev_split, prev_path = md5_map[h]
                msg = f"{split}/{img.name}  ==  {prev_split}/{prev_path.name}"
                if prev_split != split:
                    cross_split_leaks.append(msg)
                else:
                    exact_dups.append(msg)
            else:
                md5_map[h] = (split, img)

            # Perceptual hash
            if not skip_near_dup:
                ph = _phash(img)
                if ph is not None:
                    phash_map[ph].append((split, img))

            # Label
            lbl = labels_root / split / (img.stem + ".txt")
            if not lbl.exists():
                missing_labels.append(f"{split}/{img.name}")
            else:
                errs = _validate_label(lbl, num_classes)
                label_errors.extend(errs)
                # Count instances
                for line in lbl.read_text(encoding="utf-8").strip().splitlines():
                    parts = line.strip().split()
                    if len(parts) == 5:
                        try:
                            instance_counts[int(parts[0])] += 1
                        except ValueError:
                            pass

    # Perceptual near-dup analysis
    near_dup_groups: list[list[tuple[str, Path]]] = []
    cross_near_dup: list[str] = []
    if not skip_near_dup and _HASH_OK:
        for ph, group in phash_map.items():
            if len(group) > 1:
                splits_in_group = {s for s, _ in group}
                if len(splits_in_group) > 1:
                    cross_near_dup.append(
                        "  " + "  |  ".join(f"{s}/{p.name}" for s, p in group)
                    )
                else:
                    near_dup_groups.append(group)

    # ── Print results ────────────────────────────────────────────
    def _report(label: str, items: list[str], *, is_error: bool = True) -> None:
        mark = "✗" if is_error and items else ("⚠" if items else "✓")
        print(f"\n  {mark} {label}: {len(items)}")
        if verbose and items:
            for item in items[:20]:
                print(f"      {item}")
            if len(items) > 20:
                print(f"      ... and {len(items)-20} more (use --verbose to see all)")

    _report("Corrupt images", corrupt)
    _report("Exact duplicates (within same split)", exact_dups, is_error=False)
    _report("Cross-split exact duplicates (LEAKAGE)", cross_split_leaks)
    _report("Images missing label files", missing_labels)
    _report("Label format errors", label_errors)

    if not skip_near_dup:
        if not _HASH_OK:
            print(
                "\n  ⚠  Near-duplicate check skipped: imagehash not installed.\n"
                "     pip install imagehash   (then re-run)"
            )
        else:
            _report(
                "Near-duplicate groups (within same split, review manually)",
                [
                    "  " + "  |  ".join(f"{s}/{p.name}" for s, p in g)
                    for g in near_dup_groups
                ],
                is_error=False,
            )
            _report(
                "Near-duplicate cross-split groups (POTENTIAL LEAKAGE — review manually)",
                cross_near_dup,
            )

    # ── Class distribution ───────────────────────────────────────
    print(f"\n{'─'*60}")
    print("  CHECK 6: Instance counts per class")
    empty_classes: list[str] = []
    for cls_id, name in enumerate(class_names):
        count = instance_counts.get(cls_id, 0)
        bar = "█" * min(count // 10, 40)
        status = "✓" if count > 0 else "✗ EMPTY"
        print(f"    [{cls_id}] {name:<30} {count:>5} boxes  {bar}  {status}")
        if count == 0:
            empty_classes.append(name)

    unlabelled_ids = [k for k in instance_counts if k >= len(class_names)]
    if unlabelled_ids:
        print(f"\n  ✗ Labels reference class IDs not in dataset.yaml: {unlabelled_ids}")

    # ── Summary ──────────────────────────────────────────────────
    print(f"\n{'='*60}")
    blocking = bool(
        corrupt or cross_split_leaks or label_errors or empty_classes or unlabelled_ids
    )
    if blocking:
        print("  RESULT: Blocking issues found — fix them before training.")
    else:
        print("  RESULT: No blocking issues found.")
    print(f"{'='*60}")

    if missing_labels:
        print(
            f"\n  NOTE: {len(missing_labels)} image(s) have no label file.\n"
            "  If these are background (no-animal) examples, that is intentional.\n"
            "  Keep background images to ≤ 5–10 % of the training set."
        )

    return not blocking


# ──────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Comprehensive dataset quality check (corruption, duplicates, labels, class balance)."
    )
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config" / "settings.yaml"))
    parser.add_argument(
        "--near-dup-threshold", type=int, default=8, metavar="BITS",
        help="Max Hamming distance to flag two images as near-duplicates (default: 8).",
    )
    parser.add_argument(
        "--no-near-dup", action="store_true",
        help="Skip the perceptual-hash near-duplicate check (faster, but misses near-dups).",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    from src.config import load_config, get_class_names
    cfg = load_config(args.config)
    class_names = get_class_names(cfg)
    data_dir = Path(cfg["paths"]["data_dir"])

    print("=" * 60)
    print("  DATASET QUALITY CHECK")
    print("=" * 60)
    print(f"  Dataset root : {data_dir}")
    print(f"  Classes ({len(class_names)}): {class_names}")
    if args.no_near_dup:
        print("  Near-dup check: DISABLED (--no-near-dup)")
    elif not _HASH_OK:
        print("  Near-dup check: DISABLED (imagehash not installed)")
    else:
        print(f"  Near-dup check: ENABLED (threshold = {args.near_dup_threshold} bits)")

    ok = run_checks(
        data_dir=data_dir,
        num_classes=len(class_names),
        class_names=class_names,
        near_dup_threshold=args.near_dup_threshold,
        skip_near_dup=args.no_near_dup,
        verbose=args.verbose,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
