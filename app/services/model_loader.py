from ultralytics import YOLO
from tensorflow.keras.models import load_model # type: ignore
from app.config.settings import settings

def load_models():
    print("[INFO] Loading models from YAML config ...")
    models = {}

    for name, cfg in settings.MODELS.items():
        path = cfg.get("path")
        if path.endswith(".pt"): 
            models[name] = YOLO(path)
        elif path.endswith(".h5"):
            models[name] = load_model(path)
        else:
            print(f"[WARN] Unsupported model format for {name}: {path}")
    print("[INFO] All models loaded successfully.")
    return models
