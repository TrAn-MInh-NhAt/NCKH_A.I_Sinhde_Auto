import os
import re
import json
import time
import unicodedata
import urllib.parse
from http import HTTPStatus

import requests
import bs4
import gdown
import pypdf
from docx import Document as DocxDocument

# Định vị thư mục chuẩn của dự án (D:\AI_Agent_NCKH)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data_raw")
SYNC_DIR = os.path.join(RAW_DIR, "drive_sync")
OCR_CACHE_DIR = os.path.join(BASE_DIR, "data", "ocr_cache")
TEMPLATES_OUT = os.path.join(BASE_DIR, "data", "exam_templates.json")

DRIVE_FOLDER_URL = "https://drive.google.com/drive/folders/1QVt0RvX7-t4y0jrTOma8hGXAUJYvBwlA?usp=sharing"
DRIVE_ROOT_FOLDER_ID = "1QVt0RvX7-t4y0jrTOma8hGXAUJYvBwlA"

# ==============================================================================
# BỘ LỌC TÊN THƯ MỤC & TÊN FILE (BLACKLIST / WHITELIST)
# ==============================================================================

# BỎ QUA HOÀN TOÀN các file/thư mục hành chính, bài báo khoa học, tổng quan, sai cấp lớp
BLACKLIST_KEYWORDS = [
    "1_quanly_hanhchinh", "2_tailieu_thamkhao", "8_luutru_tam",
    "bài báo", "bai bao", "bai_bao",
    "nghiên cứu", "nghien cuu", "nghien_cuu",
    "nckh", "literature", "survey", "review",
    "tổng quan", "tong quan", "tong_quan",
    "kế hoạch", "ke hoach", "ke_hoach",
    "hoạt động", "hoat dong", "hoat_dong",
    "biên bản", "bien ban", "bien_ban",
    "thcs", "lớp 9", "lop 9", "tin học 9", "tin hoc 9",
    "lớp 11", "lop 11", "tin học 11", "tin hoc 11",
    "lớp 12", "lop 12", "tin học 12", "tin hoc 12",
    "đơn đăng ký", "don dang ky", "đề cương", "de cuong",
    "thuyết minh", "thuyet minh", "kinh phí", "hóa đơn",
    "báo cáo", "bao cao", "slide", "video", "poster", "nhật ký", "nhat ky",
    "sơ đồ", "so do", "sgk", "cách hoạt động", "cach hoat dong",
]

# Các thư mục gốc chắc chắn không chứa đề thi -> cắt nhánh không cần duyệt sâu
HARD_PRUNE_FOLDERS = [
    "2_tailieu_thamkhao", "8_luutru_tam",
    "1.1_bieumau_quydinh", "1.2_thuyetminh_decuong", "1.4_kinhphi_hoadon",
    "4_phattrien_sanpham", "5_ketqua_danhgia", "6_baocao_congbo", "7_nghiemthu_trinhbay",
    "nội dung bài báo", "noi dung bai bao", "nội dung của bài báo",
    "2.1_baibao_quocte", "2.2_tailieu_trongnuoc",
]

# GIỮ LẠI ĐỂ LẤY FORM: đề thi, đề kiểm tra, cấu trúc, thang điểm, ma trận, năng lực
WHITELIST_KEYWORDS = [
    "đề thi", "de thi", "de_thi",
    "đề kiểm tra", "de kiem tra", "de_kiem_tra",
    "đề minh họa", "de minh hoa", "de_minh_hoa",
    "cấu trúc", "cau truc", "cau_truc",
    "chấm điểm", "cham diem", "cham_diem",
    "ma trận", "ma tran", "ma_tran",
    "năng lực", "nang luc", "nang_luc",
    "thang điểm", "thang diem",
    "thpt", "form",
]
# Các mã viết tắt CK, GK phải khớp ranh giới từ (tránh khớp nhầm trong từ tiếng Anh)
WHITELIST_REGEX = [
    r"\bck[12]?\b",
    r"\bgk[12]?\b",
    r"\bkthk[12]?\b",
    r"\bktgk[12]?\b",
]

# Từ khóa nội dung ngoài Chủ đề F (tuyệt đối không để lọt vào mẫu ví dụ)
NON_PYTHON_NOISE = [
    "html", "css", "sql", "cơ sở dữ liệu", "mạng lan", "switch",
    "địa chỉ ip", "đạo đức", "bắt nạt", "bản quyền", "trí tuệ nhân tạo",
]


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text).lower().strip()


