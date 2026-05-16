from app.services.lane_context_service import (
    analyze_current_lane,
    annotate_detection_lane_position,
)


def test_analyze_current_lane_when_vehicle_is_centered():
    detections = [
        {
            "class_name": "left_lane",
            "confidence": 0.8,
            "line": [160.0, 479.0, 280.0, 288.0],
        },
        {
            "class_name": "right_lane",
            "confidence": 0.9,
            "line": [480.0, 479.0, 360.0, 288.0],
        },
    ]

    current_lane = analyze_current_lane(detections, (480, 640, 3))

    assert current_lane["available"] is True
    assert current_lane["status"] == "centered"
    assert current_lane["lane_center_x"] == 320.0
    assert current_lane["lane_width_px"] == 320.0
    assert current_lane["offset_px"] == 0.0


def test_annotate_detection_lane_position():
    current_lane = {
        "available": True,
        "left_boundary": {"x_at_reference": 160.0},
        "right_boundary": {"x_at_reference": 480.0},
    }

    result = annotate_detection_lane_position(
        {"box": [300.0, 200.0, 340.0, 300.0]},
        current_lane,
    )

    assert result["in_current_lane"] is True
    assert result["lane_position"] == "current_lane"
