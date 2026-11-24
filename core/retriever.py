import os
import re
import json
import random
from typing import Any

os.environ["ANONYMIZED_TELEMETRY"] = "False"

from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma

# Định vị thư mục chuẩn của dự án (D:\AI_Agent_NCKH)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_DIR = os.path.join(DATA_DIR, "chroma_db_v2")
GLOSSARY_PATH = os.path.join(DATA_DIR, "grounded_glossary.json")
TEMPLATES_PATH = os.path.join(DATA_DIR, "exam_templates.json")
MATRIX_PATH = os.path.join(DATA_DIR, "ma_tran_de.json")

VALID_LESSONS = {f"Bài {i}" for i in range(16, 33)}
VALID_TYPES = {"MCQ", "TRUE_FALSE", "SHORT_ANSWER", "ESSAY_CODE"}

# Singleton cache (chạy tuần tự, tránh khởi tạo lại kết nối embedding/DB)
_VECTOR_DB: Chroma | None = None
_GLOSSARY_CACHE: list[dict] | None = None
_TEMPLATES_CACHE: dict | None = None
_MATRIX_CACHE: dict | None = None
_SGK_CHUNK_CACHE: dict[tuple[str, str, int], list[dict]] = {}


def _get_vector_db() -> Chroma:
    global _VECTOR_DB
    if _VECTOR_DB is None:
        embeddings = OllamaEmbeddings(model="nomic-embed-text")
        _VECTOR_DB = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
    return _VECTOR_DB


def _load_json_cached(path: str) -> Any:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_glossary() -> list[dict]:
    global _GLOSSARY_CACHE
    if _GLOSSARY_CACHE is None:
        data = _load_json_cached(GLOSSARY_PATH)
        _GLOSSARY_CACHE = data if isinstance(data, list) else []
    return _GLOSSARY_CACHE


def get_exam_templates() -> dict:
    global _TEMPLATES_CACHE
    if _TEMPLATES_CACHE is None:
        data = _load_json_cached(TEMPLATES_PATH)
        _TEMPLATES_CACHE = data if isinstance(data, dict) else {}
    return _TEMPLATES_CACHE


def get_exam_matrix() -> dict:
    global _MATRIX_CACHE
    if _MATRIX_CACHE is None:
        data = _load_json_cached(MATRIX_PATH)
        _MATRIX_CACHE = data if isinstance(data, dict) else {}
    return _MATRIX_CACHE


def normalize_lesson_name(bai_hoc: str) -> str:
    """Chuẩn hóa tên bài học về dạng khóa cứng 'Bài 16' .. 'Bài 32' (Chủ đề F)."""
    m = re.search(r"(?:bài|bai)\s*(\d{2})", bai_hoc.strip(), re.IGNORECASE)
    if not m:
        m = re.search(r"\b(1[6-9]|2\d|3[0-2])\b", bai_hoc.strip())
    if not m:
        raise ValueError(
            f"Bài học '{bai_hoc}' không hợp lệ. Hệ thống khóa chặt phạm vi Chủ đề F (Bài 16 - Bài 32)."
        )
    lesson = f"Bài {int(m.group(1))}"
    if lesson not in VALID_LESSONS:
        raise ValueError(
            f"'{lesson}' nằm ngoài phạm vi Chủ đề F Tin học 10 (chỉ cho phép Bài 16 - Bài 32)."
        )
    return lesson


def estimate_tokens(text: str) -> int:
    """Ước lượng bảo thủ số token cho văn bản tiếng Việt + mã Python (~3.2 ký tự/token)."""
    if not text:
        return 0
    return max(1, int(len(text) / 3.2))


