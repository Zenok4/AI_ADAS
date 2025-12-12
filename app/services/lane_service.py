import numpy as np
from app.services.model_loader import get_model

def lane_prediction(frame: np.ndarray, conf_threshold=None, iou_threshold=None):
    # Lấy model lane đã load (cần cấu hình thêm trong model_loader.py)
    lane_info = get_model("lane") 
    model = lane_info["model"]
    conf_threshold = conf_threshold or lane_info["conf"]
    iou_threshold = iou_threshold or lane_info["iou"]

    results = model.predict(
        source=frame, 
        conf=conf_threshold, 
        iou=iou_threshold, 
        verbose=False,
        half=True,
        imgsz=640,
        max_det=5,
        agnostic_nms=True
        )[0]

    detections = []
    # Lưu ý: Nếu model lane là Segmentation, cần xử lý results.masks thay vì results.boxes
    for box in results.boxes:
        cls_id = int(box.cls[0])
        detections.append({
            "box": box.xyxy[0].tolist(),
            "confidence": float(box.conf[0]),
            "class_id": cls_id,
            "class_name": model.names[cls_id]
        })
    return detections