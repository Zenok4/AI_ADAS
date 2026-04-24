import time
import cv2
import numpy as np

from debug.visual_logger import VisualLogger
from debug.event_logger import EventLogger

import proto.object_pb2 as object_pb2
import proto.object_pb2_grpc as object_pb2_grpc

from app.services.object_service import object_prediction
from app.services.sub_service.tracking_service import TrackingService
from app.services.sub_service.speed_service import SpeedEstimationService


class ObjectService(object_pb2_grpc.ObjectServiceServicer):

    def __init__(self):
        self.tracker = TrackingService()
        self.speed_service = SpeedEstimationService()
        self.visual = VisualLogger()
        self.event_logger = EventLogger()

    def Detect(self, request, context):
        start_time = time.time()

        try:
            # decode image
            np_arr = np.frombuffer(request.image, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if frame is None:
                return object_pb2.DetectResponse()

            # detection
            detections = object_prediction(frame)

            # tracking
            tracks = self.tracker.track(detections)

            # ego speed
            ego_speed = self.speed_service.compute_ego_speed(
                lat=request.latitude,
                lon=request.longitude,
                captured_at=request.captured_at
            )

            # speed estimation
            results = self.speed_service.estimate(tracks, ego_speed)

            # 🎨 draw (đã chuyển vào VisualLogger)
            debug_frame = self.visual.draw_object(
                frame.copy(),
                results,
                ego_speed
            )

            # 📸 save
            image_path = self.visual.save(debug_frame, "object")

            # ⏱️ latency
            processing_time = time.time() - start_time

            # 🧾 log
            if len(results) > 0:
                self.event_logger.log(
                    "object",
                    image_path,
                    {
                        "num_objects": len(results),
                        "ego_speed": ego_speed,
                        "latency_ms": processing_time * 1000
                    }
                )

            # response
            objects = [
                object_pb2.ObjectData(
                    id=obj["id"],
                    label=obj.get("label", ""),
                    confidence=obj.get("confidence", 0),
                    bbox=obj["bbox"],
                    speed=obj["speed"]
                )
                for obj in results
            ]

            return object_pb2.DetectResponse(
                objects=objects,
                processing_time=processing_time
            )

        except Exception as e:
            print("Object gRPC Error:", e)
            return object_pb2.DetectResponse()