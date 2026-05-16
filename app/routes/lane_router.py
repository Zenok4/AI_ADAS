from flask import Blueprint, request, jsonify
import time

from app.services.lane_service import lane_prediction
from app.utils.image_helper import decode_base64_image


lane_bp = Blueprint("lane", __name__)


@lane_bp.route("/predict", methods=["POST"])
def lane_predict():
    start_time = time.time()

    try:
        data = request.get_json(silent=True) or {}
        if "image_base64" not in data:
            return jsonify({"data": []})

        frame = decode_base64_image(data.get("image_base64"))
        if frame is None:
            print("Cannot decode lane image from base64")
            return jsonify({"data": []})

        method = data.get("method", "opencv")
        detections = lane_prediction(frame, method=method)
        print(f"Detected {len(detections)} lane markings")

        return jsonify(
            {
                "data": detections,
                "detections": detections,
                "processing_time": time.time() - start_time,
            }
        )

    except Exception as e:
        print("Lane Error:", e)
        return jsonify({"data": []})
