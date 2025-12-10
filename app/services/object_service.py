from app.services.model_loader import get_model

def object_prediction(frame):
    """
    Hàm xử lý dự đoán vật cản (Object Detection)
    Input: Frame ảnh (OpenCV numpy array)
    Output: List các object detect được
    """
    try:
        # 1. Lấy model đã load
        model_info = get_model("object")
        model = model_info["model"]

        # 2. Dự đoán (Giữ ngưỡng 0.40 để nhạy hơn với xe ở xa)
        results = model.predict(frame, conf=0.40, verbose=False)
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
                    "confidence": round(conf, 2)
                })
        
        return detections

    except Exception as e:
        print(f"Error in object_prediction: {e}")
        return []