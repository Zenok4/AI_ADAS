import numpy as np

from app.config.settings import settings
from app.services.lane_opencv_service import detect_lane_lines
from app.utils.convert_classname import get_vietnamese_name


def lane_prediction(frame: np.ndarray, conf_threshold=None, iou_threshold=None, method=None):
    method = method or settings.MODELS.get("lane", {}).get("method", "opencv")

    if method == "opencv":
        return detect_lane_lines(frame)
    if method == "ufldv2":
        from app.services.lane_ufldv2_service import detect_lane_lines_ufldv2

        detections = detect_lane_lines_ufldv2(frame)
        if detections:
            return detections
        return detect_lane_lines(frame)

    from app.services.model_loader import get_model
    from app.utils.run_predict import run_prediction

    lane_info = get_model("lane")
    lane_info = {
        **lane_info,
        "conf": conf_threshold or lane_info["conf"],
        "iou": iou_threshold or lane_info["iou"],
    }

    results = run_prediction(lane_info, frame)

    detections = []
    for box in results.boxes:
        cls_id = int(box.cls[0])
        vietnamese_label = get_vietnamese_name(cls_id, model_type="lane")
        detections.append(
            {
                "box": box.xyxy[0].tolist(),
                "confidence": float(box.conf[0]),
                "class_id": cls_id,
                "class_name": vietnamese_label,
                "method": "yolo",
            }
        )

    return detections
