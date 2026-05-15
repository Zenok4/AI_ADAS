import argparse
import math
import os
import sys
import time
from datetime import datetime

import cv2
import numpy as np
import unicodedata

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    Image = None
    ImageDraw = None
    ImageFont = None

CURRENT_FILE = os.path.abspath(__file__)
TEST_DIR = os.path.dirname(CURRENT_FILE)
PROJECT_ROOT = os.path.dirname(TEST_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.services.model_loader import load_models
from app.services.object_service import object_prediction
from app.services.lane_service import lane_prediction
from app.services.sign_service import sign_prediction
from app.services.collision_service import CollisionService
from app.services.sub_service.tracking_service import TrackingService
from app.services.sub_service.speed_service import SpeedEstimationService
from app.utils.convert_classname import OBJECT_CLASSES
from debug.visual_logger import VisualLogger

try:
    from app.services.sub_service.combined_sign_service import CombinedSignService
except Exception:
    CombinedSignService = None


LEVEL_COLOR = {
    "safe": (0, 255, 0),
    "low": (0, 255, 255),
    "medium": (0, 165, 255),
    "high": (0, 0, 255),
    "critical": (0, 0, 180),
}


_FONT_CACHE = {}
OBJECT_LABEL_TO_ID = {name: idx for idx, name in OBJECT_CLASSES.items()}


class SignEventCounter:
    """
    Äáº¿m sá»± kiá»‡n biá»ƒn bÃ¡o theo track thay vÃ¬ Ä‘áº¿m thÃ´ theo tá»«ng frame.

    Má»¥c tiÃªu:
    - CÃ¹ng 1 biá»ƒn xuáº¥t hiá»‡n nhiá»u frame chá»‰ tÃ­nh 1 láº§n.
    - Chá»‹u Ä‘Æ°á»£c trÆ°á»ng há»£p che khuáº¥t ngáº¯n háº¡n (occlusion).
    - Giáº£m Ä‘áº¿m láº·p báº±ng bá»™ nhá»› biá»ƒn Ä‘Ã£ tÃ­nh gáº§n Ä‘Ã¢y.
    """

    def __init__(
        self,
        iou_threshold=0.35,
        max_missed=15,
        min_hits=3,
        recall_window_frames=180,
        recall_distance_px=180.0,
    ):
        self.iou_threshold = float(iou_threshold)
        self.max_missed = int(max_missed)
        self.min_hits = int(min_hits)
        self.recall_window_frames = int(recall_window_frames)
        self.recall_distance_px = float(recall_distance_px)

        self.next_id = 1
        self.total_count = 0
        self.tracks = {}
        self.recent_counted = []

    @staticmethod
    def _iou(box_a, box_b):
        ax1, ay1, ax2, ay2 = [float(v) for v in box_a]
        bx1, by1, bx2, by2 = [float(v) for v in box_b]

        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)
        iw = max(0.0, ix2 - ix1)
        ih = max(0.0, iy2 - iy1)
        inter = iw * ih
        if inter <= 0:
            return 0.0

        area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
        area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
        union = max(area_a + area_b - inter, 1e-6)
        return inter / union

    def _cleanup_stale(self, frame_idx):
        stale_ids = [
            track_id
            for track_id, tr in self.tracks.items()
            if frame_idx - int(tr["last_frame"]) > self.max_missed
        ]
        for track_id in stale_ids:
            del self.tracks[track_id]
        self.recent_counted = [
            item
            for item in self.recent_counted
            if frame_idx - int(item["frame"]) <= self.recall_window_frames
        ]

    @staticmethod
    def _center(box):
        x1, y1, x2, y2 = [float(v) for v in box]
        return (0.5 * (x1 + x2), 0.5 * (y1 + y2))

    def _should_suppress_recount(self, label, bbox, frame_idx):
        cx, cy = self._center(bbox)
        for item in self.recent_counted:
            if item["label"] != label:
                continue
            if frame_idx - int(item["frame"]) > self.recall_window_frames:
                continue
            dx = cx - float(item["cx"])
            dy = cy - float(item["cy"])
            if (dx * dx + dy * dy) ** 0.5 <= self.recall_distance_px:
                return True
        return False

    def _mark_counted_memory(self, label, bbox, frame_idx):
        cx, cy = self._center(bbox)
        self.recent_counted.append(
            {
                "label": label,
                "cx": cx,
                "cy": cy,
                "frame": frame_idx,
            }
        )

    def update(self, detections, frame_idx):
        self._cleanup_stale(frame_idx)
        new_events = 0

        unmatched_det_idx = set(range(len(detections)))
        active_track_ids = list(self.tracks.keys())

        # Greedy matching based on highest IoU with same label.
        candidates = []
        for track_id in active_track_ids:
            tr = self.tracks[track_id]
            for det_idx, det in enumerate(detections):
                if det["label"] != tr["label"]:
                    continue
                iou = self._iou(tr["bbox"], det["bbox"])
                if iou >= self.iou_threshold:
                    candidates.append((iou, track_id, det_idx))

        candidates.sort(reverse=True, key=lambda x: x[0])
        matched_tracks = set()
        matched_dets = set()
        for _, track_id, det_idx in candidates:
            if track_id in matched_tracks or det_idx in matched_dets:
                continue
            tr = self.tracks[track_id]
            det = detections[det_idx]
            tr["bbox"] = det["bbox"]
            tr["last_frame"] = frame_idx
            tr["hits"] += 1
            matched_tracks.add(track_id)
            matched_dets.add(det_idx)
            if not tr["counted"] and tr["hits"] >= self.min_hits:
                tr["counted"] = True
                if not self._should_suppress_recount(tr["label"], tr["bbox"], frame_idx):
                    self.total_count += 1
                    new_events += 1
                    self._mark_counted_memory(tr["label"], tr["bbox"], frame_idx)

        unmatched_det_idx -= matched_dets

        # Create new tracks for detections that did not match.
        for det_idx in sorted(unmatched_det_idx):
            det = detections[det_idx]
            track_id = self.next_id
            self.next_id += 1

            counted = self.min_hits <= 1
            self.tracks[track_id] = {
                "label": det["label"],
                "bbox": det["bbox"],
                "hits": 1,
                "last_frame": frame_idx,
                "counted": counted,
            }

            if counted:
                if not self._should_suppress_recount(det["label"], det["bbox"], frame_idx):
                    self.total_count += 1
                    new_events += 1
                    self._mark_counted_memory(det["label"], det["bbox"], frame_idx)

        return self.total_count, new_events


