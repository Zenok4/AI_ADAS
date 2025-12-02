from flask import Blueprint, request, jsonify
import cv2
import numpy as np
import base64
from app.services.model_loader import get_model

object_bp = Blueprint('object', __name__)

@object_bp.route('/predict', methods=['POST'])
def predict():
    try:
        # 1. Nhận dữ liệu JSON
        data = request.get_json()
        if not data or 'image_base64' not in data:
            return jsonify({"error": "No image provided"}), 400

        image_base64 = data['image_base64']

        # 2. Decode Base64 -> Ảnh OpenCV
        try:
            image_bytes = base64.b64decode(image_base64)
            np_arr = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        except Exception:
            return jsonify({"error": "Invalid base64 string"}), 400

        if frame is None:
            return jsonify({"error": "Cannot decode image"}), 400

        # 3. Lấy model Object (Key phải khớp với trong config.yaml)
        try:
            # Lưu ý: Key này phải là "object" hoặc tên bạn đặt trong config.yaml
            model_info = get_model("object") 
        except ValueError as e:
            return jsonify({"error": str(e)}), 500

        model = model_info["model"]
        conf_thres = model_info.get("conf", 0.5)

        # 4. Predict
        results = model.predict(frame, conf=conf_thres, verbose=False)
        r = results[0]

        detections = []
        if r.boxes:
            for box in r.boxes:
                # Lấy tọa độ và thông tin
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                label = model.names[cls_id]

                detections.append({
                    "box": [int(x1), int(y1), int(x2), int(y2)],
                    "class_name": label,
                    "confidence": round(conf, 2),
                    "type": "object"
                })

        return jsonify({
            "status": "success",
            "data": detections
        })

    except Exception as e:
        print(f"Error in object predict: {e}")
        return jsonify({"error": str(e)}), 500