import numpy as np
from app.services.model_loader import get_model
from app.utils.convert_classname import get_vietnamese_name
from app.utils.run_predict import run_prediction
from app.middleware.roi_filter import apply_roi, patch_detections
from app.config.settings import settings
from app.services.sub_service.lane_departure import LaneDepartureAnalyzer, build_lane_departure_config

# Khởi tạo analyzer một lần duy nhất (dùng cấu hình từ settings nếu có)
_ldw_cfg = build_lane_departure_config(
    getattr(settings, "LANE_DEPARTURE", None)
)
_analyzer = LaneDepartureAnalyzer(
    offset_threshold=_ldw_cfg["offset_threshold"],
    min_confidence=_ldw_cfg["min_confidence"],
    stable_frames_required=_ldw_cfg["stable_frames_required"],
)


def lane_prediction(frame: np.ndarray, conf_threshold=None, iou_threshold=None):
    """
    Nhận diện vạch làn đường và phân tích lệch làn.

    Returns
    -------
    dict với 2 key:
      - "detections"     : list các vạch phát hiện được (tọa độ hệ gốc)
      - "lane_departure" : dict kết quả phân tích lệch làn
    """
    lane_info = get_model("lane")
    conf_threshold = conf_threshold or lane_info["conf"]
    iou_threshold = iou_threshold or lane_info["iou"]

    # Lưu kích thước frame gốc trước khi crop
    orig_h, orig_w = frame.shape[:2]

    # Áp dụng ROI
    roi_frame, ctx = apply_roi(frame, settings.ROI["lane"])

    results = run_prediction(lane_info, roi_frame)

    detections = []
    for box in results.boxes:
        cls_id = int(box.cls[0])
        vietnamese_label = get_vietnamese_name(cls_id, model_type='lane')
        detections.append({
            "box": box.xyxy[0].tolist(),
            "confidence": float(box.conf[0]),
            "class_id": cls_id,
            "class_name": vietnamese_label
        })

    # Dịch tọa độ về hệ gốc nếu đã crop
    detections = patch_detections(detections, ctx)

    # Phân tích lệch làn dựa trên tọa độ hệ gốc
    ldw_result = _analyzer.analyze(detections, orig_w, orig_h)

    return {
        "detections": detections,
        "lane_departure": {
            "status": ldw_result.status,
            "message": ldw_result.message,
            "lane_offset": ldw_result.lane_offset,
            "left_lane": ldw_result.left_lane,
            "right_lane": ldw_result.right_lane,
        }
    }
