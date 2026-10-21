# ============================================================
# scripts/add_images.py
# Easy pipeline for adding new images to the dataset.
#
# This script handles the full workflow for adding your own
# photos (taken in the field, downloaded, or collected from
# any source) into the project dataset.
#
# TWO MODES:
#
# MODE 1 — Add already-labelled images (you have .txt labels):
#   python scripts/add_images.py \
#       --source /path/to/my_photos/ \
#       --species nilgiri_tahr \
#       --mode labelled
#
# MODE 2 — Add raw images for later annotation:
#   python scripts/add_images.py \
#       --source /path/to/my_photos/ \
#       --species bengal_tiger \
#       --mode raw
#   (Images are copied to data/raw/<species>/ for annotation)
#
# ADDING IMAGES SAFELY (future use):
#   - New images default to the TRAIN split (safest for small datasets).
#   - Use --split val to add to validation instead.
#   - The script NEVER moves existing images; it only COPIES new ones.
#   - It appends to metadata.csv automatically.
#
# AFTER ADDING IMAGES:
#   1. Run: python scripts/validate_dataset.py
#   2. Retrain: python scripts/train.py
# ============================================================

from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.config import load_config, get_class_names  # noqa: E402

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

CSV_FIELDS = [
    "filename", "species", "scientific_name", "source_site", "source_url",
    "observation_id", "photographer", "license", "attribution_text",
    "date_downloaded", "split", "notes",
]

# Scientific name lookup
SCIENTIFIC_NAMES: dict[str, str] = {
    "nilgiri_tahr":          "Nilgiritragus hylocrius",
    "lion_tailed_macaque":   "Macaca silenus",
    "nilgiri_langur":        "Semnopithecus johnii",
    "malabar_civet":         "Viverra civettina",
    "gaur":                  "Bos gaurus",
    "bengal_tiger":          "Panthera tigris tigris",
    "sloth_bear":            "Melursus ursinus",
    "asian_elephant":        "Elephas maximus",
    "nilgiri_marten":        "Martes gwatkinsii",
    "anaimalai_flying_frog": "Rhacophorus pseudomalabaricus",
}


# ════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════

