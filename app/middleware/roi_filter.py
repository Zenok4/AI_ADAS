"""
app/middleware/roi_filter.py

Module giới hạn vùng nhận diện (Region of Interest - ROI) cho các module AI.

Hỗ trợ 2 chế độ:
  - "crop"  : Cắt frame theo vùng ROI, trả về ảnh nhỏ hơn.
              Tọa độ box trong kết quả sẽ được dịch ngược về hệ tọa độ gốc.
  - "mask"  : Giữ nguyên kích thước frame, vùng ngoài ROI bị tô đen.
              Tọa độ box giữ nguyên hệ tọa độ gốc.

Cấu hình trong config.yaml:
  roi:
    sign:
      enabled: true
      mode: crop          # "crop" | "mask"
      x1: 0.0             # tỉ lệ (0.0 – 1.0) hoặc pixel (int > 1)
      y1: 0.0
      x2: 1.0
      y2: 0.5
    object:
      enabled: true
      mode: mask
      x1: 0
      y1: 100
      x2: 1280
      y2: 720
    lane:
      enabled: false
    drowsy:
      enabled: false
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple, Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ROIConfig:
    enabled: bool = False
    mode: str = "crop"          # "crop" | "mask"
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 1.0
    y2: float = 1.0


@dataclass
class ROIContext:
    """Thông tin offset để dịch tọa độ box về hệ gốc (dùng khi mode='crop')."""
    offset_x: int = 0
    offset_y: int = 0
    original_shape: Tuple[int, int] = (0, 0)   # (height, width)
    cropped_shape: Tuple[int, int] = (0, 0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_coord(value: float, dim: int) -> int:
    """
    Chuyển giá trị tọa độ về pixel.
    - Nếu 0 < value <= 1  → coi là tỉ lệ, nhân với dim.
    - Nếu value > 1        → coi là pixel tuyệt đối.
    """
    if 0.0 < value <= 1.0:
        return int(value * dim)
    return int(value)


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def apply_roi(frame: np.ndarray, cfg: ROIConfig) -> Tuple[np.ndarray, ROIContext]:
    """
    Áp dụng ROI lên frame.

    Returns:
        processed_frame : frame đã được crop/mask
        ctx             : ROIContext để dịch tọa độ về sau
    """
    if not cfg.enabled:
        h, w = frame.shape[:2]
        return frame, ROIContext(original_shape=(h, w), cropped_shape=(h, w))

    h, w = frame.shape[:2]

    x1 = _clamp(_resolve_coord(cfg.x1, w), 0, w)
    y1 = _clamp(_resolve_coord(cfg.y1, h), 0, h)
    x2 = _clamp(_resolve_coord(cfg.x2, w), 0, w)
    y2 = _clamp(_resolve_coord(cfg.y2, h), 0, h)

    # Đảm bảo x1 < x2, y1 < y2
    x1, x2 = min(x1, x2), max(x1, x2)
    y1, y2 = min(y1, y2), max(y1, y2)

    ctx = ROIContext(
        offset_x=x1,
        offset_y=y1,
        original_shape=(h, w),
        cropped_shape=(y2 - y1, x2 - x1),
    )

    if cfg.mode == "crop":
        processed = frame[y1:y2, x1:x2].copy()
    else:  # mask
        processed = frame.copy()
        # Tô đen vùng ngoài ROI
        mask = np.zeros((h, w), dtype=np.uint8)
        mask[y1:y2, x1:x2] = 255
        processed[mask == 0] = 0

    return processed, ctx


def restore_boxes_xyxy(boxes: List[List[float]], ctx: ROIContext) -> List[List[float]]:
    """
    Dịch tọa độ [x1,y1,x2,y2] từ hệ tọa độ crop về hệ tọa độ gốc.
    Chỉ cần thiết khi mode='crop'.
    """
    if ctx.offset_x == 0 and ctx.offset_y == 0:
        return boxes
    restored = []
    for box in boxes:
        x1, y1, x2, y2 = box
        restored.append([
            x1 + ctx.offset_x,
            y1 + ctx.offset_y,
            x2 + ctx.offset_x,
            y2 + ctx.offset_y,
        ])
    return restored


def restore_bbox(bbox: List[int], ctx: ROIContext) -> List[int]:
    """Dịch tọa độ [x1,y1,x2,y2] dạng int (dùng cho object_service)."""
    if ctx.offset_x == 0 and ctx.offset_y == 0:
        return bbox
    x1, y1, x2, y2 = bbox
    return [x1 + ctx.offset_x, y1 + ctx.offset_y, x2 + ctx.offset_x, y2 + ctx.offset_y]


# ---------------------------------------------------------------------------
# Detection result patching
# ---------------------------------------------------------------------------

def patch_detections(detections: List[Dict[str, Any]], ctx: ROIContext) -> List[Dict[str, Any]]:
    """
    Dịch tọa độ trong danh sách detections về hệ tọa độ gốc.
    Tự động nhận diện key 'box' (list 4 float) hoặc 'bbox' (list 4 int).
    Bỏ qua các dict chứa key 'meta'.
    """
    if ctx.offset_x == 0 and ctx.offset_y == 0:
        return detections

    patched = []
    for det in detections:
        if "meta" in det:
            patched.append(det)
            continue
        det = dict(det)
        if "box" in det:
            det["box"] = restore_boxes_xyxy([det["box"]], ctx)[0]
        if "bbox" in det:
            det["bbox"] = restore_bbox(det["bbox"], ctx)
        patched.append(det)
    return patched


# ---------------------------------------------------------------------------
# Config builder
# ---------------------------------------------------------------------------

def build_roi_config(raw: Optional[Dict[str, Any]]) -> ROIConfig:
    """Tạo ROIConfig từ dict đọc trong config.yaml."""
    if not raw or not raw.get("enabled", False):
        return ROIConfig(enabled=False)
    return ROIConfig(
        enabled=True,
        mode=raw.get("mode", "crop"),
        x1=float(raw.get("x1", 0.0)),
        y1=float(raw.get("y1", 0.0)),
        x2=float(raw.get("x2", 1.0)),
        y2=float(raw.get("y2", 1.0)),
    )