def match_blacklist(name: str) -> str | None:
    low = _norm(name)
    for kw in BLACKLIST_KEYWORDS:
        if kw in low:
            return kw
    return None


def match_whitelist(name: str) -> str | None:
    low = _norm(name)
    for kw in WHITELIST_KEYWORDS:
        if kw in low:
            return kw
    for pat in WHITELIST_REGEX:
        if re.search(pat, low):
            return pat
    return None


def should_prune_folder(folder_name: str) -> bool:
    low = _norm(folder_name)
    return any(kw in low for kw in HARD_PRUNE_FOLDERS)


def evaluate_file(file_name: str, parent_path: str) -> tuple[bool, str]:
    """
    Quyết định GIỮ (True) hay BỎ QUA (False) một file dựa trên Blacklist & Whitelist.
    - Blacklist trên tên file luôn ưu tiên cao nhất (bỏ qua hoàn toàn).
    - Whitelist kiểm tra trên tên file (và chấp nhận thư mục cha trực tiếp là thư mục form đề).
    """
    bl_file = match_blacklist(file_name)
    if bl_file:
        return False, f"Blacklist tên file ('{bl_file}')"

    wl_file = match_whitelist(file_name)
    if wl_file:
        return True, f"Whitelist tên file ('{wl_file}')"

    # Nếu nằm trong thư mục đích danh chứa form đề (ví dụ 'form đề, cấu trúc đề thi')
    immediate_parent = os.path.basename(parent_path.rstrip("/\\"))
    wl_parent = match_whitelist(immediate_parent)
    if wl_parent and file_name.lower().endswith((".pdf", ".docx", ".doc", ".txt", ".md")):
        return True, f"Whitelist thư mục cha ('{immediate_parent}')"

    bl_path = match_blacklist(parent_path)
    if bl_path:
        return False, f"Blacklist đường dẫn ('{bl_path}')"

    return False, "Không khớp Whitelist mẫu đề/cấu trúc"


# ==============================================================================
# DUYỆT ĐỆ QUY GOOGLE DRIVE & TẢI CHỌN LỌC CÁC FILE WHITELIST
# ==============================================================================

def _parse_drive_folder_children(sess: requests.Session, folder_id: str) -> tuple[str, list[tuple[str, str, str]]]:
    url = f"https://drive.google.com/embeddedfolderview?{urllib.parse.urlencode({'id': folder_id})}"
    res = sess.get(url, timeout=20)
    if res.status_code != HTTPStatus.OK:
        raise RuntimeError(f"HTTP {res.status_code} khi truy cập thư mục Drive {folder_id}")

    soup = bs4.BeautifulSoup(res.text, features="html.parser")
    folder_name = soup.title.string.strip() if (soup.title and soup.title.string) else folder_id

    children: list[tuple[str, str, str]] = []
    for a_tag in soup.find_all("a"):
        href = a_tag.get("href", "")
        if not isinstance(href, str):
            continue
        name = a_tag.get_text(strip=True)
        if not name:
            continue

        m_file = re.match(r"https://drive\.google\.com/file/d/([-\w]{25,})/view", href)
        if m_file:
            children.append((m_file.group(1), name, "file"))
            continue

        m_doc = re.match(r"https://docs\.google\.com/(\w+)/d/([-\w]{25,})/", href)
        if m_doc:
            children.append((m_doc.group(2), name, f"gdoc:{m_doc.group(1)}"))
            continue

        m_folder = re.search(r"/folders/([-\w]{25,})", href)
        if m_folder:
            children.append((m_folder.group(1), name, "folder"))
            continue

    return folder_name, children


