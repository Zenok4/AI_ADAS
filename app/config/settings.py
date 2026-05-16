import yaml

from app.middleware.roi_filter import build_roi_config
from app.services.sub_service.lane_departure import build_lane_departure_config

class Settings:
    def __init__(self, file_path="config.yaml"):
        with open(file_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        self.HOST = config["server"]["host"]
        self.PORT = config["server"]["port"]
        self.GRPC_PORT = config["server"]["grpc_port"]
        self.MODELS = config["models"]

        roi_config = config.get("roi", {})
        self.ROI = {
            name: build_roi_config(raw)
            for name, raw in roi_config.items()
        }
        self.LANE_DEPARTURE = build_lane_departure_config(
            config.get("lane_departure", {})
        )
        self.COLLISION = config.get("collision", {})

settings = Settings()
