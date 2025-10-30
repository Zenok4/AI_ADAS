import math
from datetime import datetime

import cv2
import mediapipe as mp
from scipy.spatial import distance as dis

# ========= Giữ tối giản: không phát âm thanh, không pygame, không thread =========


class drowsiDetector:
    def __init__(self) -> None:
        self.face_mesh = mp.solutions.face_mesh
        self.draw_utils = mp.solutions.drawing_utils
        self.landmark_style = self.draw_utils.DrawingSpec(
            (0, 255, 0), thickness=2, circle_radius=2
        )
        self.connection_style = self.draw_utils.DrawingSpec(
            (0, 0, 255), thickness=2, circle_radius=2
        )

        self.STATIC_IMAGE = False
        self.MAX_NO_FACES = 2
        self.DETECTION_CONFIDENCE = 0.6
        self.TRACKING_CONFIDENCE = 0.5

        self.COLOR_RED = (0, 0, 255)
        self.COLOR_BLUE = (255, 0, 0)
        self.COLOR_GREEN = (0, 255, 0)

        self.LIPS = [
            61,
            146,
            91,
            181,
            84,
            17,
            314,
            405,
            321,
            375,
            291,
            308,
            324,
            318,
            402,
            317,
            14,
            87,
            178,
            88,
            95,
            185,
            40,
            39,
            37,
            0,
            267,
            269,
            270,
            409,
            415,
            310,
            311,
            312,
            13,
            82,
            81,
            42,
            183,
            78,
        ]
        self.RIGHT_EYE = [
            33,
            7,
            163,
            144,
            145,
            153,
            154,
            155,
            133,
            173,
            157,
            158,
            159,
            160,
            161,
            246,
        ]
        self.LEFT_EYE = [
            362,
            382,
            381,
            380,
            374,
            373,
            390,
            249,
            263,
            466,
            388,
            387,
            386,
            385,
            384,
            398,
        ]

        self.LEFT_EYE_TOP_BOTTOM = [386, 374]
        self.LEFT_EYE_LEFT_RIGHT = [263, 362]
        self.RIGHT_EYE_TOP_BOTTOM = [159, 145]
        self.RIGHT_EYE_LEFT_RIGHT = [133, 33]

        self.UPPER_LOWER_LIPS = [13, 14]
        self.LEFT_RIGHT_LIPS = [78, 308]

        self.FACE = [
            10,
            338,
            297,
            332,
            284,
            251,
            389,
            356,
            454,
            323,
            361,
            288,
            397,
            365,
            379,
            378,
            400,
            377,
            152,
            148,
            176,
            149,
            150,
            136,
            172,
            58,
            132,
            93,
            234,
            127,
            162,
            21,
            54,
            103,
            67,
            109,
        ]

        self.face_model = self.face_mesh.FaceMesh(
            static_image_mode=self.STATIC_IMAGE,
            max_num_faces=self.MAX_NO_FACES,
            min_detection_confidence=self.DETECTION_CONFIDENCE,
            min_tracking_confidence=self.TRACKING_CONFIDENCE,
        )

        self.frame_count = 0
        self.message = "DANG TINH TAO"
        self.ratio_eyes = 3.2

    def euclidean_distance(self, image, top, bottom):
        h, w = image.shape[0:2]
        p1 = int(top.x * w), int(top.y * h)
        p2 = int(bottom.x * w), int(bottom.y * h)
        return dis.euclidean(p1, p2)

    def get_aspect_ratio(self, image, outputs, top_bottom, left_right):
        lmk = outputs.multi_face_landmarks[0]
        top = lmk.landmark[top_bottom[0]]
        bottom = lmk.landmark[top_bottom[1]]
        left = lmk.landmark[left_right[0]]
        right = lmk.landmark[left_right[1]]

        tb = self.euclidean_distance(image, top, bottom)
        lr = self.euclidean_distance(image, left, right)
        return lr / (tb + 1e-4)

    def draw_landmarks(self, image, outputs, land_mark, color):
        h, w = image.shape[:2]
        for idx in land_mark:
            p = outputs.multi_face_landmarks[0].landmark[idx]
            cv2.circle(image, (int(p.x * w), int(p.y * h)), 2, color, 1)

    def draw_eye_line_and_calculate_angle(self, image, outputs):
        h, w = image.shape[:2]
        lmk = outputs.multi_face_landmarks[0]
        right_eye_left_point = lmk.landmark[self.RIGHT_EYE_LEFT_RIGHT[1]]
        left_eye_right_point = lmk.landmark[self.LEFT_EYE_LEFT_RIGHT[0]]
        p1 = (int(right_eye_left_point.x * w), int(right_eye_left_point.y * h))
        p2 = (int(left_eye_right_point.x * w), int(left_eye_right_point.y * h))
        cv2.line(image, p1, p2, self.COLOR_BLUE, 2)
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        angle = math.degrees(math.atan2(dx, dy))
        cv2.putText(
            image,
            f"Angle: {round(angle, 2)}",
            (p1[0], max(0, p1[1] - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            self.COLOR_BLUE,
            1,
            cv2.LINE_AA,
        )
        return image, angle

    def _compute_face_bbox(self, image, outputs):
        """Tạo border box (x1,y1,x2,y2) dựa trên landmarks khuôn mặt đầu tiên."""
        h, w = image.shape[:2]
        lmk = outputs.multi_face_landmarks[0]
        xs, ys = [], []
        # Lấy toàn bộ landmarks của FACE để khung khít khuôn mặt
        for idx in self.FACE:
            p = lmk.landmark[idx]
            xs.append(int(p.x * w))
            ys.append(int(p.y * h))
        if not xs or not ys:  # fallback nếu vì lý do nào đó rỗng
            return None
        x1, y1 = max(0, min(xs)), max(0, min(ys))
        x2, y2 = min(w - 1, max(xs)), min(h - 1, max(ys))
        return (x1, y1, x2, y2)

    def analyze(self, image):
        """
        Trả về:
          - message: trạng thái
          - ratio_eyes: tỉ lệ mắt
          - angle: góc giữa 2 mắt (đường nối)
          - bbox: (x1, y1, x2, y2) hoặc None
          - image_annotated: ảnh đã vẽ landmarks, line, bbox, STATE
        """
        img = image.copy()
        image_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        outputs = self.face_model.process(image_rgb)

        angle = None
        bbox = None

        if outputs.multi_face_landmarks:
            # Vẽ vài landmarks tham chiếu
            self.draw_landmarks(img, outputs, self.FACE, self.COLOR_GREEN)
            self.draw_landmarks(img, outputs, self.LEFT_EYE_TOP_BOTTOM, self.COLOR_RED)
            self.draw_landmarks(img, outputs, self.LEFT_EYE_LEFT_RIGHT, self.COLOR_RED)
            self.draw_landmarks(img, outputs, self.RIGHT_EYE_TOP_BOTTOM, self.COLOR_RED)
            self.draw_landmarks(img, outputs, self.RIGHT_EYE_LEFT_RIGHT, self.COLOR_RED)

            ratio_left = round(
                self.get_aspect_ratio(
                    img, outputs, self.LEFT_EYE_TOP_BOTTOM, self.LEFT_EYE_LEFT_RIGHT
                ),
                2,
            )
            ratio_right = round(
                self.get_aspect_ratio(
                    img, outputs, self.RIGHT_EYE_TOP_BOTTOM, self.RIGHT_EYE_LEFT_RIGHT
                ),
                2,
            )
            self.ratio_eyes = round((ratio_left + ratio_right) / 2.0, 2)

            img, angle = self.draw_eye_line_and_calculate_angle(img, outputs)

            # Logic trạng thái (giống code gốc, nhưng đơn giản frame_count vì xử lý từng ảnh)
            # Ở chế độ ảnh tĩnh, coi như frame_count > 10 nếu mắt bất thường
            if self.ratio_eyes >= 3.5 or self.ratio_eyes <= 2.9:
                # Xét hướng nghiêng đầu nếu đã có angle
                if angle is not None and angle > 110:
                    self.message = "CANH BAO TAI XE DANG NGU GUC SANG PHAI"
                elif angle is not None and angle < 60:
                    self.message = "CANH BAO TAI XE DANG NGU GUC SANG TRAI"
                else:
                    self.message = "CANH BAO TAI XE DANG NGU GAT"
            else:
                self.message = "AWAKE"
        else:
            self.message = "FOCUS"

        # Border box từ landmarks mặt
        if outputs and outputs.multi_face_landmarks:
            bbox = self._compute_face_bbox(img, outputs)
            if bbox:
                x1, y1, x2, y2 = bbox
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 215, 255), 2)  # cam vàng
                cv2.putText(
                    img,
                    "FACE",
                    (x1, max(0, y1 - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 215, 255),
                    1,
                    cv2.LINE_AA,
                )

        # In STATE
        cv2.putText(
            img,
            f"STATE: {self.message}",
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0) if self.message == "AWAKE" else (0, 0, 255),
            2,
            cv2.LINE_AA,
        )

        return (
            self.message,
            self.ratio_eyes,
            angle,
        )
