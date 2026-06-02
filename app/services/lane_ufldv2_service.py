from __future__ import annotations

import os
import site
from dataclasses import dataclass
from threading import Lock

import cv2
import numpy as np

from app.config.settings import settings


@dataclass(frozen=True)
class UFLDV2Config:
    model_path: str
    dataset: str = "Tusimple"
    input_width: int = 800
    input_height: int = 320
    resize_height: int = 400
    num_row: int = 56
    num_col: int = 41
    num_cell_row: int = 100
    num_cell_col: int = 100
    local_width: int = 1


class UFLDV2LaneDetector:
    def __init__(self, cfg: UFLDV2Config):
        self.cfg = cfg
        if not os.path.exists(cfg.model_path):
            raise FileNotFoundError(f"UFLD V2 ONNX model not found: {cfg.model_path}")

        self.session = None
        self.input_name = None
        self.output_names = None
        self.net = None
        self.backend = "opencv_dnn"

        self._init_onnxruntime()
        if self.session is None:
            self.net = cv2.dnn.readNetFromONNX(cfg.model_path)
            self.output_names = list(self.net.getUnconnectedOutLayersNames())
            print("UFLD V2 using OpenCV DNN backend")

        self.row_anchor, self.col_anchor = _anchors(cfg.dataset, cfg.num_row, cfg.num_col)

    def predict(self, frame: np.ndarray) -> list[dict]:
        if frame is None or frame.size == 0:
            return []

        original_h, original_w = frame.shape[:2]
        blob = self._preprocess(frame)
        raw_outputs = self._forward(blob)
        pred = {name: output for name, output in zip(self.output_names, raw_outputs)}

        lanes = _pred_to_coords(
            pred=pred,
            row_anchor=self.row_anchor,
            col_anchor=self.col_anchor,
            cfg=self.cfg,
            original_image_width=original_w,
            original_image_height=original_h,
        )
        return _lanes_to_detections(lanes, original_w, original_h)

    def _init_onnxruntime(self) -> None:
        _preload_nvidia_dlls()
        try:
            import onnxruntime as ort
        except ImportError:
            return

        available = ort.get_available_providers()
        providers = []
        if "CUDAExecutionProvider" in available:
            providers.append("CUDAExecutionProvider")
        providers.append("CPUExecutionProvider")

        self.session = ort.InferenceSession(self.cfg.model_path, providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [output.name for output in self.session.get_outputs()]
        self.backend = "onnxruntime"
        print(f"UFLD V2 using ONNX Runtime providers: {self.session.get_providers()}")

    def _forward(self, blob: np.ndarray) -> list[np.ndarray]:
        if self.session is not None:
            return self.session.run(self.output_names, {self.input_name: blob})

        self.net.setInput(blob)
        return self.net.forward(self.output_names)

    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (self.cfg.input_width, self.cfg.resize_height))
        cropped = resized[-self.cfg.input_height :, :, :]
        image = cropped.astype(np.float32) / 255.0
        image = (image - np.array([0.485, 0.456, 0.406], dtype=np.float32)) / np.array(
            [0.229, 0.224, 0.225],
            dtype=np.float32,
        )
        return np.transpose(image, (2, 0, 1))[None, ...].astype(np.float32)


_detector = None
_detector_lock = Lock()


def detect_lane_lines_ufldv2(frame: np.ndarray) -> list[dict]:
    detector = _get_detector()
    return detector.predict(frame)


def _get_detector() -> UFLDV2LaneDetector:
    global _detector
    if _detector is None:
        with _detector_lock:
            if _detector is None:
                _detector = UFLDV2LaneDetector(_config_from_settings())
    return _detector


def _config_from_settings() -> UFLDV2Config:
    lane_cfg = settings.MODELS.get("lane", {})
    model_path = lane_cfg.get(
        "ufldv2_onnx",
        "external/Ultra-Fast-Lane-Detection-v2/ufldv2_tusimple_res18_320x800.onnx",
    )
    return UFLDV2Config(
        model_path=model_path,
        dataset=lane_cfg.get("ufldv2_dataset", "Tusimple"),
        input_width=int(lane_cfg.get("ufldv2_input_width", 800)),
        input_height=int(lane_cfg.get("ufldv2_input_height", 320)),
        resize_height=int(lane_cfg.get("ufldv2_resize_height", 400)),
        num_row=int(lane_cfg.get("ufldv2_num_row", 56)),
        num_col=int(lane_cfg.get("ufldv2_num_col", 41)),
        num_cell_row=int(lane_cfg.get("ufldv2_num_cell_row", 100)),
        num_cell_col=int(lane_cfg.get("ufldv2_num_cell_col", 100)),
    )


_dll_directory_handles = []
_dll_directories_loaded = False


def _preload_nvidia_dlls() -> None:
    global _dll_directories_loaded
    if _dll_directories_loaded:
        return

    if os.name != "nt" or not hasattr(os, "add_dll_directory"):
        return

    package_roots = []
    try:
        package_roots.extend(site.getsitepackages())
    except AttributeError:
        pass

    for root in package_roots:
        nvidia_root = os.path.join(root, "nvidia")
        if not os.path.isdir(nvidia_root):
            continue

        for package_name in os.listdir(nvidia_root):
            dll_dir = os.path.join(nvidia_root, package_name, "bin")
            if os.path.isdir(dll_dir):
                _dll_directory_handles.append(os.add_dll_directory(dll_dir))
                os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")

    _dll_directories_loaded = True