def _truncate_text(text: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _select_glossary_terms(lesson: str, query: str, max_terms: int = 3) -> list[dict]:
    """Lấy thuật ngữ chuẩn SGK ưu tiên đúng bài học, bổ sung theo từ khóa nếu cần."""
    glossary = get_glossary()
    exact = [item for item in glossary if item.get("bai_hoc") == lesson]
    if exact:
        return exact[:max_terms]

    q_lower = query.lower()
    matched = [
        item for item in glossary
        if item.get("thuat_ngu", "").lower() in q_lower
        or any(w in item.get("dinh_nghia_sgk", "").lower() for w in q_lower.split() if len(w) > 3)
    ]
    return matched[:max_terms]


def _select_single_template(loai_cau_hoi: str) -> dict:
    """Lấy đúng 1 mẫu khuôn đề tương ứng từ data/exam_templates.json để tối ưu token."""
    templates_data = get_exam_templates()
    templates_by_type = templates_data.get("templates", templates_data)
    items = templates_by_type.get(loai_cau_hoi, [])
    if isinstance(items, list) and items:
        return items[0]
    if isinstance(items, dict):
        return items
    # Fallback khuôn tối giản nếu chưa chạy drive_form_sync
    defaults = {
        "MCQ": {
            "ten_mau": "MCQ chuẩn 4 phương án (0.25đ)",
            "cau_dan_mau": "Cho đoạn chương trình Python sau / Trong Python, ... phương án nào sau đây đúng?",
            "quy_tac": "4 phương án A, B, C, D độc lập, độ dài tương đương, duy nhất 1 đáp án đúng.",
        },
        "TRUE_FALSE": {
            "ten_mau": "Đúng/Sai 4 ý a, b, c, d (chấm bậc thang 0.1-0.25-0.5-1.0đ)",
            "cau_dan_mau": "Cho chương trình Python sau: ... Sau khi tìm hiểu chương trình, có các phát biểu sau:",
            "quy_tac": "4 mệnh đề a, b, c, d độc lập, có đủ cả Đúng và Sai.",
        },
        "SHORT_ANSWER": {
            "ten_mau": "Trả lời ngắn (0.5đ)",
            "cau_dan_mau": "Cho đoạn chương trình Python sau: ... Kết quả in ra màn hình là bao nhiêu?",
            "quy_tac": "Đáp án là 1 giá trị số hoặc xâu ngắn duy nhất.",
        },
        "ESSAY_CODE": {
            "ten_mau": "Tự luận lập trình Python",
            "cau_dan_mau": "Viết chương trình Python giải bài toán với dữ liệu đầu vào cụ thể.",
            "quy_tac": "Đưa dữ liệu mẫu cụ thể, mã Python chạy được trong Sandbox, kèm tiêu chí chấm.",
        },
    }
    return defaults.get(loai_cau_hoi, defaults["MCQ"])


def _get_nlc_and_scoring(lesson: str, loai_cau_hoi: str) -> tuple[list[dict], dict]:
    """Tra bảng ánh xạ chỉ báo năng lực NLc và thang điểm từ data/ma_tran_de.json."""
    matrix = get_exam_matrix()
    chi_bao_map = matrix.get("chi_bao_nang_luc_NLc", {}).get("chi_bao", {})
    nlc_list = []
    for code, info in chi_bao_map.items():
        if lesson in info.get("bai_hoc_anh_xa", []):
            nlc_list.append({
                "ma": code,
                "bieu_hien": info.get("bieu_hien_chuan", ""),
            })
    thang_diem = matrix.get("cau_truc_va_thang_diem_2025_2026", {}).get(loai_cau_hoi, {})
    return nlc_list[:3], thang_diem


def generate_problem_seed(lesson: str, loai: str) -> dict:
    """
    Tạo ngẫu nhiên 1 Hạt giống dữ liệu (Problem Seed) riêng biệt cho mỗi lần sinh câu hỏi,
    gồm tên biến và bộ số/xâu/danh sách cụ thể theo đúng nhóm bài học, tránh mô hình 3B sao chép mẫu 1-shot.
    """
    m = re.search(r"(\d+)", lesson)
    lesson_num = int(m.group(1)) if m else 19

    # Tránh tuyệt đối các dữ liệu 1-shot cũ: x = 7, range(1, 5), [7, 4, 9, 6, 8], 'Chan'/'Le'
    if lesson_num == 18:
        v_in = random.choice(["n", "chieu_dai", "tuoi", "gia_ban", "diem_toan"])
        conv_fn = random.choice(["int", "float"])
        seed_text = (
            f"Trọng tâm Bài 18 (Vào/Ra): bắt buộc dùng lệnh `input()`, chuyển đổi kiểu `{conv_fn}(...)` và lệnh `print()` "
            f"với biến `{v_in}`."
        )
        return {"nhom": "io", "vars": [v_in], "data": [conv_fn], "prompt_hint": seed_text}

    if lesson_num in (29, 30):
        err_kind = random.choice([
            ("SyntaxError", "lỗi cú pháp (thiếu dấu hai chấm hoặc ngoặc)"),
            ("ZeroDivisionError", "ngoại lệ chia cho 0"),
            ("IndexError", "ngoại lệ vượt chỉ số danh sách"),
            ("NameError", "ngoại lệ dùng biến chưa khai báo"),
            ("TypeError", "ngoại lệ sai kiểu dữ liệu khi cộng xâu với số"),
            ("lỗi logic", "lỗi logic sai kết quả dù chương trình không báo lỗi"),
        ])
        seed_text = (
            f"Trọng tâm Bài {lesson_num} (Lỗi & Kiểm thử): đề bài/phương án BẮT BUỘC xoay quanh `{err_kind[0]}` "
            f"({err_kind[1]}) hoặc quy trình kiểm thử, gỡ lỗi chương trình Python."
        )
        return {"nhom": "error_debug", "vars": [], "data": [err_kind[0]], "prompt_hint": seed_text}

    if lesson_num in (22, 23) or (lesson_num in (31, 32) and loai == "ESSAY_CODE"):
        var_list = random.choice(["ds", "mang", "diem", "so_lieu", "kq", "arr"])
        nums = random.sample([2, 3, 5, 6, 8, 10, 11, 12, 13, 15, 16, 18, 20], 5)
        extra_val = random.choice([4, 9, 14, 17, 21])
        threshold = random.choice([8, 10, 12])
        task_hint = random.choice([
            f"tìm giá trị lớn nhất trong danh sách `{var_list}`",
            f"đếm số phần tử lớn hơn {threshold} trong danh sách `{var_list}`",
            f"tính trung bình cộng các phần tử trong danh sách `{var_list}`",
            f"đếm số phần tử chia hết cho 3 trong danh sách `{var_list}`",
            f"thêm phần tử `{extra_val}` vào cuối danh sách bằng `append()` và tính độ dài `len({var_list})`",
            f"tìm giá trị nhỏ nhất trong danh sách `{var_list}`",
        ])
        seed_text = (
            f"Dùng biến danh sách `{var_list} = {nums}` (ghi rõ dữ liệu này trong đề, gán trực tiếp ngay dòng đầu trong đáp án, "
            f"không dùng input(), yêu cầu bài toán: {task_hint})."
        )
        return {"nhom": "list", "vars": [var_list], "data": nums, "prompt_hint": seed_text}

    if lesson_num in (24, 25):
        var_str = random.choice(["s", "chuoi", "ten", "ma_so", "van_ban", "tu"])
        sample_str = random.choice([
            "TinHoc10", "HaNoi2026", "Python_KNTT", "LapTrinh",
            "KhoaHoc", "HocSinh", "DuLieuSo", "MayTinh", "ThuatToan", "Lop10A1",
        ])
        seed_text = f"Dùng biến xâu kí tự `{var_str} = '{sample_str}'` (bắt buộc làm việc trực tiếp trên xâu này với `len()`, `find()`, hoặc trích kí tự)."
        return {"nhom": "string", "vars": [var_str], "data": sample_str, "prompt_hint": seed_text}

    if lesson_num in (26, 27, 28):
        fn_name, fn_goal = random.choice([
            ("tim_lon_nhat", "trả về số lớn hơn giữa hai tham số"),
            ("tinh_hieu", "trả về hiệu hai tham số"),
            ("tinh_tich", "trả về tích hai tham số"),
            ("tinh_tb", "trả về trung bình cộng hai tham số"),
            ("chia_het", "kiểm tra tham số thứ nhất có chia hết cho tham số thứ hai không"),
            ("chu_vi_hcn", "trả về chu vi hình chữ nhật 2 * (tham_so_1 + tham_so_2)"),
        ])
        p1, p2 = random.choice([("a", "b"), ("m", "n"), ("p", "q"), ("u", "v"), ("k", "t")])
        v1, v2 = random.randint(3, 9), random.randint(2, 12)
        seed_text = (
            f"Bắt buộc có định nghĩa hàm `def {fn_name}({p1}, {p2}):` ({fn_goal}) "
            f"và gọi thử với `{p1} = {v1}, {p2} = {v2}`."
        )
        return {"nhom": "function", "vars": [fn_name, p1, p2], "data": [v1, v2], "prompt_hint": seed_text}

    if lesson_num in (20, 21):
        acc_var = random.choice(["tong", "dem", "kq", "tich", "t"])
        loop_var = random.choice(["k", "j", "v", "n", "so"])
        start = random.choice([1, 2, 3])
        stop = random.choice([6, 7, 8, 9, 10])
        if (start, stop) == (1, 5):
            stop = 8
        step = random.choice([1, 2])
        seed_text = (
            f"Dùng biến tích lũy `{acc_var}` và biến đếm `{loop_var}` "
            f"(khoảng lặp range({start}, {stop}, {step}))."
        )
        return {"nhom": "loop", "vars": [acc_var, loop_var], "data": [start, stop, step], "prompt_hint": seed_text}

    # Bài 16-19 và Bài 29-32 (Biến, gán, vào/ra, rẽ nhánh if, lỗi, ôn tập)
    v1_name, v2_name = random.choice([("a", "b"), ("m", "n"), ("p", "q"), ("u", "v"), ("diem", "nguong"), ("gia", "sl")])
    n1 = random.choice([3, 4, 6, 8, 9, 11, 12, 14, 15, 18])
    n2 = random.choice([2, 3, 4, 5, 6, 8, 10])
    lbl_true, lbl_false = random.choice([
        ("Dat", "ChuaDat"), ("Lon", "Nho"), ("Duong", "KhongDuong"),
        ("HopLe", "KhongHopLe"), ("Cao", "Thap"), ("Dung", "Sai"),
    ])
    seed_text = (
        f"Dùng các biến `{v1_name} = {n1}`, `{v2_name} = {n2}`"
        + (f" và nhãn in ra `'{lbl_true}'` / `'{lbl_false}'`." if lesson_num == 19 else ".")
    )
    return {"nhom": "general", "vars": [v1_name, v2_name], "data": [n1, n2], "prompt_hint": seed_text}


def retrieve_evidence_package(
    bai_hoc: str,
    loai_cau_hoi: str,
    chu_de_chi_tiet: str = "",
    muc_do: str = "TH",
    k_sgk: int = 3,
    max_context_tokens: int = 1150,
) -> dict:
    """
    Truy xuất Evidence Package sạch, khóa cứng theo bai_hoc (Bài 16-32) từ chroma_db_v2,
    kết hợp thuật ngữ chuẩn SGK (grounded_glossary.json), đúng 1 khuôn mẫu đề (exam_templates.json)
    và 1 Hạt giống dữ liệu ngẫu nhiên (Problem Seed) để chống trùng lặp.
    """
    lesson = normalize_lesson_name(bai_hoc)
    loai = loai_cau_hoi.strip().upper()
    if loai not in VALID_TYPES:
        raise ValueError(f"Dạng câu hỏi '{loai_cau_hoi}' không hợp lệ. Chỉ hỗ trợ: {sorted(VALID_TYPES)}")

    query_text = f"{lesson} {chu_de_chi_tiet}".strip()

    # 1. Truy xuất SGK khóa cứng theo nguon=SGK_Tin10_KNTT và bai_hoc=lesson (có cache theo lesson + chi_tiet)
    sgk_cache_key = (lesson, chu_de_chi_tiet.strip(), k_sgk)
    if sgk_cache_key in _SGK_CHUNK_CACHE:
        sgk_chunks = [dict(c) for c in _SGK_CHUNK_CACHE[sgk_cache_key]]
    else:
        db = _get_vector_db()
        sgk_filter = {"$and": [{"nguon": "SGK_Tin10_KNTT"}, {"bai_hoc": lesson}]}
        sgk_chunks = []
        # Khi không có từ khóa phụ (preset ma trận), lấy trực tiếp chunk khóa bài từ ChromaDB (0ms embedding, tránh đổi VRAM)
        if not chu_de_chi_tiet.strip():
            try:
                raw_got = db._collection.get(where=sgk_filter, limit=k_sgk, include=["documents", "metadatas"])
                docs_list = raw_got.get("documents") or []
                metas_list = raw_got.get("metadatas") or []
                for doc_txt, meta in zip(docs_list, metas_list):
                    m_obj = meta if isinstance(meta, dict) else {}
                    if doc_txt and str(doc_txt).strip():
                        sgk_chunks.append({
                            "bai_hoc": m_obj.get("bai_hoc", lesson),
                            "trang": m_obj.get("trang", ""),
                            "content": str(doc_txt).strip(),
                        })
            except Exception:
                sgk_chunks = []

        if not sgk_chunks:
            sgk_raw_docs = db.similarity_search(query_text, k=k_sgk, filter=sgk_filter)
            sgk_chunks = [
                {
                    "bai_hoc": d.metadata.get("bai_hoc", lesson),
                    "trang": d.metadata.get("trang", ""),
                    "content": d.page_content.strip(),
                }
                for d in sgk_raw_docs
            ]
        _SGK_CHUNK_CACHE[sgk_cache_key] = [dict(c) for c in sgk_chunks]

    # 2. Tra thuật ngữ chuẩn SGK + 1 khuôn mẫu đề + năng lực NLc + Hạt giống dữ liệu (Problem Seed)
    glossary_terms = _select_glossary_terms(lesson, query_text, max_terms=3)
    exam_template = _select_single_template(loai)
    nlc_indicators, thang_diem = _get_nlc_and_scoring(lesson, loai)
    problem_seed = generate_problem_seed(lesson, loai)

    # Chỉ truy xuất De_Tham_Khao_2026 khi template chưa có vi_du_1shot (tránh gọi embedding dư thừa)
    ref_sample = ""
    if not exam_template.get("vi_du_1shot"):
        try:
            db = _get_vector_db()
            ref_filter_exact = {
                "$and": [
                    {"nguon": "De_Tham_Khao_2026"},
                    {"bai_hoc": lesson},
                    {"dang_cau_hoi": loai},
                ]
            }
            ref_docs = db.similarity_search(query_text, k=1, filter=ref_filter_exact)
            if ref_docs:
                ref_sample = _truncate_text(ref_docs[0].page_content, 280)
        except Exception:
            ref_sample = ""

    # 4. Đóng gói ngữ cảnh gọn dạng văn bản thuần (KHÔNG chèn JSON phụ gây nhiễu LLM 3B)
    sections: list[str] = []

    # 4a. Lý thuyết chuẩn SGK
    sgk_lines = [f"### BẰNG CHỨNG SGK TIN HỌC 10 KNTT ({lesson}):"]
    per_chunk_limit = 420
    for ch in sgk_chunks:
        sgk_lines.append(f"- [SGK {ch['bai_hoc']}, trang {ch['trang']}]: {_truncate_text(ch['content'], per_chunk_limit)}")
    sections.append("\n".join(sgk_lines))

    # 4b. Thuật ngữ chuẩn bắt buộc
    if glossary_terms:
        g_lines = ["### THUẬT NGỮ CHUẨN SGK (BẮT BUỘC DÙNG ĐÚNG):"]
        for g in glossary_terms:
            g_lines.append(f"- {g['thuat_ngu']} ({g['bai_hoc']}, tr.{g['trang']}): {_truncate_text(g['dinh_nghia_sgk'], 200)}")
        sections.append("\n".join(g_lines))

    # 4c. Khuôn mẫu hình thức đề thi
    trinh_bay_mau = exam_template.get("trinh_bay") or exam_template.get("quy_tac", "")
    diem_mau = exam_template.get("thang_diem") or exam_template.get("diem", "")
    tpl_lines = [
        f"### QUY CÁCH HÌNH THỨC ĐỀ ({loai} - Chuẩn 2025-2026):",
        f"- Yêu cầu trình bày: {trinh_bay_mau}",
    ]
    if diem_mau != "":
        tpl_lines.append(f"- Thang điểm: {diem_mau}")
    sections.append("\n".join(tpl_lines))

    # 4d. Chỉ báo năng lực NLc
    if nlc_indicators:
        nlc_str = "; ".join(f"{x['ma']}: {x['bieu_hien']}" for x in nlc_indicators)
        sections.append(f"### CHỈ BÁO NĂNG LỰC NLc: {nlc_str}")

    seed_section = f"### HẠT GIỐNG DỮ LIỆU MỚI (BẮT BUỘC DÙNG ĐỂ ĐA DẠNG BÀI TOÁN):\n- {problem_seed['prompt_hint']}"
    seed_tokens = estimate_tokens(seed_section) + 10
    body_budget = max(250, max_context_tokens - seed_tokens)

    # 4e. Chỉ bổ sung ref_sample nếu khuôn mẫu chưa có ví dụ 1-shot
    formatted_body = "\n\n".join(sections)
    has_one_shot = bool(exam_template.get("vi_du_1shot"))
    if (not has_one_shot) and ref_sample and estimate_tokens(formatted_body + "\n\n" + ref_sample) <= body_budget:
        formatted_body += f"\n\n### THAM KHẢO PHONG CÁCH CÂU HỎI CÙNG BÀI ({lesson}):\n{ref_sample}"

    # Cắt gọn phần thân SGK nếu vượt ngân sách, luôn bảo toàn nguyên vẹn Hạt giống dữ liệu
    while estimate_tokens(formatted_body) > body_budget and len(formatted_body) > 350:
        formatted_body = formatted_body[: int(len(formatted_body) * 0.9)].rstrip() + "..."

    formatted_context = f"{formatted_body}\n\n{seed_section}"

    return {
        "bai_hoc": lesson,
        "loai_cau_hoi": loai,
        "muc_do": muc_do,
        "sgk_chunks": sgk_chunks,
        "glossary_terms": glossary_terms,
        "exam_template": exam_template,
        "reference_sample": ref_sample,
        "nlc_indicators": nlc_indicators,
        "thang_diem": thang_diem,
        "problem_seed": problem_seed,
        "formatted_context": formatted_context,
        "estimated_context_tokens": estimate_tokens(formatted_context),
    }


if __name__ == "__main__":
    pkg = retrieve_evidence_package("Bài 19: Câu lệnh rẽ nhánh if", "MCQ")
    print(f"Bài học: {pkg['bai_hoc']} | SGK chunks: {len(pkg['sgk_chunks'])} | Glossary: {len(pkg['glossary_terms'])} | Tokens: {pkg['estimated_context_tokens']}")
    print(pkg["formatted_context"])
