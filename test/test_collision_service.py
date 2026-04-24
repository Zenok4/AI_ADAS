import unittest

from app.services.collision_service import CollisionRiskService


class TestCollisionRiskService(unittest.TestCase):
    def setUp(self):
        self.service = CollisionRiskService()

    def test_camera_object_in_path_should_not_be_low_when_close(self):
        result = self.service.analyze(
            detections=[
                {
                    "box": [540, 300, 740, 600],
                    "class_id": 2,
                    "class_name": "Ô tô",
                    "confidence": 0.92,
                }
            ],
            ego_state={"speed_mps": 15.0, "heading_deg": 0.0},
            frame_shape=(720, 1280, 3),
            camera_params={
                "focal_length_px": 800,
                "principal_point": {"x": 640, "y": 360},
            },
            session_id="cam_test_1",
        )

        risk = result["objects"][0]["risk"]
        self.assertIn(risk["severity"], ["medium", "high", "critical"])

    def test_sensor_object_should_generate_ttc(self):
        result = self.service.analyze(
            ego_state={"speed_mps": 0.0, "heading_deg": 0.0},
            sensor_objects=[
                {
                    "object_id": "sensor_1",
                    "class_name": "Ô tô",
                    "position": {"x": 0.2, "y": 10.0},
                    "velocity": {"x": 0.0, "y": -5.0},
                }
            ],
            session_id="sensor_test_1",
        )

        risk = result["objects"][0]["risk"]
        self.assertIsNotNone(risk["ttc_s"])
        self.assertTrue(risk["emit_event"])

    def test_empty_request_should_return_no_objects(self):
        result = self.service.analyze(
            ego_state={},
            sensor_objects=[],
            detections=[],
            frame_shape=None,
            session_id="empty_test",
        )

        self.assertEqual(result["summary"]["num_objects"], 0)
        self.assertEqual(result["summary"]["highest_severity"], "safe")


if __name__ == "__main__":
    unittest.main()
