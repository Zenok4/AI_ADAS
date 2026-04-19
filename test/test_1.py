import cv2
import os
import glob
import sys
import traceback
from datetime import datetime

# --- 1. SETUP ĐƯỜNG DẪN & IMPORT ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Import hàm test Lane (cùng thư mục test/)
try:
    from test_lane_detection import run_lane_detection
except ImportError:
    print(" Cảnh báo: Không tìm thấy file 'test_lane_detection.py' cùng thư mục.")

# Import class DrowsyDetector (từ app/services/)
try:
    from app.services.drowsy_service import DrowsinessDetectorService
except ImportError as e:
    print(f" Lỗi Import: Không thể tìm thấy class DrowsinessDetectorService.")
    print(f"Chi tiết lỗi: {e}")
    DrowsinessDetectorService = None 

# Import cho Sign Detection (từ ultralytics)
try:
    from ultralytics import YOLO
except ImportError:
    print(" Cảnh báo: Không tìm thấy thư viện 'ultralytics' cho Sign Detection.")
    YOLO = None

# Import cho Object Detection (từ app)
try:
    from app.config.settings import settings
    from app.services.model_loader import get_model
except ImportError as e:
    print(f" Cảnh báo: Lỗi import cấu hình Object Detection từ app.")
    settings = None
    get_model = None

# Hàm hỗ trợ: Tạo thư mục run# mới
def get_next_run_folder(base_dir, prefix="run_#"):
    os.makedirs(base_dir, exist_ok=True)
    existing = [d for d in os.listdir(base_dir) if d.startswith(prefix)]
    run_ids = []
    for d in existing:
        try:
            run_ids.append(int(d.replace(prefix, "")))
        except:
            pass
    next_id = max(run_ids) + 1 if run_ids else 1
    new_dir = os.path.join(base_dir, f"{prefix}{next_id}")
    os.makedirs(new_dir, exist_ok=True)
    return new_dir, next_id


# --- 2. CÁC HÀM TEST CHỨC NĂNG ---

def run_drowsiness_test():
    print("\n" + "="*40)
    print("  BẮT ĐẦU TEST: DROWSINESS DETECTION")
    print("="*40)

    if DrowsinessDetectorService is None:
        print(" Bỏ qua test Drowsiness do lỗi import library.")
        return

    input_dir = os.path.join(current_dir, "images")
    output_dir = os.path.join(current_dir, "results", "drowsy_results")

    os.makedirs(output_dir, exist_ok=True)
    image_paths = glob.glob(os.path.join(input_dir, "*.jpg")) + glob.glob(os.path.join(input_dir, "*.png"))

    if not image_paths:
        print(f" Không tìm thấy ảnh nào trong: {input_dir}")
        return

    print(f" Tìm thấy {len(image_paths)} ảnh. Đang xử lý...")

    try:
        detector = DrowsinessDetectorService()
    except Exception as e:
        print(f" Lỗi khởi tạo detector: {e}")
        return

    for img_path in image_paths:
        filename = os.path.basename(img_path)
        image = cv2.imread(img_path)

        if image is None:
            continue
        try:
            annotated_image, message, angle, _= detector.process_frame(image, current_frame_count=0)
            print(f" {filename}: {message} | Angle: {angle:.2f}")
            output_path = os.path.join(output_dir, f"res_{filename}")
            cv2.imwrite(output_path, annotated_image)
        except Exception as e:
            print(f" Lỗi file {filename}: {e}")

    print(f"✅ Hoàn thành test Drowsiness. Kết quả tại: {output_dir}")


