import cv2
import numpy as np

from gRPC.gRPC_service.grpc_lane_service import LaneService
from proto.lane_pb2 import LaneRequest


def test_grpc_lane_response_includes_line_points():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.line(frame, (170, 456), (280, 288), (255, 255, 255), 8)
    cv2.line(frame, (470, 456), (360, 288), (255, 255, 255), 8)

    _, encoded = cv2.imencode(".jpg", frame)
    response = LaneService().Predict(LaneRequest(image=encoded.tobytes()), None)

    assert len(response.detections) == 2
    assert all(len(detection.line) == 4 for detection in response.detections)
    assert response.current_lane.available is True
    assert response.current_lane.status == "centered"
    assert response.current_lane.left_boundary.class_name == "left_lane"
    assert response.current_lane.right_boundary.class_name == "right_lane"
