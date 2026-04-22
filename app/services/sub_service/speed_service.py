import math
import time

from app.services.sub_service.frame_cache import FrameCacheService
from app.services.sub_service.speed_smoother import SpeedSmoother


class SpeedEstimationService:

    def __init__(self, pixel_to_meter=0.05):
        self.cache = FrameCacheService()
        self.smoother = SpeedSmoother()
        self.pixel_to_meter = pixel_to_meter

        # 🔥 GPS state
        self.prev_gps = None

    def _distance(self, p1, p2):
        return math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)

    # 🔥 tính khoảng cách GPS
    def _haversine(self, lat1, lon1, lat2, lon2):
        R = 6371000
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)

        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

    # 🔥 tính tốc độ xe (ego speed)
    def compute_ego_speed(self, lat, lon, captured_at):
        if not self.prev_gps:
            self.prev_gps = (lat, lon, captured_at)
            return 0.0

        prev_lat, prev_lon, prev_time = self.prev_gps

        dt = captured_at - prev_time
        if dt <= 0:
            return 0.0

        dist = self._haversine(prev_lat, prev_lon, lat, lon)
        speed = (dist / dt) * 3.6  # km/h

        self.prev_gps = (lat, lon, captured_at)

        return speed

    # 🔥 main
    def estimate(self, tracked_objects, ego_speed):

        results = []
        current_ids = set()
        now = time.time()

        for obj in tracked_objects:
            obj_id = obj["id"]
            x1, y1, x2, y2 = obj["bbox"]

            center = ((x1+x2)/2, (y1+y2)/2)
            area = (x2 - x1) * (y2 - y1)

            current_ids.add(obj_id)

            prev = self.cache.get(obj_id)

            # =========================
            # 1. Tính relative speed
            # =========================
            if prev is None:
                relative_speed = 0
            else:
                dt = now - prev["time"]

                if dt < 1e-4:
                    relative_speed = 0
                else:
                    pixel_distance = self._distance(prev["center"], center)

                    if pixel_distance < 2:
                        relative_speed = 0
                    else:
                        speed_mps = (pixel_distance * self.pixel_to_meter) / dt
                        relative_speed = speed_mps * 3.6

            # smoothing
            relative_speed = self.smoother.smooth(obj_id, relative_speed)

            # =========================
            # 2. Combine với ego speed
            # =========================
            final_speed = ego_speed

            if prev is not None:
                prev_area = prev.get("area", area)
                delta_area = area - prev_area

                if abs(delta_area) < 5:
                    final_speed = ego_speed
                elif delta_area > 0:
                    # object gần hơn → bạn nhanh hơn
                    final_speed = max(0, ego_speed - abs(relative_speed))
                else:
                    # object xa hơn → object nhanh hơn
                    final_speed = ego_speed + abs(relative_speed)

            # =========================
            # 3. Update cache
            # =========================
            self.cache.update(obj_id, {
                "center": center,
                "time": now,
                "area": area
            })

            obj["speed"] = round(final_speed, 2)
            results.append(obj)

        self.cache.clear_missing(current_ids)
        self.smoother.clear_missing(current_ids)

        return results