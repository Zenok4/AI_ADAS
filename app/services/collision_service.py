import time
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from app.config.settings import settings


class CollisionService:
    """Estimate collision risk from tracked objects.

    The service uses a simple pinhole-camera approximation to estimate the
    distance of an object from its bounding-box width:

        distance_m = real_width_m * focal_length_px / bbox_width_px

    It then compares the current distance with the previous frame to infer
    whether the object is closing in and to estimate TTC.
    """

    _LABEL_WIDTH_M = {
        # English labels
        "bicycle": 0.6,
        "bike": 0.8,
        "car": 1.8,
        "human": 0.6,
        "priorityvehicle": 2.2,
        # Vietnamese labels from the current object model, normalized to ASCII
        "xe dap": 0.6,
        "xe may": 0.8,
        "o to": 1.8,
        "nguoi di bo": 0.6,
        "xe uu tien": 2.2,
    }

    _LEVEL_RANK = {
        "safe": 0,
        "low": 1,
        "medium": 2,
        "high": 3,
        "critical": 4,
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Load collision thresholds and initialize frame history."""
        cfg = config if config is not None else settings.COLLISION

        self.critical_distance_m = float(cfg.get("critical_distance_m", 2.5))
        self.high_distance_m = float(cfg.get("high_distance_m", 5.0))
        self.medium_distance_m = float(cfg.get("medium_distance_m", 10.0))

        self.critical_ttc_s = float(cfg.get("critical_ttc_s", 1.5))
        self.high_ttc_s = float(cfg.get("high_ttc_s", 3.0))
        self.medium_ttc_s = float(cfg.get("medium_ttc_s", 5.0))

        self.min_confidence = float(cfg.get("min_confidence", 0.40))
        self.min_box_width_px = int(cfg.get("min_box_width_px", 20))
        self.min_box_height_px = int(cfg.get("min_box_height_px", 20))
        self.default_focal_length_px = float(cfg.get("default_focal_length_px", 1000.0))

        # Keep previous distance/timestamp per object id.
        self._history: Dict[int, Dict[str, float]] = {}

    def _normalize_label(self, label: Any) -> str:
        """Normalize labels for lookup in the size table."""
        if label is None:
            return ""
        normalized = unicodedata.normalize("NFKD", str(label))
        ascii_label = normalized.encode("ascii", "ignore").decode("ascii")
        return ascii_label.strip().lower()

    def _bbox_dimensions(self, bbox: List[float]) -> Tuple[float, float]:
        """Return bbox width and height in pixels."""
        if not bbox or len(bbox) < 4:
            return 0.0, 0.0

        x1, y1, x2, y2 = bbox[:4]
        return abs(float(x2) - float(x1)), abs(float(y2) - float(y1))

    def _estimate_real_width_m(self, label: Any) -> float:
        """Map a label to an approximate real-world width."""
        normalized = self._normalize_label(label)
        return self._LABEL_WIDTH_M.get(normalized, 1.0)

    def _estimate_distance_m(self, label: Any, bbox: List[float]) -> Optional[float]:
        """Estimate object distance from bbox width using the pinhole model."""
        box_width_px, box_height_px = self._bbox_dimensions(bbox)
        if (
            box_width_px < self.min_box_width_px
            or box_height_px < self.min_box_height_px
        ):
            return None

        real_width_m = self._estimate_real_width_m(label)
        if real_width_m <= 0:
            return None

        return (real_width_m * self.default_focal_length_px) / max(box_width_px, 1.0)

    def _estimate_ttc_s(
        self, obj_id: int, current_distance_m: float, now_s: float
    ) -> Optional[float]:
        """Estimate TTC by comparing current distance with previous distance."""
        prev = self._history.get(obj_id)
        if not prev:
            return None

        prev_distance_m = prev.get("distance_m")
        prev_time_s = prev.get("time_s")
        if prev_distance_m is None or prev_time_s is None:
            return None

        dt = now_s - prev_time_s
        if dt <= 1e-4:
            return None

        closing_speed_mps = (prev_distance_m - current_distance_m) / dt
        if closing_speed_mps <= 1e-4:
            return None

        return current_distance_m / closing_speed_mps

    # def _classify_risk(
    #     self, distance_m: Optional[float], ttc_s: Optional[float]
    # ) -> Tuple[str, str]:
    #     """Convert distance/TTC into a warning level and message."""
    #     if distance_m is None:
    #         return "safe", "AN TOAN - KHONG DU DU LIEU DE DANH GIA"

    #     if distance_m <= self.critical_distance_m or (
    #         ttc_s is not None and ttc_s <= self.critical_ttc_s
    #     ):
    #         return "critical", "NGUY HIEM KHAN CAP - PHANH NGAY"

    #     if distance_m <= self.high_distance_m or (
    #         ttc_s is not None and ttc_s <= self.high_ttc_s
    #     ):
    #         return "high", "CANH BAO CAO - VAT CAN DANG RAT GAN"

    #     if distance_m <= self.medium_distance_m or (
    #         ttc_s is not None and ttc_s <= self.medium_ttc_s
    #     ):
    #         return "medium", "CANH BAO TRUNG BINH - GIAM TOC"

    #     return "low", "CANH BAO THAP - CO VAT CAN PHIA TRUOC"
    def _classify_risk(
        self, distance_m: Optional[float], ttc_s: Optional[float]
    ) -> Tuple[str, str]:
        """Strict AND logic: both distance and TTC must satisfy the threshold."""
        if distance_m is None:
            return "safe", "AN TOAN - KHONG DU DU LIEU DE DANH GIA"

        if (
            distance_m <= self.critical_distance_m
            and ttc_s is not None
            and ttc_s <= self.critical_ttc_s
        ):
            return "critical", "NGUY HIEM KHAN CAP - PHANH NGAY"

        if (
            distance_m <= self.high_distance_m
            and ttc_s is not None
            and ttc_s <= self.high_ttc_s
        ):
            return "high", "CANH BAO CAO - VAT CAN DANG RAT GAN"

        if (
            distance_m <= self.medium_distance_m
            and ttc_s is not None
            and ttc_s <= self.medium_ttc_s
        ):
            return "medium", "CANH BAO TRUNG BINH - GIAM TOC"

        if distance_m <= self.medium_distance_m:
            return "low", "CANH BAO THAP - CO VAT CAN PHIA TRUOC"

        return "safe", "AN TOAN"

    def _is_relevant(self, obj: Dict[str, Any]) -> bool:
        """Filter out low-quality detections before risk analysis."""
        confidence = float(obj.get("confidence", 0.0) or 0.0)
        if confidence < self.min_confidence:
            return False

        bbox = obj.get("bbox") or []
        box_width_px, box_height_px = self._bbox_dimensions(bbox)
        return (
            box_width_px >= self.min_box_width_px
            and box_height_px >= self.min_box_height_px
        )

    def _severity_key(self, level: str) -> int:
        """Translate a risk level to an integer rank."""
        return self._LEVEL_RANK.get(level, 0)

    def analyze(
        self,
        objects: List[Dict[str, Any]],
        frame_shape: Optional[Tuple[int, int, int]] = None,
        captured_at: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Analyze tracked objects and return warnings plus a summary.

        Args:
            objects: Tracked objects with at least `id`, `label`, `confidence`,
                and `bbox`.
            frame_shape: Optional image shape `(height, width, channels)`.
                The current implementation keeps this for future path filtering.
            captured_at: Optional timestamp for the current frame.

        Returns:
            A dictionary with:
            - `objects`: original objects enriched with collision metadata
            - `warnings`: only risky objects
            - `summary`: the highest-severity warning in the frame
        """
        now_s = float(captured_at if captured_at is not None else time.time())
        analyzed_objects: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        for obj in objects or []:
            obj_id = int(obj.get("id", -1))
            bbox = obj.get("bbox") or []

            enriched = dict(obj)
            enriched["distance_m"] = None
            enriched["ttc_s"] = None
            enriched["warning_level"] = "safe"
            enriched["warning_message"] = "AN TOAN"

            if obj_id < 0 or not self._is_relevant(enriched):
                analyzed_objects.append(enriched)
                continue

            distance_m = self._estimate_distance_m(enriched.get("label"), bbox)
            ttc_s = None
            if distance_m is not None:
                ttc_s = self._estimate_ttc_s(obj_id, distance_m, now_s)

            level, message = self._classify_risk(distance_m, ttc_s)

            enriched["distance_m"] = (
                round(distance_m, 2) if distance_m is not None else None
            )
            enriched["ttc_s"] = round(ttc_s, 2) if ttc_s is not None else None
            enriched["warning_level"] = level
            enriched["warning_message"] = message

            if level != "safe":
                warnings.append(
                    {
                        "object_id": obj_id,
                        "label": enriched.get("label", ""),
                        "confidence": enriched.get("confidence", 0.0),
                        "distance_m": enriched["distance_m"],
                        "ttc_s": enriched["ttc_s"],
                        "warning_level": level,
                        "warning_message": message,
                    }
                )

            self._history[obj_id] = {
                "distance_m": float(distance_m) if distance_m is not None else None,
                "time_s": now_s,
            }
            analyzed_objects.append(enriched)

        current_ids = {
            int(obj.get("id", -1))
            for obj in objects or []
            if int(obj.get("id", -1)) >= 0
        }
        self._cleanup_missing(current_ids)

        return {
            "objects": analyzed_objects,
            "warnings": warnings,
            "summary": self._build_summary(warnings),
            "frame_shape": frame_shape,
        }

    def _build_summary(self, warnings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Pick the most severe warning to represent the whole frame."""
        if not warnings:
            return {
                "overall_level": "safe",
                "overall_message": "AN TOAN - KHONG CO NGUY CO VA CHAM RO RANG",
                "highest_risk_object": None,
            }

        top_warning = max(
            warnings,
            key=lambda item: self._severity_key(item.get("warning_level", "safe")),
        )
        return {
            "overall_level": top_warning.get("warning_level", "safe"),
            "overall_message": top_warning.get("warning_message", "AN TOAN"),
            "highest_risk_object": {
                "object_id": top_warning.get("object_id"),
                "label": top_warning.get("label", ""),
                "distance_m": top_warning.get("distance_m"),
                "ttc_s": top_warning.get("ttc_s"),
            },
        }

    def _cleanup_missing(self, current_ids: set) -> None:
        """Remove stale object history that did not appear in the current frame."""
        self._history = {
            obj_id: state
            for obj_id, state in self._history.items()
            if obj_id in current_ids
        }