def _find_unicode_font():
    """TÃ¬m font há»‡ thá»‘ng cÃ³ há»— trá»£ Unicode tiáº¿ng Viá»‡t."""
    candidates = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\tahoma.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _get_font(size):
    """Láº¥y font tá»« cache Ä‘á»ƒ giáº£m chi phÃ­ váº½ text má»—i frame."""
    if ImageFont is None:
        return None
    size = max(12, int(size))
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    font_path = _find_unicode_font()
    if not font_path:
        return None
    try:
        font = ImageFont.truetype(font_path, size=size)
        _FONT_CACHE[size] = font
        return font
    except Exception:
        return None


def _ascii_fallback(text):
    """Fallback khi khÃ´ng cÃ³ PIL/font Unicode: bá» dáº¥u Ä‘á»ƒ cv2 váº«n váº½ Ä‘Æ°á»£c."""
    normalized = unicodedata.normalize("NFKD", str(text))
    return normalized.encode("ascii", "ignore").decode("ascii")


def draw_text(frame, text, org, color, font_px=18):
    """
    Váº½ text Unicode lÃªn frame.
    - Æ¯u tiÃªn PIL + font TTF (hiá»ƒn thá»‹ tiáº¿ng Viá»‡t Ä‘Ãºng).
    - Náº¿u thiáº¿u PIL/font thÃ¬ fallback sang cv2.putText.
    """
    x, y = int(org[0]), int(org[1])
    if Image is None or ImageDraw is None:
        cv2.putText(
            frame,
            _ascii_fallback(text),
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
        )
        return frame

    font = _get_font(font_px)
    if font is None:
        cv2.putText(
            frame,
            _ascii_fallback(text),
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
        )
        return frame

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb)
    drawer = ImageDraw.Draw(pil_img)
    rgb_color = (int(color[2]), int(color[1]), int(color[0]))
    drawer.text((x, y), str(text), font=font, fill=rgb_color)
    bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    frame[:, :] = bgr
    return frame


