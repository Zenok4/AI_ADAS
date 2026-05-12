"""
app/services/sub_service/lane_departure.py

Module phân tích lệch làn đường (Lane Departure Warning - LDW).

Logic:
  1. Nhận danh sách detections từ YOLO lane model (các vạch kẻ đường).
  2. Phân loại vạch TRÁI / PHẢI dựa trên vị trí tâm box so với tâm frame.
  3. Tính vị trí tương đối của xe trong làn (lane_offset):
       - 0.0  = chính giữa làn
       - < 0  = lệch trái
       - > 0  = lệch phải
  4. So sánh với ngưỡng cảnh báo → trả về trạng thái và thông điệp.
  5. FrameStabilizer chống cảnh báo nhấp nháy: chỉ phát cảnh báo khi
     lệch N frame liên tiếp.

Cấu hình trong config.yaml:
  lane_departure:
    enabled: true
    offset_threshold: 0.2     # 0.0–1.0, tỉ lệ so với nửa chiều rộng frame
    min_confidence: 0.4       # bỏ qua vạch có confidence thấp hơn
    stable_frames_required: 5 # số frame lệch liên tiếp trước khi cảnh báo
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple


# ---------------------------------------------------------------------------
# Các class ID được coi là vạch làn đường (loại trừ mũi tên hướng đi)
# ---------------------------------------------------------------------------
LANE_MARKING_CLASS_IDS = {0, 1, 2, 3, 4, 5, 8, 9}   # bỏ 6, 7, 10 (mũi tên)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class LaneSide:
    """Thông tin một bên vạch (trái hoặc phải)."""
    detections: List[Dict[str, Any]] = field(default_factory=list)
    # Tọa độ X cạnh trong cùng (gần tâm xe nhất), set sau khi phân loại
    inner_x: Optional[float] = field(default=None, init=False)

    @property
    def found(self) -> bool:
        return len(self.detections) > 0

    @property
    def best(self) -> Optional[Dict[str, Any]]:
        """Vạch có confidence cao nhất."""
        if not self.detections:
            return None
        return max(self.detections, key=lambda d: d["confidence"])


@dataclass
class LaneDepartureResult:
    """Kết quả phân tích lệch làn."""
    status: str             # "normal" | "warning_left" | "warning_right" | "no_lane"
    message: str            # Thông điệp tiếng Việt
    lane_offset: float      # -1.0 (trái) … 0.0 (giữa) … +1.0 (phải)
    left_lane: Optional[Dict]   # Vạch trái tốt nhất (hoặc None)
    right_lane: Optional[Dict]  # Vạch phải tốt nhất (hoặc None)
    frame_width: int
    frame_height: int


# ---------------------------------------------------------------------------
# Frame Stabilizer — chống cảnh báo nhấp nháy
# ---------------------------------------------------------------------------

class FrameStabilizer:
    """
    Chỉ phát cảnh báo khi trạng thái lệch xuất hiện liên tiếp
    đủ số frame yêu cầu. Reset về 0 khi trạng thái trở về "normal"
    hoặc "no_lane".

    Parameters
    ----------
    required : int
        Số frame lệch liên tiếp tối thiểu trước khi xác nhận cảnh báo.
    """

    def __init__(self, required: int = 5):
        self.required = required
        self._count: int = 0
        self._last_raw: str = "normal"

    def update(self, raw_status: str) -> str:
        """
        Nhận raw_status từ analyzer, trả về status đã được ổn định.

        - Nếu raw_status là cảnh báo và đếm đủ required → trả cảnh báo.
        - Nếu raw_status là normal/no_lane → reset đếm, trả nguyên.
        """
        is_warning = raw_status in ("warning_left", "warning_right")

        if is_warning:
            if raw_status == self._last_raw:
                self._count += 1
            else:
                # Đổi hướng cảnh báo → reset đếm
                self._count = 1
                self._last_raw = raw_status

            if self._count >= self.required:
                return raw_status
            else:
                # Chưa đủ frame → coi như normal (đang tích lũy)
                return "normal"
        else:
            self._count = 0
            self._last_raw = raw_status
            return raw_status

    def reset(self):
        self._count = 0
        self._last_raw = "normal"


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class LaneDepartureAnalyzer:
    """
    Phân tích lệch làn từ danh sách detections của YOLO lane model.

    Parameters
    ----------
    offset_threshold : float
        Ngưỡng lệch (0.0–1.0) tính theo tỉ lệ nửa chiều rộng frame.
        Ví dụ 0.2 → cảnh báo khi xe lệch > 20% nửa chiều rộng.
    min_confidence : float
        Bỏ qua vạch có confidence thấp hơn ngưỡng này.
    stable_frames_required : int
        Số frame lệch liên tiếp trước khi phát cảnh báo thực sự.
    """

    def __init__(
        self,
        offset_threshold: float = 0.2,
        min_confidence: float = 0.4,
        stable_frames_required: int = 5,
    ):
        self.offset_threshold = offset_threshold
        self.min_confidence = min_confidence
        self._stabilizer = FrameStabilizer(required=stable_frames_required)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        detections: List[Dict[str, Any]],
        frame_width: int,
        frame_height: int,
    ) -> LaneDepartureResult:
        """
        Phân tích danh sách detections và trả về LaneDepartureResult.

        Parameters
        ----------
        detections   : list of dict với keys 'box', 'confidence', 'class_id'
        frame_width  : chiều rộng frame gốc (pixel)
        frame_height : chiều cao frame gốc (pixel)
        """
        cx_frame = frame_width / 2.0

        # 1. Lọc chỉ lấy vạch làn đường, bỏ mũi tên & confidence thấp
        lane_dets = [
            d for d in detections
            if d.get("class_id") in LANE_MARKING_CLASS_IDS
            and d.get("confidence", 0) >= self.min_confidence
        ]

        if not lane_dets:
            stable_status = self._stabilizer.update("no_lane")
            return LaneDepartureResult(
                status=stable_status,
                message="Không phát hiện vạch làn đường",
                lane_offset=0.0,
                left_lane=None,
                right_lane=None,
                frame_width=frame_width,
                frame_height=frame_height,
            )

        # 2. Phân loại trái / phải theo tâm box so với tâm frame
        left_side = LaneSide()
        right_side = LaneSide()

        for det in lane_dets:
            box = det["box"]          # [x1, y1, x2, y2]
            box_cx = (box[0] + box[2]) / 2.0
            if box_cx <= cx_frame:
                left_side.detections.append(det)
            else:
                right_side.detections.append(det)

        # 3. Lấy cạnh trong của mỗi bên (gần tâm xe nhất)
        #    Vạch trái  → cạnh phải của box (x2) là cạnh gần tâm nhất
        #    Vạch phải → cạnh trái của box (x1) là cạnh gần tâm nhất
        if left_side.found and left_side.best:
            left_side.inner_x = left_side.best["box"][2]   # x2

        if right_side.found and right_side.best:
            right_side.inner_x = right_side.best["box"][0]  # x1

        # 4. Tính lane_offset thô
        raw_offset, raw_status, message = self._compute_offset(
            cx_frame, left_side.inner_x, right_side.inner_x, frame_width
        )

        # 5. Ổn định qua FrameStabilizer
        stable_status = self._stabilizer.update(raw_status)

        # Nếu stabilizer hạ cấp cảnh báo → cập nhật message
        if stable_status == "normal" and raw_status != "normal":
            message = "✅ Xe đang đi đúng làn"

        return LaneDepartureResult(
            status=stable_status,
            message=message,
            lane_offset=round(raw_offset, 4),
            left_lane=left_side.best,
            right_lane=right_side.best,
            frame_width=frame_width,
            frame_height=frame_height,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_offset(
        self,
        cx_frame: float,
        left_x: Optional[float],
        right_x: Optional[float],
        frame_width: int,
    ) -> Tuple[float, str, str]:
        """
        Tính lane_offset và xác định trạng thái thô (chưa qua stabilizer).

        Quy ước lane_offset:
          - âm  → xe lệch về phía trái làn
          - 0   → xe ở giữa làn
          - dương → xe lệch về phía phải làn

        Returns: (lane_offset, status, message)
        """
        half_w = frame_width / 2.0

        # --- Cả hai bên đều có vạch (trường hợp tốt nhất) ---
        if left_x is not None and right_x is not None:
            lane_center = (left_x + right_x) / 2.0
            # cx_frame > lane_center → xe lệch phải → offset dương
            lane_offset = (cx_frame - lane_center) / half_w

            if lane_offset < -self.offset_threshold:
                return lane_offset, "warning_left", "⚠️ Cảnh báo: Xe đang lệch sang trái"
            elif lane_offset > self.offset_threshold:
                return lane_offset, "warning_right", "⚠️ Cảnh báo: Xe đang lệch sang phải"
            else:
                return lane_offset, "normal", "✅ Xe đang đi đúng làn"

        # --- Chỉ có vạch trái ---
        elif left_x is not None:
            # dist_left: khoảng cách từ vạch trái đến tâm xe
            # Bình thường dist_left ≈ half_w * 0.5 (vạch ở 1/4 trái frame)
            # Nếu dist_left nhỏ → xe đang tiến gần vạch trái → lệch trái
            dist_left = cx_frame - left_x
            # offset âm = lệch trái, chuẩn hóa về [-1, 0]
            lane_offset = -(1.0 - dist_left / half_w)

            if dist_left < half_w * (1.0 - self.offset_threshold):
                return lane_offset, "warning_left", "⚠️ Cảnh báo: Xe đang lệch sang trái (chỉ thấy vạch trái)"
            return lane_offset, "normal", "✅ Phát hiện vạch trái – đang theo dõi"

        # --- Chỉ có vạch phải ---
        elif right_x is not None:
            # dist_right: khoảng cách từ tâm xe đến vạch phải
            # Nếu dist_right nhỏ → xe đang tiến gần vạch phải → lệch phải
            dist_right = right_x - cx_frame
            # offset dương = lệch phải, chuẩn hóa về [0, 1]
            lane_offset = 1.0 - dist_right / half_w

            if dist_right < half_w * (1.0 - self.offset_threshold):
                return lane_offset, "warning_right", "⚠️ Cảnh báo: Xe đang lệch sang phải (chỉ thấy vạch phải)"
            return lane_offset, "normal", "✅ Phát hiện vạch phải – đang theo dõi"

        # --- Fallback (không bao giờ xảy ra vì đã lọc ở trên) ---
        return 0.0, "no_lane", "Không phát hiện vạch làn đường"


# ---------------------------------------------------------------------------
# Config builder
# ---------------------------------------------------------------------------

def build_lane_departure_config(raw: Optional[Dict]) -> Dict:
    """Đọc cấu hình lane_departure từ config.yaml."""
    if not raw:
        return {
            "enabled": True,
            "offset_threshold": 0.2,
            "min_confidence": 0.4,
            "stable_frames_required": 5,
        }
    return {
        "enabled": raw.get("enabled", True),
        "offset_threshold": float(raw.get("offset_threshold", 0.2)),
        "min_confidence": float(raw.get("min_confidence", 0.4)),
        "stable_frames_required": int(raw.get("stable_frames_required", 5)),
    }
