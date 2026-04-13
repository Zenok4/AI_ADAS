from app.services.model_loader import get_model
from app.utils.convert_classname import get_vietnamese_name

def object_prediction(frame):
    try:
        model_info = get_model("object")
        model = model_info["model"]

        results = model.predict(frame, conf=0.40, verbose=False)
        r = results[0]
        
        detections = []

        if r.boxes:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])

                label = get_vietnamese_name(cls_id, model_type='object')

                detections.append({
                    "bbox": [int(x1), int(y1), int(x2), int(y2)],  # ✅ FIX
                    "label": label,                                 # ✅ FIX
                    "confidence": round(conf, 2)
                })
        
        return detections

    except Exception as e:
        print(f"Error in object_prediction: {e}")
        return []