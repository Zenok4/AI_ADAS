from __future__ import annotations

from typing import Iterable


def analyze_current_lane(
    detections: Iterable[dict],
    frame_shape: tuple[int, int] | tuple[int, int, int],
) -> dict:
    height, width = frame_shape[:2]
    reference_y = float(height - 1)
    vehicle_center_x = width / 2.0

    left_boundary = _nearest_boundary(
        detections=detections,
        class_name="left_lane",
        reference_y=reference_y,
        vehicle_center_x=vehicle_center_x,
        side="left",
    )
    right_boundary = _nearest_boundary(
        detections=detections,
        class_name="right_lane",
        reference_y=reference_y,
        vehicle_center_x=vehicle_center_x,
        side="right",
    )

    if left_boundary is None or right_boundary is None:
        return {
            "available": False,
            "status": "unknown",
            "message": "Need both left and right lane boundaries",
            "reference_y": reference_y,
            "vehicle_center_x": vehicle_center_x,
            "lane_center_x": 0.0,
            "lane_width_px": 0.0,
            "offset_px": 0.0,
            "offset_ratio": 0.0,
            "left_boundary": left_boundary,
            "right_boundary": right_boundary,
        }

    lane_width_px = right_boundary["x_at_reference"] - left_boundary["x_at_reference"]
    if lane_width_px <= 1.0:
        return {
            "available": False,
            "status": "invalid",
            "message": "Invalid lane width",
            "reference_y": reference_y,
            "vehicle_center_x": vehicle_center_x,
            "lane_center_x": 0.0,
            "lane_width_px": lane_width_px,
            "offset_px": 0.0,
            "offset_ratio": 0.0,
            "left_boundary": left_boundary,
            "right_boundary": right_boundary,
        }

    lane_center_x = (left_boundary["x_at_reference"] + right_boundary["x_at_reference"]) / 2.0
    offset_px = vehicle_center_x - lane_center_x
    offset_ratio = offset_px / (lane_width_px / 2.0)
    status, message = _lane_status(offset_ratio)

    return {
        "available": True,
        "status": status,
        "message": message,
        "reference_y": reference_y,
        "vehicle_center_x": vehicle_center_x,
        "lane_center_x": lane_center_x,
        "lane_width_px": lane_width_px,
        "offset_px": offset_px,
        "offset_ratio": offset_ratio,
        "left_boundary": left_boundary,
        "right_boundary": right_boundary,
    }


def annotate_detection_lane_position(detection: dict, current_lane: dict, box_key: str = "box") -> dict:
    annotated = {**detection}
    box = detection.get(box_key) or detection.get("bbox") or []

    if not current_lane.get("available") or len(box) < 4:
        annotated["lane_position"] = "unknown"
        annotated["in_current_lane"] = False
        return annotated

    left = current_lane["left_boundary"]["x_at_reference"]
    right = current_lane["right_boundary"]["x_at_reference"]
    object_center_x = (float(box[0]) + float(box[2])) / 2.0

    annotated["in_current_lane"] = left <= object_center_x <= right
    if annotated["in_current_lane"]:
        annotated["lane_position"] = "current_lane"
    elif object_center_x < left:
        annotated["lane_position"] = "left_of_current_lane"
    else:
        annotated["lane_position"] = "right_of_current_lane"

    return annotated


def _nearest_boundary(
    detections: Iterable[dict],
    class_name: str,
    reference_y: float,
    vehicle_center_x: float,
    side: str,
) -> dict | None:
    candidates = []

    for det in detections:
        if det.get("class_name") != class_name:
            continue

        line = det.get("line") or []
        if len(line) != 4:
            continue

        x_at_reference = _x_at_y(line, reference_y)
        if x_at_reference is None:
            continue

        if side == "left" and x_at_reference >= vehicle_center_x:
            continue
        if side == "right" and x_at_reference <= vehicle_center_x:
            continue

        candidates.append(
            {
                "class_name": class_name,
                "line": [float(value) for value in line],
                "confidence": float(det.get("confidence", 0.0)),
                "x_at_reference": float(x_at_reference),
            }
        )

    if not candidates:
        return None

    return min(candidates, key=lambda item: abs(item["x_at_reference"] - vehicle_center_x))


def _x_at_y(line: list[float], y: float) -> float | None:
    x1, y1, x2, y2 = [float(value) for value in line]
    if abs(y2 - y1) < 1e-6:
        return None

    ratio = (y - y1) / (y2 - y1)
    return x1 + ratio * (x2 - x1)


def _lane_status(offset_ratio: float) -> tuple[str, str]:
    if offset_ratio <= -0.45:
        return "left_departure", "Vehicle is leaving the lane to the left"
    if offset_ratio >= 0.45:
        return "right_departure", "Vehicle is leaving the lane to the right"
    if offset_ratio <= -0.20:
        return "left_drift", "Vehicle is drifting left in current lane"
    if offset_ratio >= 0.20:
        return "right_drift", "Vehicle is drifting right in current lane"
    return "centered", "Vehicle is centered in current lane"
