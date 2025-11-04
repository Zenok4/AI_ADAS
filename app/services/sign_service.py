from matplotlib.pylab import det
import numpy as np
from app.services.model_loader import get_model

# Lấy model 'sign'
sign_info = get_model("sign")
model = sign_info["model"]
conf_threshold = sign_info["conf"]
iou_threshold = sign_info["iou"]


def sign_prediction(frame: np.ndarray, conf_threshold=0.5):
    results = model.predict(source=frame, conf=conf_threshold, iou=iou_threshold, verbose=False)[0]
    
    detections = []
    for box in results.boxes:
        cls_id = int(box.cls[0])
        detections.append({
            "box": box.xyxy[0].tolist(),  # Convert to regular list
            "confidence": float(box.conf[0]),
            "class_id": cls_id,
            "class_name": model.names[cls_id]
        })
        
    return detections