import yaml
from app.middleware.roi_filter import build_roi_config, ROIConfig
from typing import Dict

class Settings:
    def __init__(self, file_path="config.yaml"):
        with open(file_path, "r") as f:
            config = yaml.safe_load(f)

        self.HOST = config["server"]["host"]
        self.PORT = config["server"]["port"]
        self.GRPC_PORT = config["server"]["grpc_port"]
        self.MODELS = config["models"]

        # ROI config cho từng module
        raw_roi = config.get("roi", {})
        self.ROI: Dict[str, ROIConfig] = {
            module: build_roi_config(raw_roi.get(module))
            for module in ("sign", "object", "lane")
        }

settings = Settings()
