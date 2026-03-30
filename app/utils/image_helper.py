import base64
import numpy as np
import cv2

def read_image(file_storage):
    img_bytes = np.frombuffer(file_storage.read(), np.uint8)
    frame = cv2.imdecode(img_bytes, cv2.IMREAD_COLOR)
    return frame

def decode_base64_image(image_base64: str):
    if not image_base64:
        return None

    try:
        if "," in image_base64:
            image_base64 = image_base64.split(",", 1)[1]

        image_bytes = base64.b64decode(image_base64)
        np_arr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return frame
    except Exception:
        return None
