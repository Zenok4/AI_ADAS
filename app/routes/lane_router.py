from flask import Blueprint, request, jsonify
from app.services.lane_service import lane_prediction
import base64, cv2
import numpy as np

lane_bp = Blueprint("lane", __name__)

_EMPTY_RESPONSE = {
    "detections": [],
    "lane_departure": {
        "status": "no_lane",
        "message": "Không phát hiện vạch làn đường",
        "lane_offset": 0.0,
        "left_lane": None,
        "right_lane": None,
    }
}


@lane_bp.route("/predict", methods=["POST"])
def lane_predict():
    try:
        data = request.get_json()
        if not data or "image_base64" not in data:
            return jsonify(_EMPTY_RESPONSE), 400

        base64_url = data["image_base64"]

        # Decode ảnh từ base64
        try:
            if "," in base64_url:
                base64_url = base64_url.split(",")[1]

            img_bytes = base64.b64decode(base64_url)
            np_arr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        except Exception as e:
            print("Decode base64 lane failed:", e)
            return jsonify(_EMPTY_RESPONSE), 400

        if frame is None:
            print("Không tạo được ảnh lane từ base64")
            return jsonify(_EMPTY_RESPONSE), 400

        # YOLO detect lane + phân tích lệch làn
        result = lane_prediction(frame)
        departure = result["lane_departure"]

        print(
            f"Phát hiện {len(result['detections'])} vạch | "
            f"Trạng thái: {departure['status']} | "
            f"Offset: {departure['lane_offset']:.3f}"
        )

        return jsonify(result)

    except Exception as e:
        print("Lane Error:", e)
        return jsonify(_EMPTY_RESPONSE), 500
