import time
import cv2
import numpy as np

from debug.visual_logger import VisualLogger
from debug.event_logger import EventLogger

import proto.lane_pb2 as lane_pb2
import proto.lane_pb2_grpc as lane_pb2_grpc

from app.services.lane_service import lane_prediction


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
                )
            )

        except Exception as e:
            print("Lane gRPC Error:", e)
            return lane_pb2.LaneResponse()