def parse_args():
    """Khai bÃ¡o toÃ n bá»™ tham sá»‘ cháº¡y script test video."""
    parser = argparse.ArgumentParser(
        description="Run AI_ADAS logic on an input video and export annotated output video."
    )
    parser.add_argument("--input", required=True, help="Input video path.")
    parser.add_argument("--output", default="", help="Output video path (.mp4 recommended).")
    parser.add_argument("--max-frames", type=int, default=0, help="Limit processed frames (0 = all).")
    parser.add_argument("--resize-width", type=int, default=0, help="Resize output width (0 = original).")
    parser.add_argument("--output-fps", type=float, default=0.0, help="Override output FPS (0 = use source FPS).")

    parser.add_argument("--disable-object", action="store_true", help="Disable object logic.")
    parser.add_argument("--disable-lane", action="store_true", help="Disable lane logic.")
    parser.add_argument("--disable-sign", action="store_true", help="Disable sign logic.")

    parser.add_argument(
        "--use-combined-sign",
        action="store_true",
        help="Use CombinedSignService (EasyOCR pipeline).",
    )
    parser.add_argument(
        "--ego-speed-kmh",
        type=float,
        default=0.0,
        help="Simulated ego speed used for GPS emulation in speed pipeline.",
    )
    parser.add_argument("--start-lat", type=float, default=10.762622, help="Starting latitude.")
    parser.add_argument("--start-lon", type=float, default=106.660172, help="Starting longitude.")
    parser.add_argument(
        "--sign-log-every",
        type=int,
        default=30,
        help="Print sign detection count every N frames (0 = disable).",
    )
    parser.add_argument(
        "--class-log",
        default="",
        help="Optional TXT path to save timestamp + class_id logs for object/sign/lane.",
    )
    return parser.parse_args()


def simulate_next_gps(lat, lon, speed_kmh, dt):
    """Sinh GPS giáº£ cho frame káº¿ tiáº¿p dá»±a trÃªn tá»‘c Ä‘á»™ giáº£ láº­p."""
    meters = max(speed_kmh, 0.0) / 3.6 * max(dt, 0.0)
    if meters <= 0:
        return lat, lon

    lat_rad = math.radians(lat)
    dlon = meters / max(111320.0 * math.cos(lat_rad), 1e-6)
    return lat, lon + dlon


def draw_objects_with_collision(frame, objects, ego_speed, summary):
    """
    Váº½ object + thÃ´ng tin cáº£nh bÃ¡o va cháº¡m.
    Logic giá»¯ nguyÃªn: chá»‰ hiá»ƒn thá»‹ dá»¯ liá»‡u Ä‘Ã£ tÃ­nh tá»« collision pipeline.
    """
    for obj in objects:
        bbox = obj.get("bbox") or []
        if len(bbox) < 4:
            continue

        x1, y1, x2, y2 = [int(v) for v in bbox]
        level = str(obj.get("warning_level", "safe")).lower()
        color = LEVEL_COLOR.get(level, (0, 255, 0))

        label = obj.get("label", "")
        conf = float(obj.get("confidence", 0.0))
        obj_id = int(obj.get("id", 0))
        speed = float(obj.get("speed", 0.0))
        distance = obj.get("distance_m")
        ttc = obj.get("ttc_s")

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        line1 = f"{label} {conf:.2f} | ID:{obj_id} | v:{speed:.1f}km/h"
        line2 = f"d:{distance if distance is not None else '-'}m ttc:{ttc if ttc is not None else '-'}s {level}"

        draw_text(frame, line1, (x1, max(20, y1 - 34)), color, font_px=17)
        draw_text(frame, line2, (x1, max(20, y1 - 16)), color, font_px=16)

    draw_text(frame, f"EGO: {ego_speed:.1f} km/h", (20, 10), (255, 255, 255), font_px=34)

    overall_level = str(summary.get("overall_level", "safe")).lower()
    overall_msg = str(summary.get("overall_message", "AN TOAN"))
    level_color = LEVEL_COLOR.get(overall_level, (0, 255, 0))

    draw_text(frame, f"COLLISION: {overall_level.upper()}", (20, 48), level_color, font_px=30)
    draw_text(frame, overall_msg[:90], (20, 78), level_color, font_px=28)

    return frame


def draw_basic_sign(frame, detections):
    """Váº½ label biá»ƒn bÃ¡o tá»« sign_prediction (dáº¡ng dict)."""
    for det in detections:
        if "meta" in det:
            continue
        box = det.get("box") or []
        if len(box) < 4:
            continue
        x1, y1, x2, y2 = [int(v) for v in box]
        label = det.get("class_name", "")
        conf = float(det.get("confidence", 0.0))
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 0), 2)
        draw_text(frame, f"{label} {conf:.2f}", (x1, max(20, y1 - 18)), (0, 220, 0), font_px=17)
    return frame


