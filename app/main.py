from flask import Flask

from app.routes.drowsy_router import drowsy_bp
from app.routes.sign_router import sign_bp
from app.services.model_loader import load_models


def create_app():
    app = Flask(__name__)
    app.register_blueprint(drowsy_bp, url_prefix="/drowsy")
    app.register_blueprint(sign_bp, url_prefix="/sign")

    # Load models AI
    load_models()

    return app
