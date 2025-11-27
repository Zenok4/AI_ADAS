import numpy as np
import time
import logging
from datetime import datetime
from app.services.model_loader import get_model

logger = logging.getLogger(__name__)

def sign_prediction(frame: np.ndarray, conf_threshold=None, iou_threshold=None):
    sign_info = get_model("sign")
    model = sign_info["model"]
    conf_threshold = conf_threshold or sign_info["conf"]
    iou_threshold = iou_threshold or sign_info["iou"]

    start_ts = datetime.now().isoformat()
    start = time.perf_counter()
    logger.debug(f"sign_prediction start: {start_ts}")

    results = model.predict(source=frame, conf=conf_threshold, iou=iou_threshold, verbose=False)[0]

    detections = []
    for box in results.boxes:
        cls_id = int(box.cls[0])
        detections.append({
            "box": box.xyxy[0].tolist(),
            "confidence": float(box.conf[0]),
            "class_id": cls_id,
            "class_name": model.names[cls_id]
        })

    end = time.perf_counter()
    end_ts = datetime.now().isoformat()
    duration_ms = (end - start) * 1000.0
    logger.info(
        f"sign_prediction finished: start={start_ts}, end={end_ts}, "
        f"duration_ms={duration_ms:.2f}, detections={len(detections)}"
    )

    detections.append({
        "meta": {
            "start_time": start_ts,
            "end_time": end_ts,
            "duration_ms": duration_ms
        }
    })

    return detections
