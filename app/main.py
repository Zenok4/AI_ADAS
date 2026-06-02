from flask import Flask
import logging

from app.routes.drowsy_router import drowsy_bp
from app.routes.sign_router import sign_bp
from app.routes.object_router import object_bp 
from app.routes.lane_router import lane_bp
from app.routes.vehicle_state_router import vehicle_state_bp

from app.services.model_loader import load_models, loaded_models
from app.utils.warm_up_model import warmup_all

from debug.visual_logger import VisualLogger
from logger import setup_logger


def create_app():
    setup_logger()
    logger = logging.getLogger("APP")

    app = Flask(__name__)
    
    app.register_blueprint(drowsy_bp, url_prefix="/drowsy")
    app.register_blueprint(sign_bp, url_prefix="/sign")
    app.register_blueprint(object_bp, url_prefix="/object") 
    app.register_blueprint(lane_bp, url_prefix="/lane")
    app.register_blueprint(vehicle_state_bp, url_prefix="/vehicle")

    logger.info("✅ Routes registered")

    # Load models AI
    if not loaded_models:
        logger.info("🧠 Loading models...")
        load_models()
        warmup_all()
        logger.info("🔥 Models ready")

    # 👉 thêm debug tools
    app.config["visual_logger"] = VisualLogger()

    return app