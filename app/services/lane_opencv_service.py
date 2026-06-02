from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import cv2
import numpy as np


@dataclass(frozen=True)
class LaneLine:
    side: str
    points: tuple[tuple[int, int], tuple[int, int]]
    slope: float
    intercept: float
    confidence: float


def detect_lane_lines(frame: np.ndarray) -> list[dict]:
    """Detect left and right lane markings with Canny + Hough transform."""
    if frame is None or frame.size == 0:
        return []

    edges = _canny_edges(frame)
    roi_edges = _region_selection(edges)
    hough_lines = _hough_transform(roi_edges)
    lanes = _lane_lines(frame, hough_lines)

    return [_lane_to_detection(lane, frame.shape[:2]) for lane in lanes]


def draw_lane_overlay(frame: np.ndarray, detections: Iterable[dict]) -> np.ndarray:
    overlay = np.zeros_like(frame)

    for det in detections:
        points = det.get("line")
        if not points or len(points) != 4:
            continue

        x1, y1, x2, y2 = map(int, points)
        side = det.get("class_name", "")
        color = (0, 255, 255) if side == "left_lane" else (255, 0, 255)
        cv2.line(overlay, (x1, y1), (x2, y2), color, 10)

    return cv2.addWeighted(frame, 1.0, overlay, 0.9, 0.0)


def _canny_edges(frame: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    return cv2.Canny(blur, 35, 110)


def _region_selection(image: np.ndarray) -> np.ndarray:
    mask = np.zeros_like(image)
    rows, cols = image.shape[:2]

    vertices = np.array(
        [
            [
                [cols * 0.02, rows * 0.98],
                [cols * 0.30, rows * 0.45],
                [cols * 0.70, rows * 0.45],
                [cols * 0.98, rows * 0.98],
            ]
        ],
        dtype=np.int32,
    )

    fill_color = (255,) * image.shape[2] if len(image.shape) > 2 else 255
    cv2.fillPoly(mask, vertices, fill_color)
    return cv2.bitwise_and(image, mask)


def _hough_transform(image: np.ndarray):
    return cv2.HoughLinesP(
        image,
        rho=1,
        theta=np.pi / 180,
        threshold=12,
        minLineLength=12,
        maxLineGap=350,
    )


def _lane_lines(frame: np.ndarray, lines) -> list[LaneLine]:
    if lines is None:
        return []

    left_lane, right_lane = _average_slope_intercept(lines, frame.shape[1])
    y1 = frame.shape[0]
    y2 = int(y1 * 0.60)

    lanes: list[LaneLine] = []
    for side, lane in (("left_lane", left_lane), ("right_lane", right_lane)):
        if lane is None:
            continue

        slope, intercept, confidence = lane
        points = _pixel_points(y1, y2, slope, intercept)
        if points is None:
            continue

        lanes.append(
            LaneLine(
                side=side,
                points=points,
                slope=float(slope),
                intercept=float(intercept),
                confidence=float(confidence),
            )
        )

    return lanes


def _average_slope_intercept(lines, image_width: int):
    left_lines = []
    left_weights = []
    right_lines = []
    right_weights = []

    min_abs_slope = 0.25
    max_abs_slope = 3.0
    center_x = image_width / 2

    for line in lines:
        for x1, y1, x2, y2 in line:
            if x1 == x2:
                continue

            slope = (y2 - y1) / (x2 - x1)
            abs_slope = abs(slope)
            if abs_slope < min_abs_slope or abs_slope > max_abs_slope:
                continue

            intercept = y1 - slope * x1
            length = float(np.hypot(y2 - y1, x2 - x1))
            midpoint_x = (x1 + x2) / 2

            if slope < 0 and midpoint_x < center_x:
                left_lines.append((slope, intercept))
                left_weights.append(length)
            elif slope > 0 and midpoint_x > center_x:
                right_lines.append((slope, intercept))
                right_weights.append(length)

    return (
        _weighted_lane(left_lines, left_weights),
        _weighted_lane(right_lines, right_weights),
    )


def _weighted_lane(lines: list[tuple[float, float]], weights: list[float]):
    if not weights:
        return None

    lane = np.dot(weights, lines) / np.sum(weights)
    confidence = min(1.0, np.sum(weights) / 400.0)
    return float(lane[0]), float(lane[1]), float(confidence)


def _pixel_points(y1: int, y2: int, slope: float, intercept: float):
    if abs(slope) < 1e-6:
        return None

    x1 = int((y1 - intercept) / slope)
    x2 = int((y2 - intercept) / slope)
    return (x1, int(y1)), (x2, int(y2))


def _lane_to_detection(lane: LaneLine, image_shape: tuple[int, int]) -> dict:
    height, width = image_shape
    (x1, y1), (x2, y2) = lane.points

    clipped_x1 = int(np.clip(x1, 0, width - 1))
    clipped_x2 = int(np.clip(x2, 0, width - 1))
    clipped_y1 = int(np.clip(y1, 0, height - 1))
    clipped_y2 = int(np.clip(y2, 0, height - 1))

    return {
        "box": [
            float(min(clipped_x1, clipped_x2)),
            float(min(clipped_y1, clipped_y2)),
            float(max(clipped_x1, clipped_x2)),
            float(max(clipped_y1, clipped_y2)),
        ],
        "line": [
            float(clipped_x1),
            float(clipped_y1),
            float(clipped_x2),
            float(clipped_y2),
        ],
        "confidence": lane.confidence,
        "class_id": 0 if lane.side == "left_lane" else 1,
        "class_name": lane.side,
        "slope": lane.slope,
        "intercept": lane.intercept,
        "method": "opencv_hough",
    }
