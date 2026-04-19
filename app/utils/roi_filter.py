"""
ROI (Region of Interest) Filter Middleware
Giới hạn vùng nhận diện cho từng module AI.

Coordinate system:
  - x: 0.0 (trái) -> 1.0 (phải)  [tỉ lệ theo chiều ngang]
  - y: 0.0 (trên) -> 1.0 (dưới)  [tỉ lệ theo chiều dọc]

Mỗi ROI được định nghĩa bằng (x_min, y_min, x_max, y_max) theo tỉ lệ.
"""

import numpy as np
import cv2
from typing import List, Dict, Tuple, Optional

# ─────────────────────────────────────────────
# Định nghĩa ROI mặc định cho từng module
# ─────────────────────────────────────────────

# Biển báo: vùng trung tâm phía trước (bỏ 2 bên đường, chỉ lấy 60% giữa, nửa trên)
SIGN_ROI = (0.20, 0.0, 0.80, 0.65)

# Vật cản: làn đường phía trước (dải giữa 50%, nửa dưới đến cuối)
OBJECT_ROI = (0.25, 0.35, 0.75, 1.0)

# Drowsy: toàn frame (không giới hạn)
DROWSY_ROI = (0.0, 0.0, 1.0, 1.0)

ROI_PRESETS: Dict[str, Tuple[float, float, float, float]] = {
    "sign": SIGN_ROI,
    "object": OBJECT_ROI,
    "drowsy": DROWSY_ROI,
}


# ─────────────────────────────────────────────
# Core functions
# ─────────────────────────────────────────────

def get_roi_pixels(frame: np.ndarray, roi: Tuple[float, float, float, float]) -> Tuple[int, int, int, int]:
    """Chuyển ROI tỉ lệ -> tọa độ pixel thực tế."""
    h, w = frame.shape[:2]
    x_min, y_min, x_max, y_max = roi
    return (
        int(x_min * w),
        int(y_min * h),
        int(x_max * w),
        int(y_max * h),
    )


def crop_roi(frame: np.ndarray, roi: Tuple[float, float, float, float]) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
    """
    Cắt frame theo ROI.
    Trả về: (cropped_frame, (px1, py1, px2, py2)) để dùng khi remap box về tọa độ gốc.
    """
    px1, py1, px2, py2 = get_roi_pixels(frame, roi)
    cropped = frame[py1:py2, px1:px2]
    return cropped, (px1, py1, px2, py2)


def remap_boxes(detections: List[Dict], offset: Tuple[int, int, int, int]) -> List[Dict]:
    """
    Dịch chuyển tọa độ box từ hệ tọa độ cropped -> hệ tọa độ frame gốc.
    offset = (px1, py1, px2, py2) từ crop_roi.
    """
    px1, py1 = offset[0], offset[1]
    remapped = []
    for det in detections:
        if "box" not in det:
            # Giữ nguyên các entry meta (vd: timing info)
            remapped.append(det)
            continue
        x1, y1, x2, y2 = det["box"]
        remapped.append({
            **det,
            "box": [x1 + px1, y1 + py1, x2 + px1, y2 + py1],
        })
    return remapped


def filter_detections_by_roi(
    detections: List[Dict],
    frame_shape: Tuple[int, int],
    roi: Tuple[float, float, float, float],
) -> List[Dict]:
    """
    Lọc các detection có tâm box nằm trong ROI (dùng khi không crop trước).
    frame_shape = (height, width).
    """
    h, w = frame_shape[:2]
    x_min, y_min, x_max, y_max = roi
    filtered = []
    for det in detections:
        if "box" not in det:
            filtered.append(det)
            continue
        x1, y1, x2, y2 = det["box"]
        cx = ((x1 + x2) / 2) / w
        cy = ((y1 + y2) / 2) / h
        if x_min <= cx <= x_max and y_min <= cy <= y_max:
            filtered.append(det)
    return filtered


def draw_roi(frame: np.ndarray, roi: Tuple[float, float, float, float], label: str = "", color=(0, 255, 255)) -> np.ndarray:
    """Vẽ vùng ROI lên frame để debug/visualize."""
    px1, py1, px2, py2 = get_roi_pixels(frame, roi)
    overlay = frame.copy()
    cv2.rectangle(overlay, (px1, py1), (px2, py2), color, 2)
    # Tô mờ vùng ngoài ROI
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    mask[py1:py2, px1:px2] = 255
    darkened = (frame * 0.4).astype(np.uint8)
    result = np.where(mask[:, :, np.newaxis] == 255, frame, darkened)
    cv2.rectangle(result, (px1, py1), (px2, py2), color, 2)
    if label:
        cv2.putText(result, f"ROI: {label}", (px1 + 4, py1 + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    return result


# ─────────────────────────────────────────────
# Middleware class
# ─────────────────────────────────────────────

class ROIMiddleware:
    """
    Middleware giới hạn vùng nhận diện cho các module AI.

    Cách dùng:
        roi_mw = ROIMiddleware()

        # Crop trước khi predict (khuyến nghị - nhanh hơn)
        cropped, offset = roi_mw.crop("sign", frame)
        detections = sign_prediction(cropped)
        detections = roi_mw.remap("sign", detections, offset)

        # Hoặc filter sau khi predict
        detections = sign_prediction(frame)
        detections = roi_mw.filter("sign", detections, frame.shape)
    """

    def __init__(self, custom_rois: Optional[Dict[str, Tuple[float, float, float, float]]] = None):
        self.rois = {**ROI_PRESETS, **(custom_rois or {})}

    def get_roi(self, module: str) -> Tuple[float, float, float, float]:
        return self.rois.get(module, (0.0, 0.0, 1.0, 1.0))

    def crop(self, module: str, frame: np.ndarray) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
        """Crop frame theo ROI của module. Trả về (cropped, offset)."""
        return crop_roi(frame, self.get_roi(module))

    def remap(self, module: str, detections: List[Dict], offset: Tuple[int, int, int, int]) -> List[Dict]:
        """Remap tọa độ box từ cropped -> frame gốc."""
        return remap_boxes(detections, offset)

    def filter(self, module: str, detections: List[Dict], frame_shape: Tuple[int, int]) -> List[Dict]:
        """Filter detection theo ROI (dùng khi không crop trước)."""
        return filter_detections_by_roi(detections, frame_shape, self.get_roi(module))

    def set_roi(self, module: str, roi: Tuple[float, float, float, float]):
        """Cập nhật ROI động cho một module."""
        x_min, y_min, x_max, y_max = roi
        assert 0.0 <= x_min < x_max <= 1.0, "x_min/x_max phải trong [0,1]"
        assert 0.0 <= y_min < y_max <= 1.0, "y_min/y_max phải trong [0,1]"
        self.rois[module] = roi

    def visualize(self, module: str, frame: np.ndarray) -> np.ndarray:
        """Vẽ ROI lên frame để debug."""
        return draw_roi(frame, self.get_roi(module), label=module)


# Singleton dùng chung toàn app - load ROI từ config.yaml nếu có
def _load_roi_from_config():
    try:
        from app.config.settings import settings
        if settings.ROI:
            return settings.ROI
    except Exception:
        pass
    return {}

roi_middleware = ROIMiddleware(custom_rois=_load_roi_from_config())
