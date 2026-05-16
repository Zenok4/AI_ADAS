"""
app/services/sub_service/sign_name_builder.py

Ghép tên biển chính + thông tin biển phụ thành tên hiển thị theo template.

Ví dụ:
  main="Cấm đỗ xe"  time_ranges=["6h30-8h", "16h30-18h"]
  → "Cấm đỗ xe [6h30-8h, 16h30-18h]"

  main="Cấm xe tải"  vehicle="xe tải >2.5t"  time_ranges=["7h-19h"]
  → "Cấm xe tải >2.5t [7h-19h]"
"""

from __future__ import annotations


def build_combined_name(
    main_name: str,
    *,
    time_range:   str | None = None,        # backward-compat (1 range)
    time_ranges:  list[str] | None = None,  # ưu tiên nếu có nhiều range
    distance:     str | None = None,
    vehicle_type: str | None = None,
    extra_texts:  list[str] | None = None,
) -> str:
    """
    Template:
        <tên chính> [<vehicle>] [cách <distance>] [<time1>, <time2>, ...]  [<extra>...]
    """
    # Xác định danh sách time range cần hiển thị
    ranges = time_ranges or ([time_range] if time_range else [])

    parts: list[str] = []

    # Tên chính — nếu có vehicle_type thì thay thế phần loại xe chung
    if vehicle_type:
        base = _strip_generic_vehicle(main_name)
        parts.append(f"{base} {vehicle_type}".strip())
    else:
        parts.append(main_name.strip())

    if distance:
        parts.append(f"[cách {distance}]")

    if ranges:
        parts.append(f"[{', '.join(ranges)}]")

    if extra_texts:
        for t in extra_texts:
            t = t.strip()
            if t:
                parts.append(f"[{t}]")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GENERIC_VEHICLE_SUFFIXES = (
    " xe tải",
    " xe khách",
    " xe máy",
    " ô tô",
    " oto",
)


def _strip_generic_vehicle(name: str) -> str:
    lower = name.lower()
    for suffix in _GENERIC_VEHICLE_SUFFIXES:
        if lower.endswith(suffix):
            return name[: -len(suffix)].strip()
    return name