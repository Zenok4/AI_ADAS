import cv2
import os
from datetime import datetime


class VisualLogger:
    def __init__(self):
        self.base_dir = "debug_frames"
        os.makedirs(self.base_dir, exist_ok=True)

    # ================= SAVE =================
    def save(self, frame, category="general"):
        folder = os.path.join(self.base_dir, category)
        os.makedirs(folder, exist_ok=True)

        name = datetime.now().strftime("%H%M%S_%f") + ".jpg"
        path = os.path.join(folder, name)

        cv2.imwrite(path, frame)
        return path

    # ================= OBJECT =================
    def draw_object(self, frame, objects, ego_speed=0):
        for obj in objects:
            x1, y1, x2, y2 = map(int, obj["bbox"])

            label = obj.get("label", "")
            conf = obj.get("confidence", 0)
            obj_id = obj.get("id", 0)
            speed = obj.get("speed", 0)

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            text = f"{label} {conf:.2f} | ID:{obj_id} {speed:.1f}"
            cv2.putText(frame, text,
                        (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 0), 2)

        cv2.putText(frame,
                    f"EGO: {ego_speed:.1f}",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 0, 255), 3)

        return frame

    # ================= SIGN =================
    def draw_sign(self, frame, detections):
        for det in detections:
            x1, y1, x2, y2 = map(int, det.box)

            label = det.combined_name
            conf = det.confidence

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            text = f"{label} {conf:.2f}"
            cv2.putText(frame, text,
                        (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 0), 2)

        return frame

    # ================= LANE =================
    def draw_lane(self, frame, detections):
        for det in detections:
            box = det.get("box", [])
            if len(box) < 4:
                continue

            x1, y1, x2, y2 = map(int, box)

            label = det.get("class_name", "")
            conf = det.get("confidence", 0)

            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)

            text = f"{label} {conf:.2f}"
            cv2.putText(frame, text,
                        (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (255, 0, 0), 2)

        return frame