def sync_whitelisted_forms_from_drive() -> tuple[list[dict], list[dict]]:
    """
    Duyệt đệ quy thư mục Google Drive chia sẻ, áp dụng bộ lọc Blacklist/Whitelist trước khi tải,
    chỉ tải các file đề thi/cấu trúc hợp lệ về data_raw/drive_sync/.
    """
    os.makedirs(SYNC_DIR, exist_ok=True)
    kept_files: list[dict] = []
    skipped_items: list[dict] = []
    seen_folders: set[str] = set()
    seen_file_names: set[str] = set()

    sess = requests.Session()
    sess.headers.update({"User-Agent": "Mozilla/5.0"})

    def crawl(folder_id: str, rel_path: str, depth: int = 0):
        if folder_id in seen_folders or depth > 6:
            return
        seen_folders.add(folder_id)

        try:
            _, children = _parse_drive_folder_children(sess, folder_id)
        except Exception as e:
            print(f"   ⚠️ Không thể đọc thư mục Drive '{rel_path or folder_id}': {e}")
            return

        for child_id, child_name, child_type in children:
            child_rel = f"{rel_path}/{child_name}" if rel_path else child_name

            if child_type == "folder":
                if should_prune_folder(child_name):
                    skipped_items.append({
                        "item": f"[Thư mục] {child_rel}",
                        "reason": f"Blacklist thư mục ('{match_blacklist(child_name) or child_name}')",
                    })
                    continue
                crawl(child_id, child_rel, depth + 1)
                continue

            # Bỏ qua file Google Docs/Sheets nội bộ không phải file đề tải trực tiếp nếu bị blacklist
            keep, reason = evaluate_file(child_name, rel_path)
            if not keep:
                skipped_items.append({"item": child_rel, "reason": reason})
                continue

            if child_type.startswith("gdoc:"):
                skipped_items.append({"item": child_rel, "reason": "Google Docs native (không tải nhị phân)"})
                continue

            # Tránh tải trùng nếu cùng tên file xuất hiện ở nhiều nhánh
            safe_name = re.sub(r'[<>:"/\\|?*]', "_", child_name)
            dest_path = os.path.join(SYNC_DIR, safe_name)
            if safe_name in seen_file_names:
                continue
            seen_file_names.add(safe_name)

            # Tải về data_raw/drive_sync/ nếu chưa tồn tại (hoặc kích thước = 0)
            downloaded_ok = os.path.exists(dest_path) and os.path.getsize(dest_path) > 0
            if not downloaded_ok:
                try:
                    out = gdown.download(id=child_id, output=dest_path, quiet=True)
                    downloaded_ok = bool(out and os.path.exists(dest_path) and os.path.getsize(dest_path) > 0)
                except Exception as e:
                    print(f"   ⚠️ Lỗi tải '{child_name}' từ Drive: {e}")
                    downloaded_ok = False

            if downloaded_ok:
                kept_files.append({
                    "name": safe_name,
                    "source": f"Drive:{child_rel}",
                    "local_path": dest_path,
                    "reason": reason,
                })
            else:
                # Dự phòng tìm file cùng tên đã có sẵn trong data_raw/
                fallback_local = os.path.join(RAW_DIR, safe_name)
                if os.path.exists(fallback_local):
                    kept_files.append({
                        "name": safe_name,
                        "source": f"LocalFallback:{safe_name}",
                        "local_path": fallback_local,
                        "reason": reason,
                    })
                else:
                    skipped_items.append({"item": child_rel, "reason": "Không tải được từ Drive"})

    print(f"1. Đang duyệt đệ quy & lọc thư mục Google Drive:\n   -> {DRIVE_FOLDER_URL}")
    crawl(DRIVE_ROOT_FOLDER_ID, "")

    # Bổ sung quét thư mục data_raw/ cục bộ (chỉ lấy các file Whitelist chưa có trong danh sách)
    for fname in sorted(os.listdir(RAW_DIR)):
        fpath = os.path.join(RAW_DIR, fname)
        if not os.path.isfile(fpath) or fname in seen_file_names:
            continue
        keep, reason = evaluate_file(fname, "data_raw")
        if keep:
            seen_file_names.add(fname)
            kept_files.append({
                "name": fname,
                "source": f"Local:data_raw/{fname}",
                "local_path": fpath,
                "reason": reason,
            })
        else:
            skipped_items.append({"item": f"data_raw/{fname}", "reason": reason})

    return kept_files, skipped_items


# ==============================================================================
# TRÍCH XUẤT CẤU TRÚC HÌNH THỨC (FORM) -> data/exam_templates.json (< 3KB)
# ==============================================================================

