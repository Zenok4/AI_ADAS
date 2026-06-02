import os
from threading import Lock

_yolo_config_dir = os.path.abspath(".ultralytics")
os.makedirs(_yolo_config_dir, exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", _yolo_config_dir)

import torch
from ultralytics import YOLO

from app.config.settings import settings


_loaded_once = False
_lock = Lock()
loaded_models = {}


def load_models():
    """Load all configured YOLO models once."""
    global loaded_models, _loaded_once
    with _lock:
        if _loaded_once:
            return loaded_models

        print("Loading models...")
        torch.backends.cudnn.benchmark = True

        use_cuda = torch.cuda.is_available()
        device = 0 if use_cuda else "cpu"
        if use_cuda:
            print(f"CUDA available: {torch.cuda.get_device_name(0)}")
        else:
            print("CUDA unavailable: using CPU")

        for name, info in settings.MODELS.items():
            model_path = info.get("path")
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Model '{name}' not found at: {model_path}")

            print(f"  -> Loading '{name}' model from: {model_path}")
            model = YOLO(model_path)
            if use_cuda:
                model.to("cuda")
                print(f"     Model '{name}' loaded on GPU.")
            else:
                print(f"     Model '{name}' loaded on CPU.")

            loaded_models[name] = {
                "model": model,
                "conf": info.get("conf", 0.5),
                "iou": info.get("iou", 0.45),
                "imgsz": info.get("imgsz", 640),
                "max_det": info.get("max_det", 100),
                "agnostic_nms": info.get("agnostic_nms", False),
                "half": bool(info.get("half", False) and use_cuda),
                "device": device,
            }

        _loaded_once = True
        print("All models loaded successfully.")
        return loaded_models


def get_model(name: str):
    """Return a loaded model, loading all models lazily if needed."""
    if not loaded_models:
        load_models()
    model = loaded_models.get(name)
    if not model:
        raise ValueError(f"Model '{name}' not loaded.")
    return model
