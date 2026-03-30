import math
import time
from typing import Dict, List, Optional, Tuple
from app.config.settings import settings



class CollisionRiskService:
    """
    Cảnh báo va chạm:
    - Nhận vật thể từ sensor hoặc camera
    - Ước lượng khoảng cách, tốc độ tiến gần
    - Tính Time To Collision (thời gian tới va chạm)
    - Phát cảnh báo nguy cơ va chạm
    """

    def __init__(self) -> None:
        """Khởi tạo ngưỡng cảnh báo và bộ nhớ theo dõi."""
        collision_cfg = settings.COLLISION or {}

        self.object_widths_m = {
            0: 0.60,   # bicycle
            1: 0.75,   # bike
            2: 1.80,   # car
            3: 0.45,   # human
            4: 2.10,   # priorityvehicle
        }

        self.lane_half_width_m = float(collision_cfg.get("lane_half_width_m", 1.75))
        self.max_match_distance_px = float(collision_cfg.get("max_match_distance_px", 90.0))
        self.max_track_age_s = float(collision_cfg.get("max_track_age_s", 3.0))

        self.critical_distance_m = float(collision_cfg.get("critical_distance_m", 2.5))
        self.high_distance_m = float(collision_cfg.get("high_distance_m", 5.0))
        self.medium_distance_m = float(collision_cfg.get("medium_distance_m", 10.0))

        self.critical_ttc_s = float(collision_cfg.get("critical_ttc_s", 1.5))
        self.high_ttc_s = float(collision_cfg.get("high_ttc_s", 3.0))
        self.medium_ttc_s = float(collision_cfg.get("medium_ttc_s", 5.0))

        self.default_focal_length_ratio = float(collision_cfg.get("default_focal_length_ratio", 0.9))
        self.sensor_velocity_mode = str(collision_cfg.get("sensor_velocity_mode", "relative")).lower()

        self.session_tracks: Dict[str, Dict[str, object]] = {}


    def analyze(
        self,
        detections: Optional[List[dict]] = None,
        ego_state: Optional[dict] = None,
        sensor_objects: Optional[List[dict]] = None,
        frame_shape: Optional[Tuple[int, ...]] = None,
        camera_params: Optional[dict] = None,
        session_id: str = "default",
        now: Optional[float] = None,
    ) -> dict:
        """Phân tích nguy cơ va chạm từ camera và sensor."""
        now = now or time.time()

        ego = self._parse_ego_state(ego_state or {})
        camera_objects = self._build_camera_objects(
            detections=detections or [],
            frame_shape=frame_shape,
            camera_params=camera_params or {},
        )
        self._attach_camera_closing_speed(
            session_id=session_id,
            camera_objects=camera_objects,
            now=now,
        )

        parsed_sensor_objects = self._build_sensor_objects(sensor_objects or [])
        merged_objects = self._merge_objects(parsed_sensor_objects, camera_objects)

        scored_objects: List[dict] = []
        events: List[dict] = []
        highest_severity = "safe"

        for obj in merged_objects:
            scored = self._score_object(obj=obj, ego=ego, now=now)
            scored_objects.append(scored)

            severity = scored["risk"]["severity"]
            if self._severity_rank(severity) > self._severity_rank(highest_severity):
                highest_severity = severity

            if scored["risk"]["emit_event"]:
                events.append(scored["risk"]["event"])

        return {
            "ego_state": ego,
            "objects": scored_objects,
            "events": events,
            "summary": {
                "session_id": session_id,
                "highest_severity": highest_severity,
                "num_objects": len(scored_objects),
                "num_events": len(events),
                "requires_brake": highest_severity in ("high", "critical"),
                "timestamp": now,
            },
        }

    def _parse_ego_state(self, payload: dict) -> dict:
        """Chuẩn hóa trạng thái xe hiện tại."""
        speed_mps = self._safe_float(payload.get("speed_mps", 0.0))
        heading_deg = self._safe_float(payload.get("heading_deg", 0.0))

        position_payload = payload.get("position") or {}
        position = {
            "x": self._safe_float(position_payload.get("x", 0.0)),
            "y": self._safe_float(position_payload.get("y", 0.0)),
        }

        velocity_payload = payload.get("velocity")
        if velocity_payload is None:
            velocity = self._vector_from_speed_heading(speed_mps, heading_deg)
        else:
            velocity = {
                "x": self._safe_float(velocity_payload.get("x", 0.0)),
                "y": self._safe_float(velocity_payload.get("y", 0.0)),
            }

        return {
            "speed_mps": speed_mps,
            "heading_deg": heading_deg,
            "position": position,
            "velocity": velocity,
        }

    def _build_sensor_objects(self, items: List[dict]) -> List[dict]:
        """Chuẩn hóa vật thể lấy từ sensor."""
        parsed: List[dict] = []

        for index, item in enumerate(items):
            position_payload = item.get("position") or {}
            x = self._safe_float(position_payload.get("x", item.get("lateral_m", 0.0)))
            y = self._safe_float(position_payload.get("y", item.get("longitudinal_m", 0.0)))

            velocity_payload = item.get("velocity")
            heading_deg = self._safe_float(item.get("heading_deg", 0.0))

            if velocity_payload is None:
                speed_mps = self._safe_float(item.get("speed_mps", 0.0))
                velocity = self._vector_from_speed_heading(speed_mps, heading_deg)
            else:
                velocity = {
                    "x": self._safe_float(velocity_payload.get("x", 0.0)),
                    "y": self._safe_float(velocity_payload.get("y", 0.0)),
                }

            distance_m = math.hypot(x, y)

            parsed.append(
                {
                    "object_id": item.get("object_id", f"sensor_{index}"),
                    "class_name": item.get("class_name", "unknown"),
                    "source": item.get("source", "sensor"),
                    "position": {"x": x, "y": y},
                    "velocity": velocity,
                    "heading_deg": heading_deg,
                    "confidence": self._safe_float(item.get("confidence", 1.0)),
                    "box": item.get("box"),
                    "distance_m": distance_m,
                    "estimation_method": item.get("estimation_method", "sensor_relative_position"),
                    "estimated_closing_speed_mps": None,
                }
            )

        return parsed

    def _build_camera_objects(
        self,
        detections: List[dict],
        frame_shape: Optional[Tuple[int, ...]],
        camera_params: dict,
    ) -> List[dict]:
        """Ước lượng vị trí và khoảng cách vật thể từ bbox camera."""
        if not detections or not frame_shape:
            return []

        frame_h = int(frame_shape[0])
        frame_w = int(frame_shape[1])

        focal_length_px = self._safe_float(
            camera_params.get("focal_length_px", frame_w * self.default_focal_length_ratio)
        )

        principal_point = camera_params.get("principal_point") or {
            "x": frame_w / 2.0,
            "y": frame_h / 2.0,
        }
        principal_x = self._safe_float(principal_point.get("x", frame_w / 2.0))
        principal_y = self._safe_float(principal_point.get("y", frame_h / 2.0))

        camera_objects: List[dict] = []

        for index, det in enumerate(detections):
            box = det.get("box")
            if not box or len(box) != 4:
                continue

            x1, y1, x2, y2 = [float(v) for v in box]
            box_width_px = max(1.0, x2 - x1)
            center_x = (x1 + x2) / 2.0
            center_y = (y1 + y2) / 2.0

            class_id = det.get("class_id")
            class_name = det.get("class_name", "unknown")

            distance_m = self._estimate_distance_from_box(
                class_id=class_id,
                box_width_px=box_width_px,
                focal_length_px=focal_length_px,
            )

            lateral_offset_m = ((center_x - principal_x) / max(focal_length_px, 1.0)) * distance_m

            camera_objects.append(
                {
                    "object_id": det.get("object_id", f"camera_{index}"),
                    "class_id": class_id,
                    "class_name": class_name,
                    "source": "camera",
                    "position": {
                        "x": lateral_offset_m,
                        "y": distance_m,
                    },
                    "velocity": {"x": 0.0, "y": 0.0},
                    "heading_deg": 0.0,
                    "confidence": self._safe_float(det.get("confidence", 0.0)),
                    "box": [int(x1), int(y1), int(x2), int(y2)],
                    "distance_m": distance_m,
                    "estimation_method": "monocular_bbox_width",
                    "center_px": {
                        "x": center_x,
                        "y": center_y,
                    },
                    "principal_point_px": {
                        "x": principal_x,
                        "y": principal_y,
                    },
                    "estimated_closing_speed_mps": None,
                }
            )

        return camera_objects


    def _attach_camera_closing_speed(
        self,
        session_id: str,
        camera_objects: List[dict],
        now: float,
    ) -> None:
        """Ghép vật thể giữa các frame để ước lượng tốc độ tiến gần."""
        previous_session = self.session_tracks.get(session_id, {})
        previous_objects = previous_session.get("objects", [])
        previous_ts = self._safe_float(previous_session.get("timestamp", now))

        used_previous = set()

        for obj in camera_objects:
            best_index = None
            best_distance_px = float("inf")

            current_center = obj.get("center_px") or {}
            current_x = self._safe_float(current_center.get("x", 0.0))
            current_y = self._safe_float(current_center.get("y", 0.0))

            for index, prev in enumerate(previous_objects):
                if index in used_previous:
                    continue
                if prev.get("class_name") != obj.get("class_name"):
                    continue

                prev_center = prev.get("center_px") or {}
                prev_x = self._safe_float(prev_center.get("x", 0.0))
                prev_y = self._safe_float(prev_center.get("y", 0.0))

                pixel_gap = math.hypot(current_x - prev_x, current_y - prev_y)
                if pixel_gap <= self.max_match_distance_px and pixel_gap < best_distance_px:
                    best_distance_px = pixel_gap
                    best_index = index

            if best_index is None:
                continue

            dt = max(now - previous_ts, 1e-6)
            prev_obj = previous_objects[best_index]
            prev_distance_m = self._safe_float(prev_obj.get("distance_m", obj["distance_m"]))
            curr_distance_m = self._safe_float(obj.get("distance_m", 0.0))

            closing_speed_mps = max(0.0, (prev_distance_m - curr_distance_m) / dt)
            obj["estimated_closing_speed_mps"] = closing_speed_mps
            used_previous.add(best_index)

        self.session_tracks[session_id] = {
            "timestamp": now,
            "objects": [
                {
                    "class_name": obj.get("class_name"),
                    "center_px": obj.get("center_px"),
                    "distance_m": obj.get("distance_m"),
                }
                for obj in camera_objects
            ],
        }

        self._cleanup_sessions(now)

    def _merge_objects(self, sensor_objects: List[dict], camera_objects: List[dict]) -> List[dict]:
        """Gộp dữ liệu vật thể từ sensor và camera."""
        if not sensor_objects:
            return camera_objects
        if not camera_objects:
            return sensor_objects

        merged: List[dict] = []
        used_camera = set()

        for sensor_obj in sensor_objects:
            sensor_pos = sensor_obj.get("position", {})
            sx = self._safe_float(sensor_pos.get("x", 0.0))
            sy = self._safe_float(sensor_pos.get("y", 0.0))

            best_index = None
            best_score = float("inf")

            for index, camera_obj in enumerate(camera_objects):
                if index in used_camera:
                    continue
                if camera_obj.get("class_name") != sensor_obj.get("class_name"):
                    continue

                camera_pos = camera_obj.get("position", {})
                cx = self._safe_float(camera_pos.get("x", 0.0))
                cy = self._safe_float(camera_pos.get("y", 0.0))

                dx = abs(sx - cx)
                dy = abs(sy - cy)

                if dx <= 1.5 and dy <= 6.0:
                    score = dx * 2.0 + dy
                    if score < best_score:
                        best_score = score
                        best_index = index

            if best_index is None:
                merged.append(sensor_obj)
                continue

            matched_camera = camera_objects[best_index]
            enriched = dict(sensor_obj)
            enriched["source"] = "sensor+camera"
            enriched["box"] = matched_camera.get("box")
            enriched["confidence"] = max(
                self._safe_float(sensor_obj.get("confidence", 0.0)),
                self._safe_float(matched_camera.get("confidence", 0.0)),
            )
            enriched["distance_m"] = self._safe_float(sensor_obj.get("distance_m", matched_camera.get("distance_m", 0.0)))
            enriched["camera_distance_m"] = self._safe_float(matched_camera.get("distance_m", 0.0))
            enriched["estimated_closing_speed_mps"] = matched_camera.get("estimated_closing_speed_mps")
            used_camera.add(best_index)
            merged.append(enriched)

        for index, camera_obj in enumerate(camera_objects):
            if index not in used_camera:
                merged.append(camera_obj)

        return merged

    def _score_object(self, obj: dict, ego: dict, now: float) -> dict:
        """Tính rủi ro cho từng vật thể."""
        obj = dict(obj)

        pos = obj.get("position") or {}
        x = self._safe_float(pos.get("x", 0.0))
        y = self._safe_float(pos.get("y", 0.0))

        distance_m = self._safe_float(obj.get("distance_m", math.hypot(x, y)))
        if distance_m <= 0.0:
            distance_m = math.hypot(x, y)

        obj_velocity = obj.get("velocity") or {"x": 0.0, "y": 0.0}
        ego_velocity = ego.get("velocity") or {"x": 0.0, "y": 0.0}

        if self.sensor_velocity_mode == "relative":
            rel_vx = self._safe_float(obj_velocity.get("x", 0.0))
            rel_vy = self._safe_float(obj_velocity.get("y", 0.0))
        else:
            rel_vx = self._safe_float(obj_velocity.get("x", 0.0)) - self._safe_float(ego_velocity.get("x", 0.0))
            rel_vy = self._safe_float(obj_velocity.get("y", 0.0)) - self._safe_float(ego_velocity.get("y", 0.0))

        if distance_m > 1e-6:
            los_x = x / distance_m
            los_y = y / distance_m
        else:
            los_x = 0.0
            los_y = 1.0

        vector_based_closing = max(0.0, -(rel_vx * los_x + rel_vy * los_y))
        camera_based_closing = self._safe_float(obj.get("estimated_closing_speed_mps", 0.0))

        if obj.get("source") == "camera":
            closing_speed_mps = camera_based_closing
        else:
            closing_speed_mps = max(vector_based_closing, camera_based_closing)


        ttc_s = None
        if closing_speed_mps > 0.1:
            ttc_s = distance_m / closing_speed_mps

        in_path = y > 0.0 and abs(x) <= self.lane_half_width_m

        severity = self._classify_severity(
            distance_m=distance_m,
            longitudinal_distance_m=y,
            lateral_offset_m=abs(x),
            closing_speed_mps=closing_speed_mps,
            ttc_s=ttc_s,
            in_path=in_path,
        )

        warning = self._warning_text(severity, obj.get("class_name", "vat can"))
        emit_event = severity in ("medium", "high", "critical")

        event = None
        if emit_event:
            event = {
                "event_type": "collision_risk",
                "severity": severity,
                "warning": warning,
                "object_id": obj.get("object_id"),
                "object_class": obj.get("class_name"),
                "source": obj.get("source"),
                "distance_m": round(distance_m, 2),
                "longitudinal_distance_m": round(y, 2),
                "lateral_offset_m": round(x, 2),
                "closing_speed_mps": round(closing_speed_mps, 2),
                "ttc_s": None if ttc_s is None else round(ttc_s, 2),
                "timestamp": now,
            }

        obj["distance_m"] = round(distance_m, 2)
        obj["risk"] = {
            "severity": severity,
            "warning": warning,
            "in_path": in_path,
            "distance_m": round(distance_m, 2),
            "longitudinal_distance_m": round(y, 2),
            "lateral_offset_m": round(x, 2),
            "closing_speed_mps": round(closing_speed_mps, 2),
            "ttc_s": None if ttc_s is None else round(ttc_s, 2),
            "emit_event": emit_event,
            "event": event,
        }

        return obj

    def _classify_severity(
        self,
        distance_m: float,
        longitudinal_distance_m: float,
        lateral_offset_m: float,
        closing_speed_mps: float,
        ttc_s: Optional[float],
        in_path: bool,
    ) -> str:
        """Xếp mức cảnh báo theo khoảng cách và Time To Collision."""
        if longitudinal_distance_m <= 0.0:
            return "safe"

        # Ưu tiên theo khoảng cách để frame camera đầu tiên vẫn cảnh báo được.
        if in_path and distance_m <= self.critical_distance_m:
            return "critical"

        if in_path and distance_m <= self.high_distance_m:
            return "high"

        if in_path and distance_m <= self.medium_distance_m:
            return "medium"

        # Sau đó xét theo Time To Collision khi đã có dữ liệu vận tốc.
        if in_path and ttc_s is not None and ttc_s <= self.critical_ttc_s:
            return "critical"

        if in_path and ttc_s is not None and ttc_s <= self.high_ttc_s:
            return "high"

        if in_path and ttc_s is not None and ttc_s <= self.medium_ttc_s:
            return "medium"

        if lateral_offset_m <= self.lane_half_width_m * 1.5 and longitudinal_distance_m < 20.0:
            return "low"

        return "safe"


    def _warning_text(self, severity: str, class_name: str) -> str:
        """Tạo nội dung cảnh báo."""
        if severity == "critical":
            return f"PHANH KHAN CAP - NGUY CO VA CHAM VOI {class_name}"
        if severity == "high":
            return f"CANH BAO CAO - VAT CAN {class_name} DANG RAT GAN"
        if severity == "medium":
            return f"CANH BAO - CAN GIAM TOC DO VI {class_name}"
        if severity == "low":
            return f"LUU Y - THEO DOI VAT CAN {class_name}"
        return "AN TOAN"

    def _estimate_distance_from_box(
        self,
        class_id,
        box_width_px: float,
        focal_length_px: float,
    ) -> float:
        """Ước lượng khoảng cách từ độ rộng bbox."""
        real_width_m = self.object_widths_m.get(class_id, 1.8)
        return max(0.5, (real_width_m * max(focal_length_px, 1.0)) / max(box_width_px, 1.0))


    def _vector_from_speed_heading(self, speed_mps: float, heading_deg: float) -> dict:
        """Đổi tốc độ và hướng sang vector vận tốc 2D."""
        # Quy ước:
        # heading = 0 độ -> hướng thẳng phía trước
        # x -> lệch ngang, y -> phía trước
        rad = math.radians(heading_deg)
        return {
            "x": speed_mps * math.sin(rad),
            "y": speed_mps * math.cos(rad),
        }

    def _severity_rank(self, severity: str) -> int:
        """Đổi mức cảnh báo sang số để so sánh."""
        order = {
            "safe": 0,
            "low": 1,
            "medium": 2,
            "high": 3,
            "critical": 4,
        }
        return order.get(severity, 0)

    def _cleanup_sessions(self, now: float) -> None:
        """Xóa track camera đã hết hạn."""
        expired = []

        for session_id, session_data in self.session_tracks.items():
            ts = self._safe_float(session_data.get("timestamp", 0.0))
            if now - ts > self.max_track_age_s:
                expired.append(session_id)

        for session_id in expired:
            self.session_tracks.pop(session_id, None)

    def _safe_float(self, value, default: float = 0.0) -> float:
        """Ép giá trị sang float an toàn."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def analyze_camera_detections(
        self,
        detections: List[dict],
        frame_shape: Tuple[int, ...],
        session_id: Optional[str] = None,
        ego_state: Optional[dict] = None,
        camera_params: Optional[dict] = None,
    ) -> dict:
        """Phân tích nhanh khi chỉ có dữ liệu camera."""
        effective_session_id = session_id or f"single_{time.time_ns()}"

        return self.analyze(
            detections=detections,
            ego_state=ego_state or {},
            sensor_objects=[],
            frame_shape=frame_shape,
            camera_params=camera_params or {},
            session_id=effective_session_id,
        )
