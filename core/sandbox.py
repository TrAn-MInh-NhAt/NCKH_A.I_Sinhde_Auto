import subprocess
import sys
import tempfile
import os
import time

def cham_code_python(student_code: str, test_input: str = "", timeout_sec: float = 2.0) -> dict:
    """
    Hệ thống Sandbox chạy code Python cục bộ, có cô lập và giới hạn thời gian.
    Chống lỗi vòng lặp vô hạn làm treo máy và ép buộc Windows Console dùng UTF-8.
    """
    print("\n[SANDBOX] Đang khởi tạo môi trường chạy code an toàn...")
    
    # Tạo một file Python tạm thời để chứa code của học sinh (ép chuẩn utf-8)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tmp:
        tmp.write(student_code)
        tmp_path = tmp.name

    start_time = time.time()
    
    # Tạo bản sao môi trường của hệ thống và ép luồng I/O thành utf-8
    env_vars = os.environ.copy()
    env_vars["PYTHONIOENCODING"] = "utf-8"
    
    try:
        # Chạy file code tạm thời bằng process con (dùng đúng trình thông dịch hiện hành)
        result = subprocess.run(
            [sys.executable, "-I", "-X", "utf8", tmp_path], # Cờ -X utf8 ép tiến trình con dùng UTF-8
            input=test_input,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace", # Thay thế ký tự lạ thay vì làm sập chương trình
            timeout=timeout_sec,
            env=env_vars # Truyền môi trường ép utf-8 vào
        )
        execution_time = round(time.time() - start_time, 4)
        
        # Trích xuất dữ liệu an toàn chống lỗi NoneType
        stdout_str = result.stdout.strip() if result.stdout else ""
        stderr_str = result.stderr.strip() if result.stderr else ""
        
        # Nếu code chạy thành công (returncode == 0)
        if result.returncode == 0:
            return {
                "trang_thai": "THÀNH CÔNG",
                "ket_qua_in_ra": stdout_str,
                "loi_he_thong": "",
                "thoi_gian_chay": f"{execution_time}s"
            }
        else:
            # Nếu code bị lỗi cú pháp hoặc lỗi runtime
            return {
                "trang_thai": "LỖI THỰC THI (RUNTIME ERROR)",
                "ket_qua_in_ra": stdout_str,
                "loi_he_thong": stderr_str,
                "thoi_gian_chay": f"{execution_time}s"
            }
            
    except subprocess.TimeoutExpired:
        # Nếu code chạy quá thời gian cho phép (bị lặp vô hạn)
        return {
            "trang_thai": "QUÁ THỜI GIAN (TIME LIMIT EXCEEDED)",
            "ket_qua_in_ra": "",
            "loi_he_thong": f"Lỗi: Chương trình chạy quá giới hạn {timeout_sec} giây. Hãy kiểm tra lại vòng lặp vô hạn (while True)!",
            "thoi_gian_chay": f">{timeout_sec}s"
        }
    finally:
        # Luôn luôn dọn dẹp xóa file code tạm sau khi chạy xong
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == "__main__":
    print("=== KIỂM THỬ HỆ THỐNG CHẤM CODE TỰ ĐỘNG ===")
    
    # 1. TEST CASE 1: Học sinh viết code đúng (Có in tiếng Việt)
    code_dung = """
tong = 0
for i in range(1, 6):
    tong += i
print(f"Tổng từ 1 đến 5 là: {tong}")
    """
    print("\n--- TEST CASE 1: CODE ĐÚNG ---")
    kq1 = cham_code_python(code_dung)
    for key, value in kq1.items():
        print(f"{key}: {value}")
        
    # 2. TEST CASE 2: Học sinh viết code sai cú pháp
    code_sai = """
for i in range(5):
print(bien_khong_ton_tai)
    """
    print("\n--- TEST CASE 2: CODE LỖI CÚ PHÁP ---")
    kq2 = cham_code_python(code_sai)
    for key, value in kq2.items():
        print(f"{key}: {value}")
        
    # 3. TEST CASE 3: Học sinh viết vòng lặp vô hạn (Treo máy)
    code_lap_vo_han = """
while True:
    pass
    """
    print("\n--- TEST CASE 3: CODE BỊ LẶP VÔ HẠN (SẼ BỊ ÉP DỪNG SAU 2 GIÂY) ---")
    kq3 = cham_code_python(code_lap_vo_han, timeout_sec=2.0)
    for key, value in kq3.items():
        print(f"{key}: {value}")