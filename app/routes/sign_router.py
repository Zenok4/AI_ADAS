from flask import Blueprint, request, jsonify
from app.utils.image_helper import read_image
from app.services.sign_service import sign_prediction
import imghdr

sign_bp = Blueprint("sign", __name__)

@sign_bp.route("/predict", methods=["POST"])
def sign_predict():
    try:
        image_file = request.files.get("image")
        if not image_file:
            return jsonify({"data": []})

        print("Received file:", image_file.filename)

        # Kiểm tra hợp lệ
        header = image_file.read(512)
        image_file.seek(0)
        file_type = imghdr.what(None, header)
        if file_type is None:
            print("Không phải ảnh hợp lệ")
            return jsonify({"data": []})

        # Đọc ảnh
        frame = read_image(image_file)
        if frame is None:
            print("Không đọc được ảnh từ file")
            return jsonify({"data": []})

        # Nhận diện bằng YOLO
        detections = sign_prediction(frame)
        print(f"Phát hiện {len(detections)} biển báo")

        # Trả kết quả
        return jsonify({"data": detections})

    except Exception as e:
        print("Error in sign_predict:", e)
        return jsonify({"data": []})