def run_sign_test():
    print("\n" + "="*40)
    print("  BẮT ĐẦU TEST: SIGN DETECTION")
    print("="*40)

    if YOLO is None:
        print(" Bỏ qua test Sign do không có thư viện YOLO.")
        return

    model_path = os.path.join(parent_dir, "models", "sign", "best.pt")
    input_dir = os.path.join(current_dir, "images")
    base_save_dir = os.path.join(current_dir, "results", "sign_results")
    
    if not os.path.exists(model_path):
        print(f"❌ Không tìm thấy model biển báo tại: {model_path}")
        return

    save_dir, run_id = get_next_run_folder(base_save_dir)
    print(f"🆕 Tạo thư mục lưu kết quả: {save_dir}")

    try:
        model = YOLO(model_path)
        names = model.names
    except Exception as e:
        print(f"❌ Lỗi load model Sign: {e}")
        return

    valid_ext = (".jpg", ".jpeg", ".png", ".bmp")
    image_files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.lower().endswith(valid_ext)]

    if not image_files:
        print(f"❌ Không tìm thấy ảnh hợp lệ trong: {input_dir}")
        return

    for idx, image_path in enumerate(image_files, start=1):
        results = model.predict(source=image_path, conf=0.45, iou=0.45, verbose=False)
        r = results[0]
        img_name = os.path.splitext(os.path.basename(image_path))[0]
        
        im_array = r.plot()
        cv2.imwrite(os.path.join(save_dir, f"{img_name}_result.jpg"), im_array)

        boxes_data = []
        for box in r.boxes:
            cls_id = int(box.cls[0])
            label = names.get(cls_id, f"class_{cls_id}")
            conf = float(box.conf[0])
            xyxy = [round(x, 1) for x in box.xyxy[0].tolist()]
            boxes_data.append((cls_id, label, conf, xyxy))

        max_label_len = max(len(label) for _, label, _, _ in boxes_data) if boxes_data else 10
        with open(os.path.join(save_dir, f"{img_name}_result.txt"), "w", encoding="utf-8") as f:
            f.write(f"📦 Run ID: #{run_id}\n")
            f.write(f"🕒 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"📸 Image: {os.path.basename(image_path)}\n\n")
            f.write(f"{'Class':<7} {'Label':<{max_label_len+3}} {'Conf':<8} {'BBox (x1,y1,x2,y2)'}\n")
            f.write("-" * (25 + max_label_len) + "\n")
            for cls_id, label, conf, xyxy in boxes_data:
                f.write(f"{cls_id:<7} {label:<{max_label_len+3}} {conf:<8.2f} {str(xyxy)}\n")

        print(f"✅ [{idx}/{len(image_files)}] Đã xử lý: {img_name}")

    print(f"🎯 Toàn bộ kết quả Sign nằm trong: {save_dir}")


def run_object_test():
    print("\n" + "="*40)
    print("  BẮT ĐẦU TEST: OBJECT DETECTION")
    print("="*40)

    if settings is None or get_model is None:
        print(" Bỏ qua test Object do lỗi import module từ app.")
        return

    if not hasattr(settings, 'MODELS') or not settings.MODELS:
        print(" Config không có settings.MODELS hoặc dictionary rỗng.")
        return
    
    model_name = list(settings.MODELS.keys())[1]
    input_dir = os.path.join(current_dir, "images", "objects")
    base_save_dir = os.path.join(current_dir, "results", "object_model")

    try:
        print(f" Load model key: {model_name}")
        model_info = get_model(model_name)
        model = model_info["model"]
        conf_thres = model_info["conf"]
    except Exception as e:
        print(f" Lỗi khởi tạo model Object: {e}")
        return

    if not os.path.exists(input_dir):
        print(f" Không tìm thấy folder input: {input_dir}")
        return
    
    valid_exts = ('.jpg', '.jpeg', '.png', '.bmp')
    image_files = [f for f in os.listdir(input_dir) if f.lower().endswith(valid_exts)]
    
    if not image_files:
        print(" Không có file ảnh nào để test vật thể.")
        return

    save_dir, _ = get_next_run_folder(base_save_dir, "object_run#")
    print(f" Kết quả Object sẽ được lưu tại: {save_dir}")

    for img_name in image_files:
        img_path = os.path.join(input_dir, img_name)
        results = model.predict(source=img_path, conf=conf_thres, save=False, verbose=False)
        result = results[0]
        
        annotated_frame = result.plot()
        cv2.imwrite(os.path.join(save_dir, img_name), annotated_frame)
        
        txt_filename = os.path.splitext(img_name)[0] + ".txt"
        with open(os.path.join(save_dir, txt_filename), "w", encoding="utf-8") as f:
            f.write(f"Image: {img_name}\n")
            f.write(f"Model: {model_name} | Conf Thres: {conf_thres}\n")
            f.write(f"{'ID':<5} {'Class Name':<20} {'Conf':<10} {'BBox [x1, y1, x2, y2]'}\n")
            f.write("-" * 70 + "\n")
            if len(result.boxes) == 0:
                f.write("No objects detected.\n")
            else:
                for box in result.boxes:
                    cls_id = int(box.cls[0])
                    cls_name = model.names[cls_id]
                    conf = float(box.conf[0])
                    xyxy = [int(x) for x in box.xyxy[0].tolist()]
                    f.write(f"{cls_id:<5} {cls_name:<20} {conf:.4f}     {xyxy}\n")
        
        print(f" Processed: {img_name}")

    print(f"✅ Hoàn tất test Object! Kiểm tra folder: {save_dir}")


# --- 3. MAIN EXECUTION (MENU LỰA CHỌN) ---
if __name__ == "__main__":
    print("\n" + "="*40)
    print(" CHỌN CHỨC NĂNG MUỐN TEST:")
    print("1. Test Cảnh báo buồn ngủ (Drowsiness)")
    print("2. Test Nhận diện làn đường (Lane Detection)")
    print("3. Test Nhận diện biển báo (Sign Detection)")
    print("4. Test Nhận diện vật thể (Object Detection)")
    print("5. Chạy cả 4 chức năng (All)")
    print("="*40)
    
    choice = input("👉 Nhập số (1, 2, 3, 4 hoặc 5): ").strip()

    if choice == '1':
        run_drowsiness_test()
        
    elif choice == '2':
        try:
            if 'run_lane_detection' in globals():
                run_lane_detection()
            else:
                from test_lane_detection import run_lane_detection
                run_lane_detection()
        except Exception as e:
            print(f"Lỗi khi chạy Lane detection: {e}")

    elif choice == '3':
        run_sign_test()

    elif choice == '4':
        run_object_test()

    elif choice == '5':
        run_drowsiness_test()
        print("\n" + "-"*30 + "\n")
        
        try:
            if 'run_lane_detection' in globals():
                run_lane_detection()
            else:
                from test_lane_detection import run_lane_detection
                run_lane_detection()
        except Exception as e:
            print(f"Lỗi khi chạy Lane detection: {e}")

        print("\n" + "-"*30 + "\n")
        run_sign_test()
        
        print("\n" + "-"*30 + "\n")
        run_object_test()
            
    else:
        print("Lựa chọn không hợp lệ. Vui lòng chạy lại và nhập từ 1 đến 5.")

    print("\n === KẾT THÚC ===")