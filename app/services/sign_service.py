import numpy as np
from app.services.model_loader import get_model

def sign_prediction(frame: np.ndarray, conf_threshold=None, iou_threshold=None):
    sign_info = get_model("sign")
    model = sign_info["model"]
    conf_threshold = conf_threshold or sign_info["conf"]
    iou_threshold = iou_threshold or sign_info["iou"]

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
    return detections
