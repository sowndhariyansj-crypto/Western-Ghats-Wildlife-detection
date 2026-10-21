# ============================================================
# scripts/fetch_images.py
# Download research-grade, openly-licensed wildlife images
# from iNaturalist for the Western Ghats endangered-animal project.
#
# Species focus: Tamil Nadu & Kerala — Western Ghats Biodiversity Hotspot
# Images are filtered to India (iNaturalist place_id=6903) to keep
# results geographically relevant.
#
# Setup:
#   pip install requests Pillow PyYAML
#   (All three are already in requirements.txt)
#
# Usage:
#   # Dry-run — count available images without downloading:
#   python scripts/fetch_images.py --dry-run
#
#   # Fetch up to 100 images per active class:
#   python scripts/fetch_images.py --max 100
#
#   # Fetch only one species:
#   python scripts/fetch_images.py --species nilgiri_tahr --max 50
#
#   # Fetch ALL 10 species:
#   python scripts/fetch_images.py --all-species --max 100
#
# IMPORTANT NOTES
# ───────────────
# 1. The script writes into data/raw/<class>/ and appends rows
#    to data/metadata.csv.  It does NOT modify data/dataset.yaml.
#
# 2. Class order is fixed in config/settings.yaml -> classes.
#    NEVER reorder after labelling begins.
#
# 3. Test with --max 5 --dry-run before a large run.
#
# 4. iNaturalist API rate limit: ~100 requests/minute.
#    The default sleeps keep well below that limit.
#
# 5. All downloaded images are one-per-observation to minimise
#    near-duplicate burst sequences.
# ============================================================

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import date
from pathlib import Path

import requests

# ── Project bootstrap ────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_config, get_class_names  # noqa: E402

# ── iNaturalist API constants ────────────────────────────────────
API_BASE = "https://api.inaturalist.org/v1"
HEADERS = {"User-Agent": "student-yolo-project/1.0 (academic use)"}

# Licenses accepted.  cc-by-nc allows educational use; adjust if you
# need a more permissive set for publication.
ACCEPTED_LICENSES = "cc0,cc-by,cc-by-sa,cc-by-nc"

# Delay between API requests (seconds).  Keep >= 1.0 to respect the
# iNaturalist rate limit of ~100 requests/minute.
INTER_PAGE_SLEEP = 1.1   # between observation-list pages
INTER_IMG_SLEEP  = 0.5   # between individual image downloads

# ── Scientific names for all 10 Western Ghats species ───────────
# Fixed by taxonomy — never change these values.
# Active class list (and class IDs) is controlled by
# config/settings.yaml -> classes.
SCIENTIFIC_NAMES: dict[str, str] = {
    "nilgiri_tahr":            "Nilgiritragus hylocrius",
    "lion_tailed_macaque":     "Macaca silenus",
    "nilgiri_langur":          "Semnopithecus johnii",
    "malabar_civet":           "Viverra civettina",
    "gaur":                    "Bos gaurus",
    "bengal_tiger":            "Panthera tigris",
    "sloth_bear":              "Melursus ursinus",
    "asian_elephant":          "Elephas maximus",
    "nilgiri_marten":          "Martes gwatkinsii",
    "anaimalai_flying_frog":   "Rhacophorus pseudomalabaricus",
}

# iNaturalist place_id for India — restricts results to Indian observations.
# This keeps fetched images geographically relevant to Western Ghats context.
INATURALIST_PLACE_ID = 6903  # India

# ── CSV schema (superset of what the script generates) ──────────
# Must stay compatible with the existing data/metadata.csv columns.
CSV_FIELDS = [
    "filename",
    "species",
    "scientific_name",
    "source_site",
    "source_url",
    "observation_id",
    "photographer",
    "user_id",
    "license",
    "attribution_text",
    "date_downloaded",
    "split",
    "notes",
]


# ════════════════════════════════════════════════════════════════
# Metadata helpers
# ════════════════════════════════════════════════════════════════

