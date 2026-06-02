import os
import sys

import cv2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config.settings import settings
from app.services.lane_context_service import analyze_current_lane
from app.services.lane_service import lane_prediction
from app.services.lane_opencv_service import draw_lane_overlay


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python tools/test_lane_image.py <image_path>")
        return 1

    image_path = sys.argv[1]
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"Cannot read image: {image_path}")
        return 1

    detections = lane_prediction(frame, method="opencv")
    current_lane = analyze_current_lane(
        detections,
        frame.shape,
        drift_threshold=settings.LANE_DEPARTURE["offset_threshold"],
    )

    overlay = draw_lane_overlay(frame.copy(), detections)
    if current_lane.get("available"):
        lane_center_x = int(current_lane.get("lane_center_x", 0))
        vehicle_center_x = int(current_lane.get("vehicle_center_x", 0))
        cv2.line(overlay, (lane_center_x, 0), (lane_center_x, frame.shape[0]), (0, 255, 0), 2)
        cv2.line(overlay, (vehicle_center_x, 0), (vehicle_center_x, frame.shape[0]), (255, 255, 255), 2)

    output_dir = os.path.join("debug_frames", "test_output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "lane_test_" + os.path.basename(image_path))
    cv2.imwrite(output_path, overlay)

    print("detections:")
    for det in detections:
        print(
            f"- {det.get('class_name')} line={det.get('line')} "
            f"confidence={det.get('confidence', 0):.3f} method={det.get('method')}"
        )
    print(
        "current_lane:",
        {
            key: current_lane.get(key)
            for key in (
                "available",
                "status",
                "warning",
                "warning_direction",
                "warning_level",
                "offset_ratio",
                "lane_center_x",
                "lane_width_px",
            )
        },
    )
    print("saved:", output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
