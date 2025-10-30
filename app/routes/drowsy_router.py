# app/routers/drowsy_bp.py
from flask import Blueprint, request, jsonify
import time
import numpy as np
import cv2

# ĐÚNG TÊN CLASS bạn đang dùng:
# Nếu service là DrowsyDetector:
from app.services.drowsy_service import drowsiDetector as DrowsyDetector

# Nếu file bạn giữ tên class cũ drowsiDetector thì dùng dòng sau thay cho dòng trên:
# from app.services.drowsy_service import drowsiDetector as DrowsyDetector

drowsy_bp = Blueprint("drowsy", __name__)

# Tạo 1 instance dùng chung (tránh khởi tạo mediapipe mỗi request)
detector = DrowsyDetector()


def _bytes_to_cv2_image(b: bytes):
    """Decode ảnh từ bytes -> cv2 BGR image."""
    arr = np.frombuffer(b, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


@drowsy_bp.route("/predict", methods=["POST"])
def drowsy_predict():
    """
    Nhận 1 ảnh (field: 'image') -> JSON:
    {
      "is_drowsy": bool,
      "message": str,
      "ratio_eyes": float,
      "angle": float | null,
      "bbox": [x1,y1,x2,y2] | null,
      "latency_ms": int
    }
    """
    t0 = time.time()

    file = request.files.get("image")
    if file is None:
        return jsonify({"error": "Missing 'image' file"}), 400

    img_bytes = file.read()
    img = _bytes_to_cv2_image(img_bytes)
    if img is None:
        return jsonify({"error": "Invalid image bytes"}), 400

    try:
        message, ratio, angle = detector.analyze(img)

        # Quy ước is_drowsy: khác "AWAKE" và khác "FOCUS" thì coi là buồn ngủ/cảnh báo
        is_drowsy = message not in ("AWAKE", "FOCUS")

        resp = {
            "is_drowsy": bool(is_drowsy),
            "message": message,
            "ratio_eyes": float(ratio),
            "angle": None if angle is None else float(round(angle, 2)),
            "latency_ms": int((time.time() - t0) * 1000),
        }
        return jsonify(resp), 200

    except Exception as e:
        # Log thêm e nếu bạn có logger
        return jsonify({"error": str(e)}), 500
