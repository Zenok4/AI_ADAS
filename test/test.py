import cv2
import os
import glob
import sys

# Thêm thư mục gốc vào path để có thể import drowsy_service
# Giả sử file này nằm trong 'test/' và file 'drowsy_service.py' nằm trong 'test/'

# Nếu cấu trúc file là /drowsy_service.py và /test/run_functional_test.py
# Chúng ta cần thêm thư mục cha vào sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Thử import lại từ file gốc (ví dụ: 'app/services/drowsy_service.py')
# *** ĐIỀU CHỈNH DÒNG NÀY THEO CẤU TRÚC THỰC TẾ CỦA BẠN ***
# Giả sử file drowsy_service.py nằm cùng cấp với thư mục 'test'
try:
    from app.services.drowsy_service import drowsiDetector
except ImportError as e:
    print(f"Lỗi Import: Không thể tìm thấy class DrowsyDetector.")
    print("Vui lòng đảm bảo file drowsy_service.py nằm đúng vị trí.")
    print(f"Chi tiết lỗi: {e}")
    sys.exit(1)


def run_test_on_images():
    """
    Chạy DrowsyDetector trên tất cả ảnh trong thư mục 'test_images'
    và lưu kết quả vào 'test_results'.
    """

    # __file__ là đường dẫn đến file script này (run_functional_test.py)
    # os.path.dirname(__file__) là thư mục 'test'
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. Thư mục đầu vào (chứa ảnh test)
    input_dir = os.path.join(base_dir, "images")

    # 2. Thư mục đầu ra (để lưu kết quả)
    output_dir = os.path.join(base_dir, "results")

    # Tạo thư mục đầu ra nếu nó chưa tồn tại
    os.makedirs(output_dir, exist_ok=True)

    # Tìm tất cả các file ảnh .jpg và .png trong thư mục đầu vào
    image_paths = glob.glob(os.path.join(input_dir, "*.jpg")) + glob.glob(
        os.path.join(input_dir, "*.png")
    )

    if not image_paths:
        print(f"LỖI: Không tìm thấy ảnh .jpg hoặc .png nào trong thư mục:")
        print(f"{input_dir}")
        print(
            "Vui lòng tạo thư mục 'test_images' cùng cấp với file test này và thêm ảnh vào."
        )
        return

    print(f"Tìm thấy {len(image_paths)} ảnh. Bắt đầu xử lý...")

    # Khởi tạo detector
    try:
        detector = drowsiDetector()
    except Exception as e:
        print(f"Lỗi khi khởi tạo DrowsyDetector: {e}")
        print(
            "Vui lòng kiểm tra các thư viện (mediapipe, opencv) đã được cài đặt đúng."
        )
        return

    for img_path in image_paths:
        # Đọc ảnh
        image = cv2.imread(img_path)

        if image is None:
            print(f"[Bỏ qua] Không thể đọc file ảnh: {img_path}")
            continue

        print(f"\n--- Đang xử lý: {os.path.basename(img_path)} ---")

        # 3. Chạy phân tích
        try:
            message, ratio, angle, bbox, annotated_image = detector.analyze(image)

            # In kết quả ra console
            print(f"  Trạng thái: {message}")
            print(f"  Tỷ lệ mắt: {ratio}")
            print(f"  Góc nghiêng: {angle}")
            print(f"  Bbox: {bbox}")

            # 4. Lưu ảnh kết quả
            output_filename = f"result_{os.path.basename(img_path)}"
            output_path = os.path.join(output_dir, output_filename)

            cv2.imwrite(output_path, annotated_image)
            print(f"  => Đã lưu kết quả vào: {output_path}")

        except Exception as e:
            print(f"  LỖI khi xử lý ảnh {os.path.basename(img_path)}: {e}")
            import traceback

            traceback.print_exc()  # In ra chi tiết lỗi đầy đủ

    print("\n✅ Hoàn thành xử lý tất cả các ảnh.")


if __name__ == "__main__":
    run_test_on_images()
