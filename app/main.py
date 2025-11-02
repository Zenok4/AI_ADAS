from flask import Flask
from app.routes.sign_router import sign_bp

def create_app():
    app = Flask(__name__)
    app.register_blueprint(sign_bp, url_prefix="/sign")
    return app
