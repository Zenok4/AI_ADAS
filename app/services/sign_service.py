import numpy as np
import time
import logging
from datetime import datetime
from app.services.model_loader import get_model
from app.utils.convert_classname import get_vietnamese_name
from app.utils.run_predict import run_prediction
from app.middleware.roi_filter import apply_roi, patch_detections
from app.config.settings import settings

logger = logging.getLogger(__name__)

def sign_prediction(frame: np.ndarray, conf_threshold=None, iou_threshold=None):
    # load model and config
    model_info = get_model("sign")

    start_ts = datetime.now().isoformat()
    start = time.perf_counter()
    logger.debug(f"sign_prediction start: {start_ts}")

    # Áp dụng ROI
    roi_frame, ctx = apply_roi(frame, settings.ROI["sign"])

    results = run_prediction(model_info, roi_frame)

    detections = []
    
    for box in results.boxes:
        cls_id = int(box.cls[0])
        sign_name_vi = get_vietnamese_name(cls_id, model_type='sign')
        detections.append({
            "box": box.xyxy[0].tolist(),
            "confidence": float(box.conf[0]),
            "class_id": cls_id,
            "class_name": sign_name_vi
        })

    # Dịch tọa độ về hệ gốc nếu đã crop
    detections = patch_detections(detections, ctx)

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
