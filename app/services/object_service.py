import time
from app.services.model_loader import get_model
from app.utils.convert_classname import get_vietnamese_name
from app.services.collision_service import CollisionRiskService


risk_service = CollisionRiskService()

def object_prediction(
    frame,
    session_id=None,
    ego_state=None,
    camera_params=None,
):                     
    """
    1. Detect objects
    2. Analyze collision risk from camera detections
    3. Return enriched objects + summary
    """
    try:
        model_info = get_model("object")

        results = run_prediction(model_info, frame)
        
        detections = []

        detections.append({
            "box": [int(x1), int(y1), int(x2), int(y2)],
            "class_id": cls_id,
            "class_name": label,
            "confidence": round(conf, 2)
        })
        
        analysis = risk_service.analyze_camera_detections(
                    detections=detections,
                    frame_shape=frame.shape,
                    session_id=session_id,
                    ego_state=ego_state or {},
                    camera_params=camera_params or {},
                )

        enriched_objects = []
        analyzed_objects = analysis.get("objects", [])

        for index, det in enumerate(detections):
            enriched = dict(det)

            if index < len(analyzed_objects):
                scored = analyzed_objects[index]
                risk = scored.get("risk", {})

                enriched["distance_m"] = scored.get("distance_m")
                enriched["collision_risk"] = {
                    "severity": risk.get("severity"),
                    "warning": risk.get("warning"),
                    "ttc_s": risk.get("ttc_s"),
                    "closing_speed_mps": risk.get("closing_speed_mps"),
                    "in_path": risk.get("in_path"),
                    "emit_event": risk.get("emit_event"),
                }

            enriched_objects.append(enriched)

        return {
            "objects": enriched_objects,
            "summary": analysis.get("summary", {
                "highest_severity": "safe",
                "num_objects": len(enriched_objects),
                "num_events": 0,
                "requires_brake": False,
            })
        }

    except Exception as e:
        print(f"Error in object_prediction: {e}")
        return {
            "objects": [],
            "summary": {
                "highest_severity": "safe",
                "num_objects": 0,
                "num_events": 0,
                "requires_brake": False,
            }
        }