def _read_text_for_form_analysis(local_path: str) -> str:
    """Đọc văn bản gọn từ PDF / DOCX / OCR cache chỉ để phân tích cấu trúc hình thức đề."""
    ext = os.path.splitext(local_path)[1].lower()
    text = ""
    try:
        if ext == ".docx":
            doc = DocxDocument(local_path)
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        elif ext == ".pdf":
            reader = pypdf.PdfReader(local_path)
            pages_txt = []
            # Chỉ cần đọc tối đa 8 trang đầu để nhận diện cấu trúc hình thức đề
            for page in reader.pages[:8]:
                t = page.extract_text() or ""
                if t.strip():
                    pages_txt.append(t)
            text = "\n".join(pages_txt)
        elif ext in (".txt", ".md"):
            with open(local_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
    except Exception:
        text = ""

    # Nếu PDF dạng ảnh scan (0 ký tự text), đối chiếu bản OCR cache tương ứng nếu có
    if len(text.strip()) < 100 and os.path.isdir(OCR_CACHE_DIR):
        stem_norm = re.sub(r"[^a-z0-9]", "", _norm(os.path.splitext(os.path.basename(local_path))[0]))
        for cname in os.listdir(OCR_CACHE_DIR):
            cstem = re.sub(r"[^a-z0-9]", "", _norm(os.path.splitext(cname)[0]))
            # Khớp tên file không dấu (ví dụ xuyenmoc, lop10, thptquocgia)
            if (
                ("xuyen" in stem_norm and "xuyen" in cstem)
                or ("10" in stem_norm and "lop10" in cstem and "xuyen" not in stem_norm)
                or ("thpt" in stem_norm and "thpt" in cstem)
            ):
                with open(os.path.join(OCR_CACHE_DIR, cname), "r", encoding="utf-8") as f:
                    text = f.read()
                break

    return text


def _detect_exam_patterns(kept_files: list[dict]) -> dict:
    """Phân tích cấu trúc hình thức (phần thi, câu dẫn, A/B/C/D, a/b/c/d, thang điểm) từ các file hợp lệ."""
    detected_sources: list[str] = []
    has_mcq_code = False
    has_tf_4_items = False
    has_step_scoring = False
    has_short_or_essay = False

    for item in kept_files:
        fname = item["name"]
        detected_sources.append(fname)
        txt = _read_text_for_form_analysis(item["local_path"])
        low = txt.lower()
        if not low:
            continue
        if ("phần i" in low or "câu 1" in low) and ("a." in low and "b." in low and "c." in low and "d." in low):
            has_mcq_code = True
        if ("phần ii" in low or "đúng/sai" in low or "đúng sai" in low) and ("a)" in low or "a." in low):
            has_tf_4_items = True
        if "0,1" in low or "0.1" in low or "0,25" in low or "0.25" in low:
            has_step_scoring = True
        if "phần iii" in low or "trả lời ngắn" in low or "tự luận" in low or "viết chương trình" in low:
            has_short_or_essay = True

    # Đóng gói khuôn mẫu siêu gọn (< 3KB, tối đa 2 mẫu/dạng, 100% khung hình thức Python lớp 10)
    templates_payload = {
        "phien_ban": "2025-2026",
        "nguon_trich_form": detected_sources,
        "ghi_chu": "Chỉ trích cấu trúc trình bày chuẩn đề thi 2025-2026; nội dung sinh đề khóa cứng Chủ đề F Tin học 10 (Bài 16-32).",
        "da_xac_nhan_tu_de_goc": {
            "mcq_4_phuong_an": has_mcq_code,
            "dung_sai_4_menh_de": has_tf_4_items,
            "thang_diem_2025_2026": has_step_scoring,
            "tra_loi_ngan_tu_luan": has_short_or_essay,
        },
        "templates": {
            "MCQ": [
                {
                    "id": "MCQ_1_LY_THUYET",
                    "cau_dan": "Trong Python, <khái niệm/cú pháp Chủ đề F> nào sau đây đúng?",
                    "trinh_bay": "4 phương án A, B, C, D độc lập, độ dài tương đương nhau, duy nhất 1 đáp án đúng.",
                    "diem": 0.25,
                },
                {
                    "id": "MCQ_2_DOC_CODE",
                    "cau_dan": "Cho đoạn chương trình Python sau: <mã Python 3-6 dòng>. Kết quả hiển thị trên màn hình là gì?",
                    "trinh_bay": "4 phương án A, B, C, D là các giá trị kết quả phân biệt (phương án nhiễu từ lỗi tính tay/lỗi chỉ số).",
                    "diem": 0.25,
                },
            ],
            "TRUE_FALSE": [
                {
                    "id": "TF_1_DOC_HIEU_CODE",
                    "cau_dan": "Cho đoạn chương trình Python sau: <mã Python 4-8 dòng>. Sau khi tìm hiểu chương trình, có các phát biểu sau:",
                    "trinh_bay": "4 ý a, b, c, d độc lập (tăng dần NB->TH->VD), bắt buộc có cả Đúng và Sai.",
                    "thang_diem": "1ý:0.1 | 2ý:0.25 | 3ý:0.5 | 4ý:1.0",
                },
                {
                    "id": "TF_2_TINH_HUONG",
                    "cau_dan": "Một học sinh viết chương trình Python giải bài toán <bài toán Chủ đề F>: <mã Python>. Xét các nhận định sau:",
                    "trinh_bay": "4 ý a, b, c, d kiểm tra kiểu dữ liệu, cú pháp, kết quả với dữ liệu mẫu và cách sửa/mở rộng.",
                    "thang_diem": "1ý:0.1 | 2ý:0.25 | 3ý:0.5 | 4ý:1.0",
                },
            ],
            "SHORT_ANSWER": [
                {
                    "id": "SA_1_KET_QUA_CODE",
                    "cau_dan": "Cho đoạn chương trình Python sau: <mã Python>. Sau khi thực hiện, giá trị in ra màn hình là bao nhiêu?",
                    "trinh_bay": "Đáp án ngắn duy nhất (con số hoặc xâu ngắn tường minh), kèm giải thích từng bước.",
                    "diem": 0.5,
                },
            ],
            "ESSAY_CODE": [
                {
                    "id": "EC_1_VIET_CHUONG_TRINH",
                    "cau_dan": "Cho dữ liệu cụ thể (VD: danh sách A = [...] hoặc xâu s = '...'). Viết chương trình Python thực hiện yêu cầu.",
                    "trinh_bay": "Gồm tình huống có dữ liệu mẫu, yêu cầu rõ ràng, mã Python mẫu chạy được và 3 tiêu chí chấm điểm.",
                    "diem": 1.0,
                },
            ],
        },
    }

    return templates_payload


def save_compact_templates(payload: dict) -> int:
    """Lưu data/exam_templates.json và đảm bảo dung lượng < 3KB (3072 bytes)."""
    os.makedirs(os.path.dirname(TEMPLATES_OUT), exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    raw_bytes = serialized.encode("utf-8")

    # Nếu vượt 3KB (ví dụ danh sách tên nguồn quá dài), tự động nén gọn JSON không thụt lề
    if len(raw_bytes) >= 3072:
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        raw_bytes = serialized.encode("utf-8")

    # Nếu vẫn >= 3KB, cắt gọn danh sách nguon_trich_form
    if len(raw_bytes) >= 3072:
        payload["nguon_trich_form"] = payload["nguon_trich_form"][:6]
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        raw_bytes = serialized.encode("utf-8")

    with open(TEMPLATES_OUT, "w", encoding="utf-8") as f:
        f.write(serialized)

    return len(raw_bytes)


def main():
    print("=== ĐỒNG BỘ & LỌC TỰ ĐỘNG MẪU FORM ĐỀ TỪ GOOGLE DRIVE ===\n")
    t0 = time.time()
    kept_files, skipped_items = sync_whitelisted_forms_from_drive()

    print(f"\n2. DANH SÁCH FILE ĐÃ GIỮ LẠI ĐỂ LẤY FORM ({len(kept_files)} file):")
    for idx, f in enumerate(kept_files, 1):
        print(f"   ✅ {idx:02d}. {f['name']}  [{f['reason']}]  ({f['source']})")

    print(f"\n3. DANH SÁCH THƯ MỤC / FILE ĐÃ BỎ QUA ({len(skipped_items)} mục):")
    for idx, s in enumerate(skipped_items, 1):
        print(f"   ⏭️ {idx:02d}. {s['item']}  -> {s['reason']}")

    print("\n4. Đang trích xuất cấu trúc hình thức (FORM) vào data/exam_templates.json...")
    payload = _detect_exam_patterns(kept_files)
    size_bytes = save_compact_templates(payload)

    print(f"\n🎉 HOÀN TẤT trong {time.time() - t0:.1f}s!")
    print(f"   • File mẫu đã lưu    : {TEMPLATES_OUT}")
    print(f"   • Dung lượng thực tế : {size_bytes} bytes ({size_bytes / 1024:.2f} KB) {'< 3KB ✅' if size_bytes < 3072 else '>= 3KB ⚠️'}")
    print("   • ChromaDB (chroma_db_v2): KHÔNG BỊ ĐỤNG CHẠM (giữ thuần khiết 100% Chủ đề F Python lớp 10).")


if __name__ == "__main__":
    main()
