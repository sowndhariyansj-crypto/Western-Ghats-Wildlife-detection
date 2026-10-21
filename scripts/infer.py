# ============================================================
# scripts/infer.py
# Command-line inference tool.
#
# Run YOLO detection on a single image or video from the terminal.
# Results are saved to results/cli_outputs/.
#
# Usage:
#   # On an image (uses config checkpoint by default):
#   python scripts/infer.py --source path/to/image.jpg
#
#   # On a video with a specific checkpoint:
#   python scripts/infer.py --source path/to/video.mp4 --weights runs/.../best.pt
#
#   # Adjust confidence threshold:
#   python scripts/infer.py --source image.jpg --conf 0.4
# ============================================================

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_config, get_class_names, get_model_checkpoint, is_trained_model_available
from src.inference import run_inference, draw_status_overlay

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}


def _check_ultralytics() -> None:
    try:
        import ultralytics  # noqa: F401
    except ImportError:
        print("[ERROR] Ultralytics is not installed. Run: pip install ultralytics")
        sys.exit(1)


def infer_image(
    source: Path,
    model,
    class_names: list[str],
    conf: float,
    iou: float,
    max_det: int,
    is_trained: bool,
    output_dir: Path,
    species_info: dict[str, dict[str, str]] | None = None,
) -> None:
    """Run inference on a single image and save the annotated result."""
    bgr = cv2.imread(str(source))
    if bgr is None:
        print(f"[ERROR] Cannot read image: {source}")
        sys.exit(1)

    annotated, detections = run_inference(
        model=model,
        image=bgr,
        class_names=class_names,
        conf_threshold=conf,
        iou_threshold=iou,
        max_det=max_det,
        is_trained=is_trained,
    )
    mode_str = "Trained" if is_trained else "Generic"
    annotated = draw_status_overlay(annotated, mode_str, len(detections))

    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_img = output_dir / f"detected_{source.stem}_{ts}{source.suffix}"
    out_json = output_dir / f"detections_{source.stem}_{ts}.json"

    cv2.imwrite(str(out_img), annotated)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(detections, f, indent=2)

    print(f"\n  Detections     : {len(detections)}")
    for d in detections:
        cname = d["class_name"]
        pct = d["confidence"] * 100.0
        info = (species_info or {}).get(cname, {})
        code = info.get("iucn_code")
        status_tag = f" [IUCN: {code}]" if code else ""
        print(f"    [{d['class_id']}] {cname:<25} conf={pct:5.1f}% ({d['confidence']:.3f}){status_tag}")
    print(f"\n  Annotated image: {out_img}")
    print(f"  JSON results   : {out_json}")


def infer_video(
    source: Path,
    model,
    class_names: list[str],
    conf: float,
    iou: float,
    max_det: int,
    frame_skip: int,
    is_trained: bool,
    output_dir: Path,
) -> None:
    """Run inference on a video file frame by frame."""
    from src.video_processor import process_video

    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_vid = output_dir / f"detected_{source.stem}_{ts}.mp4"
    out_json = output_dir / f"summary_{source.stem}_{ts}.json"

    print(f"  Processing video: {source}")
    print(f"  Frame skip      : {frame_skip}")

    def _progress(frame_idx: int, total: int) -> None:
        pct = int(100 * frame_idx / max(total, 1))
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        print(f"\r  [{bar}] {pct:3d}%  frame {frame_idx}/{total}", end="", flush=True)

    summary = process_video(
        video_path=source,
        output_path=out_vid,
        model=model,
        class_names=class_names,
        conf_threshold=conf,
        iou_threshold=iou,
        max_det=max_det,
        frame_skip=frame_skip,
        is_trained=is_trained,
        progress_callback=_progress,
    )
    print()  # newline after progress bar

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\n  Total detections: {summary['total_detections']}")
    print(f"  Frames processed: {summary['processed_frames']}")
    print(f"  Average FPS     : {summary['average_fps']:.2f}")
    print(f"  Annotated video : {out_vid}")
    print(f"  JSON summary    : {out_json}")


def main() -> None:
    _check_ultralytics()
    from ultralytics import YOLO

    parser = argparse.ArgumentParser(description="CLI inference for animal detection.")
    parser.add_argument("--source", required=True, help="Path to image or video file.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config" / "settings.yaml"))
    parser.add_argument("--weights", default=None, help="Override checkpoint path.")
    parser.add_argument("--conf", type=float, default=None, help="Confidence threshold.")
    parser.add_argument("--iou", type=float, default=None, help="IoU NMS threshold.")
    parser.add_argument("--max-det", type=int, default=None, help="Max detections.")
    parser.add_argument("--frame-skip", type=int, default=1, help="Video frame skip interval.")
    args = parser.parse_args()

    cfg = load_config(args.config)
    m_cfg = cfg.get("model", {})

    weights = args.weights or get_model_checkpoint(cfg)
    conf = args.conf or m_cfg.get("confidence_threshold", 0.25)
    iou = args.iou or m_cfg.get("iou_threshold", 0.45)
    max_det = args.max_det or m_cfg.get("max_det", 300)
    is_trained = is_trained_model_available(cfg) and (args.weights is None)
    class_names = get_class_names(cfg)
    output_dir = Path(cfg["paths"]["results_dir"]) / "cli_outputs"

    species_info = cfg.get("species_info", {})
    region_info = cfg.get("project", {}).get("region", "Western Ghats")

    print("\n" + "=" * 65)
    print("  WESTERN GHATS ENDANGERED ANIMAL DETECTION — CLI INFERENCE")
    print("=" * 65)
    print(f"  Region     : {region_info}")
    print(f"  Source     : {args.source}")
    print(f"  Checkpoint : {weights}")
    print(f"  Mode       : {'Trained (your dataset)' if is_trained else 'Generic pretrained'}")
    print(f"  Classes    : {len(class_names)} configured species")
    print(f"  Confidence : {conf} ({conf * 100:.0f}%)")
    print("=" * 65)

    model = YOLO(weights)
    source = Path(args.source)

    if not source.exists():
        print(f"[ERROR] Source file not found: {source}")
        sys.exit(1)

    if source.suffix.lower() in IMAGE_EXTENSIONS:
        infer_image(source, model, class_names, conf, iou, max_det, is_trained, output_dir, species_info)
    elif source.suffix.lower() in VIDEO_EXTENSIONS:
        infer_video(source, model, class_names, conf, iou, max_det, args.frame_skip, is_trained, output_dir)
    else:
        print(f"[ERROR] Unsupported file type: {source.suffix}")
        print(f"  Supported images: {IMAGE_EXTENSIONS}")
        print(f"  Supported videos: {VIDEO_EXTENSIONS}")
        sys.exit(1)


if __name__ == "__main__":
    main()
