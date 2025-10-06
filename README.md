# 🧠 AI_ADAS Server

---

## ⚙️ Chức năng chính
- Phát hiện làn đường
- Nhận dạng biển báo giao thông  
- Phát hiện buồn ngủ 
- Phát hiện vật thể
- Cấu hình thông qua `config.yaml`

---

## 🧩 Cấu trúc thư mục dự án
```
├── 📂 app/
│   ├── 📄 __init__.py
│   ├── 📂 config/
│   │   ├── 📄 __init__.py
│   │   └── 📄 settings.py
│   ├── 📄 main.py
│   ├── 📂 routes/
│   │   ├── 📄 __init__.py
│   │   └── 📄 predict.py
│   ├── 📂 services/
│   │   ├── 📄 __init__.py
│   │   └── 📄 model_loader.py
│   └── 📂 utils/
│       └── 📄 image_helper.py
├── 📄 config.yaml
├── 📄 generate_changelog.py
├── 📄 generate_readme.py
├── 📂 models/
├── 📄 README.md
├── 📄 requirements.txt
├── 📄 run.py
```

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

**Lệnh 1 (Windows):**
```bash
venv-ai-adas\Scripts\activate
```

**Lệnh 2 (Linux/macOS):**
```bash
source venv-ai-adas/bin/activate
```

### 3. Cài đặt thư viện cần thiết
Cài đặt toàn bộ thư viện từ tệp `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 4. Cài thêm thư viện mới (nếu cần)
```bash
pip install <tên_thư_viện>
pip freeze > requirements.txt
```

### 5. Chạy server AI
```bash
python run.py
```

Server chạy tại:
```
http://localhost:8500/api/predict
```

---

## 🧠 Các mô hình AI khả dụng
- **lane** → `models/lane.pt`
- **sign** → `models/sign.pt`
- **object** → `models/object.pt`
- **drowsy** → `models/drowsy.h5`


---

## 🕒 Generated
2025-10-06 16:08:48

---

> File này được tạo tự động bởi `generate_readme.py`. Đừng chỉnh sửa thủ công!
