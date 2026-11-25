import os
import re
import io
import json
import time
import random
import requests
import hashlib
from typing import Any

from docx import Document as DocxDocument
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

from core.generator import generate_question, OLLAMA_BASE_URL
from core.retriever import (
    get_exam_matrix,
    retrieve_evidence_package,
    generate_problem_seed,
    normalize_lesson_name,
    estimate_tokens,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MATRIX_PATH = os.path.join(BASE_DIR, "data", "ma_tran_de.json")
RECENT_BLUEPRINTS_PATH = os.path.join(BASE_DIR, "data", "recent_blueprints.json")

# Mặc định mẫu đề mini chuẩn kiểm tra nhanh (3 MCQ + 1 TRUE_FALSE + 1 SHORT_ANSWER + 1 ESSAY_CODE)
DEFAULT_MINI_EXAM_SPECS = [
    {"bai_hoc": "Bài 17", "loai_cau_hoi": "MCQ", "muc_do": "NB"},
    {"bai_hoc": "Bài 19", "loai_cau_hoi": "MCQ", "muc_do": "TH"},
    {"bai_hoc": "Bài 22", "loai_cau_hoi": "MCQ", "muc_do": "TH"},
    {"bai_hoc": "Bài 20", "loai_cau_hoi": "TRUE_FALSE", "muc_do": "TH"},
    {"bai_hoc": "Bài 21", "loai_cau_hoi": "SHORT_ANSWER", "muc_do": "VD"},
    {"bai_hoc": "Bài 26", "loai_cau_hoi": "ESSAY_CODE", "muc_do": "VD"},
]


def _load_recent_blueprints() -> list[str]:
    """Tải danh sách tối đa 90 blueprint_id đã dùng ở 5 lần sinh đề gần nhất."""
    try:
        if os.path.exists(RECENT_BLUEPRINTS_PATH):
            with open(RECENT_BLUEPRINTS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [str(x).strip() for x in data if str(x).strip()]
            if isinstance(data, dict):
                return [str(x).strip() for x in data.get("recent_blueprints", []) if str(x).strip()]
    except Exception as e:
        print(f"   ⚠️ Không đọc được recent_blueprints.json ({e})", flush=True)
    return []


def _save_recent_blueprints(new_blueprint_ids: list[str]) -> None:
    """Lưu danh sách blueprint_id vào data/recent_blueprints.json, giữ tối đa 90 ID của 5 đề gần nhất."""
    try:
        existing = _load_recent_blueprints()
        clean_new = [str(x).strip() for x in new_blueprint_ids if str(x).strip()]
        combined = [x for x in existing if x not in set(clean_new)] + clean_new
        trimmed = combined[-90:]
        os.makedirs(os.path.dirname(RECENT_BLUEPRINTS_PATH), exist_ok=True)
        with open(RECENT_BLUEPRINTS_PATH, "w", encoding="utf-8") as f:
            json.dump({"recent_blueprints": trimmed}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"   ⚠️ Không ghi được recent_blueprints.json ({e})", flush=True)


def _rotate_topic_f_specs(specs: list[dict]) -> list[dict]:
    """
    Khi sinh đề toàn Chủ đề F (số câu >= 10 và bao quát >= 5 bài học),
    tự động xoay vòng ngẫu nhiên danh sách bài học cho từng phần để phủ đều Bài 16 đến Bài 32,
    bao gồm Bài 23 (thao tác danh sách), Bài 27 (tham số/đối số), Bài 30 (gỡ lỗi), Bài 32 (tổng hợp),
    và xoay vòng đa dạng giữa các bài toán phần tự luận ESSAY_CODE (lọc nhiệt độ, đếm số nguyên tố,
    tìm min/max, tính tiền điện/hóa đơn, kiểm tra mật khẩu, xử lý xâu mã học sinh, tính trung bình danh sách).
    Chỉ gán bài học L cho dạng T nếu cặp (L, T) thực sự có blueprint khả dụng trong kho.
    """
    if not specs or len(specs) < 10:
        return specs

    distinct_lessons = {s.get("bai_hoc", "").split(":")[0].strip() for s in specs}
    if len(distinct_lessons) < 5:
        return specs

    mcq_specs = [s for s in specs if s.get("loai_cau_hoi") == "MCQ"]
    tf_specs = [s for s in specs if s.get("loai_cau_hoi") == "TRUE_FALSE"]
    sa_specs = [s for s in specs if s.get("loai_cau_hoi") == "SHORT_ANSWER"]
    ec_specs = [s for s in specs if s.get("loai_cau_hoi") == "ESSAY_CODE"]

    # 1. Xoay vòng MCQ (phủ cả Bài 16..32, đặc biệt Bài 23, 27, 30, 32)
    n_mcq = len(mcq_specs)
    all_mcq_lessons = [f"Bài {i}" for i in range(16, 33)]
    if n_mcq <= len(all_mcq_lessons):
        if n_mcq >= 8:
            g1 = ["Bài 16", "Bài 17", "Bài 18"]
            g2 = ["Bài 19", "Bài 20", "Bài 21"]
            g3 = ["Bài 22", "Bài 23", "Bài 24", "Bài 25"]
            g4 = ["Bài 26", "Bài 27", "Bài 28", "Bài 29", "Bài 30", "Bài 31", "Bài 32"]
            k1 = min(len(g1), max(2, n_mcq // 4))
            k2 = min(len(g2), max(2, n_mcq // 4))
            k3 = min(len(g3), max(2, n_mcq // 4))
            c1 = random.sample(g1, k1)
            c2 = random.sample(g2, k2)
            c3 = random.sample(g3, k3)
            rem = max(0, n_mcq - len(c1) - len(c2) - len(c3))
            c4 = random.sample(g4, min(len(g4), rem))
            chosen_mcq = c1 + c2 + c3 + c4
            if len(chosen_mcq) < n_mcq:
                unused_mcq = [x for x in all_mcq_lessons if x not in chosen_mcq]
                chosen_mcq.extend(random.sample(unused_mcq, min(len(unused_mcq), n_mcq - len(chosen_mcq))))
            random.shuffle(chosen_mcq)
        else:
            chosen_mcq = random.sample(all_mcq_lessons, n_mcq)
    else:
        mult = (n_mcq // len(all_mcq_lessons)) + 1
        extended_pool = all_mcq_lessons * mult
        random.shuffle(extended_pool)
        chosen_mcq = extended_pool[:n_mcq]

    # 2. Xoay vòng TRUE_FALSE (phủ các bài có blueprint Đúng/Sai thật)
    n_tf = len(tf_specs)
    tf_available = ["Bài 16", "Bài 17", "Bài 18", "Bài 19", "Bài 20", "Bài 21", "Bài 22", "Bài 23", "Bài 24", "Bài 25", "Bài 26", "Bài 27", "Bài 28", "Bài 29", "Bài 30"]
    if n_tf <= len(tf_available):
        chosen_tf = random.sample(tf_available, n_tf)
    else:
        mult = (n_tf // len(tf_available)) + 1
        extended_tf = tf_available * mult
        random.shuffle(extended_tf)
        chosen_tf = extended_tf[:n_tf]

    # 3. Xoay vòng SHORT_ANSWER (phủ các bài có blueprint Trả lời ngắn thật)
    n_sa = len(sa_specs)
    sa_available = ["Bài 16", "Bài 17", "Bài 18", "Bài 19", "Bài 20", "Bài 21", "Bài 22", "Bài 23", "Bài 24", "Bài 25", "Bài 26", "Bài 27", "Bài 28", "Bài 29", "Bài 30"]
    if n_sa <= len(sa_available):
        chosen_sa = random.sample(sa_available, n_sa)
    else:
        mult = (n_sa // len(sa_available)) + 1
        extended_sa = sa_available * mult
        random.shuffle(extended_sa)
        chosen_sa = extended_sa[:n_sa]

    # 4. Xoay vòng ESSAY_CODE (kho bài toán thực tế đa dạng, không trùng bài học)
    n_ec = len(ec_specs)
    ec_pool = [
        ("Bài 18", "Tính chỉ số thể trạng BMI và phân loại"),
        ("Bài 19", "Tính tiền điện sinh hoạt theo bậc thang"),
        ("Bài 19", "Tính tiền nước sinh hoạt gia đình"),
        ("Bài 19", "Tính cước taxi theo km bậc thang"),
        ("Bài 19", "Kiểm tra 3 cạnh của một tam giác"),
        ("Bài 20", "Tìm giá trị lớn nhất trong dãy số không dùng hàm max"),
        ("Bài 20", "Đếm số lượng số chính phương trong đoạn"),
        ("Bài 21", "Vòng lặp while cộng dồn đến khi vượt ngưỡng"),
        ("Bài 21", "Tính tiền gửi tiết kiệm lãi kép qua các năm"),
        ("Bài 22", "Lọc các ngày có nhiệt độ vượt ngưỡng trong danh sách"),
        ("Bài 22", "Tính điểm trung bình học tập của học sinh"),
        ("Bài 22", "Tìm phần tử lớn thứ nhì trong danh sách"),
        ("Bài 22", "Lọc các khoản doanh thu đạt chỉ tiêu"),
        ("Bài 23", "Duyệt và tách danh sách các số chẵn"),
        ("Bài 23", "Tách danh sách thành hai danh sách chẵn và lẻ"),
        ("Bài 24", "Đếm số lần xuất hiện của kí tự trong xâu họ tên"),
        ("Bài 24", "Đếm số lượng nguyên âm trong xâu tiếng Anh"),
        ("Bài 25", "Chuẩn hóa xâu họ tên loại bỏ khoảng trắng thừa"),
        ("Bài 26", "Hàm tính chu vi và diện tích hình chữ nhật"),
        ("Bài 26", "Hàm kiểm tra tính hợp lệ của mật khẩu"),
        ("Bài 26", "Hàm kiểm tra và đếm số lượng số nguyên tố"),
        ("Bài 26", "Hàm tính diện tích hình tròn"),
        ("Bài 27", "Hàm đánh giá độ mạnh của mật khẩu người dùng"),
        ("Bài 29", "Kiểm thử phòng ngừa lỗi chia cho 0 (ZeroDivisionError)"),
        ("Bài 31", "Đếm số chia hết cho 5 và tìm giá trị nhỏ nhất"),
        ("Bài 31", "Lọc các từ có độ dài lớn hơn ngưỡng trong xâu"),
        ("Bài 32", "Đếm số lượng chữ số trong xâu mã học sinh"),
        ("Bài 32", "Đếm tần suất xuất hiện từ khóa trong văn bản"),
    ]
    random.shuffle(ec_pool)
    chosen_ec = []
    seen_ec_lessons = set()
    for bh, det in ec_pool:
        if bh not in seen_ec_lessons:
            chosen_ec.append((bh, det))
            seen_ec_lessons.add(bh)
            if len(chosen_ec) == n_ec:
                break
    if len(chosen_ec) < n_ec:
        for item in ec_pool:
            if item not in chosen_ec:
                chosen_ec.append(item)
                if len(chosen_ec) == n_ec:
                    break

    rotated: list[dict] = []
    for orig, new_bh in zip(mcq_specs, chosen_mcq):
        c = dict(orig)
        c["bai_hoc"] = new_bh
        rotated.append(c)

    for orig, new_bh in zip(tf_specs, chosen_tf):
        c = dict(orig)
        c["bai_hoc"] = new_bh
        rotated.append(c)

    for orig, new_bh in zip(sa_specs, chosen_sa):
        c = dict(orig)
        c["bai_hoc"] = new_bh
        rotated.append(c)

    for orig, (new_bh, detail) in zip(ec_specs, chosen_ec):
        c = dict(orig)
        c["bai_hoc"] = new_bh
        c["chu_de_chi_tiet"] = detail
        rotated.append(c)

    return rotated

STOPWORDS = {
    "là", "và", "của", "các", "trong", "cho", "với", "được", "một", "có", "để",
    "khi", "này", "đó", "từ", "theo", "sau", "đây", "về", "hay", "hoặc", "như",
    "không", "thì", "mà", "những", "bằng", "vào", "ra", "trên", "dưới", "tại",
    "câu", "lệnh", "chương", "trình", "python", "kết", "quả", "màn", "hình",
}


def _tokenize(text: str) -> set[str]:
    toks = re.findall(r"[0-9a-zA-ZÀ-ỹ_]+", str(text).lower())
    return {t for t in toks if len(t) >= 2 and t not in STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _get_point_map() -> dict[str, float]:
    """Đọc thang điểm chuẩn 2025-2026 trực tiếp từ data/ma_tran_de.json."""
    matrix = get_exam_matrix()
    cfg = matrix.get("cau_truc_va_thang_diem_2025_2026", {})
    return {
        "MCQ": float(cfg.get("MCQ", {}).get("diem_moi_cau", 0.25)),
        "TRUE_FALSE": float(cfg.get("TRUE_FALSE", {}).get("diem_toi_da_moi_cau", 1.0)),
        "SHORT_ANSWER": float(cfg.get("SHORT_ANSWER", {}).get("diem_moi_cau", 0.5)),
        "ESSAY_CODE": float(cfg.get("ESSAY_CODE", {}).get("diem_moi_cau", 1.0)),
    }


def _extract_item_text(item: dict) -> str:
    q = item.get("question_json", {})
    loai = item.get("loai_cau_hoi", "MCQ")
    if loai == "MCQ":
        return " ".join(str(q.get(k, "")) for k in ("cau_hoi", "A", "B", "C", "D"))
    if loai == "TRUE_FALSE":
        parts = [str(q.get("cau_hoi_chung", ""))]
        for k in ("a", "b", "c", "d"):
            obj = q.get(k) or {}
            if isinstance(obj, dict):
                parts.append(str(obj.get("menh_de", "")))
        return " ".join(parts)
    if loai == "SHORT_ANSWER":
        return f"{q.get('cau_hoi', '')} {q.get('dap_an_ngan', '')}"
    return f"{q.get('tinh_huong', '')} {q.get('yeu_cau_hoc_sinh', '')}"


def _extract_answer_phrase(item: dict) -> str:
    """Lấy nội dung đáp án cốt lõi của một câu hỏi để phát hiện lộ đáp án chéo."""
    q = item.get("question_json", {})
    loai = item.get("loai_cau_hoi", "MCQ")
    if loai == "MCQ":
        ans_key = str(q.get("dap_an", "")).strip().upper()
        if ans_key in ("A", "B", "C", "D"):
            return str(q.get(ans_key, "")).strip()
        return ""
    if loai == "SHORT_ANSWER":
        return str(q.get("dap_an_ngan", "")).strip()
    return ""


def _extract_stem(item: dict) -> str:
    q = item.get("question_json", {})
    loai = item.get("loai_cau_hoi", "MCQ")
    if loai in ("MCQ", "SHORT_ANSWER"):
        return str(q.get("cau_hoi", "")).strip()
    if loai == "TRUE_FALSE":
        return str(q.get("cau_hoi_chung", "")).strip()
    return f"{q.get('tinh_huong', '')} {q.get('yeu_cau_hoc_sinh', '')}".strip()


def _detect_exam_motifs(item: dict) -> list[tuple[str, str]]:
    """
    Nhận diện các mô-típ thuật toán / chủ đề dễ bị lặp trên toàn đề thi (bất kể thuộc phần nào):
      1. 'tính tổng các số chẵn'
      2. 'chế độ gõ lệnh trực tiếp'
      3. 'lệnh gán đúng cú pháp'
    """
    q = item.get("question_json") or {}
    combined = _extract_item_text(item)
    if item.get("loai_cau_hoi") == "ESSAY_CODE":
        combined = f"{combined}\n{q.get('dap_an_mau', '')}"
    low = combined.lower()

    motifs: list[tuple[str, str]] = []

    # 1. Mô-típ tính tổng các số tự nhiên chẵn / tổng các số ... chẵn
    has_even_sum_text = bool(
        "tổng các số tự nhiên chẵn" in low
        or re.search(r"tổng\s+(?:các\s+)?(?:số|phần\s+tử|giá\s+trị)[^.\n]{0,30}chẵn|tính\s+tổng\s+chẵn", low)
    )
    has_even_sum_code = bool(
        re.search(r"%\s*2\s*==\s*0", low)
        and re.search(r"(?:tong|sum|total|s)\s*(?:\+=|=\s*(?:tong|sum|total|s)\s*\+)", low)
    )
    if has_even_sum_text or has_even_sum_code:
        motifs.append(("tong_so_chan", "tổng các số tự nhiên chẵn / tổng các số chẵn"))

    # 2. Mô-típ chế độ gõ lệnh trực tiếp (chỉ cho phép tối đa 1 câu duy nhất trong toàn đề)
    if any(
        cue in low
        for cue in (
            "chế độ gõ lệnh trực tiếp",
            "gõ lệnh trực tiếp",
            "chế độ tương tác",
            "dấu nhắc >>>",
        )
    ):
        motifs.append(("che_do_go_lenh_truc_tiep", "chế độ gõ lệnh trực tiếp"))

    # 3. Mô-típ lệnh gán đúng cú pháp
    if re.search(r"(?:lệnh\s+gán|cách\s+gán|phép\s+gán|câu\s+lệnh\s+gán)[^\n.?]*(?:đúng|hợp\s+lệ)", low):
        motifs.append(("lenh_gan_dung_cu_phap", "lệnh gán đúng cú pháp"))

    return motifs


# ==============================================================================
# NODE EXAM_CRITIC: PHẢN BIỆN TOÀN ĐỀ (CHỐNG TRÙNG LẶP & LỘ ĐÁP ÁN CHÉO)
# ==============================================================================

def _get_item_stem_hash(item: dict) -> str:
    """Tạo mã băm chuẩn hóa của câu dẫn để chống trùng 100%."""
    stem = _extract_stem(item)
    norm = re.sub(r"\s+", " ", stem).strip().lower()
    return hashlib.md5(norm.encode("utf-8")).hexdigest()


def exam_critic(draft_items: list[dict]) -> dict[str, Any]:
    """
    Phản biện toàn bộ đề dự thảo:
      1. Loại bỏ các câu hỏi bị trùng lặp ý/nội dung (Jaccard >= 0.62 hoặc câu dẫn trùng nhau).
      2. Chống trùng mô-típ thuật toán trên toàn đề ('tính tổng các số chẵn', 'chế độ gõ lệnh trực tiếp', 'lệnh gán đúng cú pháp').
      3. Phát hiện & loại bỏ trường hợp câu này làm lộ trực tiếp đáp án dài của câu kia trong cùng bài học.
      4. Tính tổng điểm & bảng phân bổ điểm chuẩn theo cấu trúc 2025-2026 từ data/ma_tran_de.json.
    """
    point_map = _get_point_map()
    kept_items: list[dict] = []
    removed_items: list[dict] = []
    critic_notes: list[str] = []

    kept_tokens: list[set[str]] = []
    kept_stems: list[str] = []
    kept_blueprint_ids: set[str] = set()
    kept_stem_hashes: set[str] = set()
    seen_motifs: dict[str, tuple[int, str]] = {}
    motif_counts: dict[str, int] = {}

    for idx, item in enumerate(draft_items, 1):
        q_obj = item.get("question_json") or {}
        val_obj = item.get("validation_result")
        full_txt = _extract_item_text(item)
        stem = _extract_stem(item)
        toks = _tokenize(full_txt)
        stem_norm = re.sub(r"\s+", " ", stem.lower())
        stem_hash = _get_item_stem_hash(item)
        bp_id = str(item.get("blueprint_id", "")).strip()
        item_motifs = _detect_exam_motifs(item)

        drop_reason = ""

        # Chốt chặn tuyệt đối: loại câu rỗng hoặc câu chưa đạt chuẩn kiểm định (is_pass == False)
        if not isinstance(q_obj, dict) or not q_obj or not stem_norm:
            drop_reason = "Câu hỏi rỗng hoặc thiếu thân câu hỏi."
        elif isinstance(val_obj, dict) and val_obj and val_obj.get("is_pass") is False:
            drop_reason = "Câu hỏi chưa đạt chuẩn kiểm định 2 tầng (is_pass=False), đưa vào hàng đợi Backfill."
        elif bp_id and bp_id in kept_blueprint_ids:
            drop_reason = f"Trùng blueprint_id '{bp_id}' với câu đã có trong đề."
        elif stem_hash and stem_hash in kept_stem_hashes:
            drop_reason = f"Trùng lặp hoàn toàn câu dẫn (stem hash {stem_hash[:8]}) với câu đã có trong đề."

        # Bộ đếm chủ đề bài toán toàn đề: chỉ cho phép tối đa 1 câu duy nhất mỗi mô-típ dễ lặp
        if not drop_reason:
            for m_key, m_label in item_motifs:
                if motif_counts.get(m_key, 0) >= 1:
                    first_k_idx, first_bh = seen_motifs[m_key]
                    drop_reason = (
                        f"Trùng mô-típ bài toán '{m_label}' với Câu #{first_k_idx} ({first_bh}) "
                        "(tối đa 1 câu/đề) -> đẩy sang Backfill bắt buộc đổi sang bài toán khác "
                        "(tìm max/min, đếm phần tử, xử lý xâu, hàm tính toán)."
                    )
                    break

        # Kiểm tra trùng lặp ý / nội dung với các câu đã giữ lại
        if not drop_reason:
            for k_idx, (prev_item, prev_toks, prev_stem) in enumerate(zip(kept_items, kept_tokens, kept_stems), 1):
                sim = _jaccard(toks, prev_toks)
                if (stem_norm and stem_norm == prev_stem) or sim >= 0.62:
                    drop_reason = (
                        f"Trùng lặp nội dung/ý tưởng với Câu #{k_idx} ({prev_item['bai_hoc']} - {prev_item['loai_cau_hoi']}, độ tương đồng {sim:.0%})."
                    )
                    break

                # Kiểm tra lộ đáp án chéo (chỉ xét với đáp án dài >= 18 ký tự mang nghĩa định nghĩa/cú pháp, tránh báo nhầm con số đơn lẻ)
                ans_prev = _extract_answer_phrase(prev_item)
                if len(ans_prev) >= 18 and ans_prev.lower() in full_txt.lower() and prev_item["bai_hoc"] == item["bai_hoc"]:
                    drop_reason = (
                        f"Làm lộ đáp án trực tiếp của Câu #{k_idx} ({prev_item['bai_hoc']}): chứa nguyên văn đáp án '{ans_prev[:50]}'."
                    )
                    break

                ans_curr = _extract_answer_phrase(item)
                prev_full = _extract_item_text(prev_item)
                if len(ans_curr) >= 18 and ans_curr.lower() in prev_full.lower() and prev_item["bai_hoc"] == item["bai_hoc"]:
                    drop_reason = (
                        f"Bị Câu #{k_idx} ({prev_item['bai_hoc']}) làm lộ đáp án '{ans_curr[:50]}'."
                    )
                    break

        if drop_reason:
            removed_items.append({**item, "ly_do_loai": drop_reason})
            critic_notes.append(f"Loại câu dự thảo #{idx} ({item['bai_hoc']} - {item['loai_cau_hoi']}): {drop_reason}")
        else:
            loai = item["loai_cau_hoi"]
            new_pos = len(kept_items) + 1
            enriched = {
                **item,
                "so_thu_tu": new_pos,
                "diem_toi_da": point_map.get(loai, 0.25),
            }
            kept_items.append(enriched)
            kept_tokens.append(toks)
            kept_stems.append(stem_norm)
            if bp_id:
                kept_blueprint_ids.add(bp_id)
            if stem_hash:
                kept_stem_hashes.add(stem_hash)
            for m_key, _ in item_motifs:
                seen_motifs.setdefault(m_key, (new_pos, item["bai_hoc"]))
                motif_counts[m_key] = motif_counts.get(m_key, 0) + 1

    # Tính bảng phân bổ điểm chuẩn 2025-2026
    breakdown: dict[str, dict[str, Any]] = {}
    tong_diem = 0.0
    for loai in ("MCQ", "TRUE_FALSE", "SHORT_ANSWER", "ESSAY_CODE"):
        sub = [x for x in kept_items if x["loai_cau_hoi"] == loai]
        if sub:
            d_cau = point_map[loai]
            d_phan = round(len(sub) * d_cau, 2)
            tong_diem = round(tong_diem + d_phan, 2)
            breakdown[loai] = {
                "so_cau": len(sub),
                "diem_moi_cau": d_cau,
                "tong_diem_phan": d_phan,
            }

    if not critic_notes:
        critic_notes.append("Toàn bộ đề kiểm tra không bị trùng lặp ý và không có câu nào làm lộ đáp án của câu khác.")

    return {
        "items": kept_items,
        "removed_items": removed_items,
        "critic_notes": critic_notes,
        "bang_diem_chi_tiet": breakdown,
        "tong_so_cau": len(kept_items),
        "tong_diem": tong_diem,
    }


def _extract_compact_code_signature(item: dict) -> str:
    """Trích xuất đoạn mã Python (hoặc câu dẫn rút gọn) của 1 câu hỏi để truyền vào avoid_snippets chống lặp."""
    stem = _extract_stem(item)
    code_lines = [
        line.strip()
        for line in stem.splitlines()
        if line.strip() and any(m in line for m in ("=", "for ", "while ", "if ", "def ", "print(", "range(", "["))
    ]
    if code_lines:
        return " ; ".join(code_lines[:4])[:95]
    return re.sub(r"\s+", " ", stem).strip()[:90]


def _recompute_exam_summary(items: list[dict], point_map: dict[str, float]) -> tuple[dict[str, dict[str, Any]], float]:
    """Đánh lại số thứ tự và tính lại bảng phân bổ điểm + tổng điểm chuẩn 2025-2026."""
    breakdown: dict[str, dict[str, Any]] = {}
    tong_diem = 0.0
    for idx, it in enumerate(items, 1):
        loai = it["loai_cau_hoi"]
        it["so_thu_tu"] = idx
        it["diem_toi_da"] = point_map.get(loai, 0.25)
    for loai in ("MCQ", "TRUE_FALSE", "SHORT_ANSWER", "ESSAY_CODE"):
        sub = [x for x in items if x["loai_cau_hoi"] == loai]
        if sub:
            d_cau = point_map[loai]
            d_phan = round(len(sub) * d_cau, 2)
            tong_diem = round(tong_diem + d_phan, 2)
            breakdown[loai] = {
                "so_cau": len(sub),
                "diem_moi_cau": d_cau,
                "tong_diem_phan": d_phan,
            }
    return breakdown, tong_diem


def _unload_embedding_vram() -> bool:
    """
    Giải phóng 100% VRAM của mô hình embedding (nomic-embed-text) trên Ollama
    trước khi bước vào Pha 2 sinh câu hỏi trên llama3.2_tinhoc10 (an toàn tuyệt đối cho 4GB VRAM).
    """
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/embed",
            json={"model": "nomic-embed-text", "keep_alive": 0},
            timeout=15,
        )
        ok = resp.status_code == 200
        print(
            f"[VRAM CLEANUP] Giải phóng nomic-embed-text (keep_alive=0): {'OK' if ok else f'HTTP {resp.status_code}'}",
            flush=True,
        )
        return ok
    except Exception as e:
        print(f"[VRAM CLEANUP] Cảnh báo không thể giải phóng embedding VRAM: {e}", flush=True)
        return False


def _clone_evidence_with_fresh_seed(base_pkg: dict, loai: str) -> dict:
    """
    Sao chép Evidence Package đã tiền truy xuất và thay bằng 1 Hạt giống dữ liệu (Problem Seed)
    ngẫu nhiên mới hoàn toàn (thuần Python, 0ms embedding, không tải lại nomic-embed-text vào VRAM).
    """
    cloned = dict(base_pkg)
    lesson = cloned.get("bai_hoc", "Bài 19")
    fresh_seed = generate_problem_seed(lesson, loai)
    cloned["problem_seed"] = fresh_seed

    ctx = str(cloned.get("formatted_context", ""))
    seed_marker = "\n\n### HẠT GIỐNG DỮ LIỆU MỚI"
    new_seed_block = (
        f"### HẠT GIỐNG DỮ LIỆU MỚI (BẮT BUỘC DÙNG ĐỂ ĐA DẠNG BÀI TOÁN):\n- {fresh_seed['prompt_hint']}"
    )
    if seed_marker in ctx:
        body_part = ctx.split(seed_marker, 1)[0]
        new_ctx = f"{body_part}\n\n{new_seed_block}"
    else:
        new_ctx = f"{ctx}\n\n{new_seed_block}"

    cloned["formatted_context"] = new_ctx
    cloned["estimated_context_tokens"] = estimate_tokens(new_ctx)
    return cloned


def assemble_exam(
    specs: list[dict] | None = None,
    enable_logging: bool = True,
    progress_callback=None,
    max_backfill_rounds: int = 2,
    use_neuro_symbolic: bool = True,
) -> dict[str, Any]:
    """
    Ghép một đề kiểm tra hoàn chỉnh theo danh sách yêu cầu (specs) theo kiến trúc 2 PHA tối ưu 4GB VRAM:
      - PHA 1 (Tiền truy xuất theo lô): Truy xuất toàn bộ ngữ cảnh SGK/Glossary/Template từ ChromaDB
        cho tất cả ô ma trận, sau đó giải phóng 100% VRAM embedding (`nomic-embed-text`, `keep_alive=0`).
      - PHA 2 (Sinh & Kiểm định tuần tự): Ghim trọn `llama3.2_tinhoc10` trên 4GB VRAM, dùng ngữ cảnh
        tiền truy xuất (kèm Hạt giống dữ liệu tươi riêng cho từng ô & Backfill), chạy `exam_critic`
        và Backfill tối đa 2 vòng đảm bảo đề 18/21 câu đủ 100% số câu / trọn vẹn 10.0 điểm.
    """
    exam_specs = _rotate_topic_f_specs(specs if specs else DEFAULT_MINI_EXAM_SPECS)
    target_count = len(exam_specs)
    t0 = time.time()

    recent_blueprints = _load_recent_blueprints()
    if recent_blueprints:
        print(f"[CROSS-EXAM] Đã nạp {len(recent_blueprints)} blueprint_id gần nhất từ data/recent_blueprints.json để chống lặp xuyên đề.", flush=True)

    # ==========================================================================
    # PHA 1: TIỀN TRUY XUẤT THEO LÔ (BATCH PRE-RETRIEVAL) & GIẢI PHÓNG VRAM EMBEDDING
    # ==========================================================================
    print(f"=== PHA 1: TIỀN TRUY XUẤT NGỮ CẢNH THEO LÔ ({target_count} Ô MA TRẬN) ===", flush=True)
    t_p1 = time.time()
    base_ev_cache: dict[tuple[str, str, str, str], dict] = {}
    lesson_type_cache: dict[tuple[str, str], dict] = {}
    slot_evidences: list[dict] = []

    for idx, spec in enumerate(exam_specs, 1):
        raw_bh = spec["bai_hoc"]
        loai = spec["loai_cau_hoi"].strip().upper()
        muc_do = spec.get("muc_do", "TH")
        chi_tiet = spec.get("chu_de_chi_tiet", "")
        norm_bh = normalize_lesson_name(raw_bh)
        cache_key = (norm_bh, loai, muc_do, chi_tiet)

        if progress_callback:
            progress_callback(idx, target_count, f"Pha 1 – Tiền truy xuất SGK: {norm_bh}", loai)

        if cache_key not in base_ev_cache:
            pkg = retrieve_evidence_package(
                bai_hoc=norm_bh,
                loai_cau_hoi=loai,
                chu_de_chi_tiet=chi_tiet,
                muc_do=muc_do,
                max_context_tokens=600,
            )
            base_ev_cache[cache_key] = pkg
            lesson_type_cache.setdefault((norm_bh, loai), pkg)

        # Mỗi ô ma trận nhận 1 bản sao kèm Hạt giống dữ liệu (Problem Seed) riêng biệt
        slot_ev = _clone_evidence_with_fresh_seed(base_ev_cache[cache_key], loai)
        slot_ev["muc_do"] = muc_do
        slot_evidences.append(slot_ev)

    phase1_sec = round(time.time() - t_p1, 2)
    print(
        f"   -> Tiền truy xuất xong {len(base_ev_cache)} cụm (bai_hoc, loai, muc_do) cho {target_count} câu trong {phase1_sec}s.",
        flush=True,
    )
    if phase1_sec > 3.0:
        _unload_embedding_vram()

    # ==========================================================================
    # PHA 2: SINH & KIỂM ĐỊNH TUẦN TỰ TRÊN LLAMA3.2 (VRAM 100% DÀNH CHO LLM)
    # ==========================================================================
    t_p2 = time.time()
    draft_items: list[dict] = []
    failed_specs_queue: list[dict] = []
    used_sigs_by_lesson: dict[str, list[str]] = {}
    used_sigs_all: list[str] = []
    used_blueprint_ids: set[str] = set()
    used_in_current_exam: set[str] = set()
    used_question_hashes: set[str] = set()

    print(f"\n=== PHA 2: SINH & KIỂM ĐỊNH TUẦN TỰ NEURO-SYMBOLIC ({target_count} CÂU - LLAMA3.2 4GB VRAM) ===", flush=True)
    for idx, (spec, slot_ev) in enumerate(zip(exam_specs, slot_evidences), 1):
        bai_hoc = spec["bai_hoc"]
        loai = spec["loai_cau_hoi"].strip().upper()
        muc_do = spec.get("muc_do", "TH")
        chi_tiet = spec.get("chu_de_chi_tiet", "")

        if progress_callback:
            progress_callback(idx, target_count, bai_hoc, loai)

        # Truyền danh sách đoạn mã và blueprint_id đã dùng để bốc thăm không hoàn lại toàn đề
        lesson_key = slot_ev.get("bai_hoc", bai_hoc.split(":")[0].strip())
        prior_avoid = list(dict.fromkeys(used_sigs_by_lesson.get(lesson_key, []) + used_sigs_all[-3:]))

        res = generate_question(
            bai_hoc=bai_hoc,
            loai_cau_hoi=loai,
            chu_de_chi_tiet=chi_tiet,
            muc_do=muc_do,
            enable_logging=enable_logging,
            avoid_snippets=prior_avoid,
            pre_retrieved_evidence=slot_ev,
            used_blueprint_ids=used_blueprint_ids,
            recent_blueprint_ids=recent_blueprints,
            use_neuro_symbolic=use_neuro_symbolic,
        )
        val_res = res.get("validation_result") or {}
        bp_id = str(res.get("blueprint_id", "")).strip()
        item_record = {
            "bai_hoc": res["bai_hoc"],
            "loai_cau_hoi": res["loai_cau_hoi"],
            "muc_do": res["muc_do"],
            "chu_de_chi_tiet": chi_tiet,
            "blueprint_id": bp_id,
            "question_json": res.get("question_json", {}),
            "validation_result": val_res,
            "retry_count": res.get("retry_count", 0),
            "prompt_tokens": res.get("prompt_tokens", 0),
            "latency_sec": res.get("latency_sec", 0.0),
            "log_timestamp": res.get("log_timestamp", ""),
        }
        # CHỈ đưa vào đề dự thảo các câu đạt chuẩn 100% (is_pass == True) và KHÔNG trùng lặp
        stem_hash = _get_item_stem_hash(item_record)
        is_dup_bp = bool(bp_id and bp_id in used_in_current_exam)
        is_dup_stem = bool(stem_hash and stem_hash in used_question_hashes)

        if bool(val_res.get("is_pass", False)) and not is_dup_bp and not is_dup_stem:
            draft_items.append(item_record)
            if bp_id:
                used_blueprint_ids.add(bp_id)
                used_in_current_exam.add(bp_id)
            if stem_hash:
                used_question_hashes.add(stem_hash)
            sig = _extract_compact_code_signature(item_record)
            if sig:
                used_sigs_by_lesson.setdefault(res["bai_hoc"], []).append(sig)
                used_sigs_all.append(sig)
        else:
            reason = "trùng blueprint/câu dẫn trong đề" if (is_dup_bp or is_dup_stem) else "chưa đạt is_pass=True"
            print(
                f"   ↪ [CHẶN LỌT ĐỀ] Câu #{idx} ({res['bai_hoc']} - {loai}) {reason} -> chuyển sang hàng đợi Backfill.",
                flush=True,
            )
            failed_specs_queue.append(item_record)

    print("\n[EXAM_CRITIC] Đang phản biện toàn đề (chống trùng lặp & lộ đáp án chéo)...", flush=True)
    reviewed = exam_critic(draft_items)
    all_removed_history: list[dict] = list(failed_specs_queue) + list(reviewed.get("removed_items", []))
    backfill_notes: list[str] = []
    if failed_specs_queue:
        backfill_notes.append(
            f"Đã chặn {len(failed_specs_queue)} câu rớt chuẩn (is_pass=False) ở lượt đầu và chuyển sang hàng đợi Backfill."
        )
    backfill_rounds_used = 0
    pending_backfill = list(failed_specs_queue) + list(reviewed.get("removed_items", []))

    # VÒNG LẶP BACKFILL: SINH MỚI SẠCH HOÀN TOÀN CHO CÁC Ô RỚT CHUẨN / TRÙNG LẶP (CHỈ NHẬN is_pass == True)
    for bf_round in range(1, max_backfill_rounds + 1):
        deficit = target_count - reviewed["tong_so_cau"]
        if deficit <= 0 or not pending_backfill:
            break

        backfill_rounds_used = bf_round
        to_regen = pending_backfill[:deficit]
        print(
            f"\n[BACKFILL VÒNG {bf_round}/{max_backfill_rounds}] Cần sinh bù {len(to_regen)} câu sạch "
            f"(hiện đạt {reviewed['tong_so_cau']}/{target_count} câu chuẩn is_pass=True)...",
            flush=True,
        )

        kept_pool = list(reviewed["items"])
        round_still_failed: list[dict] = []

        for regen_idx, dropped in enumerate(to_regen, 1):
            bh = dropped["bai_hoc"]
            loai = dropped["loai_cau_hoi"]
            md = dropped.get("muc_do", "TH")
            base_detail = dropped.get("chu_de_chi_tiet", "")
            drop_reason_str = str(dropped.get("ly_do_loai", ""))
            motif_diversify = (
                " | Đổi sang bài toán thuật toán khác (tìm số lớn nhất, đếm số dương, tính trung bình cộng, kiểm tra chia hết hoặc xử lý xâu kí tự)"
                if "Trùng mô-típ" in drop_reason_str
                else ""
            )
            anti_dup_hint = (
                f"{base_detail} | Đổi hoàn toàn tình huống, tên biến và bộ dữ liệu{motif_diversify} (vòng sinh bù {bf_round}.{regen_idx})"
                if base_detail
                else f"Đổi hoàn toàn tình huống, tên biến và bộ dữ liệu{motif_diversify} (vòng sinh bù {bf_round}.{regen_idx})"
            )

            same_lesson_sigs = [
                _extract_compact_code_signature(x)
                for x in kept_pool
                if x.get("bai_hoc") == bh
            ]
            dropped_sig = _extract_compact_code_signature(dropped)
            avoid_for_bf = [s for s in dict.fromkeys(same_lesson_sigs + ([dropped_sig] if dropped_sig else []) + used_sigs_all[-4:]) if s]

            cached_base = lesson_type_cache.get((bh, loai))
            bf_ev = _clone_evidence_with_fresh_seed(cached_base, loai) if cached_base else None
            if bf_ev is not None:
                bf_ev["muc_do"] = md

            if progress_callback:
                progress_callback(
                    target_count,
                    target_count,
                    f"Sinh bù V{bf_round} ({regen_idx}/{len(to_regen)}): {bh}",
                    loai,
                )

            res = generate_question(
                bai_hoc=bh,
                loai_cau_hoi=loai,
                chu_de_chi_tiet=anti_dup_hint,
                muc_do=md,
                enable_logging=enable_logging,
                avoid_snippets=avoid_for_bf,
                pre_retrieved_evidence=bf_ev,
                used_blueprint_ids=used_blueprint_ids,
                recent_blueprint_ids=recent_blueprints,
                use_neuro_symbolic=use_neuro_symbolic,
            )
            bf_val = res.get("validation_result") or {}
            bp_id = str(res.get("blueprint_id", "")).strip()
            new_rec = {
                "bai_hoc": res["bai_hoc"],
                "loai_cau_hoi": res["loai_cau_hoi"],
                "muc_do": res["muc_do"],
                "chu_de_chi_tiet": base_detail,
                "blueprint_id": bp_id,
                "question_json": res.get("question_json", {}),
                "validation_result": bf_val,
                "retry_count": res.get("retry_count", 0),
                "prompt_tokens": res.get("prompt_tokens", 0),
                "latency_sec": res.get("latency_sec", 0.0),
                "log_timestamp": res.get("log_timestamp", ""),
            }
            bf_stem_hash = _get_item_stem_hash(new_rec)
            bf_is_dup_bp = bool(bp_id and bp_id in used_in_current_exam)
            bf_is_dup_stem = bool(bf_stem_hash and bf_stem_hash in used_question_hashes)

            if bool(bf_val.get("is_pass", False)) and not bf_is_dup_bp and not bf_is_dup_stem:
                kept_pool.append(new_rec)
                if bp_id:
                    used_blueprint_ids.add(bp_id)
                    used_in_current_exam.add(bp_id)
                if bf_stem_hash:
                    used_question_hashes.add(bf_stem_hash)
                new_sig = _extract_compact_code_signature(new_rec)
                if new_sig:
                    used_sigs_by_lesson.setdefault(res["bai_hoc"], []).append(new_sig)
                    used_sigs_all.append(new_sig)
            else:
                bf_reason = "trùng blueprint/câu dẫn" if (bf_is_dup_bp or bf_is_dup_stem) else "vẫn chưa đạt is_pass=True"
                print(
                    f"   ↪ [BACKFILL V{bf_round}] Câu bù ({bh} - {loai}) {bf_reason} -> loại bỏ, không đưa vào đề.",
                    flush=True,
                )
                round_still_failed.append(new_rec)

        reviewed = exam_critic(kept_pool)
        all_removed_history.extend(round_still_failed)
        all_removed_history.extend(reviewed.get("removed_items", []))
        pending_backfill = round_still_failed + list(reviewed.get("removed_items", []))
        backfill_notes.append(
            f"Vòng Backfill #{bf_round}: đã sinh bù {len(to_regen)} câu -> đạt {reviewed['tong_so_cau']}/{target_count} câu chuẩn is_pass=True ({reviewed['tong_diem']}đ)."
        )

    # Bù vét cuối cùng nếu chỉ còn thiếu 1-2 ô sau max_backfill_rounds (vẫn bắt buộc is_pass == True 100%)
    if 0 < (target_count - reviewed["tong_so_cau"]) <= 2 and pending_backfill:
        kept_pool = list(reviewed["items"])
        for extra_idx, dropped in enumerate(pending_backfill[: target_count - reviewed["tong_so_cau"]], 1):
            bh = dropped["bai_hoc"]
            loai = dropped["loai_cau_hoi"]
            md = dropped.get("muc_do", "TH")
            base_detail = dropped.get("chu_de_chi_tiet", "")
            cached_base = lesson_type_cache.get((bh, loai))
            for sub_try in range(1, 3):
                bf_ev = _clone_evidence_with_fresh_seed(cached_base, loai) if cached_base else None
                if bf_ev is not None:
                    bf_ev["muc_do"] = md
                res = generate_question(
                    bai_hoc=bh,
                    loai_cau_hoi=loai,
                    chu_de_chi_tiet=f"{base_detail} | Tạo câu hỏi rõ ràng, ngắn gọn (bù cuối {extra_idx}.{sub_try})".strip(" |"),
                    muc_do=md,
                    enable_logging=enable_logging,
                    avoid_snippets=used_sigs_all[-4:],
                    pre_retrieved_evidence=bf_ev,
                    used_blueprint_ids=used_blueprint_ids,
                    recent_blueprint_ids=recent_blueprints,
                    use_neuro_symbolic=use_neuro_symbolic,
                )
                bf_val = res.get("validation_result") or {}
                if bool(bf_val.get("is_pass", False)):
                    bp_id = str(res.get("blueprint_id", "")).strip()
                    if bp_id:
                        used_blueprint_ids.add(bp_id)
                    new_rec = {
                        "bai_hoc": res["bai_hoc"],
                        "loai_cau_hoi": res["loai_cau_hoi"],
                        "muc_do": res["muc_do"],
                        "chu_de_chi_tiet": base_detail,
                        "blueprint_id": bp_id,
                        "question_json": res.get("question_json", {}),
                        "validation_result": bf_val,
                        "retry_count": res.get("retry_count", 0),
                        "prompt_tokens": res.get("prompt_tokens", 0),
                        "latency_sec": res.get("latency_sec", 0.0),
                        "log_timestamp": res.get("log_timestamp", ""),
                    }
                    cand_review = exam_critic(kept_pool + [new_rec])
                    if cand_review["tong_so_cau"] > len(kept_pool):
                        kept_pool = list(cand_review["items"])
                        reviewed = cand_review
                        backfill_notes.append(
                            f"Bù vét ô cuối ({bh} - {loai}): đạt chuẩn is_pass=True -> {reviewed['tong_so_cau']}/{target_count} câu ({reviewed['tong_diem']}đ)."
                        )
                        break

    # TUYỆT ĐỐI KHÔNG khôi phục câu rớt chuẩn (is_pass == False) hoặc câu bị loại do trùng lặp toàn đề
    if reviewed["tong_so_cau"] < target_count:
        passed_removed = [
            it for it in reviewed.get("removed_items", [])
            if bool((it.get("validation_result") or {}).get("is_pass", False))
            and "Trùng" not in str(it.get("ly_do_loai", ""))
            and str(it.get("blueprint_id", "")).strip() not in used_in_current_exam
            and _get_item_stem_hash(it) not in used_question_hashes
        ]
        if passed_removed:
            deficit = target_count - reviewed["tong_so_cau"]
            restored = passed_removed[:deficit]
            reviewed["items"].extend(restored)
            for it in restored:
                b = str(it.get("blueprint_id", "")).strip()
                if b:
                    used_in_current_exam.add(b)
                used_question_hashes.add(_get_item_stem_hash(it))
            reviewed["removed_items"] = [it for it in reviewed.get("removed_items", []) if it not in restored]
            breakdown, tong_diem = _recompute_exam_summary(reviewed["items"], _get_point_map())
            reviewed["bang_diem_chi_tiet"] = breakdown
            reviewed["tong_so_cau"] = len(reviewed["items"])
            reviewed["tong_diem"] = tong_diem
            backfill_notes.append(
                f"Khôi phục {len(restored)} câu đạt chuẩn is_pass=True để tối ưu số lượng ({reviewed['tong_so_cau']}/{target_count} câu, {tong_diem}đ)."
            )
        if reviewed["tong_so_cau"] < target_count:
            backfill_notes.append(
                f"Giữ nguyên kỷ luật chất lượng: từ chối đưa {target_count - reviewed['tong_so_cau']} câu chưa đạt chuẩn (is_pass=False) vào đề thi."
            )

    phase2_sec = round(time.time() - t_p2, 2)
    if backfill_notes:
        reviewed["critic_notes"] = list(reviewed.get("critic_notes", [])) + backfill_notes
    reviewed["backfill_rounds_used"] = backfill_rounds_used
    reviewed["total_removed_history"] = all_removed_history
    reviewed["target_so_cau"] = target_count
    reviewed["phase1_retrieve_sec"] = phase1_sec
    reviewed["phase2_generate_sec"] = phase2_sec
    reviewed["tong_thoi_gian_sec"] = round(time.time() - t0, 2)
    reviewed["thang_diem_ap_dung"] = "Cấu trúc đề thi 2025-2026 (MCQ 0.25đ | Đ/S bậc thang 0.1-0.25-0.5-1.0đ | TLN 0.5đ | Code 1.0đ)"

    # Xáo trộn ngẫu nhiên thứ tự các câu hỏi bên trong từng phần (Phần I, II, III, IV)
    final_items = reviewed.get("items", [])
    if final_items:
        mcq_list = [x for x in final_items if x.get("loai_cau_hoi") == "MCQ"]
        tf_list = [x for x in final_items if x.get("loai_cau_hoi") == "TRUE_FALSE"]
        sa_list = [x for x in final_items if x.get("loai_cau_hoi") == "SHORT_ANSWER"]
        ec_list = [x for x in final_items if x.get("loai_cau_hoi") == "ESSAY_CODE"]

        random.shuffle(mcq_list)
        random.shuffle(tf_list)
        random.shuffle(sa_list)
        random.shuffle(ec_list)

        shuffled_all = mcq_list + tf_list + sa_list + ec_list
        point_map = _get_point_map()
        for new_idx, it in enumerate(shuffled_all, 1):
            it["so_thu_tu"] = new_idx
            it["diem_toi_da"] = point_map.get(it.get("loai_cau_hoi", ""), 0.25)
        reviewed["items"] = shuffled_all

    final_accepted_bp = [
        str(x.get("blueprint_id", "")).strip()
        for x in reviewed.get("items", [])
        if str(x.get("blueprint_id", "")).strip()
    ]
    if final_accepted_bp:
        _save_recent_blueprints(final_accepted_bp)
        print(f"[CROSS-EXAM] Đã lưu {len(final_accepted_bp)} blueprint_id vào data/recent_blueprints.json để chống lặp cho các đề tiếp theo.", flush=True)

    print(
        f"✅ HOÀN TẤT GHÉP ĐỀ: {reviewed['tong_so_cau']}/{target_count} câu đạt | "
        f"Backfill: {backfill_rounds_used} vòng | "
        f"Tổng điểm: {reviewed['tong_diem']}đ | "
        f"Thời gian: {reviewed['tong_thoi_gian_sec']}s (Pha 1: {phase1_sec}s | Pha 2: {phase2_sec}s)",
        flush=True,
    )
    return reviewed


# ==============================================================================
# XUẤT ĐỀ THI WORD (.DOCX) - 100% ĐEN TRẮNG, 2 PHẦN TÁCH TRANG (ĐỀ + ĐÁP ÁN & SGK)
# ==============================================================================

def _set_run_font(run, font_name: str = "Times New Roman", size_pt: float = 12, bold: bool = False, italic: bool = False):
    """Định dạng font chuẩn văn bản in ấn 100% đen trắng (RGBColor(0, 0, 0))."""
    run.font.name = font_name
    run.font.size = Pt(size_pt)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = RGBColor(0, 0, 0)


def _add_styled_paragraph(doc: DocxDocument, text: str = "", size_pt: float = 12, bold: bool = False, italic: bool = False, align=None, space_after: float = 4, font_name: str = "Times New Roman"):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(space_after)
    if text:
        run = p.add_run(text)
        _set_run_font(run, font_name=font_name, size_pt=size_pt, bold=bold, italic=italic)
    return p


_VIET_PROSE_CUES = (
    "là gì",
    "như thế nào",
    "bao nhiêu",
    "viết chương trình",
    "tính tổng",
    "trong môi trường",
    "sau khi thực hiện",
    "cho biết",
    "hãy chọn",
    "phương án nào",
    "câu lệnh nào",
    "đoạn chương trình",
    "xét các phát biểu",
    "kết quả in ra",
    "giá trị in ra",
)

_PY_START_REGEX = re.compile(
    r"^(?:def\s+|for\s+|while\s+|if\s+|elif\s+|else\s*:|print\s*\(|return\b|pass\b|break\b|continue\b|global\b|import\s+|from\s+|>>>|#)"
)
_PY_PURE_ASSIGN_REGEX = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*|\s*\[\s*[^\]]+\s*\])*\s*(?:=|\+=|-=|\*=|//=|/=|%=)\s*[^=].*$"
)
_PY_PURE_CALL_REGEX = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?\s*\([^)]*\)\s*$"
)


def _is_docx_python_line(line: str, prev_was_code: bool = False) -> bool:
    """
    Phân biệt chuẩn xác Dòng lệnh Python (Consolas 10.5pt) vs Văn bản tiếng Việt (Times New Roman 12pt):
      - CHỈ trả True khi dòng BẮT ĐẦU bằng từ khóa/cú pháp Python (`def `, `for `, `while `, `if `, `elif `,
        `else:`, `print(`, `return `, `>>>`, `#`, khoảng trắng thụt lề), HOẶC là lệnh gán thuần túy
        (`^[a-zA-Z_]\\w*\\s*=`), HOẶC là lời gọi hàm/phương thức thuần túy;
      - Loại trừ mọi câu văn tiếng Việt có dấu / câu hỏi (`là gì`, `như thế nào`, `bao nhiêu`,
        `Viết chương trình`, `Tính tổng`, `Trong môi trường`, kết thúc bằng `?`).
    """
    raw = line.rstrip("\r")
    s = raw.strip()
    if not s:
        return False

    # Dòng bắt đầu bằng comment `#` hoặc prompt `>>>` luôn là code
    if s.startswith(("#", ">>>")):
        return True

    s_low = s.lower()
    # Loại trừ tuyệt đối câu văn / câu hỏi tiếng Việt (trừ trường hợp bắt đầu tường minh bằng print(...))
    if not re.match(r"^print\s*\(", s):
        if s.endswith("?") or any(cue in s_low for cue in _VIET_PROSE_CUES):
            return False

    # 1. Bắt đầu bằng từ khóa / cú pháp Python rõ ràng
    if _PY_START_REGEX.match(s):
        return True

    # 2. Lệnh gán thuần túy (VD: a = 5, ds[0] = 9, tong += k)
    if _PY_PURE_ASSIGN_REGEX.match(s):
        return True

    # 3. Lời gọi hàm / phương thức thuần túy (VD: ds.append(5), tinh_tong(2, 3))
    if _PY_PURE_CALL_REGEX.match(s):
        return True

    # 4. Dòng có thụt lề đầu dòng (4 dấu cách / tab) nằm trong khối mã Python
    if raw.startswith((" ", "\t")):
        # Chỉ nhận là code thụt lề nếu không chứa câu văn tiếng Việt dài có dấu
        if not re.search(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", s_low):
            return True
        if prev_was_code:
            return True

    return False


def _add_code_line_docx(doc: DocxDocument, line: str) -> None:
    """In 1 dòng lệnh Python thành paragraph riêng bằng font Consolas 10.5pt, giữ nguyên thụt lề đầu dòng."""
    expanded = line.replace("\t", "    ").rstrip()
    leading_spaces = len(expanded) - len(expanded.lstrip(" "))
    # Thay khoảng trắng đầu dòng bằng non-breaking space (\u00a0) để Word không bao giờ nén mất thụt lề
    preserved_text = ("\u00a0" * leading_spaces) + expanded.lstrip(" ")

    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.35)
    p.paragraph_format.space_before = Pt(0.5)
    p.paragraph_format.space_after = Pt(1.5)
    run = p.add_run(preserved_text)
    _set_run_font(run, font_name="Consolas", size_pt=10.5)


def _add_code_block_docx(doc: DocxDocument, code_text: str) -> None:
    """Tách khối mã Python theo '\\n' và in từng dòng riêng biệt bằng font Consolas 10.5pt, giữ nguyên thụt lề."""
    cleaned = str(code_text or "").replace("```python", "").replace("```", "").replace("\r\n", "\n")
    # Hỗ trợ chuỗi bị escape '\\n' nếu có
    if "\\n" in cleaned and "\n" not in cleaned:
        cleaned = cleaned.replace("\\n", "\n")
    for line in cleaned.split("\n"):
        if line.strip():
            _add_code_line_docx(doc, line)


def _add_mixed_content_docx(doc: DocxDocument, text: str, prefix_bold: str = "") -> None:
    """
    Xuất nội dung hỗn hợp (văn bản tiếng Việt + đoạn mã Python) ra Word theo từng dòng ('\\n'):
      - Dòng văn bản thường: Times New Roman 12pt.
      - Dòng mã Python (chứa =, if, else:, for, while, def, print(, hoặc thụt lề): Consolas 10.5pt, giữ thụt lề.
    """
    cleaned = str(text or "").replace("```python", "").replace("```", "").replace("\r\n", "\n").strip()
    if "\\n" in cleaned and "\n" not in cleaned:
        cleaned = cleaned.replace("\\n", "\n")

    lines = cleaned.split("\n")
    prefix_used = False
    prev_was_code = False

    for raw_line in lines:
        if not raw_line.strip():
            continue
        is_code = _is_docx_python_line(raw_line, prev_was_code=prev_was_code)
        if is_code:
            if prefix_bold and not prefix_used:
                p_hdr = doc.add_paragraph()
                p_hdr.paragraph_format.space_after = Pt(2)
                _set_run_font(p_hdr.add_run(prefix_bold.strip()), size_pt=12, bold=True)
                prefix_used = True
            _add_code_line_docx(doc, raw_line)
            prev_was_code = True
        else:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(2.5)
            if prefix_bold and not prefix_used:
                _set_run_font(p.add_run(prefix_bold), size_pt=12, bold=True)
                prefix_used = True
            _set_run_font(p.add_run(raw_line.strip()), size_pt=12)
            prev_was_code = False

    if prefix_bold and not prefix_used:
        p = doc.add_paragraph()
        _set_run_font(p.add_run(prefix_bold.strip()), size_pt=12, bold=True)


def export_exam_to_docx(
    exam_pkg: dict[str, Any],
    output_path: str | None = None,
    ten_truong: str = "TRƯỜNG THPT (CHƯƠNG TRÌNH GDPT 2018)",
    ten_ky_thi: str = "ĐỀ KIỂM TRA CHỦ ĐỀ F",
    thoi_gian: str = "45 phút (không kể thời gian phát đề)",
    include_answers: bool = True,
) -> bytes:
    """
    Xuất đề thi chuẩn định dạng 2025–2026 ra file Word (.docx) 100% trắng đen:
      - PHẦN 1: Đề kiểm tra dành cho học sinh (PHẦN I: MCQ, PHẦN II: Đúng/Sai, PHẦN III: Trả lời ngắn, PHẦN IV: Tự luận Code).
      - PHẦN 2 (khi include_answers=True, sau ngắt trang): Đáp án chuẩn, Biểu điểm chi tiết 2025–2026 & Trích dẫn SGK.
    Trả về bytes (.docx) để tải trực tiếp trên Streamlit, đồng thời ghi ra output_path nếu được truyền.
    """
    doc = DocxDocument()

    # Căn lề trang A4 gọn gàng
    for sec in doc.sections:
        sec.top_margin = Inches(0.75)
        sec.bottom_margin = Inches(0.75)
        sec.left_margin = Inches(0.85)
        sec.right_margin = Inches(0.75)

    items = exam_pkg.get("items", [])
    tong_diem = exam_pkg.get("tong_diem", 0.0)
    bang_diem = exam_pkg.get("bang_diem_chi_tiet", {})

    # ------------------------------------------------------------------
    # PHẦN 1: ĐỀ KIỂM TRA HỌC SINH (CHUẨN FORM 2025–2026)
    # ------------------------------------------------------------------
    hdr_table = doc.add_table(rows=1, cols=2)
    hdr_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    c_left, c_right = hdr_table.rows[0].cells

    p_l1 = c_left.paragraphs[0]
    p_l1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_run_font(p_l1.add_run("SỞ GIÁO DỤC VÀ ĐÀO TẠO\n"), size_pt=11)
    _set_run_font(p_l1.add_run(ten_truong), size_pt=11, bold=True)

    p_r1 = c_right.paragraphs[0]
    p_r1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _set_run_font(p_r1.add_run(f"{ten_ky_thi}\n"), size_pt=11, bold=True)
    _set_run_font(p_r1.add_run(f"Năm học 2025 – 2026 | Thời gian: {thoi_gian}"), size_pt=10.5, italic=True)

    _add_styled_paragraph(
        doc,
        "Họ và tên học sinh: ........................................................................   Lớp: 10........",
        size_pt=11.5,
        space_after=8,
    )

    mcq_items = [x for x in items if x.get("loai_cau_hoi") == "MCQ"]
    tf_items = [x for x in items if x.get("loai_cau_hoi") == "TRUE_FALSE"]
    sa_items = [x for x in items if x.get("loai_cau_hoi") == "SHORT_ANSWER"]
    ec_items = [x for x in items if x.get("loai_cau_hoi") == "ESSAY_CODE"]

    # PHẦN I: MCQ
    if mcq_items:
        _add_styled_paragraph(
            doc,
            f"PHẦN I. Câu trắc nghiệm nhiều phương án lựa chọn ({len(mcq_items)} câu – 0.25 điểm/câu). "
            "Thí sinh chỉ chọn một phương án đúng nhất.",
            size_pt=12,
            bold=True,
            space_after=6,
        )
        for idx, item in enumerate(mcq_items, 1):
            q = item.get("question_json", {})
            _add_mixed_content_docx(doc, q.get("cau_hoi", ""), prefix_bold=f"Câu {idx}. ")
            for opt in ("A", "B", "C", "D"):
                opt_clean = str(q.get(opt, "")).replace("```python", "").replace("```", "").replace("\r\n", "\n").strip()
                if "\\n" in opt_clean and "\n" not in opt_clean:
                    opt_clean = opt_clean.replace("\\n", "\n")
                if "\n" in opt_clean:
                    p_prefix = doc.add_paragraph()
                    p_prefix.paragraph_format.left_indent = Inches(0.25)
                    p_prefix.paragraph_format.space_before = Pt(0)
                    p_prefix.paragraph_format.space_after = Pt(1.0)
                    _set_run_font(p_prefix.add_run(f"{opt}."), size_pt=11.5, bold=True)
                    prev_code = False
                    for raw_l in opt_clean.split("\n"):
                        if not raw_l.strip():
                            continue
                        if _is_docx_python_line(raw_l, prev_was_code=prev_code):
                            _add_code_line_docx(doc, raw_l)
                            prev_code = True
                        else:
                            pl = doc.add_paragraph()
                            pl.paragraph_format.left_indent = Inches(0.4)
                            pl.paragraph_format.space_before = Pt(0)
                            pl.paragraph_format.space_after = Pt(1.0)
                            _set_run_font(pl.add_run(raw_l.strip()), size_pt=11.5)
                            prev_code = False
                else:
                    po = doc.add_paragraph()
                    po.paragraph_format.left_indent = Inches(0.25)
                    po.paragraph_format.space_before = Pt(0)
                    po.paragraph_format.space_after = Pt(1.5)
                    _set_run_font(po.add_run(f"{opt}. "), size_pt=11.5, bold=True)
                    is_single_code = _is_docx_python_line(opt_clean)
                    _set_run_font(
                        po.add_run(opt_clean),
                        font_name="Consolas" if is_single_code else "Times New Roman",
                        size_pt=10.5 if is_single_code else 11.5,
                    )

    # PHẦN II: ĐÚNG / SAI
    if tf_items:
        _add_styled_paragraph(
            doc,
            f"\nPHẦN II. Câu trắc nghiệm Đúng/Sai ({len(tf_items)} câu – tối đa 1.0 điểm/câu; chấm bậc thang: "
            "đúng 1 ý 0.1đ, 2 ý 0.25đ, 3 ý 0.5đ, 4 ý 1.0đ).",
            size_pt=12,
            bold=True,
            space_after=6,
        )
        for idx, item in enumerate(tf_items, 1):
            q = item.get("question_json", {})
            _add_mixed_content_docx(doc, q.get("cau_hoi_chung", ""), prefix_bold=f"Câu {idx}. ")
            for letter in ("a", "b", "c", "d"):
                obj = q.get(letter) or {}
                md = obj.get("menh_de", "") if isinstance(obj, dict) else str(obj)
                pm = doc.add_paragraph()
                pm.paragraph_format.left_indent = Inches(0.25)
                pm.paragraph_format.space_after = Pt(1.5)
                _set_run_font(pm.add_run(f"{letter}) "), size_pt=11.5, bold=True)
                _set_run_font(pm.add_run(str(md)), size_pt=11.5)

    # PHẦN III: TRẢ LỜI NGẮN
    if sa_items:
        _add_styled_paragraph(
            doc,
            f"\nPHẦN III. Câu trắc nghiệm Trả lời ngắn ({len(sa_items)} câu – 0.5 điểm/câu).",
            size_pt=12,
            bold=True,
            space_after=6,
        )
        for idx, item in enumerate(sa_items, 1):
            q = item.get("question_json", {})
            _add_mixed_content_docx(doc, q.get("cau_hoi", ""), prefix_bold=f"Câu {idx}. ")
            _add_styled_paragraph(doc, "Đáp án: ........................................", size_pt=11.5, italic=True, space_after=4)

    # PHẦN IV: TỰ LUẬN LẬP TRÌNH PYTHON
    if ec_items:
        _add_styled_paragraph(
            doc,
            f"\nPHẦN IV. Tự luận lập trình Python ({len(ec_items)} câu – 1.0 điểm/câu).",
            size_pt=12,
            bold=True,
            space_after=6,
        )
        for idx, item in enumerate(ec_items, 1):
            q = item.get("question_json", {})
            combined_essay = "\n".join(
                part for part in (str(q.get("tinh_huong", "")).strip(), str(q.get("yeu_cau_hoc_sinh", "")).strip()) if part
            )
            _add_mixed_content_docx(doc, combined_essay, prefix_bold=f"Câu {idx}. ")

    _add_styled_paragraph(doc, "\n--- HẾT ---", size_pt=12, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)

    # ------------------------------------------------------------------
    # NGẮT TRANG -> PHẦN 2: ĐÁP ÁN, BIỂU ĐIỂM CHI TIẾT & TRÍCH DẪN SGK
    # ------------------------------------------------------------------
    if include_answers:
        doc.add_page_break()

        _add_styled_paragraph(
            doc,
            "HƯỚNG DẪN CHẤM, BIỂU ĐIỂM CHI TIẾT & BẰNG CHỨNG SGK",
            size_pt=13.5,
            bold=True,
            align=WD_ALIGN_PARAGRAPH.CENTER,
            space_after=4,
        )
        _add_styled_paragraph(
            doc,
            f"Phạm vi: Chủ đề F Tin học 10 (SGK Kết nối tri thức) | Tổng số câu: {len(items)} | Tổng điểm chuẩn 2025–2026: {tong_diem} điểm",
            size_pt=11,
            italic=True,
            align=WD_ALIGN_PARAGRAPH.CENTER,
            space_after=8,
        )

        # Bảng tổng hợp biểu điểm
        if bang_diem:
            tbl = doc.add_table(rows=1, cols=4)
            tbl.style = "Table Grid"
            tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
            headers = ["Dạng câu hỏi", "Số câu", "Điểm / câu", "Tổng điểm phần"]
            for i, h in enumerate(headers):
                r = tbl.rows[0].cells[i].paragraphs[0].add_run(h)
                _set_run_font(r, size_pt=11, bold=True)
            for loai_k, info in bang_diem.items():
                row_cells = tbl.add_row().cells
                vals = [loai_k, str(info["so_cau"]), f"{info['diem_moi_cau']}đ", f"{info['tong_diem_phan']}đ"]
                for i, v in enumerate(vals):
                    _set_run_font(row_cells[i].paragraphs[0].add_run(v), size_pt=11)
            _add_styled_paragraph(doc, "", space_after=4)

        # Chi tiết đáp án từng phần
        def _add_answer_header(title: str):
            _add_styled_paragraph(doc, title, size_pt=12, bold=True, space_after=4)

        if mcq_items:
            _add_answer_header("I. ĐÁP ÁN PHẦN I – TRẮC NGHIỆM NHIỀU LỰA CHỌN (0.25đ/câu)")
            for idx, item in enumerate(mcq_items, 1):
                q = item.get("question_json", {})
                ans = str(q.get("dap_an", "A")).strip().upper()
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(2)
                _set_run_font(p.add_run(f"Câu {idx} ({item.get('bai_hoc', '')} – {item.get('muc_do', '')}): Đáp án {ans} (0.25đ). "), size_pt=11.5, bold=True)
                _set_run_font(p.add_run(f"Giải thích: {q.get('giai_thich', '')}"), size_pt=11.5)
                _add_styled_paragraph(doc, f"   Bằng chứng SGK: \"{q.get('trich_dan_sgk', '')}\"", size_pt=10.5, italic=True, space_after=4)

        if tf_items:
            _add_answer_header("II. ĐÁP ÁN PHẦN II – TRẮC NGHIỆM ĐÚNG/SAI (Bậc thang: 1ý 0.1đ | 2ý 0.25đ | 3ý 0.5đ | 4ý 1.0đ)")
            for idx, item in enumerate(tf_items, 1):
                q = item.get("question_json", {})
                _add_styled_paragraph(doc, f"Câu {idx} ({item.get('bai_hoc', '')} – {item.get('muc_do', '')}):", size_pt=11.5, bold=True, space_after=2)
                for letter in ("a", "b", "c", "d"):
                    obj = q.get(letter) or {}
                    da = obj.get("dap_an", "") if isinstance(obj, dict) else ""
                    gt = obj.get("giai_thich", "") if isinstance(obj, dict) else ""
                    pm = doc.add_paragraph()
                    pm.paragraph_format.left_indent = Inches(0.25)
                    pm.paragraph_format.space_after = Pt(1.5)
                    _set_run_font(pm.add_run(f"{letter}) {da}: "), size_pt=11, bold=True)
                    _set_run_font(pm.add_run(str(gt)), size_pt=11)
                _add_styled_paragraph(doc, f"   Bằng chứng SGK: \"{q.get('trich_dan_sgk', '')}\"", size_pt=10.5, italic=True, space_after=4)

        if sa_items:
            _add_answer_header("III. ĐÁP ÁN PHẦN III – TRẢ LỜI NGẮN (0.5đ/câu)")
            for idx, item in enumerate(sa_items, 1):
                q = item.get("question_json", {})
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(2)
                _set_run_font(p.add_run(f"Câu {idx} ({item.get('bai_hoc', '')} – {item.get('muc_do', '')}): Đáp án = {q.get('dap_an_ngan', '')} (0.5đ). "), size_pt=11.5, bold=True)
                _set_run_font(p.add_run(f"Giải thích: {q.get('giai_thich', '')}"), size_pt=11.5)
                _add_styled_paragraph(doc, f"   Bằng chứng SGK: \"{q.get('trich_dan_sgk', '')}\"", size_pt=10.5, italic=True, space_after=4)

        if ec_items:
            _add_answer_header("IV. ĐÁP ÁN & RUBRIC PHẦN IV – TỰ LUẬN LẬP TRÌNH PYTHON (1.0đ/câu)")
            for idx, item in enumerate(ec_items, 1):
                q = item.get("question_json", {})
                _add_styled_paragraph(doc, f"Câu {idx} ({item.get('bai_hoc', '')} – {item.get('muc_do', '')}) – Mã Python mẫu:", size_pt=11.5, bold=True, space_after=2)
                raw_mau = q.get("dap_an_mau", "")
                if isinstance(raw_mau, list):
                    raw_mau = "\n".join(str(x) for x in raw_mau)
                code_mau = str(raw_mau).replace("```python", "").replace("```", "").strip()
                if code_mau:
                    _add_code_block_docx(doc, code_mau)
                for tc in q.get("tieu_chi_cham_diem", []):
                    _add_styled_paragraph(doc, f"   - {tc}", size_pt=11, space_after=1.5)
                _add_styled_paragraph(doc, f"   Bằng chứng SGK: \"{q.get('trich_dan_sgk', '')}\"", size_pt=10.5, italic=True, space_after=4)

    buf = io.BytesIO()
    doc.save(buf)
    docx_bytes = buf.getvalue()

    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(docx_bytes)

    return docx_bytes


if __name__ == "__main__":
    # Kiểm thử thực tế 2 Pha (Tiền truy xuất + Giải phóng VRAM -> Sinh tuần tự 4 câu đủ 4 dạng)
    sample_4_specs = [
        {"bai_hoc": "Bài 19", "loai_cau_hoi": "MCQ", "muc_do": "TH"},
        {"bai_hoc": "Bài 20", "loai_cau_hoi": "TRUE_FALSE", "muc_do": "TH"},
        {"bai_hoc": "Bài 21", "loai_cau_hoi": "SHORT_ANSWER", "muc_do": "TH"},
        {"bai_hoc": "Bài 22", "loai_cau_hoi": "ESSAY_CODE", "muc_do": "VD"},
    ]
    report = assemble_exam(specs=sample_4_specs, enable_logging=False)
    summary = {
        "tong_so_cau": report["tong_so_cau"],
        "target_so_cau": report["target_so_cau"],
        "tong_diem": report["tong_diem"],
        "phase1_retrieve_sec": report.get("phase1_retrieve_sec", 0.0),
        "phase2_generate_sec": report.get("phase2_generate_sec", 0.0),
        "tong_thoi_gian_sec": report["tong_thoi_gian_sec"],
        "tb_giay_moi_cau": round(report["tong_thoi_gian_sec"] / max(report["tong_so_cau"], 1), 2),
        "backfill_rounds_used": report.get("backfill_rounds_used", 0),
        "chi_tiet_tung_cau": [
            {
                "stt": it.get("so_thu_tu"),
                "bai_hoc": it.get("bai_hoc"),
                "loai": it.get("loai_cau_hoi"),
                "xep_loai": (it.get("validation_result") or {}).get("xep_loai"),
                "diem_fuzzy": (it.get("validation_result") or {}).get("diem_chat_luong"),
                "sandbox": (it.get("validation_result") or {}).get("sandbox_verified"),
                "retries": it.get("retry_count"),
                "latency_sec": it.get("latency_sec"),
            }
            for it in report.get("items", [])
        ],
        "critic_notes": report["critic_notes"],
    }
    print("\n=== TỔNG KẾT KIỂM THỬ 4 CÂU ĐỦ 4 DẠNG ===", flush=True)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
