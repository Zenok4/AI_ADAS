import os

import cv2
import pytest

from app.services.lane_service import lane_prediction


def test_ufldv2_detects_lanes_on_sample_video_frame():
    model_path = "external/Ultra-Fast-Lane-Detection-v2/ufldv2_tusimple_res18_320x800.onnx"
    video_path = "external/Ultra-Fast-Lane-Detection-v2/example.mp4"
    if not os.path.exists(model_path) or not os.path.exists(video_path):
        pytest.skip("UFLD V2 external model or sample video is not available")

    cap = cv2.VideoCapture(video_path)
    ok, frame = cap.read()
    cap.release()
    assert ok

    detections = lane_prediction(frame, method="ufldv2")

    assert {det["class_name"] for det in detections} == {"left_lane", "right_lane"}
    assert all(det["method"].startswith("ufldv2_") for det in detections)
    assert all(len(det["line"]) == 4 for det in detections)
