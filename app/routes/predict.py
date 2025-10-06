from flask import Blueprint, request, jsonify
from app.services.model_loader import load_models
from app.utils.image_helper import read_image
from app.config.settings import settings
import time

predict_bp = Blueprint("predict", __name__)
models = load_models()

@predict_bp.route("/predict", methods=["POST"])
def predict():
    image = request.files.get("image")
    model_name = request.form.get("model", "lane")

    if not image:
        return jsonify({"error": "Missing image"}), 400

    if model_name not in models:
        return jsonify({"error": f"Unknown model: {model_name}"}), 400

    frame = read_image(image)
    cfg = settings.MODELS.get(model_name, {})
    start = time.time()

    if model_name == "sign":
        detections = []
    elif model_name == "drowsy":
        detections = []

    else:
        return jsonify({"error": "Unsupported model type"}), 400

    duration = round((time.time() - start) * 1000, 2)

    return jsonify({
        "model": model_name,
        "detections": detections,
        "time_ms": duration
    })
