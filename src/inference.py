# ============================================================
# src/inference.py
# Single-image inference module.
#
# Handles:
#   - Running YOLO on an image (numpy array or file path)
#   - Drawing bounding boxes + labels with OpenCV
#   - Building a structured list of detections (dict)
#   - Mode labelling: "demo/generic" vs "trained"
# ============================================================

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np


# ──────────────────────────────────────────────────────────────────
# Colour palette (BGR — OpenCV convention)
# Uses a fixed set of visually distinct colours, cycling if needed.
# ──────────────────────────────────────────────────────────────────

_PALETTE: list[tuple[int, int, int]] = [
    (0, 200, 255),    # amber
    (0, 255, 128),    # mint green
    (255, 80,  80),   # coral
    (128, 80, 255),   # violet
    (255, 200,  0),   # gold
    (0, 180, 180),    # teal
    (255, 100, 200),  # pink
    (60,  200, 60),   # green
]


def _colour_for_class(class_id: int) -> tuple[int, int, int]:
    return _PALETTE[class_id % len(_PALETTE)]


# ──────────────────────────────────────────────────────────────────
# Inference
# ──────────────────────────────────────────────────────────────────

def run_inference(
    model: Any,                         # ultralytics YOLO model instance
    image: np.ndarray,                  # BGR numpy array (from cv2.imread or VideoCapture)
    class_names: list[str],
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.45,
    max_det: int = 300,
    is_trained: bool = False,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Run YOLO inference on a single BGR image and draw annotated results.

    Args:
        model: Loaded Ultralytics YOLO model.
        image: Input image as a BGR numpy array.
        class_names: List of class names matching the model's class IDs.
        conf_threshold: Minimum confidence to keep a detection.
        iou_threshold: IoU threshold for NMS.
        max_det: Maximum detections per image.
        is_trained: True if this is a user-trained model (affects label text).

    Returns:
        annotated_image: BGR numpy array with bounding boxes drawn.
        detections: List of dicts, one per detection, containing:
            - class_id (int)
            - class_name (str)
            - confidence (float)
            - bbox_xyxy (list[float]) — absolute pixel coordinates [x1, y1, x2, y2]
            - bbox_xywh (list[float]) — [x_centre, y_centre, width, height] in pixels
    """
    t0 = time.perf_counter()

    results = model.predict(
        source=image,
        conf=conf_threshold,
        iou=iou_threshold,
        max_det=max_det,
        verbose=False,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    annotated = image.copy()
    detections: list[dict[str, Any]] = []

    if not results or results[0].boxes is None:
        return annotated, detections

    boxes = results[0].boxes

    for box in boxes:
        cls_id = int(box.cls[0].item())
        conf = float(box.conf[0].item())
        x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
        xc = (x1 + x2) / 2
        yc = (y1 + y2) / 2
        bw = x2 - x1
        bh = y2 - y1

        # Resolve class name safely
        if 0 <= cls_id < len(class_names):
            class_name = class_names[cls_id]
        else:
            class_name = "unrecognised_species"

        # Build label text
        mode_tag = "" if is_trained else " [generic]"
        label_text = f"{class_name}{mode_tag} {conf:.2f}"

        colour = _colour_for_class(cls_id)
        _draw_detection(annotated, x1, y1, x2, y2, label_text, colour)

        detections.append(
            {
                "class_id": cls_id,
                "class_name": class_name,
                "confidence": round(conf, 4),
                "bbox_xyxy": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                "bbox_xywh": [round(xc, 1), round(yc, 1), round(bw, 1), round(bh, 1)],
            }
        )

    return annotated, detections


# ──────────────────────────────────────────────────────────────────
# Drawing helpers
# ──────────────────────────────────────────────────────────────────

def _draw_detection(
    image: np.ndarray,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    label: str,
    colour: tuple[int, int, int],
    thickness: int = 2,
    font_scale: float = 0.55,
) -> None:
    """Draw a single bounding box and label on image (in-place)."""
    ix1, iy1, ix2, iy2 = int(x1), int(y1), int(x2), int(y2)
    cv2.rectangle(image, (ix1, iy1), (ix2, iy2), colour, thickness)

    font = cv2.FONT_HERSHEY_SIMPLEX
    (text_w, text_h), baseline = cv2.getTextSize(label, font, font_scale, thickness)

    # Background rectangle for text
    label_y = max(iy1 - 6, text_h + 6)
    cv2.rectangle(
        image,
        (ix1, label_y - text_h - baseline - 4),
        (ix1 + text_w + 4, label_y + baseline),
        colour,
        cv2.FILLED,
    )
    # White text on coloured background
    cv2.putText(
        image, label,
        (ix1 + 2, label_y - baseline),
        font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA,
    )


def draw_status_overlay(
    image: np.ndarray,
    mode: str,
    n_detections: int,
    fps: float | None = None,
) -> np.ndarray:
    """Draw a semi-transparent status bar at the top of the image.

    Args:
        image: BGR image (modified in-place; a copy is returned).
        mode: Short string describing the detection mode (e.g., "Generic", "Trained").
        n_detections: Number of detections in this frame.
        fps: Frames per second (None = not shown).

    Returns:
        Image with overlay drawn.
    """
    out = image.copy()
    h, w = out.shape[:2]
    bar_h = 36
    overlay = out.copy()
    cv2.rectangle(overlay, (0, 0), (w, bar_h), (30, 30, 30), cv2.FILLED)
    cv2.addWeighted(overlay, 0.65, out, 0.35, 0, out)

    font = cv2.FONT_HERSHEY_SIMPLEX
    text = f"Mode: {mode}  |  Detections: {n_detections}"
    if fps is not None:
        text += f"  |  FPS: {fps:.1f}"
    cv2.putText(out, text, (10, 24), font, 0.55, (200, 240, 200), 1, cv2.LINE_AA)
    return out
