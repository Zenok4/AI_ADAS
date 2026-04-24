from flask import Blueprint, request, jsonify
import time

from app.services.object_service import object_prediction
from app.utils.image_helper import decode_base64_image

object_bp = Blueprint("object", __name__)


@object_bp.route("/predict", methods=["POST"])
def predict():
    start_time = time.time()

    try:
        data = request.get_json(silent=True) or {}
        if "image_base64" not in data:
            return jsonify({"data": []})

        image_base64 = data.get("image_base64")
        session_id = data.get("session_id")
        ego_state = data.get("ego_state") or {}
        camera_params = data.get("camera") or {}

        frame = decode_base64_image(image_base64)
        if frame is None:
            return jsonify({"data": []})

        result = object_prediction(
            frame=frame,
            session_id=session_id,
            ego_state=ego_state,
            camera_params=camera_params,
        )

        process_time = time.time() - start_time
        return jsonify({
            "data": result.get("objects", []),
            "collision_summary": result.get("summary", {}),
            "processing_time": process_time
        })

    except Exception as e:
        print(f"Router Error: {e}")
        return jsonify({"data": []})