def draw_combined_sign_unicode(frame, detections):
    """Váº½ label biá»ƒn bÃ¡o tá»« CombinedSignService (dáº¡ng dataclass/object)."""
    for det in detections:
        box = getattr(det, "box", None) or []
        if len(box) < 4:
            continue
        x1, y1, x2, y2 = [int(v) for v in box]
        label = getattr(det, "combined_name", "") or getattr(det, "class_name", "")
        conf = float(getattr(det, "confidence", 0.0))
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 0), 2)
        draw_text(frame, f"{label} {conf:.2f}", (x1, max(20, y1 - 18)), (0, 220, 0), font_px=17)
    return frame


def collect_sign_items(detections):
    """
    Chuáº©n hÃ³a output sign vá» format chung cho SignEventCounter:
    [{bbox, label}, ...]
    """
    items = []
    for det in detections:
        if isinstance(det, dict):
            if "meta" in det:
                continue
            box = det.get("box") or []
            label = str(det.get("class_name", "")).strip()
        else:
            box = getattr(det, "box", None) or []
            label = str(getattr(det, "combined_name", "") or getattr(det, "class_name", "")).strip()

        if len(box) < 4:
            continue
        if not label:
            label = "unknown_sign"
        items.append({"bbox": [float(v) for v in box[:4]], "label": label})
    return items


def collect_sign_records(detections):
    """Chuáº©n hÃ³a records sign Ä‘á»ƒ ghi TXT class_id theo tá»«ng frame."""
    records = []
    for det in detections:
        if isinstance(det, dict):
            if "meta" in det:
                continue
            box = det.get("box") or []
            class_id = int(det.get("class_id", -1))
            label = str(det.get("class_name", "")).strip()
            conf = float(det.get("confidence", 0.0))
        else:
            box = getattr(det, "box", None) or []
            class_id = int(getattr(det, "class_id", -1))
            label = str(getattr(det, "combined_name", "") or getattr(det, "class_name", "")).strip()
            conf = float(getattr(det, "confidence", 0.0))

        if len(box) < 4:
            continue
        records.append(
            {
                "class_id": class_id,
                "label": label if label else "unknown_sign",
                "confidence": conf,
                "bbox": [int(v) for v in box[:4]],
            }
        )
    return records


def collect_lane_records(detections):
    """Chuáº©n hÃ³a records lane Ä‘á»ƒ ghi TXT class_id theo tá»«ng frame."""
    records = []
    for det in detections:
        box = det.get("box", [])
        if len(box) < 4:
            continue
        records.append(
            {
                "class_id": int(det.get("class_id", -1)),
                "label": str(det.get("class_name", "")).strip(),
                "confidence": float(det.get("confidence", 0.0)),
                "bbox": [int(v) for v in box[:4]],
            }
        )
    return records


def collect_object_records(detections):
    """Chuáº©n hÃ³a records object Ä‘á»ƒ ghi TXT class_id theo tá»«ng frame."""
    records = []
    for det in detections:
        box = det.get("bbox", [])
        if len(box) < 4:
            continue
        label = str(det.get("label", "")).strip()
        records.append(
            {
                "class_id": int(OBJECT_LABEL_TO_ID.get(label, -1)),
                "label": label if label else "unknown_object",
                "confidence": float(det.get("confidence", 0.0)),
                "bbox": [int(v) for v in box[:4]],
            }
        )
    return records


def write_class_section(log_fp, section_name, records):
    log_fp.write(f"{section_name}_COUNT: {len(records)}\n")
    if not records:
        return
    for rec in records:
        log_fp.write(
            f"  class_id={rec['class_id']} | label={rec['label']} | conf={rec['confidence']:.2f} | bbox={rec['bbox']}\n"
        )


def make_default_output_path(input_path):
    """Táº¡o Ä‘Æ°á»ng dáº«n output máº·c Ä‘á»‹nh theo timestamp."""
    base = os.path.splitext(os.path.basename(input_path))[0]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join("test", "results", "video_pipeline")
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, f"{base}_full_logic_{stamp}.mp4")


