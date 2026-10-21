# ============================================================
# src/video_processor.py
# Frame-by-frame video processing with OpenCV.
#
# Processes a video file without loading it fully into memory.
# Writes annotated frames to a new video file and collects
# per-frame detection data.
#
# Usage (standalone):
#   from src.video_processor import process_video
# ============================================================

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Generator

import cv2
import numpy as np


# ──────────────────────────────────────────────────────────────────
# Generator: yield annotated frames
# ──────────────────────────────────────────────────────────────────

def iter_video_frames(
    video_path: Path | str,
    model: Any,
    class_names: list[str],
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.45,
    max_det: int = 300,
    frame_skip: int = 1,
    is_trained: bool = False,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Generator[tuple[np.ndarray, list[dict[str, Any]], int, float], None, None]:
    """Yield annotated frames from a video file one at a time.

    Args:
        video_path: Path to the input video file.
        model: Loaded Ultralytics YOLO model.
        class_names: Class name list.
        conf_threshold: Detection confidence threshold.
        iou_threshold: NMS IoU threshold.
        max_det: Max detections per frame.
        frame_skip: Process every N-th frame (1 = all frames).
        is_trained: True if using a user-trained model.
        progress_callback: Optional callback(frame_index, total_frames).

    Yields:
        (annotated_bgr_frame, detections, frame_index, fps_this_frame)
    """
    from src.inference import run_inference, draw_status_overlay

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise IOError(f"Cannot open video file: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    mode_str = "Trained" if is_trained else "Generic (pretrained)"
    frame_idx = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_skip != 0:
                frame_idx += 1
                continue

            t0 = time.perf_counter()
            annotated, detections = run_inference(
                model=model,
                image=frame,
                class_names=class_names,
                conf_threshold=conf_threshold,
                iou_threshold=iou_threshold,
                max_det=max_det,
                is_trained=is_trained,
            )
            elapsed = time.perf_counter() - t0
            fps = 1.0 / elapsed if elapsed > 0 else 0.0

            annotated = draw_status_overlay(annotated, mode_str, len(detections), fps)

            if progress_callback:
                progress_callback(frame_idx, total_frames)

            yield annotated, detections, frame_idx, fps
            frame_idx += 1
    finally:
        cap.release()


# ──────────────────────────────────────────────────────────────────
# Full video processing (saves output file)
# ──────────────────────────────────────────────────────────────────

def process_video(
    video_path: Path | str,
    output_path: Path | str,
    model: Any,
    class_names: list[str],
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.45,
    max_det: int = 300,
    frame_skip: int = 1,
    is_trained: bool = False,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Process a video file and write the annotated result.

    Args:
        video_path: Path to the input video.
        output_path: Where to write the annotated video (mp4).
        model: Loaded YOLO model.
        class_names: Class names.
        conf_threshold: Detection confidence threshold.
        iou_threshold: NMS IoU threshold.
        max_det: Max detections per frame.
        frame_skip: Process every N-th frame.
        is_trained: True if using a user-trained model.
        progress_callback: Optional progress callback.

    Returns:
        Summary dict with processing statistics and aggregated detections.
    """
    video_path = Path(video_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ── Read video properties ────────────────────────────────────
    cap_probe = cv2.VideoCapture(str(video_path))
    if not cap_probe.isOpened():
        raise IOError(f"Cannot open video: {video_path}")
    fps_original = cap_probe.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap_probe.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap_probe.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap_probe.get(cv2.CAP_PROP_FRAME_COUNT))
    cap_probe.release()

    # ── Set up writer ────────────────────────────────────────────
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, fps_original, (width, height))
    if not writer.isOpened():
        raise IOError(f"Cannot create output video: {output_path}")

    all_detections: list[dict[str, Any]] = []
    processed_frames = 0
    fps_readings: list[float] = []

    try:
        for annotated, dets, frame_idx, fps_frame in iter_video_frames(
            video_path=video_path,
            model=model,
            class_names=class_names,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            max_det=max_det,
            frame_skip=frame_skip,
            is_trained=is_trained,
            progress_callback=progress_callback,
        ):
            writer.write(annotated)
            for d in dets:
                d["frame_index"] = frame_idx
            all_detections.extend(dets)
            fps_readings.append(fps_frame)
            processed_frames += 1
    finally:
        writer.release()

    avg_fps = float(np.mean(fps_readings)) if fps_readings else 0.0
    summary = {
        "input_video": str(video_path),
        "output_video": str(output_path),
        "total_frames": total_frames,
        "processed_frames": processed_frames,
        "frame_skip": frame_skip,
        "total_detections": len(all_detections),
        "average_fps": round(avg_fps, 2),
        "detections": all_detections,
    }
    return summary


def save_detections_json(detections_summary: dict[str, Any], output_path: Path | str) -> None:
    """Persist the video processing summary to a JSON file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(detections_summary, f, indent=2)
