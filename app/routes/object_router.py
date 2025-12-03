from flask import Blueprint, request, jsonify
import cv2
import numpy as np
import base64
import time  # <--- 1. Import thư viện time
from app.services.model_loader import get_model

object_bp = Blueprint('object', __name__)

@object_bp.route('/predict', methods=['POST'])
def predict():
    start_time = time.time()  # <--- 2. Bắt đầu bấm giờ
    try:
        # --- (Các bước nhận ảnh và decode giữ nguyên) ---
        data = request.get_json()
        if not data or 'image_base64' not in data:
            return jsonify({"error": "No image provided"}), 400

        image_base64 = data['image_base64']
        
        # Xử lý prefix nếu có
        if "," in image_base64:
            image_base64 = image_base64.split(",")[1]

        try:
            image_bytes = base64.b64decode(image_base64)
            np_arr = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        except Exception:
            return jsonify({"error": "Invalid base64 string"}), 400

        if frame is None:
            return jsonify({"error": "Cannot decode image"}), 400

        # --- (Load model) ---
        try:
            model_info = get_model("object") 
        except ValueError as e:
            return jsonify({"error": str(e)}), 500

        model = model_info["model"]
        conf_thres = model_info.get("conf", 0.5)

        # --- (Predict) ---
        results = model.predict(frame, conf=conf_thres, verbose=False)
        r = results[0]

        detections = []
        if r.boxes:
            for box in r.boxes:
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
        
        # <--- 3. Kết thúc bấm giờ và tính toán
        end_time = time.time()
        process_time = round((end_time - start_time) * 1000, 2) # Đổi sang ms

        return jsonify({
            "status": "success",
            "time_ms": process_time,  # <--- 4. Trả về thời gian
            "data": detections
        })

    except Exception as e:
        print(f"Error in object predict: {e}")
        return jsonify({"error": str(e)}), 500