def _load_metadata(metadata_path: Path) -> list[dict[str, str]]:
    """Load existing metadata rows, skipping comment lines."""
    if not metadata_path.exists():
        return []
    rows: list[dict[str, str]] = []
    with open(metadata_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            fn = (row.get("filename") or "").strip()
            if fn and not fn.startswith("#"):
                rows.append(row)
    return rows


def _save_metadata(metadata_path: Path, rows: list[dict[str, str]]) -> None:
    """Write metadata rows, preserving all CSV_FIELDS columns."""
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with open(metadata_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=CSV_FIELDS, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)


# ════════════════════════════════════════════════════════════════
# iNaturalist API helpers
# ════════════════════════════════════════════════════════════════

def _get_taxon_id(sci_name: str) -> int:
    """Resolve a scientific name to its iNaturalist taxon ID."""
    resp = requests.get(
        f"{API_BASE}/taxa",
        params={"q": sci_name, "rank": "species"},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    for taxon in resp.json().get("results", []):
        if taxon.get("name", "").lower() == sci_name.lower():
            return int(taxon["id"])
    raise SystemExit(
        f"[ERROR] Taxon not found on iNaturalist: '{sci_name}'\n"
        "        Check spelling or try searching at https://www.inaturalist.org/taxa"
    )


def _pick_photo(obs: dict) -> dict | None:
    """Return the first openly-licensed photo for an observation, or None."""
    for photo in obs.get("photos", []):
        if photo.get("license_code"):
            return photo
    return None


def _large_url(photo: dict) -> str:
    """Convert an iNaturalist thumbnail URL to the 'large' variant."""
    return photo["url"].replace("square", "large")


# ════════════════════════════════════════════════════════════════
# Core fetch logic
# ════════════════════════════════════════════════════════════════

def fetch_species(
    cls_name: str,
    sci_name: str,
    max_images: int,
    raw_dir: Path,
    metadata_path: Path,
    dry_run: bool,
) -> int:
    """Download up to *max_images* images for one species class.

    Returns the number of NEW images downloaded (or that would be
    downloaded in dry-run mode).
    """
    # ── Load existing state ──────────────────────────────────────
    all_rows = _load_metadata(metadata_path)
    seen_obs_ids: set[str] = {r["observation_id"] for r in all_rows}
    already_have = sum(1 for r in all_rows if r["species"] == cls_name)

    out_dir = raw_dir / cls_name
    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    if already_have >= max_images:
        print(f"[{cls_name}] Already have {already_have} images — skipping.")
        return 0

    # ── Resolve taxon ID ─────────────────────────────────────────
    print(f"[{cls_name}] Resolving taxon for '{sci_name}' ...")
    taxon_id = _get_taxon_id(sci_name)
    print(f"[{cls_name}] taxon_id={taxon_id}, have={already_have}, target={max_images}")

    new_count = 0
    page = 1

    while already_have + new_count < max_images:
        need = max_images - (already_have + new_count)
        print(f"[{cls_name}] Page {page} — need {need} more ...")

        time.sleep(INTER_PAGE_SLEEP)
        resp = requests.get(
            f"{API_BASE}/observations",
            headers=HEADERS,
            timeout=30,
            params={
                "taxon_id":      taxon_id,
                "quality_grade": "research",   # only research-grade observations
                "photos":        "true",
                "photo_license": ACCEPTED_LICENSES,
                "place_id":      INATURALIST_PLACE_ID,  # restrict to India
                "per_page":      100,
                "page":          page,
                "order_by":      "votes",      # most-popular first -> better images
            },
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])

        if not results:
            print(f"[{cls_name}] No more results from iNaturalist at page {page}.")
            break

        for obs in results:
            if already_have + new_count >= max_images:
                break

            oid = str(obs.get("id", ""))
            if oid in seen_obs_ids:
                continue  # already downloaded this observation

            photo = _pick_photo(obs)
            if not photo:
                continue  # no openly-licensed photo

            url = _large_url(photo)
            fn  = f"{cls_name}_{oid}.jpg"
            dst = out_dir / fn

            if dry_run:
                print(f"  [DRY-RUN] Would download: {fn}  ({url})")
                new_count += 1
                seen_obs_ids.add(oid)
                continue

            # ── Download image ───────────────────────────────────
            time.sleep(INTER_IMG_SLEEP)
            try:
                img_resp = requests.get(url, headers=HEADERS, timeout=30)
                img_resp.raise_for_status()
            except requests.RequestException as exc:
                print(f"  [SKIP] obs {oid}: {exc}")
                continue

            dst.write_bytes(img_resp.content)

            # ── Append metadata row ──────────────────────────────
            user = obs.get("user") or {}
            new_row: dict[str, str] = {
                "filename":         fn,
                "species":          cls_name,
                "scientific_name":  sci_name,
                "source_site":      "iNaturalist",
                "source_url":       obs.get("uri", ""),
                "observation_id":   oid,
                "photographer":     user.get("login", ""),
                "user_id":          str(user.get("id", "")),
                "license":          photo.get("license_code", ""),
                "attribution_text": photo.get("attribution", ""),
                "date_downloaded":  date.today().isoformat(),
                "split":            "unassigned",
                "notes":            "",
            }
            all_rows.append(new_row)
            seen_obs_ids.add(oid)
            new_count += 1

        if not dry_run:
            # Save progress after every page so a crash loses at most one page.
            _save_metadata(metadata_path, all_rows)
            print(f"[{cls_name}] Progress saved — {already_have + new_count} total images.")

        page += 1

    return new_count


def run_fetch(
    species_to_fetch: dict[str, str],
    max_images: int,
    data_dir: Path,
    dry_run: bool,
) -> None:
    raw_dir       = data_dir / "raw"
    metadata_path = data_dir / "metadata.csv"

    if dry_run:
        print("\n  DRY-RUN MODE — no files will be written.\n")

    total_new = 0
    for cls_name, sci_name in species_to_fetch.items():
        n = fetch_species(
            cls_name=cls_name,
            sci_name=sci_name,
            max_images=max_images,
            raw_dir=raw_dir,
            metadata_path=metadata_path,
            dry_run=dry_run,
        )
        total_new += n
        print(f"[{cls_name}] +{n} new images downloaded.")

    print(
        f"\n{'='*60}\n"
        f"  Fetch complete.  New images: {total_new}\n"
        f"{'='*60}\n"
        "  Next steps:\n"
        "    1. Review images in data/raw/ — delete:\n"
        "         captive/zoo animals, wrong species, art, poor quality.\n"
        "    2. Remove their rows from data/metadata.csv as well.\n"
        "    3. Annotate with LabelImg or Roboflow (YOLO format).\n"
        "    4. Run: python scripts/add_images.py --source data/raw/\n"
        "       (This auto-splits and moves labelled images into place)\n"
        "    5. Run: python scripts/validate_dataset.py\n"
        "    6. Train: python scripts/train.py\n"
    )


# ════════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Download research-grade, openly-licensed wildlife images "
            "from iNaturalist for the YOLO endangered-animal project."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/fetch_images.py --max 10 --dry-run\n"
            "  python scripts/fetch_images.py --max 250\n"
            "  python scripts/fetch_images.py --species tiger --max 50\n"
            "  python scripts/fetch_images.py --all-species --max 250\n"
        ),
    )
    parser.add_argument(
        "--config",
        default=str(PROJECT_ROOT / "config" / "settings.yaml"),
        help="Path to settings.yaml (default: config/settings.yaml)",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=250,
        metavar="N",
        help="Maximum images to download per class (default: 250).",
    )
    parser.add_argument(
        "--species",
        metavar="CLASS_NAME",
        help=(
            "Fetch only this class (e.g. 'tiger'). "
            "Must be in SCIENTIFIC_NAMES. Overrides --all-species."
        ),
    )
    parser.add_argument(
        "--all-species",
        action="store_true",
        help=(
            "Fetch all 10 Western Ghats species. "
            "By default only the active classes in settings.yaml are fetched."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List images that would be downloaded without saving anything.",
    )
    args = parser.parse_args()

    cfg      = load_config(args.config)
    data_dir = Path(cfg["paths"]["data_dir"])

    # ── Decide which species to fetch ────────────────────────────
    if args.species:
        if args.species not in SCIENTIFIC_NAMES:
            valid = ", ".join(SCIENTIFIC_NAMES)
            print(
                f"[ERROR] --species '{args.species}' is not recognised.\n"
                f"        Valid options: {valid}"
            )
            sys.exit(1)
        species_to_fetch = {args.species: SCIENTIFIC_NAMES[args.species]}

    elif args.all_species:
        species_to_fetch = dict(SCIENTIFIC_NAMES)

    else:
        # Default: only the classes listed in settings.yaml -> classes
        active_classes = get_class_names(cfg)
        unknown = [c for c in active_classes if c not in SCIENTIFIC_NAMES]
        if unknown:
            print(
                f"[WARNING] These classes in settings.yaml have no scientific name "
                f"mapping in this script: {unknown}\n"
                "          Edit SCIENTIFIC_NAMES in fetch_images.py to add them."
            )
        species_to_fetch = {
            c: SCIENTIFIC_NAMES[c]
            for c in active_classes
            if c in SCIENTIFIC_NAMES
        }

    if not species_to_fetch:
        print("[ERROR] No species to fetch. Check settings.yaml -> classes.")
        sys.exit(1)

    print("=" * 60)
    print("  iNaturalist Image Fetcher")
    print("=" * 60)
    print(f"  Data directory : {data_dir.resolve()}")
    print(f"  Max per class  : {args.max}")
    print(f"  Species ({len(species_to_fetch)}):")
    for cls, sci in species_to_fetch.items():
        print(f"    * {cls:<30} {sci}")
    print()

    run_fetch(
        species_to_fetch=species_to_fetch,
        max_images=args.max,
        data_dir=data_dir,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
