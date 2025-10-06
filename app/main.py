from flask import Flask
from app.routes.predict import predict_bp

def create_app():
    app = Flask(__name__)
    app.register_blueprint(predict_bp, url_prefix="/api")
    return app
