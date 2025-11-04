import os
from ultralytics import YOLO
from app.config.settings import settings

# Biến toàn cục giữ model đã load
loaded_models = {}

def load_models():
    """
    Load tất cả models được khai báo trong settings.models
    Model chỉ load một lần khi server khởi động.
    """
    global loaded_models

    if loaded_models:
        # Nếu đã load thì không cần load lại
        return loaded_models

    print("🔹 Loading models...")

    for name, info in settings.MODELS.items():
        model_path = info.get("path")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model '{name}' not found at: {model_path}")

        print(f"  → Loading '{name}' model from: {model_path}")
        model = YOLO(model_path)
        loaded_models[name] = {
            "model": model,
            "conf": info.get("conf", 0.5),
            "iou": info.get("iou", 0.45)
        }

    print("All models loaded successfully!\n")
    return loaded_models


def get_model(name: str):
    """
    Lấy model theo tên (ví dụ: 'sign')
    """
    if not loaded_models:
        load_models()
    return loaded_models.get(name)
