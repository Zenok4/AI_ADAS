import math
import time
import logging

from app.services.sub_service.frame_cache import FrameCacheService
from app.services.sub_service.speed_smoother import SpeedSmoother

logger = logging.getLogger("SpeedEstimationService")


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
            logger.info(f"[GPS INIT] lat={lat}, lon={lon}")
            self.prev_gps = (lat, lon, captured_at)
            return 0.0

        prev_lat, prev_lon, prev_time = self.prev_gps

        dt = captured_at - prev_time
        if dt <= 0:
            logger.warning(f"[GPS ERROR] dt={dt}")
            return 0.0

        dist = self._haversine(prev_lat, prev_lon, lat, lon)
        speed = (dist / dt) * 3.6  # km/h

        logger.info(f"[GPS] dist={dist:.2f}m | dt={dt:.3f}s | speed={speed:.2f} km/h")

        self.prev_gps = (lat, lon, captured_at)

        return speed

    # 🔥 main
    def estimate(self, tracked_objects, ego_speed):

        logger.info(f"[START] Speed estimation | ego_speed={ego_speed:.2f}")
        logger.info(f"[INPUT] objects={len(tracked_objects)}")

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

            logger.debug(f"[OBJ {obj_id}] bbox={obj['bbox']}")

            # =========================
            # 1. Tính relative speed
            # =========================
            if prev is None:
                relative_speed = 0
                logger.debug(f"[OBJ {obj_id}] first frame")
            else:
                dt = now - prev["time"]

                if dt < 1e-4:
                    relative_speed = 0
                    logger.warning(f"[OBJ {obj_id}] dt too small={dt}")
                else:
                    pixel_distance = self._distance(prev["center"], center)

                    if pixel_distance < 2:
                        relative_speed = 0
                        logger.debug(f"[OBJ {obj_id}] pixel movement too small")
                    else:
                        speed_mps = (pixel_distance * self.pixel_to_meter) / dt
                        relative_speed = speed_mps * 3.6

                        logger.info(
                            f"[OBJ {obj_id}] pixel_dist={pixel_distance:.2f} | dt={dt:.4f} | raw_speed={relative_speed:.2f}"
                        )

            # smoothing
            smoothed_speed = self.smoother.smooth(obj_id, relative_speed)

            logger.debug(
                f"[OBJ {obj_id}] smooth: raw={relative_speed:.2f} -> smooth={smoothed_speed:.2f}"
            )

            relative_speed = smoothed_speed

            # =========================
            # 2. Combine với ego speed
            # =========================
            final_speed = ego_speed

            if prev is not None:
                prev_area = prev.get("area", area)
                delta_area = area - prev_area

                logger.debug(f"[OBJ {obj_id}] delta_area={delta_area}")

                if abs(delta_area) < 5:
                    final_speed = ego_speed
                elif delta_area > 0:
                    final_speed = max(0, ego_speed - abs(relative_speed))
                    logger.info(f"[OBJ {obj_id}] approaching → slower")
                else:
                    final_speed = ego_speed + abs(relative_speed)
                    logger.info(f"[OBJ {obj_id}] moving away → faster")

            logger.info(f"[OBJ {obj_id}] FINAL speed={final_speed:.2f} km/h")

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

        logger.info(f"[END] Speed estimation done\n")

        return results