from matplotlib.pylab import det
import numpy as np
from ultralytics import YOLO
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(BASE_DIR, "../../models/sign/best.pt")
model = YOLO(model_path)


def sign_prediction(frame: np.ndarray, conf_threshold=0.5):
    results = model.predict(source=frame, conf=conf_threshold, verbose=False)[0]
    
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