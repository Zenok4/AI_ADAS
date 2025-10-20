import os
from roboflow import Roboflow
import dotenv

dotenv.load_dotenv()

rf = Roboflow(api_key=os.getenv("ROBOFLOWKEY"))
project = rf.workspace(os.getenv("ROBOWORKSPACE")).project(os.getenv("ROBOPROJECT"))
version = project.version(os.getenv("ROVOVERSION"))
dataset = version.download(os.getenv("DATASETFORMAT"))

old_name = dataset.location
new_name = "datasets"

os.rename(old_name, new_name)
print(f"✅ Đã đổi tên thư mục thành: {new_name}")
