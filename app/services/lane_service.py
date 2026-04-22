import numpy as np
from app.services.model_loader import get_model
from app.utils.convert_classname import get_vietnamese_name
from app.utils.run_predict import run_prediction

def lane_prediction(frame: np.ndarray, conf_threshold=None, iou_threshold=None):
    # Lấy model lane đã load (cần cấu hình thêm trong model_loader.py)
    lane_info = get_model("lane")
    conf_threshold = conf_threshold or lane_info["conf"]
    iou_threshold = iou_threshold or lane_info["iou"]

    results = run_prediction(lane_info, frame)

    detections = []
    # Lưu ý: Nếu model lane là Segmentation, cần xử lý results.masks thay vì results.boxes
    for box in results.boxes:
        cls_id = int(box.cls[0])
        vietnamese_label = get_vietnamese_name(cls_id, model_type='lane')
        detections.append({
            "box": box.xyxy[0].tolist(),
            "confidence": float(box.conf[0]),
            "class_id": cls_id,
            "class_name": vietnamese_label
        })
    return detections