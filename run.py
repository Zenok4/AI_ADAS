from app.main import create_app
from app.config.settings import settings
from gRPC.grpc_server import start_grpc_server


def main():
    grpc_server = start_grpc_server()
    app = create_app()

    try:
        app.run(host=settings.HOST, port=settings.PORT, debug=False)
    finally:
        grpc_server.stop(grace=1)


if __name__ == "__main__":
    main()
else:
    app = create_app()
