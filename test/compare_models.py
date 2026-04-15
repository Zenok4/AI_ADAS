import cv2
import os
from ultralytics import YOLO

# ==========================================
# 1. CẤU HÌNH ĐƯỜNG DẪN TỰ ĐỘNG
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))

INPUT_DIR = os.path.join(current_dir, "images") 
OLD_MODEL_PATH = os.path.join(current_dir, "..", "models", "lane", "best.pt")
NEW_MODEL_PATH = os.path.join(current_dir, "..", "models", "lane", "best_new.pt")

OUTPUT_OLD_DIR = os.path.join(current_dir, "results", "compare_old")
OUTPUT_NEW_DIR = os.path.join(current_dir, "results", "compare_new")
SUMMARY_FILE = os.path.join(current_dir, "results", "compare_summary.txt")

def main():
    print("🚀 BẮT ĐẦU CHƯƠNG TRÌNH SO SÁNH 2 MODEL YOLO 🚀")
    
    if not os.path.exists(OLD_MODEL_PATH):
        print(f"❌ Không tìm thấy model cũ tại: {OLD_MODEL_PATH}")
        return
    if not os.path.exists(NEW_MODEL_PATH):
        print(f"❌ Không tìm thấy model mới tại: {NEW_MODEL_PATH}")
        return
    if not os.path.exists(INPUT_DIR):
        print(f"❌ Không tìm thấy thư mục ảnh: {INPUT_DIR}")
        return

    os.makedirs(OUTPUT_OLD_DIR, exist_ok=True)
    os.makedirs(OUTPUT_NEW_DIR, exist_ok=True)

    print("\n🔄 Đang load models vào bộ nhớ...")
    try:
        model_old = YOLO(OLD_MODEL_PATH)
        model_new = YOLO(NEW_MODEL_PATH)
    except Exception as e:
        print(f"❌ Lỗi khi load model: {e}")
        return
    print("✅ Load models thành công!")

    valid_ext = (".jpg", ".jpeg", ".png", ".bmp")
    image_files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(valid_ext)]
    
    if not image_files:
        print(f"❌ Không có ảnh nào trong thư mục {INPUT_DIR}")
        return

    total_images = len(image_files)
    print(f"\n🖼️ Tìm thấy {total_images} ảnh. Đang tiến hành dự đoán...\n")

    # --- Biến lưu trữ thống kê ---
    stats_old = {"boxes": 0, "conf_sum": 0.0, "time_sum": 0.0}
    stats_new = {"boxes": 0, "conf_sum": 0.0, "time_sum": 0.0}

    # Chạy dự đoán
    for idx, img_name in enumerate(image_files, 1):
        img_path = os.path.join(INPUT_DIR, img_name)
        
        # 1. Chạy Model Cũ
        res_old = model_old.predict(source=img_path, conf=0.45, verbose=False)[0]
        img_old_annotated = res_old.plot()
        cv2.imwrite(os.path.join(OUTPUT_OLD_DIR, img_name), img_old_annotated)
        
        # Thu thập dữ liệu Model Cũ
        num_boxes_old = len(res_old.boxes)
        stats_old["boxes"] += num_boxes_old
        if num_boxes_old > 0:
            stats_old["conf_sum"] += res_old.boxes.conf.sum().item()
        stats_old["time_sum"] += res_old.speed['inference']

        # 2. Chạy Model Mới
        res_new = model_new.predict(source=img_path, conf=0.45, verbose=False)[0]
        img_new_annotated = res_new.plot()
        cv2.imwrite(os.path.join(OUTPUT_NEW_DIR, img_name), img_new_annotated)

        # Thu thập dữ liệu Model Mới
        num_boxes_new = len(res_new.boxes)
        stats_new["boxes"] += num_boxes_new
        if num_boxes_new > 0:
            stats_new["conf_sum"] += res_new.boxes.conf.sum().item()
        stats_new["time_sum"] += res_new.speed['inference']
        
        print(f"✅ [{idx}/{total_images}] Đã xử lý xong: {img_name} (Cũ: {num_boxes_old} box | Mới: {num_boxes_new} box)")

    # --- TÍNH TOÁN TỔNG THỂ ---
    avg_conf_old = (stats_old["conf_sum"] / stats_old["boxes"]) if stats_old["boxes"] > 0 else 0
    avg_time_old = stats_old["time_sum"] / total_images

    avg_conf_new = (stats_new["conf_sum"] / stats_new["boxes"]) if stats_new["boxes"] > 0 else 0
    avg_time_new = stats_new["time_sum"] / total_images

    # --- TẠO BÁO CÁO ---
    report = f"""
==================================================
📊 BÁO CÁO ĐÁNH GIÁ TỔNG THỂ KẾT QUẢ SO SÁNH
==================================================
Tổng số ảnh đã test: {total_images} ảnh
Ngưỡng tin cậy (Conf) áp dụng: 0.45

1. MODEL CŨ (best.pt):
   - Tổng số vật thể phát hiện: {stats_old['boxes']}
   - Độ tin cậy trung bình    : {avg_conf_old:.2f} ({(avg_conf_old*100):.1f}%)
   - Tốc độ xử lý trung bình  : {avg_time_old:.2f} ms/ảnh

2. MODEL MỚI (best_new.pt):
   - Tổng số vật thể phát hiện: {stats_new['boxes']}
   - Độ tin cậy trung bình    : {avg_conf_new:.2f} ({(avg_conf_new*100):.1f}%)
   - Tốc độ xử lý trung bình  : {avg_time_new:.2f} ms/ảnh

💡 NHẬN XÉT NHANH:
- Model Mới bắt được {'nhiều hơn' if stats_new['boxes'] > stats_old['boxes'] else 'ít hơn' if stats_new['boxes'] < stats_old['boxes'] else 'bằng'} Model Cũ {abs(stats_new['boxes'] - stats_old['boxes'])} vật thể.
- Model Mới chạy {'nhanh hơn' if avg_time_new < avg_time_old else 'chậm hơn'} {(abs(avg_time_new - avg_time_old)):.2f} ms/ảnh so với Model Cũ.
==================================================
"""

    # In ra Terminal
    print("\n" + report)

    # Lưu ra file text
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"📂 Đã lưu báo cáo tại: {SUMMARY_FILE}")
    print(f"👉 Mở thư mục kết quả để xem ảnh chi tiết: \n   - Cũ: {OUTPUT_OLD_DIR}\n   - Mới: {OUTPUT_NEW_DIR}")

if __name__ == "__main__":
    main()