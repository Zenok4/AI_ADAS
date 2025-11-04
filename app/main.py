from flask import Flask
<<<<<<< HEAD

# from app.routes.predict import predict_bp
from app.routes.drowsy_router import drowsy_bp


def create_app():
    app = Flask(__name__)
    # app.register_blueprint(predict_bp, url_prefix="/api")
    app.register_blueprint(drowsy_bp, url_prefix="/drowsy")
=======
from app.routes.sign_router import sign_bp

def create_app():
    app = Flask(__name__)
    app.register_blueprint(sign_bp, url_prefix="/sign")
>>>>>>> origin/nlinh
    return app
