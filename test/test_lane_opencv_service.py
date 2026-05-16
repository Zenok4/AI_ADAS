import cv2
import numpy as np

from app.services.lane_opencv_service import detect_lane_lines


def test_detect_lane_lines_on_synthetic_road():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.line(frame, (170, 456), (280, 288), (255, 255, 255), 8)
    cv2.line(frame, (470, 456), (360, 288), (255, 255, 255), 8)

    detections = detect_lane_lines(frame)

    sides = {det["class_name"] for det in detections}
    assert sides == {"left_lane", "right_lane"}
    assert all(det["method"] == "opencv_hough" for det in detections)
    assert all(len(det["line"]) == 4 for det in detections)
