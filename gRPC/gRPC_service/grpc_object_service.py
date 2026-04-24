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
from app.services.collision_service import CollisionService


class ObjectService(object_pb2_grpc.ObjectServiceServicer):
    def __init__(self):
        self.tracker = TrackingService()
        self.speed_service = SpeedEstimationService()
        self.visual = VisualLogger()
        self.event_logger = EventLogger()
        self.collision_service = CollisionService()

    def Detect(self, request, context):
        start_time = time.time()

        try:
            # 1. Decode image từ bytes sang frame OpenCV
            np_arr = np.frombuffer(request.image, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            # print("image bytes:", len(request.image))


            if frame is None:
                return object_pb2.DetectResponse()

            # 2. Detect object trên frame
            detections = object_prediction(frame)

            # 3. Gán ID theo dõi object giữa các frame
            tracks = self.tracker.track(detections)

            # 4. Tính ego speed từ GPS
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

            # 5. Ước lượng speed cho từng object
            results = self.speed_service.estimate(tracks, ego_speed)

            # 6. Phân tích collision risk
            collision_result = self.collision_service.analyze(
                results,
                frame_shape=frame.shape,
                captured_at=request.captured_at
            )

            # 7. Map objects sang protobuf ObjectData
            objects = []
            for obj in collision_result["objects"]:
                objects.append(
                    object_pb2.ObjectData(
                        id=obj.get("id", 0),
                        label=obj.get("label", ""),
                        confidence=float(obj.get("confidence", 0.0)),
                        bbox=obj.get("bbox", []),
                        speed=float(obj.get("speed", 0.0)),
                        distance_m=float(obj.get("distance_m", 0.0) or 0.0),
                        ttc_s=float(obj.get("ttc_s", 0.0) or 0.0),
                        warning_level=obj.get("warning_level", ""),
                        warning_message=obj.get("warning_message", "")
                    )
                )

            # 8. Map warnings sang protobuf CollisionWarning
            warnings = []
            for w in collision_result["warnings"]:
                warnings.append(
                    object_pb2.CollisionWarning(
                        object_id=int(w.get("object_id", -1)),
                        label=w.get("label", ""),
                        confidence=float(w.get("confidence", 0.0)),
                        distance_m=float(w.get("distance_m", 0.0) or 0.0),
                        ttc_s=float(w.get("ttc_s", 0.0) or 0.0),
                        warning_level=w.get("warning_level", ""),
                        warning_message=w.get("warning_message", "")
                    )
                )

            # 9. Map summary sang protobuf CollisionSummary
            summary_data = collision_result["summary"]
            highest = summary_data.get("highest_risk_object") or {}

            summary = object_pb2.CollisionSummary(
                overall_level=summary_data.get("overall_level", "safe"),
                overall_message=summary_data.get("overall_message", "AN TOAN"),
                highest_risk_object_id=int(highest.get("object_id", -1)),
                highest_risk_label=highest.get("label", ""),
                highest_risk_distance_m=float(highest.get("distance_m", 0.0) or 0.0),
                highest_risk_ttc_s=float(highest.get("ttc_s", 0.0) or 0.0)
            )

            # 10. Trả response gRPC
            return object_pb2.DetectResponse(
                objects=objects,
                warnings=warnings,
                summary=summary,
                processing_time=time.time() - start_time
            )

        except Exception as e:
            print("Object gRPC Error:", e)
            return object_pb2.DetectResponse()
