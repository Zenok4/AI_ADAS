#!/usr/bin/env python3
import datetime
import yaml
from pathlib import Path

README_PATH = Path("README.md")
CONFIG_PATH = Path("config.yaml")

IGNORED_FOLDERS = {"__pycache__", "venv", "venv-ai-adas", ".vscode"}


def build_tree(directory: Path, prefix=""):
    lines = []
    items = sorted([p for p in directory.iterdir() if not p.name.startswith(".")])
    for idx, item in enumerate(items):
        connector = "└── 📂" if idx == len(items) - 1 else "├── 📄"
        if item.is_dir():
            if item.name not in IGNORED_FOLDERS:
                lines.append(f"{prefix}{connector}{item.name}/")
                extension = "    " if idx == len(items) - 1 else "│   "
                lines.extend(build_tree(item, prefix + extension))
        else:
            if item.suffix in {".py", ".yaml", ".yml", ".txt", ".md"}:
                lines.append(f"{prefix}{connector}{item.name}")
    return lines


def generate_readme():
    print("[THÔNG TIN] Đang tạo README.md ...")

    # Đọc thông tin các model từ file YAML nếu có
    models_info = ""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
            if "models" in cfg:
                for name, model_cfg in cfg["models"].items():
                    models_info += f"- **{name}** → `{model_cfg.get('path', 'chưa xác định')}`\n"

    # Tạo phần mô tả cấu trúc thư mục
    print("[THÔNG TIN] Đang quét cấu trúc thư mục ...")
    structure = ["```", *build_tree(Path(".")), "```"]

    readme_content = f"""# 🧠 AI_ADAS Server

---

## ⚙️ Chức năng chính
- Phát hiện làn đường
- Nhận dạng biển báo giao thông  
- Phát hiện buồn ngủ 
- Phát hiện vật thể
- Cấu hình thông qua `config.yaml`

---

## 🧩 Cấu trúc thư mục dự án
{chr(10).join(structure)}

---

## 📘 Hướng dẫn cài đặt và sử dụng

### 1. Tạo môi trường ảo
Tạo môi trường ảo trong thư mục gốc của dự án:
```bash
cd AI_ADAS
python -m venv venv-ai-adas
```

### 2. Kích hoạt môi trường ảo
Kích hoạt môi trường ảo bằng một trong hai lệnh sau:

**Lệnh 1: **
```bash
venv-ai-adas\\Scripts\\activate
```

**Lệnh 2 (nếu lệnh 1 không hoạt động):**
```bash
source venv-ai-adas\\Scripts\\activate
```

### 3. Cài đặt thư viện cần thiết
Cài đặt toàn bộ thư viện từ tệp `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 4. Cài thư viện
Nếu muốn cài thêm thư viện thì gõ lệnh sau:
```bash
pip install <tên_thư_viện>
pip freeze > requirements.txt
```

### 5. Chạy server AI
Chạy server Flask:
```bash
python run.py
```

Sau khi chạy thành công, server hoạt động tại:
```
http://localhost:8500/api/predict
```

## 🧠 Các mô hình AI khả dụng
{models_info if models_info else '_Chưa có model nào trong file config.yaml_'}

---

## 🕒 Generated
{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

> File này được tạo tự động bởi `generate_readme.py`. Đừng chỉnh sửa thủ công!
"""

    README_PATH.write_text(readme_content, encoding="utf-8")
    print(f"[OK] Đã tạo README.md thành công → {README_PATH.resolve()}")


if __name__ == "__main__":
    generate_readme()