def _file_md5(path: Path) -> str:
    """Compute MD5 hash of a file for duplicate detection."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_metadata(meta_path: Path) -> list[dict[str, str]]:
    if not meta_path.exists():
        return []
    rows = []
    with open(meta_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            fn = (row.get("filename") or "").strip()
            if fn and not fn.startswith("#"):
                rows.append(row)
    return rows


def _save_metadata(meta_path: Path, rows: list[dict[str, str]]) -> None:
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    with open(meta_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _safe_name(stem: str, species: str, index: int, existing_names: set[str]) -> str:
    """Generate a unique filename like nilgiri_tahr_001.jpg."""
    candidate = f"{species}_{index:04d}"
    while candidate in existing_names:
        index += 1
        candidate = f"{species}_{index:04d}"
    existing_names.add(candidate)
    return candidate


def _collect_images(source: Path) -> list[Path]:
    """Recursively collect all image files from source directory."""
    if source.is_file():
        return [source] if source.suffix.lower() in IMAGE_EXTENSIONS else []
    return [
        p for p in sorted(source.rglob("*"))
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    ]


# ════════════════════════════════════════════════════════════════
# Core: Add labelled images (image + .txt label pairs)
# ════════════════════════════════════════════════════════════════

def add_labelled(
    source: Path,
    species: str,
    split: str,
    images_dir: Path,
    labels_dir: Path,
    meta_path: Path,
    photographer: str,
    license_code: str,
    source_site: str,
    notes: str,
    dry_run: bool,
) -> None:
    """Copy labelled image+label pairs into the dataset splits."""
    images = _collect_images(source)
    if not images:
        print(f"[ERROR] No images found in: {source}")
        sys.exit(1)

    # Load existing metadata to check for duplicates
    existing_rows = _load_metadata(meta_path)
    existing_filenames: set[str] = {r["filename"] for r in existing_rows}
    existing_hashes: set[str] = set()
    for r in existing_rows:
        img_path = images_dir / r.get("split", "train") / r["filename"]
        if img_path.exists():
            try:
                existing_hashes.add(_file_md5(img_path))
            except Exception:
                pass

    # Determine next index for naming
    species_files = [r["filename"] for r in existing_rows if r.get("species") == species]
    next_idx = len(species_files) + 1

    dest_img_dir = images_dir / split
    dest_lbl_dir = labels_dir / split
    sci_name = SCIENTIFIC_NAMES.get(species, "")

    if not dry_run:
        dest_img_dir.mkdir(parents=True, exist_ok=True)
        dest_lbl_dir.mkdir(parents=True, exist_ok=True)

    added = 0
    skipped_dup = 0
    skipped_no_label = 0
    new_rows: list[dict[str, str]] = []
    used_names: set[str] = {Path(f).stem for f in existing_filenames}

    print(f"\n{'='*60}")
    print(f"  Adding labelled images for: {species}")
    print(f"  Source      : {source}")
    print(f"  Target split: {split}")
    print(f"  Images found: {len(images)}")
    if dry_run:
        print("  DRY-RUN — no files will be written")
    print(f"{'='*60}")

    for img_path in images:
        # Duplicate detection by hash
        img_hash = _file_md5(img_path)
        if img_hash in existing_hashes:
            print(f"  [SKIP-DUP] {img_path.name} — identical file already in dataset")
            skipped_dup += 1
            continue

        # Look for matching label file
        lbl_path = img_path.with_suffix(".txt")
        if not lbl_path.exists():
            # Try the labels/ sibling directory
            lbl_path = img_path.parent.parent / "labels" / img_path.stem
            lbl_path = lbl_path.with_suffix(".txt")
        has_label = lbl_path.exists()

        if not has_label:
            print(
                f"  [NO-LABEL] {img_path.name} — no .txt label found. "
                "Copy to data/raw/ for annotation."
            )
            skipped_no_label += 1
            continue

        # Generate unique destination filename
        new_stem = _safe_name(img_path.stem, species, next_idx, used_names)
        new_img_name = new_stem + img_path.suffix.lower()
        new_lbl_name = new_stem + ".txt"

        dst_img = dest_img_dir / new_img_name
        dst_lbl = dest_lbl_dir / new_lbl_name

        print(f"  [ADD] {img_path.name}  →  {split}/{new_img_name}")

        if not dry_run:
            shutil.copy2(img_path, dst_img)
            shutil.copy2(lbl_path, dst_lbl)
            existing_hashes.add(img_hash)

        new_rows.append({
            "filename":        new_img_name,
            "species":         species,
            "scientific_name": sci_name,
            "source_site":     source_site,
            "source_url":      "",
            "observation_id":  "",
            "photographer":    photographer,
            "license":         license_code,
            "attribution_text": f"{species} by {photographer}, {license_code}",
            "date_downloaded": date.today().isoformat(),
            "split":           split,
            "notes":           notes,
        })
        added += 1
        next_idx += 1

    # Save updated metadata
    if not dry_run and new_rows:
        all_rows = existing_rows + new_rows
        _save_metadata(meta_path, all_rows)

    print(f"\n  Summary:")
    print(f"    Added          : {added}")
    print(f"    Skipped (dup)  : {skipped_dup}")
    print(f"    Skipped (no label): {skipped_no_label}")
    if skipped_no_label > 0:
        print(
            f"\n  ⚠ {skipped_no_label} image(s) had no labels. "
            "Annotate them with LabelImg or Roboflow, then re-run."
        )
    if not dry_run and added > 0:
        print(f"\n  ✓ metadata.csv updated.")
        print(f"  Next: python scripts/validate_dataset.py")
        print(f"  Then: python scripts/train.py")


# ════════════════════════════════════════════════════════════════
# Core: Add raw (unannotated) images for later labelling
# ════════════════════════════════════════════════════════════════

def add_raw(
    source: Path,
    species: str,
    raw_dir: Path,
    meta_path: Path,
    photographer: str,
    license_code: str,
    source_site: str,
    notes: str,
    dry_run: bool,
) -> None:
    """Copy unannotated images to data/raw/<species>/ for later annotation."""
    images = _collect_images(source)
    if not images:
        print(f"[ERROR] No images found in: {source}")
        sys.exit(1)

    dest_dir = raw_dir / species
    existing_rows = _load_metadata(meta_path)
    existing_hashes: set[str] = set()

    if not dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)

    species_count = sum(1 for r in existing_rows if r.get("species") == species)
    next_idx = species_count + 1
    used_names: set[str] = {Path(r["filename"]).stem for r in existing_rows}

    sci_name = SCIENTIFIC_NAMES.get(species, "")
    new_rows: list[dict[str, str]] = []
    added = 0
    skipped = 0

    print(f"\n{'='*60}")
    print(f"  Staging raw images for: {species}")
    print(f"  Destination: {dest_dir}")
    print(f"  Images found: {len(images)}")
    if dry_run:
        print("  DRY-RUN — no files will be written")
    print(f"{'='*60}")

    for img_path in images:
        img_hash = _file_md5(img_path)
        if img_hash in existing_hashes:
            print(f"  [SKIP-DUP] {img_path.name}")
            skipped += 1
            continue

        new_stem = _safe_name(img_path.stem, species, next_idx, used_names)
        new_name = new_stem + img_path.suffix.lower()
        dst = dest_dir / new_name

        print(f"  [STAGE] {img_path.name}  →  raw/{species}/{new_name}")
        if not dry_run:
            shutil.copy2(img_path, dst)
            existing_hashes.add(img_hash)

        new_rows.append({
            "filename":        new_name,
            "species":         species,
            "scientific_name": sci_name,
            "source_site":     source_site,
            "source_url":      "",
            "observation_id":  "",
            "photographer":    photographer,
            "license":         license_code,
            "attribution_text": f"{species} by {photographer}, {license_code}",
            "date_downloaded": date.today().isoformat(),
            "split":           "unassigned",
            "notes":           f"raw-unannotated. {notes}".strip(". "),
        })
        added += 1
        next_idx += 1

    if not dry_run and new_rows:
        all_rows = existing_rows + new_rows
        _save_metadata(meta_path, all_rows)

    print(f"\n  Staged: {added}  |  Skipped: {skipped}")
    print(f"\n  Next steps:")
    print(f"    1. Open data/raw/{species}/ in LabelImg or Roboflow")
    print(f"    2. Annotate with YOLO format (.txt per image)")
    print(f"    3. Re-run with --mode labelled --source data/raw/{species}/")


# ════════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Add new images to the Western Ghats dataset. "
            "Handles labelled (image+.txt) or raw (unannotated) images."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Add labelled images (you have .txt labels):\n"
            "  python scripts/add_images.py \\\n"
            "      --source /path/to/photos/ \\\n"
            "      --species nilgiri_tahr \\\n"
            "      --mode labelled\n\n"
            "  # Stage raw images for annotation:\n"
            "  python scripts/add_images.py \\\n"
            "      --source /path/to/photos/ \\\n"
            "      --species bengal_tiger \\\n"
            "      --mode raw\n\n"
            "  # Dry-run (preview without writing):\n"
            "  python scripts/add_images.py \\\n"
            "      --source /path/to/photos/ \\\n"
            "      --species gaur --mode labelled --dry-run\n"
        ),
    )
    parser.add_argument(
        "--source", required=True,
        help="Path to folder (or single file) containing new images.",
    )
    parser.add_argument(
        "--species", required=True,
        help=(
            "Class name for these images. Must be in dataset.yaml names. "
            f"Available: {', '.join(SCIENTIFIC_NAMES.keys())}"
        ),
    )
    parser.add_argument(
        "--mode", choices=["labelled", "raw"], default="labelled",
        help=(
            "'labelled' : images have .txt YOLO labels (default). "
            "'raw'      : unannotated images staged for annotation."
        ),
    )
    parser.add_argument(
        "--split", choices=["train", "val", "test"], default="train",
        help="Which split to add labelled images to (default: train).",
    )
    parser.add_argument(
        "--photographer", default="unknown",
        help="Photographer credit for metadata (default: unknown).",
    )
    parser.add_argument(
        "--license", default="CC-BY-4.0",
        dest="license_code",
        help="License identifier, e.g. CC-BY-4.0, CC0-1.0 (default: CC-BY-4.0).",
    )
    parser.add_argument(
        "--source-site", default="field_collection",
        help="Where images came from, e.g. iNaturalist, Wikimedia (default: field_collection).",
    )
    parser.add_argument(
        "--notes", default="",
        help="Optional notes to record in metadata.csv.",
    )
    parser.add_argument(
        "--config", default=str(PROJECT_ROOT / "config" / "settings.yaml"),
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview actions without writing any files.",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    active_classes = get_class_names(cfg)

    if args.species not in SCIENTIFIC_NAMES and args.species not in active_classes:
        print(
            f"[ERROR] Species '{args.species}' is not recognised.\n"
            f"        Active classes: {active_classes}\n"
            f"        All known:      {list(SCIENTIFIC_NAMES.keys())}"
        )
        sys.exit(1)

    source = Path(args.source)
    if not source.exists():
        print(f"[ERROR] Source path does not exist: {source}")
        sys.exit(1)

    data_dir    = Path(cfg["paths"]["data_dir"])
    images_dir  = Path(cfg["paths"]["images_dir"])
    labels_dir  = Path(cfg["paths"]["labels_dir"])
    raw_dir     = data_dir / "raw"
    meta_path   = data_dir / "metadata.csv"

    if args.mode == "labelled":
        add_labelled(
            source=source,
            species=args.species,
            split=args.split,
            images_dir=images_dir,
            labels_dir=labels_dir,
            meta_path=meta_path,
            photographer=args.photographer,
            license_code=args.license_code,
            source_site=args.source_site,
            notes=args.notes,
            dry_run=args.dry_run,
        )
    else:
        add_raw(
            source=source,
            species=args.species,
            raw_dir=raw_dir,
            meta_path=meta_path,
            photographer=args.photographer,
            license_code=args.license_code,
            source_site=args.source_site,
            notes=args.notes,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