def main():
    # =========================================================
    # 1) Parse args + validate input/output
    # =========================================================
    args = parse_args()

    if not os.path.exists(args.input):
        raise FileNotFoundError(f"Input video not found: {args.input}")

    output_path = args.output.strip() or make_default_output_path(args.input)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    class_log_path = args.class_log.strip() or (os.path.splitext(output_path)[0] + "_classes.txt")
    os.makedirs(os.path.dirname(class_log_path) or ".", exist_ok=True)

    # =========================================================
    # 2) Init models + services (khÃ´ng thay Ä‘á»•i logic chÃ­nh)
    # =========================================================
    print("[INIT] Loading models...")
    load_models()
    print("[INIT] Models loaded.")

    visual = VisualLogger()
    tracker = TrackingService()
    speed_service = SpeedEstimationService()
    collision_service = CollisionService()
    sign_event_counter = SignEventCounter(
        iou_threshold=0.30,
        max_missed=45,
        min_hits=3,
        recall_window_frames=180,
        recall_distance_px=180.0,
    )

    # Combined sign lÃ  tÃ¹y chá»n; náº¿u khÃ´ng init Ä‘Æ°á»£c thÃ¬ fallback sign thÆ°á»ng.
    combined_sign_service = None
    if args.use_combined_sign and not args.disable_sign:
        if CombinedSignService is None:
            print("[WARN] CombinedSignService unavailable. Fallback to sign_prediction.")
        else:
            try:
                combined_sign_service = CombinedSignService(ocr_gpu=False)
                print("[INIT] CombinedSignService ready (OCR GPU disabled).")
            except Exception as exc:
                print(f"[WARN] Cannot init CombinedSignService: {exc}")
                print("[WARN] Fallback to sign_prediction.")

    # =========================================================
    # 3) Open input video + init writer
    # =========================================================
    cap = cv2.VideoCapture(args.input)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {args.input}")

    src_fps = cap.get(cv2.CAP_PROP_FPS)
    if src_fps is None or src_fps <= 1e-6:
        src_fps = 25.0
    out_fps = args.output_fps if args.output_fps > 1e-6 else src_fps

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if args.resize_width > 0:
        scale = args.resize_width / float(width)
        width = int(args.resize_width)
        height = int(height * scale)

    writer = cv2.VideoWriter(
        output_path,
        cv2.VideoWriter_fourcc(*"mp4v"),
        out_fps,
        (width, height),
    )
    if not writer.isOpened():
        cap.release()
        raise RuntimeError("Cannot open VideoWriter. Try another output path or codec.")

    print(f"[RUN] Input: {args.input}")
    print(f"[RUN] Output: {output_path}")
    print(f"[RUN] FPS: src={src_fps:.2f}, out={out_fps:.2f}")
    print(f"[RUN] Size: {width}x{height}")

    # =========================================================
    # 4) Runtime states cho vÃ²ng láº·p frame
    # =========================================================
    frame_idx = 0
    lat, lon = args.start_lat, args.start_lon
    first_capture_ts = time.time()
    sign_counter = 0
    class_log_fp = open(class_log_path, "w", encoding="utf-8")
    class_log_fp.write("# AI_ADAS frame class-id log\n")
    class_log_fp.write("# Format: per frame, timestamp + OBJECT/SIGN/LANE sections\n\n")

    # =========================================================
    # 5) Main loop: read frame -> detect -> render -> write
    # =========================================================
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            if args.resize_width > 0:
                frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_LINEAR)

            # Timestamp + GPS giáº£ cho frame hiá»‡n táº¡i
            captured_at = first_capture_ts + (frame_idx / out_fps)
            if frame_idx > 0:
                lat, lon = simulate_next_gps(lat, lon, args.ego_speed_kmh, 1.0 / out_fps)

            render = frame.copy()

            # -------------------------------------------------
            # LANE PIPELINE
            # -------------------------------------------------
            lane_detections = []
            lane_records = []
            if not args.disable_lane:
                lane_detections = lane_prediction(frame)
                lane_records = collect_lane_records(lane_detections)
                render = visual.draw_lane(render, lane_detections)
                # HOOK-LANE-DEPARTURE:
                # Náº¿u muá»‘n thÃªm tÃ­nh nÄƒng lá»‡ch lÃ n, hÃ£y báº¯t Ä‘áº§u táº¡i Ä‘Ã¢y.
                # Báº¡n Ä‘Ã£ cÃ³ sáºµn lane_detections cá»§a frame hiá»‡n táº¡i.
                # Gá»£i Ã½ triá»ƒn khai:
                # 1. TÃ­nh lane center trÃ¡i/pháº£i tá»« lane_detections.
                # 2. TÃ­nh vehicle center (vÃ­ dá»¥: width/2 cá»§a frame hoáº·c bbox ego náº¿u cÃ³).
                # 3. So sÃ¡nh Ä‘á»™ lá»‡ch (offset) vÃ  Ä‘á»•i thÃ nh tráº¡ng thÃ¡i: LEFT/RIGHT/SAFE.
                # 4. Váº½ cáº£nh bÃ¡o lÃªn render vÃ  ghi log/CSV tÆ°Æ¡ng tá»± sign_count.

            # -------------------------------------------------
            # SIGN PIPELINE + EVENT COUNTER
            # -------------------------------------------------
            sign_count = 0
            new_sign_events = 0
            sign_records = []
            if not args.disable_sign:
                if combined_sign_service is not None:
                    sign_output = combined_sign_service.predict(frame)
                    sign_count = len(sign_output.detections)
                    render = draw_combined_sign_unicode(render, sign_output.detections)
                    sign_items = collect_sign_items(sign_output.detections)
                    sign_records = collect_sign_records(sign_output.detections)
                else:
                    sign_detections = sign_prediction(frame)
                    sign_count = len([d for d in sign_detections if "meta" not in d])
                    render = draw_basic_sign(render, sign_detections)
                    sign_items = collect_sign_items(sign_detections)
                    sign_records = collect_sign_records(sign_detections)

                sign_counter, new_sign_events = sign_event_counter.update(sign_items, frame_idx)

            # -------------------------------------------------
            # OBJECT + TRACKING + SPEED + COLLISION PIPELINE
            # -------------------------------------------------
            obj_count = 0
            object_records = []
            ego_speed = 0.0
            collision_summary = {"overall_level": "safe", "overall_message": "AN TOAN"}
            if not args.disable_object:
                obj_detections = object_prediction(frame)
                object_records = collect_object_records(obj_detections)
                tracks = tracker.track(obj_detections)
                ego_speed = speed_service.compute_ego_speed(lat, lon, captured_at)
                speed_results = speed_service.estimate(tracks, ego_speed)
                collision_result = collision_service.analyze(
                    speed_results,
                    frame_shape=frame.shape,
                    captured_at=captured_at,
                )
                obj_count = len(collision_result.get("objects", []))
                collision_summary = collision_result.get("summary", collision_summary)
                render = draw_objects_with_collision(
                    render,
                    collision_result.get("objects", []),
                    ego_speed,
                    collision_summary,
                )

            # -------------------------------------------------
            # HUD overlay (thÃ´ng tin tá»•ng há»£p trÃªn video)
            # -------------------------------------------------
            draw_text(
                render,
                f"frame:{frame_idx} obj:{obj_count} sign:{sign_counter} lane:{len(lane_detections)}",
                (20, height - 32),
                (255, 255, 255),
                font_px=24,
            )
            draw_text(
                render,
                f"lat:{lat:.6f} lon:{lon:.6f}",
                (20, height - 60),
                (220, 220, 220),
                font_px=20,
            )

            # -------------------------------------------------
            # TXT logging: timestamp + class_id theo tá»«ng nhÃ³m
            # -------------------------------------------------
            ts_iso = datetime.fromtimestamp(captured_at).isoformat(timespec="milliseconds")
            class_log_fp.write(f"FRAME: {frame_idx} | TIMESTAMP: {ts_iso} | UNIX: {captured_at:.6f}\n")
            write_class_section(class_log_fp, "OBJECT", object_records)
            write_class_section(class_log_fp, "SIGN", sign_records)
            write_class_section(class_log_fp, "LANE", lane_records)
            class_log_fp.write("\n")

            writer.write(render)
            frame_idx += 1

            if args.max_frames > 0 and frame_idx >= args.max_frames:
                break

            if args.sign_log_every > 0 and frame_idx % args.sign_log_every == 0:
                print(f"[SIGN] frame={frame_idx} sign={sign_counter} new={new_sign_events} frame_det={sign_count}")
            if frame_idx % 30 == 0:
                print(f"[RUN] Processed {frame_idx} frames...")
    except KeyboardInterrupt:
        print("\n[STOP] Interrupted by user. Finalizing partial output...")
    finally:
        cap.release()
        writer.release()
        class_log_fp.close()

    print(f"[DONE] Total frames: {frame_idx}")
    print(f"[DONE] Output saved: {output_path}")
    print(f"[DONE] Class log saved: {class_log_path}")


if __name__ == "__main__":
    main()

