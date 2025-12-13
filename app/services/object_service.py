import numpy as np
from app.services.model_loader import get_model

def object_prediction(frame: np.ndarray, conf_threshold=None, iou_threshold=None):
    """
    Hàm xử lý dự đoán vật cản (Object Detection)
    Input: Frame ảnh (OpenCV numpy array)
    Output: List các object detect được
    """
    model_info = get_model("object")
    model = model_info["model"]

    conf_threshold = conf_threshold or model_info.get("conf", 0.40)
    iou_threshold = iou_threshold or model_info.get("iou", 0.45)

    results = model.predict(
        source=frame,
        conf=conf_threshold,
        iou=iou_threshold,
        verbose=False,
        half=True,         
        imgsz=640,         
        max_det=20,         
        agnostic_nms=True   
    )[0]

    detections = []

    if results.boxes:
        for box in results.boxes:
            cls_id = int(box.cls[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            
            detections.append({
                "box": [int(x1), int(y1), int(x2), int(y2)],
                "confidence": round(float(box.conf[0]), 2),
                "class_id": cls_id,
                "class_name": model.names[cls_id]
            })
            
    return detections