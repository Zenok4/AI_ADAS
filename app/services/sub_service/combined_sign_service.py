"""
app/services/combined_sign_service.py

Service post-processing độc lập — cùng process với sign service.
Luồng:
  1. Gọi sign_prediction(frame) trực tiếp.
  2. Tách meta ra khỏi danh sách detections.
  3. Phân loại biển chính / biển phụ, ghép cặp theo vị trí không gian.
  4. Crop vùng biển phụ → EasyOCR → parse thời gian / khoảng cách / loại xe.
  5. Ghép tên hiển thị theo template.
  6. Trả về CombinedSignOutput.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import easyocr
import numpy as np

from app.services.sign_service import sign_prediction
from app.services.sub_service.sign_ocr_parser import parse_sub_sign_text
from app.services.sub_service.sign_name_builder import build_combined_name

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SubSignResult:
    box: list[float]
    confidence: float
    class_id: int
    class_name: str
    ocr_text: str               = ""
    time_range: Optional[str]   = None       # range đầu tiên (backward-compat)
    time_ranges: list[str]      = field(default_factory=list)  # tất cả ranges
    distance: Optional[str]     = None
    vehicle_type: Optional[str] = None


@dataclass
class CombinedDetection:
    box: list[float]
    confidence: float
    class_id: int
    class_name: str      # tên gốc biển chính
    combined_name: str   # tên sau khi kết hợp với biển phụ
    sub_signs: list[SubSignResult] = field(default_factory=list)


@dataclass
class CombinedSignMeta:
    start_time: str
    end_time: str
    duration_ms: float
    sign_prediction_duration_ms: float


@dataclass
class CombinedSignOutput:
    detections: list[CombinedDetection]
    meta: CombinedSignMeta


# ---------------------------------------------------------------------------
# Sub-sign classification
# ---------------------------------------------------------------------------

_SUB_SIGN_KEYWORDS = frozenset({
    "bien bao phu", "bien phu",
    "bien bao phu bieu thi thoi gian", "bien bao phu xe tai",
    "bien bao phu pham vi tac dung cua bien",
    "bien bao phu khoang cach den doi tuong bao hieu",
    "bien bao phu xe khach",
    "hieu luc voi xe tai 2_5tan", "hieu luc voi xe khach", "hieu luc voi xe tai",
    "bien phu xe gan may xe dap", "bien phu thu phi do xe",
    "bien phu tru xe buyt",
    "bien khu vuc thoi gian cam xe khach", "bien khu vuc thoi gian cam xe tai",
    "bien phu quy dinh loai xe khach",
    "bien den tin hieu cho nguoi di bo",
    "bien phu khu vuc doan tra khach",
    "bien khu vuc cam do xe", "bien chi dan duong mot chieu",
    "bien phu thoi gian", "bien phu do xe ngoai gio cao diem",
    "bien phu huong tac dung", "bien chi dan huong di khoang cach",
    "bien phu o to",
    "bien chi dan danh cho nguoi di bo sang ngang",
    "bien cam do xe ngay chan",
})


def _is_sub_sign(class_name: str) -> bool:
    return any(kw in class_name.strip().lower() for kw in _SUB_SIGN_KEYWORDS)


# ---------------------------------------------------------------------------
# Spatial matching helpers
# ---------------------------------------------------------------------------

def _vertical_gap(box_main: list[float], box_sub: list[float]) -> float:
    """Khoảng cách dọc: đáy biển chính → đỉnh biển phụ."""
    return box_sub[1] - box_main[3]


def _horizontal_overlap_ratio(box_main: list[float], box_sub: list[float]) -> float:
    """Tỉ lệ chồng lấp ngang của biển phụ so với chiều rộng của chính nó."""
    x_overlap = max(0.0, min(box_main[2], box_sub[2]) - max(box_main[0], box_sub[0]))
    return x_overlap / max(1.0, box_sub[2] - box_sub[0])


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------

class CombinedSignService:
    """
    Khởi tạo một lần lúc app start, gọi .predict(frame) cho mỗi request.

    Args:
        ocr_languages    : ngôn ngữ EasyOCR, mặc định ['vi', 'en']
        ocr_gpu          : dùng GPU cho EasyOCR
        max_vertical_gap : khoảng cách dọc tối đa (px) để ghép biển phụ
        min_h_overlap    : tỉ lệ chồng lấp ngang tối thiểu để ghép biển phụ
    """

    def __init__(
        self,
        ocr_languages: list[str] | None = None,
        ocr_gpu: bool = False,
        max_vertical_gap: float = 60.0,
        min_h_overlap: float = 0.4,
    ):
        self._max_v_gap = max_vertical_gap
        self._min_h_ovl = min_h_overlap

        langs = ocr_languages or ["vi", "en"]
        logger.info(f"Loading EasyOCR (langs={langs}, gpu={ocr_gpu}) …")
        self._ocr = easyocr.Reader(langs, gpu=ocr_gpu)
        logger.info("CombinedSignService ready.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def predict(self, frame: np.ndarray) -> CombinedSignOutput:
        """
        Args:
            frame: ảnh BGR numpy array (OpenCV format).
        Returns:
            CombinedSignOutput với detections đã ghép tên và sub_signs.
        """
        start_ts = datetime.now().isoformat()
        start    = time.perf_counter()

        # 1. Gọi sign_prediction, tách meta
        raw_results = sign_prediction(frame)
        detections_raw, sign_meta = self._extract_meta(raw_results)

        # 2. Phân loại main / sub
        main_dets, sub_dets = self._split(detections_raw)

        # 3. Ghép cặp không gian
        paired = self._associate(main_dets, sub_dets)

        # 4. OCR + build tên kết hợp
        results: list[CombinedDetection] = []
        for main_det, raw_subs in paired:
            sub_results   = self._process_sub_signs(frame, raw_subs)
            combined_name = self._build_name(main_det["class_name"], sub_results)
            results.append(CombinedDetection(
                box=main_det["box"],
                confidence=main_det["confidence"],
                class_id=main_det["class_id"],
                class_name=main_det["class_name"],
                combined_name=combined_name,
                sub_signs=sub_results,
            ))

        end = time.perf_counter()
        end_ts = datetime.now().isoformat()
        duration_ms = (end - start) * 1000.0

        logger.info(
            f"CombinedSignService.predict: total_ms={duration_ms:.1f}, "
            f"sign_ms={sign_meta.get('duration_ms', 0):.1f}, "
            f"detections={len(results)}"
        )

        return CombinedSignOutput(
            detections=results,
            meta=CombinedSignMeta(
                start_time=start_ts,
                end_time=end_ts,
                duration_ms=duration_ms,
                sign_prediction_duration_ms=sign_meta.get("duration_ms", 0.0),
            ),
        )

    # ------------------------------------------------------------------
    # Internal steps
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_meta(raw_results: list[dict]) -> tuple[list[dict], dict]:
        """Tách phần tử meta ra khỏi danh sách kết quả của sign_prediction."""
        detections, meta = [], {}
        for r in raw_results:
            if "meta" in r:
                meta = r["meta"]
            else:
                detections.append(r)
        return detections, meta

    @staticmethod
    def _split(detections: list[dict]) -> tuple[list[dict], list[dict]]:
        main_list, sub_list = [], []
        for det in detections:
            (sub_list if _is_sub_sign(det["class_name"]) else main_list).append(det)
        return main_list, sub_list

    def _associate(
        self,
        main_list: list[dict],
        sub_list: list[dict],
    ) -> list[tuple[dict, list[dict]]]:
        """Ghép mỗi biển phụ vào biển chính gần nhất phía trên."""
        buckets: list[list[dict]] = [[] for _ in main_list]
        assigned = [False] * len(sub_list)

        for s_idx, sub in enumerate(sub_list):
            best_idx, best_gap = None, float("inf")
            for m_idx, main in enumerate(main_list):
                v_gap   = _vertical_gap(main["box"], sub["box"])
                h_ovlap = _horizontal_overlap_ratio(main["box"], sub["box"])
                if v_gap < -20 or v_gap > self._max_v_gap:
                    continue
                if h_ovlap < self._min_h_ovl:
                    continue
                if v_gap < best_gap:
                    best_gap = v_gap
                    best_idx = m_idx

            if best_idx is not None:
                buckets[best_idx].append(sub)
                assigned[s_idx] = True

        paired = list(zip(main_list, buckets))

        for s_idx, sub in enumerate(sub_list):
            if not assigned[s_idx]:
                paired.append((sub, []))

        return paired

    def _process_sub_signs(
        self, frame: np.ndarray, raw_subs: list[dict]
    ) -> list[SubSignResult]:
        """Crop biển phụ → OCR → parse."""
        results = []
        h, w = frame.shape[:2]

        for sub in raw_subs:
            x1, y1, x2, y2 = [int(v) for v in sub["box"]]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            crop     = frame[y1:y2, x1:x2]
            ocr_text = ""
            parsed: dict = {}

            if crop.size > 0:
                try:
                    ocr_out  = self._ocr.readtext(crop, detail=0)
                    ocr_text = " ".join(ocr_out).strip()
                    parsed   = parse_sub_sign_text(ocr_text)
                    logger.debug(f"OCR: '{ocr_text}' → {parsed}")
                except Exception as exc:
                    logger.warning(f"OCR failed {sub['box']}: {exc}")

            results.append(SubSignResult(
                box=sub["box"],
                confidence=sub["confidence"],
                class_id=sub["class_id"],
                class_name=sub["class_name"],
                ocr_text=ocr_text,
                time_range=parsed.get("time_range"),
                time_ranges=parsed.get("time_ranges", []),
                distance=parsed.get("distance"),
                vehicle_type=parsed.get("vehicle_type"),
            ))

        return results

    def _build_name(self, main_name: str, sub_results: list[SubSignResult]) -> str:
        if not sub_results:
            return main_name

        # Gom tất cả time ranges từ mọi biển phụ (giữ thứ tự, không trùng)
        seen: set[str] = set()
        all_time_ranges: list[str] = []
        for s in sub_results:
            for r in s.time_ranges:
                if r not in seen:
                    seen.add(r)
                    all_time_ranges.append(r)

        distance     = next((s.distance     for s in sub_results if s.distance),     None)
        vehicle_type = next((s.vehicle_type for s in sub_results if s.vehicle_type), None)
        extra_texts  = [
            s.ocr_text for s in sub_results
            if s.ocr_text and not any([s.time_ranges, s.distance, s.vehicle_type])
        ]

        return build_combined_name(
            main_name,
            time_ranges=all_time_ranges or None,
            distance=distance,
            vehicle_type=vehicle_type,
            extra_texts=extra_texts or None,
        )