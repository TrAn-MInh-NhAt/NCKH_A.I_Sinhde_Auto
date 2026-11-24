import csv
import os
from datetime import datetime
from typing import Any

# Định vị thư mục chuẩn (D:\AI_Agent_NCKH\experiments\system_logs.csv)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPERIMENTS_DIR = os.path.join(BASE_DIR, "experiments")
LOG_CSV_PATH = os.path.join(EXPERIMENTS_DIR, "system_logs.csv")

CSV_COLUMNS = [
    "timestamp",
    "bai_hoc",
    "muc_do",
    "loai_cau_hoi",
    "rule_pass",
    "sandbox_verified",
    "fuzzy_score",
    "retry_count",
    "latency_sec",
    "trang_thai_duyet",
]


def _ensure_csv_exists() -> None:
    os.makedirs(EXPERIMENTS_DIR, exist_ok=True)
    if not os.path.exists(LOG_CSV_PATH) or os.path.getsize(LOG_CSV_PATH) == 0:
        with open(LOG_CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()


def log_generation_event(
    bai_hoc: str,
    muc_do: str,
    loai_cau_hoi: str,
    rule_pass: bool,
    sandbox_verified: bool,
    fuzzy_score: float,
    retry_count: int,
    latency_sec: float,
    trang_thai_duyet: str = "CHO_DUYET",
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Ghi một dòng thông số thực nghiệm vào experiments/system_logs.csv."""
    _ensure_csv_exists()
    ts = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = {
        "timestamp": ts,
        "bai_hoc": str(bai_hoc),
        "muc_do": str(muc_do),
        "loai_cau_hoi": str(loai_cau_hoi).upper(),
        "rule_pass": bool(rule_pass),
        "sandbox_verified": bool(sandbox_verified),
        "fuzzy_score": round(float(fuzzy_score), 3),
        "retry_count": int(retry_count),
        "latency_sec": round(float(latency_sec), 2),
        "trang_thai_duyet": str(trang_thai_duyet),
    }
    try:
        with open(LOG_CSV_PATH, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writerow(row)
    except PermissionError:
        fallback_path = os.path.join(EXPERIMENTS_DIR, "system_logs_fallback.csv")
        write_hdr = not os.path.exists(fallback_path) or os.path.getsize(fallback_path) == 0
        with open(fallback_path, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            if write_hdr:
                writer.writeheader()
            writer.writerow(row)
        print(f"   ⚠️ system_logs.csv đang bị khóa (Excel đang mở) -> đã lưu dự phòng vào {fallback_path}", flush=True)
    return row


def update_approval_status(timestamp: str, trang_thai_duyet: str = "DA_DUYET") -> bool:
    """Cập nhật trạng thái phê duyệt của dòng log theo timestamp (khi Giáo viên bấm Phê duyệt)."""
    if not os.path.exists(LOG_CSV_PATH):
        return False
    rows = read_logs()
    updated = False
    for r in reversed(rows):
        if r.get("timestamp") == timestamp:
            r["trang_thai_duyet"] = trang_thai_duyet
            updated = True
            break
    if updated:
        with open(LOG_CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
    return updated


def read_logs() -> list[dict[str, str]]:
    """Đọc toàn bộ lịch sử log thực nghiệm từ experiments/system_logs.csv."""
    if not os.path.exists(LOG_CSV_PATH):
        return []
    with open(LOG_CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


if __name__ == "__main__":
    _ensure_csv_exists()
    print(f"Logger sẵn sàng tại: {LOG_CSV_PATH} | Cột: {CSV_COLUMNS} | Số dòng hiện có: {len(read_logs())}")
