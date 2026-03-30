import yaml

class Settings:
    def __init__(self, file_path="config.yaml"):
        with open(file_path, "r") as f:
            config = yaml.safe_load(f)

        self.HOST = config["server"]["host"]
        self.PORT = config["server"]["port"]
        self.MODELS = config["models"]

        self.COLLISION = config.get("collision", {})

settings = Settings()
