import time
import cv2
import numpy as np

from debug.visual_logger import VisualLogger
from debug.event_logger import EventLogger

from app.services.sub_service.combined_sign_service import CombinedSignService
import proto.sign_pb2 as sign_pb2
import proto.sign_pb2_grpc as sign_pb2_grpc


_combined_service = CombinedSignService(ocr_gpu=True)


class SignService(sign_pb2_grpc.SignServiceServicer):

    def __init__(self):
        self.visual = VisualLogger()
        self.event_logger = EventLogger()

    def Predict(self, request, context):
        start_time = time.time()

        # decode image
        nparr = np.frombuffer(request.image, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            return sign_pb2.SignResponse()

        # predict
        output = _combined_service.predict(frame)

        # 🎨 draw
        debug_frame = self.visual.draw_sign(
            frame.copy(),
            output.detections
        )

        # 📸 save
        image_path = self.visual.save(debug_frame, "sign")

        # ⏱️ latency
        processing_time = time.time() - start_time

        # 🧾 log
        if len(output.detections) > 0:
            self.event_logger.log(
                "sign",
                image_path,
                {
                    "num_signs": len(output.detections),
                    "latency_ms": processing_time * 1000
                }
            )

        # response
        detections = [
            sign_pb2.Detection(
                box=det.box,
                confidence=det.confidence,
                class_id=det.class_id,
                class_name=det.combined_name,
            )
            for det in output.detections
        ]

        meta = output.meta
        return sign_pb2.SignResponse(
            detections=detections,
            meta=sign_pb2.Meta(
                start_time=meta.start_time,
                end_time=meta.end_time,
                duration_ms=meta.duration_ms,
            ),
        )