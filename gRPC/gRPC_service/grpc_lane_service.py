import time
import cv2
import numpy as np

from debug.visual_logger import VisualLogger
from debug.event_logger import EventLogger

import proto.lane_pb2 as lane_pb2
import proto.lane_pb2_grpc as lane_pb2_grpc

from app.config.settings import settings
from app.services.lane_context_service import analyze_current_lane
from app.services.lane_service import lane_prediction
from app.state import get_vehicle_state


class LaneService(lane_pb2_grpc.LaneServiceServicer):

    def __init__(self):
        self.visual = VisualLogger()
        self.event_logger = EventLogger()

    def Predict(self, request, context):
        start_time = time.time()

        try:
            # decode image
            np_arr = np.frombuffer(request.image, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if frame is None:
                return lane_pb2.LaneResponse()

            # predict
            detections = lane_prediction(frame)
            vehicle_state = get_vehicle_state()
            current_lane = analyze_current_lane(
                detections,
                frame.shape,
                drift_threshold=settings.LANE_DEPARTURE["offset_threshold"],
                vehicle_state=vehicle_state,
            )

            # 🎨 draw
            debug_frame = self.visual.draw_lane(
                frame.copy(),
                detections
            )

            # 📸 save
            image_path = self.visual.save(debug_frame, "lane")

            # ⏱️ latency
            processing_time = time.time() - start_time

            # 🧾 log
            if len(detections) > 0:
                self.event_logger.log(
                    "lane",
                    image_path,
                    {
                        "num_lanes": len(detections),
                        "latency_ms": processing_time * 1000
                    }
                )

            # response
            results = [
                lane_pb2.LaneData(
                    box=det.get("box", []),
                    confidence=det.get("confidence", 0),
                    class_id=det.get("class_id", 0),
                    class_name=det.get("class_name", ""),
                    line=det.get("line", []),
                )
                for det in detections
            ]

            return lane_pb2.LaneResponse(
                detections=results,
                meta=lane_pb2.LaneMeta(
                    processing_time=processing_time
                ),
                current_lane=_to_proto_current_lane(current_lane),
            )

        except Exception as e:
            print("Lane gRPC Error:", e)
            return lane_pb2.LaneResponse()


def _to_proto_current_lane(current_lane):
    return lane_pb2.CurrentLane(
        available=current_lane.get("available", False),
        status=current_lane.get("status", ""),
        message=current_lane.get("message", ""),
        reference_y=current_lane.get("reference_y", 0.0),
        vehicle_center_x=current_lane.get("vehicle_center_x", 0.0),
        lane_center_x=current_lane.get("lane_center_x", 0.0),
        lane_width_px=current_lane.get("lane_width_px", 0.0),
        offset_px=current_lane.get("offset_px", 0.0),
        offset_ratio=current_lane.get("offset_ratio", 0.0),
        left_boundary=_to_proto_lane_boundary(current_lane.get("left_boundary")),
        right_boundary=_to_proto_lane_boundary(current_lane.get("right_boundary")),
        warning=current_lane.get("warning", False),
        warning_direction=current_lane.get("warning_direction", ""),
        warning_level=current_lane.get("warning_level", ""),
    )


def _to_proto_lane_boundary(boundary):
    if not boundary:
        return lane_pb2.LaneBoundary()

    return lane_pb2.LaneBoundary(
        class_name=boundary.get("class_name", ""),
        line=boundary.get("line", []),
        confidence=boundary.get("confidence", 0.0),
        x_at_reference=boundary.get("x_at_reference", 0.0),
    )