def _anchors(dataset: str, num_row: int, num_col: int) -> tuple[np.ndarray, np.ndarray]:
    if dataset == "Tusimple":
        row_anchor = np.linspace(160, 710, num_row, dtype=np.float32) / 720.0
    elif dataset == "CULane":
        row_anchor = np.linspace(0.42, 1.0, num_row, dtype=np.float32)
    else:
        row_anchor = np.linspace(0.4, 1.0, num_row, dtype=np.float32)
    col_anchor = np.linspace(0.0, 1.0, num_col, dtype=np.float32)
    return row_anchor, col_anchor


def _pred_to_coords(
    pred: dict[str, np.ndarray],
    row_anchor: np.ndarray,
    col_anchor: np.ndarray,
    cfg: UFLDV2Config,
    original_image_width: int,
    original_image_height: int,
) -> list[list[tuple[int, int]]]:
    loc_row = pred["loc_row"]
    loc_col = pred["loc_col"]
    exist_row = pred["exist_row"]
    exist_col = pred["exist_col"]

    max_indices_row = loc_row.argmax(axis=1)
    valid_row = exist_row.argmax(axis=1)
    max_indices_col = loc_col.argmax(axis=1)
    valid_col = exist_col.argmax(axis=1)

    coords: list[list[tuple[int, int]]] = []

    for lane_idx in [1, 2]:
        lane_points = []
        if valid_row[0, :, lane_idx].sum() > cfg.num_row / 2:
            for k in range(valid_row.shape[1]):
                if not valid_row[0, k, lane_idx]:
                    continue
                center = int(max_indices_row[0, k, lane_idx])
                indices = np.arange(
                    max(0, center - cfg.local_width),
                    min(cfg.num_cell_row - 1, center + cfg.local_width) + 1,
                    dtype=np.int64,
                )
                logits = loc_row[0, indices, k, lane_idx]
                weights = _softmax(logits)
                x = ((weights * indices.astype(np.float32)).sum() + 0.5)
                x = x / (cfg.num_cell_row - 1) * original_image_width
                y = row_anchor[k] * original_image_height
                lane_points.append((int(x), int(y)))
        coords.append(lane_points)

    for lane_idx in [0, 3]:
        lane_points = []
        if valid_col[0, :, lane_idx].sum() > cfg.num_col / 4:
            for k in range(valid_col.shape[1]):
                if not valid_col[0, k, lane_idx]:
                    continue
                center = int(max_indices_col[0, k, lane_idx])
                indices = np.arange(
                    max(0, center - cfg.local_width),
                    min(cfg.num_cell_col - 1, center + cfg.local_width) + 1,
                    dtype=np.int64,
                )
                logits = loc_col[0, indices, k, lane_idx]
                weights = _softmax(logits)
                y = ((weights * indices.astype(np.float32)).sum() + 0.5)
                y = y / (cfg.num_cell_col - 1) * original_image_height
                x = col_anchor[k] * original_image_width
                lane_points.append((int(x), int(y)))
        coords.append(lane_points)

    return [lane for lane in coords if len(lane) >= 2]


def _lanes_to_detections(
    lanes: list[list[tuple[int, int]]],
    image_width: int,
    image_height: int,
) -> list[dict]:
    center_x = image_width / 2.0
    lane_infos = []

    for lane in lanes:
        points = sorted(lane, key=lambda point: point[1])
        line = _fit_lane_line(points, image_width, image_height)
        if line is None:
            continue
        x_bottom = line[0]
        lane_infos.append(
            {
                "points": points,
                "line": line,
                "x_bottom": x_bottom,
                "distance_to_center": abs(x_bottom - center_x),
            }
        )

    left = [lane for lane in lane_infos if lane["x_bottom"] < center_x]
    right = [lane for lane in lane_infos if lane["x_bottom"] >= center_x]
    selected = []
    if left:
        selected.append(("left_lane", min(left, key=lambda lane: lane["distance_to_center"])))
    if right:
        selected.append(("right_lane", min(right, key=lambda lane: lane["distance_to_center"])))

    detections = []
    for class_name, lane in selected:
        class_id = 0 if class_name == "left_lane" else 1
        x1, y1, x2, y2 = lane["line"]
        box = [
            float(min(x1, x2)),
            float(min(y1, y2)),
            float(max(x1, x2)),
            float(max(y1, y2)),
        ]
        detections.append(
            {
                "box": box,
                "line": [float(x1), float(y1), float(x2), float(y2)],
                "confidence": min(1.0, len(lane["points"]) / 20.0),
                "class_id": class_id,
                "class_name": class_name,
                "points": [[float(x), float(y)] for x, y in lane["points"]],
                "method": "ufldv2_onnxruntime",
            }
        )

    return detections


def _fit_lane_line(
    points: list[tuple[int, int]],
    image_width: int,
    image_height: int,
) -> list[int] | None:
    if len(points) < 2:
        return None

    pts = np.array(points, dtype=np.float32)
    y = pts[:, 1]
    x = pts[:, 0]
    if np.ptp(y) < 1.0:
        return None

    slope, intercept = np.polyfit(y, x, 1)
    y_bottom = image_height - 1
    y_top = max(int(np.min(y)), int(image_height * 0.45))
    x_bottom = int(np.clip(slope * y_bottom + intercept, 0, image_width - 1))
    x_top = int(np.clip(slope * y_top + intercept, 0, image_width - 1))
    return [x_bottom, y_bottom, x_top, y_top]


def _softmax(values: np.ndarray) -> np.ndarray:
    values = values.astype(np.float32)
    values = values - np.max(values)
    exp = np.exp(values)
    return exp / np.sum(exp)
