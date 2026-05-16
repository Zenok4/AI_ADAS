"""
app/services/sub_service/sign_ocr_parser.py

Parse kết quả OCR từ biển phụ thành các trường có cấu trúc.

Hỗ trợ các format thời gian:
  - 7h, 7h30, 7H30         (dạng h)
  - 6:30, 08:00, 16:30     (dạng HH:MM)
  - 6h30 - 8h00
  - 6:30 - 8:00
  - Nhiều khoảng thời gian: "6:30 - 8:00  16:30 - 18:00"
"""

from __future__ import annotations
import re


# ---------------------------------------------------------------------------
# Regex
# ---------------------------------------------------------------------------

# Token giờ — khớp cả "7h", "7h30", "07:30", "16:30"
_TIME_TOKEN = r"\d{1,2}(?:[hH]\d{0,2}|:\d{2})"

_TIME_RANGE_RE = re.compile(
    rf"({_TIME_TOKEN})\s*[-–]\s*({_TIME_TOKEN})",
    re.IGNORECASE,
)

_DISTANCE_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(km|m)\b",
    re.IGNORECASE,
)

_VEHICLE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"xe\s*t[aả]i\s*[>≥]?\s*(\d+[.,]?\d*)\s*t[aấ]n?", re.I), "xe tải >{val}t"),
    (re.compile(r"xe\s*t[aả]i",   re.I), "xe tải"),
    (re.compile(r"xe\s*kh[áa]ch", re.I), "xe khách"),
    (re.compile(r"xe\s*m[áa]y",   re.I), "xe máy"),
    (re.compile(r"[oô]t[oô]",     re.I), "ô tô"),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_sub_sign_text(raw_text: str) -> dict:
    """
    Trả về dict:
      time_range   : str | None  — khoảng thời gian đầu tiên, vd "6h30-8h00"
      time_ranges  : list[str]   — tất cả khoảng thời gian tìm được
      distance     : str | None
      vehicle_type : str | None
      raw_text     : str
    """
    text = raw_text.strip()
    result: dict = {
        "time_range":   None,
        "time_ranges":  [],
        "distance":     None,
        "vehicle_type": None,
        "raw_text":     text,
    }

    # --- Tất cả time ranges ---
    all_ranges = []
    for m in _TIME_RANGE_RE.finditer(text):
        t1 = _normalise_time(m.group(1))
        t2 = _normalise_time(m.group(2))
        all_ranges.append(f"{t1}-{t2}")

    if all_ranges:
        result["time_ranges"] = all_ranges
        result["time_range"]  = all_ranges[0]   # backward-compat

    # --- Khoảng cách ---
    m = _DISTANCE_RE.search(text)
    if m:
        val  = m.group(1).replace(",", ".")
        unit = m.group(2).lower()
        result["distance"] = f"{val}{unit}"

    # --- Loại xe ---
    for pattern, label in _VEHICLE_PATTERNS:
        m = pattern.search(text)
        if m:
            if "{val}" in label:
                try:
                    val = m.group(1).replace(",", ".")
                    result["vehicle_type"] = label.replace("{val}", val)
                except IndexError:
                    result["vehicle_type"] = label.replace("{val}", "")
            else:
                result["vehicle_type"] = label
            break

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise_time(t: str) -> str:
    """
    Chuẩn hoá token giờ về dạng "XhYY" hoặc "Xh".
      "6:30"  → "6h30"
      "08:00" → "8h00"
      "7h"    → "7h"
      "7h30"  → "7h30"
    """
    t = t.strip()

    # Dạng HH:MM
    if ":" in t:
        parts = t.split(":")
        hour  = str(int(parts[0]))          # bỏ leading zero
        minute = parts[1].zfill(2)
        if minute == "00":
            return f"{hour}h"
        return f"{hour}h{minute}"

    # Dạng Xh hoặc XhYY
    t = t.replace("H", "h")
    if t.endswith("h"):
        return t
    return t