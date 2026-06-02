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
    assert current_lane["warning"] is False
    assert current_lane["warning_level"] == "none"


def test_analyze_current_lane_warns_when_vehicle_departs_right():
    detections = [
        {
            "class_name": "left_lane",
            "confidence": 0.8,
            "line": [60.0, 479.0, 250.0, 288.0],
        },
        {
            "class_name": "right_lane",
            "confidence": 0.9,
            "line": [380.0, 479.0, 350.0, 288.0],
        },
    ]

    current_lane = analyze_current_lane(detections, (480, 640, 3))

    assert current_lane["available"] is True
    assert current_lane["status"] == "right_departure"
    assert current_lane["warning"] is True
    assert current_lane["warning_direction"] == "right"
    assert current_lane["warning_level"] == "departure"


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
