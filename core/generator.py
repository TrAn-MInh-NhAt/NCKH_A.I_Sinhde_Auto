import os
import re
import copy
import json
import time
import requests
from typing import TypedDict

os.environ["ANONYMIZED_TELEMETRY"] = "False"

from langgraph.graph import StateGraph, END

from core.retriever import retrieve_evidence_package, estimate_tokens
from core.symbolic_engine import build_verified_skeleton
from core.validator import (
    validate_question,
    _extract_executable_python_snippets,
    _run_sandbox_verification,
    _NON_OUTPUT_QUESTION_CUES,
    _OUTPUT_QUESTION_CUES,
    _compute_sgk_citation_overlap,
    _extract_verbatim_sgk_sentences,
    _normalize_code_mau,
)
from experiments.logger import log_generation_event

# ==============================================================================
# CẤU HÌNH OLLAMA TRỰC TIẾP (CHẠY TUẦN TỰ, CÓ TIMEOUT & NUM_PREDICT THÍCH ỨNG 4GB VRAM)
# ==============================================================================
OLLAMA_BASE_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
MODEL_NAME = "llama3.2_tinhoc10"
MAX_RETRIES = 2
MAX_PROMPT_TOKENS = 1200
PROMPT_TARGET = 1100
DEFAULT_NUM_PREDICT = 520
ADAPTIVE_NUM_PREDICT = {
    "MCQ": 380,
    "SHORT_ANSWER": 360,
    "TRUE_FALSE": 620,
    "ESSAY_CODE": 520,
}
NEURAL_POLISH_NUM_PREDICT = {
    "MCQ": 130,
    "SHORT_ANSWER": 120,
    "TRUE_FALSE": 220,
    "ESSAY_CODE": 140,
}
USE_NEURO_SYMBOLIC = True
DEFAULT_REQUEST_TIMEOUT = 120


def call_ollama_json(
    prompt_text: str,
    temperature: float = 0.15,
    num_predict: int = DEFAULT_NUM_PREDICT,
    timeout_sec: int = DEFAULT_REQUEST_TIMEOUT,
    num_ctx: int = 4096,
) -> str:
    """
    Gọi trực tiếp Ollama /api/chat cục bộ với format='json', giới hạn num_predict, stop tokens & timeout=120s
    để ngăn mô hình 3B sinh lan man và giữ ổn định 4GB VRAM trên RTX 3050.
    """
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt_text}],
        "format": "json",
        "stream": False,
        "keep_alive": "15m",
        "options": {
            "num_ctx": num_ctx,
            "temperature": temperature,
            "repeat_penalty": 1.15,
            "num_predict": num_predict,
            "stop": ["\n\n\n", "```"],
        },
    }
    last_err = None
    for http_try in range(2):
        try:
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json=payload,
                timeout=timeout_sec,
            )
            if resp.status_code >= 500 and http_try == 0:
                time.sleep(1.0)
                continue
            resp.raise_for_status()
            data = resp.json()
            return str(data.get("message", {}).get("content", "")).strip()
        except requests.RequestException as e:
            last_err = e
            if http_try == 0:
                time.sleep(1.0)
                continue
            raise
    if last_err:
        raise last_err
    return ""


class AgentState(TypedDict):
    bai_hoc: str
    chu_de_chi_tiet: str
    loai_cau_hoi: str
    muc_do: str
    use_neuro_symbolic: bool
    avoid_snippets: list[str]
    used_blueprint_ids: list[str]
    recent_blueprint_ids: list[str]
    blueprint_id: str
    symbolic_skeleton: dict
    evidence_package: dict
    prompt_tokens: int
    question_json: dict
    best_question_json: dict
    best_validation: dict
    best_score: float
    validation_result: dict
    feedback: str
    is_pass: bool
    retry_count: int
    latency_sec: float
    log_timestamp: str


# ==============================================================================
# BỘ PHÂN TÍCH JSON AN TOÀN CHO LLM 3B
# ==============================================================================

def _parse_llm_json(raw_text: str) -> dict:
    """Trích xuất và giải mã JSON an toàn kể cả khi LLM sinh markdown fence hoặc ký tự xuống dòng thô."""
    if not raw_text:
        return {}
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    candidate = cleaned[start: end + 1]

    for attempt in (
        lambda s: json.loads(s),
        lambda s: json.loads(s, strict=False),
        lambda s: json.loads(re.sub(r",\s*([}\]])", r"\1", s), strict=False),
    ):
        try:
            obj = attempt(candidate)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return {}


def _build_json_schema_hint(loai: str) -> str:
    if loai == "MCQ":
        return (
            '{\n'
            '  "trich_dan_sgk": "Chép NGUYÊN VĂN 1 câu từ mục BẰNG CHỨNG SGK ở trên",\n'
            '  "cau_hoi": "Câu hỏi Python cụ thể (có thể kèm đoạn mã 3-5 dòng)",\n'
            '  "A": "Nội dung cụ thể A",\n'
            '  "B": "Nội dung cụ thể B",\n'
            '  "C": "Nội dung cụ thể C",\n'
            '  "D": "Nội dung cụ thể D",\n'
            '  "dap_an": "B",\n'
            '  "giai_thich": "Giải thích cụ thể vì sao đáp án đúng theo cú pháp Python"\n'
            '}'
        )
    if loai == "TRUE_FALSE":
        return (
            '{\n'
            '  "trich_dan_sgk": "Chép NGUYÊN VĂN 1 câu từ mục BẰNG CHỨNG SGK ở trên",\n'
            '  "cau_hoi_chung": "Cho đoạn chương trình Python sau:\\n...\\nXét các phát biểu sau:",\n'
            '  "a": {"menh_de": "Nhận định cụ thể a", "dap_an": "Đúng", "giai_thich": "Giải thích cụ thể a"},\n'
            '  "b": {"menh_de": "Nhận định cụ thể b", "dap_an": "Sai", "giai_thich": "Giải thích cụ thể b"},\n'
            '  "c": {"menh_de": "Nhận định cụ thể c", "dap_an": "Đúng", "giai_thich": "Giải thích cụ thể c"},\n'
            '  "d": {"menh_de": "Nhận định cụ thể d", "dap_an": "Sai", "giai_thich": "Giải thích cụ thể d"}\n'
            '}'
        )
    if loai == "SHORT_ANSWER":
        return (
            '{\n'
            '  "trich_dan_sgk": "Chép NGUYÊN VĂN 1 câu từ mục BẰNG CHỨNG SGK ở trên",\n'
            '  "cau_hoi": "Cho đoạn chương trình Python sau:\\n...\\nGiá trị in ra màn hình là bao nhiêu?",\n'
            '  "dap_an_ngan": "1 giá trị số hoặc xâu ngắn duy nhất",\n'
            '  "giai_thich": "Giải thích từng bước chạy đoạn mã"\n'
            '}'
        )
    return (
        '{\n'
        '  "trich_dan_sgk": "Chép NGUYÊN VĂN 1 câu từ mục BẰNG CHỨNG SGK ở trên",\n'
        '  "tinh_huong": "Mô tả bài toán kèm dữ liệu cụ thể (VD: A = [3, 8, 2, 5])",\n'
        '  "yeu_cau_hoc_sinh": "Yêu cầu viết chương trình Python lớp 10",\n'
        '  "dap_an_mau": "Mã Python 3 thuần lớp 10 chạy được không lỗi",\n'
        '  "tieu_chi_cham_diem": ["Tiêu chí 1 (0.3đ)", "Tiêu chí 2 (0.4đ)", "Tiêu chí 3 (0.3đ)"]\n'
        '}'
    )


def _format_one_shot_block(
    exam_template: dict,
    bai_hoc: str = "",
    sgk_chunks: list[dict] | None = None,
    loai: str = "",
) -> str:
    """
    Định dạng ví dụ 1-shot chuẩn JSON (đặc biệt giúp LLM 3B giữ đúng \\n và thụt lề 4 dấu cách
    cho TRUE_FALSE / ESSAY_CODE), đồng thời làm sạch mọi hằng mẫu cũ và dùng mẫu có `def`
    riêng cho nhóm Bài 26–28 để đạt ngay lượt đầu.
    """
    one_shot = exam_template.get("vi_du_1shot")
    if not isinstance(one_shot, dict) or not one_shot:
        return ""
    sample_cite = one_shot.get("trich_dan_sgk", "")
    if sgk_chunks:
        first_chunk = str(sgk_chunks[0].get("content", "")).strip()
        for sent in re.split(r"(?<=[.!?])\s+|\n", first_chunk):
            sent_c = sent.strip()
            if 40 <= len(sent_c) <= 160:
                sample_cite = sent_c
                break

    # Với Bài 19 TRUE_FALSE, cung cấp mẫu cấu trúc có if/else thụt lề 4 dấu cách chuẩn xác
    if bai_hoc == "Bài 19" and loai == "TRUE_FALSE":
        ordered_shot = {
            "trich_dan_sgk": sample_cite,
            "cau_hoi_chung": "Cho đoạn chương trình Python sau:\na = 12\nif a >= 10:\n    print('Dat')\nelse:\n    print('Chua')\nXét các phát biểu sau:",
            "a": {"menh_de": "Biểu thức điều kiện a >= 10 nhận giá trị True.", "dap_an": "Đúng", "giai_thich": "Vì a = 12 lớn hơn 10 nên a >= 10 cho giá trị True."},
            "b": {"menh_de": "Chương trình thực hiện nhánh else và in ra 'Chua'.", "dap_an": "Sai", "giai_thich": "Điều kiện đúng nên chỉ thực hiện nhánh if, bỏ qua nhánh else."},
            "c": {"menh_de": "Kết quả in ra màn hình là 'Dat'.", "dap_an": "Đúng", "giai_thich": "Nhánh if được thực hiện nên lệnh print('Dat') chạy."},
            "d": {"menh_de": "Câu lệnh if trong Python không cần dấu hai chấm (:).", "dap_an": "Sai", "giai_thich": "Cú pháp câu lệnh if bắt buộc có dấu hai chấm (:) cuối dòng điều kiện."},
        }
    # Với nhóm Bài 26-28 (Hàm & Phạm vi biến), cung cấp mẫu cấu trúc có `def` đúng trọng tâm bài học
    elif bai_hoc in ("Bài 26", "Bài 27", "Bài 28") and loai == "TRUE_FALSE":
        ordered_shot = {
            "trich_dan_sgk": sample_cite,
            "cau_hoi_chung": "Cho đoạn chương trình Python sau:\ndef nhan_doi(p):\n    return p * 2\nprint(nhan_doi(6))\nXét các phát biểu sau:",
            "a": {"menh_de": "Hàm được định nghĩa bằng từ khóa def với tên nhan_doi.", "dap_an": "Đúng", "giai_thich": "Dòng đầu dùng từ khóa def để định nghĩa hàm nhan_doi."},
            "b": {"menh_de": "Hàm nhan_doi không có tham số đầu vào.", "dap_an": "Sai", "giai_thich": "Hàm có 1 tham số hình thức là p."},
            "c": {"menh_de": "Kết quả in ra màn hình là 12.", "dap_an": "Đúng", "giai_thich": "Khi gọi nhan_doi(6), hàm trả về 6 * 2 = 12."},
            "d": {"menh_de": "Lệnh return kết thúc vòng lặp for trong hàm.", "dap_an": "Sai", "giai_thich": "Hàm không có vòng lặp; return dùng để trả về giá trị của hàm."},
        }
    elif bai_hoc in ("Bài 26", "Bài 27", "Bài 28") and loai == "ESSAY_CODE":
        ordered_shot = {
            "trich_dan_sgk": sample_cite,
            "tinh_huong": "Cho hai số nguyên m = 4 và n = 9.",
            "yeu_cau_hoc_sinh": "Viết hàm def tinh_hieu(m, n) trả về hiệu m - n và in kết quả gọi hàm.",
            "dap_an_mau": "def tinh_hieu(m, n):\n    return m - n\nprint(tinh_hieu(4, 9))",
            "tieu_chi_cham_diem": ["Định nghĩa đúng hàm bằng từ khóa def (0.4đ)", "Dùng return trả về đúng biểu thức (0.3đ)", "Gọi hàm và in kết quả chính xác (0.3đ)"],
        }
    elif bai_hoc == "Bài 21" and loai == "SHORT_ANSWER":
        ordered_shot = {
            "trich_dan_sgk": sample_cite,
            "cau_hoi": "Cho đoạn chương trình Python sau:\nk = 1\ntong = 0\nwhile k <= 4:\n    tong = tong + k\n    k = k + 1\nprint(tong)\nKết quả in ra màn hình là bao nhiêu?",
            "dap_an_ngan": "10",
            "giai_thich": "Vòng lặp while chạy với k = 1, 2, 3, 4 nên tong = 1 + 2 + 3 + 4 = 10.",
        }
    else:
        ordered_shot = {"trich_dan_sgk": sample_cite}
        for k, v in one_shot.items():
            if k != "trich_dan_sgk":
                ordered_shot[k] = v

    compact = json.dumps(ordered_shot, ensure_ascii=False, separators=(",", ":"))
    # Làm sạch triệt để các hằng số/chuỗi 1-shot bị cấm trong Validator
    for old_tok, new_tok in (
        ("x = 7", "m = 9"),
        ("'Chan'", "'Dat'"),
        ('"Chan"', '"Dat"'),
        ("'Le'", "'Chua'"),
        ('"Le"', '"Chua"'),
        ("Chan", "Dat"),
        ("Le", "Chua"),
        ("range(1, 5)", "range(2, 6)"),
        ("[7, 4, 9, 6, 8]", "[3, 8, 2, 5, 11]"),
    ):
        compact = compact.replace(old_tok, new_tok)
    return (
        f"\n### MẪU CẤU TRÚC JSON (CHỈ THAM KHẢO ĐỊNH DẠNG KHÓA & XUỐNG DÒNG \\n, TỰ TẠO BÀI MỚI CHO {bai_hoc} THEO HẠT GIỐNG):\n"
        f"{compact}\n"
    )


_SGK_HINT_PREFIX_RE = re.compile(
    r"^(?:Gợi ý|Ví dụ|Chú ý|Lưu ý)\s*:.*?(?=(?:Trong|Cho|Viết|Lệnh|Biến|Hàm|Danh sách|Xâu|Giả sử|Hãy|Xét|Kết quả|Giá trị|Một|Chương trình|Đoạn|Câu hỏi)\b)",
    flags=re.I | re.S,
)
_SGK_HINT_FALLBACK_RE = re.compile(
    r"^(?:Gợi ý|Ví dụ|Chú ý|Lưu ý)\s*:[^\n.]*(?:\.\s+|\n+)",
    flags=re.I,
)
_HERON_INLINE_RE = re.compile(
    r"(?:Gợi ý\s*:\s*)?Công\s+thức\s+Heron[^\n.]*(?:\.\s*|\n+)",
    flags=re.I,
)
_LEADING_QUESTION_TAG_RE = re.compile(r"^(?:Câu\s+hỏi|Đề\s+bài)\s*:\s*", flags=re.I)


def _strip_sgk_hint_prefix(stem: str) -> str:
    """Cắt sạch mọi tiền tố 'Câu hỏi:', 'Đề bài:', 'Gợi ý: Công thức Heron...', 'Ví dụ:...', 'Chú ý:...', 'Lưu ý:...' ở đầu đề bài."""
    s = str(stem or "").strip()
    if not s:
        return s
    cleaned = s
    for _ in range(3):
        prev = cleaned
        cleaned = _LEADING_QUESTION_TAG_RE.sub("", cleaned).strip()
        cleaned = _HERON_INLINE_RE.sub("", cleaned).strip()
        cleaned = _SGK_HINT_FALLBACK_RE.sub("", cleaned).strip()
        cleaned = _SGK_HINT_PREFIX_RE.sub("", cleaned).strip()
        cleaned = _LEADING_QUESTION_TAG_RE.sub("", cleaned).strip()
        if cleaned == prev:
            break
    return cleaned if cleaned else s


def _auto_sync_short_answer_with_sandbox(parsed: dict) -> dict:
    """
    Với SHORT_ANSWER có đoạn mã Python chạy không lỗi trên Sandbox và in ra stdout
    (dù là số như 20 hay ký tự/xâu ngắn như 'H'), ép dap_an_ngan = stdout.strip() chính xác 100%.
    """
    if not isinstance(parsed, dict) or not parsed:
        return parsed

    snippets = _extract_executable_python_snippets(parsed, "SHORT_ANSWER")
    if not snippets:
        return parsed

    has_code, sb_ok, _, sb_stdout = _run_sandbox_verification(snippets)
    stdout_exact = str(sb_stdout or "").strip()
    raw_lines = [l.strip() for l in stdout_exact.splitlines() if l.strip()]
    stdout_norm = " ".join(raw_lines) if len(raw_lines) > 1 else stdout_exact
    if has_code and sb_ok and stdout_norm and len(stdout_norm) <= 60 and len(raw_lines) <= 4:
        old_ans = str(parsed.get("dap_an_ngan", "")).strip()
        if old_ans != stdout_norm:
            print(
                f"   ⚡ [AUTO-SYNC SANDBOX] Đồng bộ dap_an_ngan: '{old_ans}' -> '{stdout_norm}' (stdout thực).",
                flush=True,
            )
            parsed = dict(parsed)
            parsed["dap_an_ngan"] = stdout_norm
    return parsed


def _build_prompt(state: AgentState) -> tuple[str, int]:
    ev = state["evidence_package"]
    loai = state["loai_cau_hoi"]
    bai_hoc = ev["bai_hoc"]
    muc_do = state.get("muc_do", "TH")
    schema_hint = _build_json_schema_hint(loai)
    # Chỉ nhúng mẫu cấu trúc JSON đã làm sạch cho TRUE_FALSE & ESSAY_CODE (cần thụt lề \n chuẩn), giúp MCQ/SHORT_ANSWER sinh siêu nhanh
    one_shot_block = (
        _format_one_shot_block(
            ev.get("exam_template", {}),
            bai_hoc=bai_hoc,
            sgk_chunks=ev.get("sgk_chunks", []),
            loai=loai,
        )
        if loai in ("TRUE_FALSE", "ESSAY_CODE") or (bai_hoc == "Bài 21" and loai == "SHORT_ANSWER")
        else ""
    )

    # Yêu cầu cú pháp trọng tâm ngay từ lần sinh đầu tiên (không chờ retry)
    lesson_mandatory_rule = ""
    if bai_hoc == "Bài 18":
        lesson_mandatory_rule = "- TRỌNG TÂM BÀI 18: Đề bài/phương án BẮT BUỘC nhắc tới `input()`, `int()`, `float()` hoặc `print()`.\n"
    elif bai_hoc in ("Bài 26", "Bài 27", "Bài 28"):
        lesson_mandatory_rule = f"- TRỌNG TÂM {bai_hoc.upper()}: Đoạn mã trong đề (hoặc `dap_an_mau`) BẮT BUỘC có định nghĩa hàm bằng từ khóa `def ten_ham(...):` và lời gọi hàm.\n"
    elif bai_hoc in ("Bài 24", "Bài 25"):
        lesson_mandatory_rule = f"- TRỌNG TÂM {bai_hoc.upper()}: Đề bài/phương án BẮT BUỘC có xâu kí tự cụ thể đặt trong dấu nháy `'...'` (hoặc `len(`, `find(`, `str`).\n"
    elif bai_hoc in ("Bài 22", "Bài 23"):
        lesson_mandatory_rule = f"- TRỌNG TÂM {bai_hoc.upper()}: Đề bài/phương án BẮT BUỘC có danh sách `list` dạng `[...]` (hoặc `append`).\n"
    elif bai_hoc == "Bài 19":
        lesson_mandatory_rule = "- TRỌNG TÂM BÀI 19: Đề bài/phương án BẮT BUỘC dùng `if`, `else`, `and`, `or`, `not` hoặc phép so sánh.\n"
    elif bai_hoc == "Bài 20":
        lesson_mandatory_rule = "- TRỌNG TÂM BÀI 20: Đề bài/phương án BẮT BUỘC dùng vòng lặp `for` hoặc hàm `range()`.\n"
    elif bai_hoc == "Bài 21":
        lesson_mandatory_rule = "- TRỌNG TÂM BÀI 21: Đề bài/phương án BẮT BUỘC dùng vòng lặp `while`.\n"
    elif bai_hoc in ("Bài 29", "Bài 30"):
        lesson_mandatory_rule = f"- TRỌNG TÂM {bai_hoc.upper()}: Đề bài/phương án BẮT BUỘC nhắc tới khái niệm lỗi (`lỗi cú pháp`, `ngoại lệ`, `lỗi logic`, `SyntaxError`, `TypeError`, `IndexError`, `ZeroDivisionError`, `NameError`, `kiểm thử`).\n"

    avoid_block = ""
    avoid_list = state.get("avoid_snippets") or []
    if avoid_list:
        compact_used = [re.sub(r"\s+", " ", str(s)).strip()[:85] for s in avoid_list[-5:] if str(s).strip()]
        if compact_used:
            avoid_block = (
                "\n### CÁC ĐOẠN MÃ / Ý ĐÃ DÙNG Ở CÂU TRƯỚC (BẮT BUỘC TẠO BÀI TOÁN KHÁC HẲN):\n"
                + "\n".join(f"- {u}" for u in compact_used)
                + "\n"
            )

    feedback_block = ""
    if state.get("feedback"):
        lesson_hint = ""
        if bai_hoc in ("Bài 26", "Bài 27", "Bài 28"):
            lesson_hint = f" LƯU Ý {bai_hoc.upper()}: BẮT BUỘC có định nghĩa hàm bằng từ khóa `def`."
        elif bai_hoc in ("Bài 24", "Bài 25"):
            lesson_hint = f" LƯU Ý {bai_hoc.upper()}: BẮT BUỘC có xâu kí tự cụ thể đặt trong dấu nháy '...' hoặc \"...\"."
        elif bai_hoc in ("Bài 22", "Bài 23"):
            lesson_hint = f" LƯU Ý {bai_hoc.upper()}: BẮT BUỘC dùng kiểu danh sách list với dấu ngoặc vuông `[...]`."
        elif bai_hoc == "Bài 19":
            lesson_hint = " LƯU Ý BÀI 19: Câu hỏi/mã nguồn PHẢI dùng biểu thức lôgic hoặc câu lệnh rẽ nhánh if / if-else."
        elif bai_hoc == "Bài 20":
            lesson_hint = " LƯU Ý BÀI 20: Câu hỏi/mã nguồn PHẢI dùng vòng lặp for và lệnh range()."
        feedback_block = (
            f"\n### PHẢN HỒI KIỂM ĐỊNH LẦN TRƯỚC (BẮT BUỘC SỬA TRIỆT ĐỂ):{lesson_hint}\n"
            f"{state['feedback']}\n"
        )

    rules_extra = {
        "MCQ": (
            "- Đặt 1 câu hỏi trắc nghiệm cụ thể kèm đoạn mã Python ngắn (nếu hỏi tính kết quả, BẮT BUỘC có đoạn mã đầy đủ và khởi tạo mọi biến).\n"
            "- 4 phương án A, B, C, D cụ thể (15-90 ký tự), duy nhất 1 đáp án đúng (nếu hỏi lệnh gán đúng, 3 phương án nhiễu phải sai cú pháp); CẤM phương án giữ chỗ ('Biểu thức A', 'Phương án 1', 'Tất cả đều đúng').\n"
            "- 'dap_an' chỉ ghi 1 chữ cái duy nhất: A, B, C hoặc D."
        ),
        "TRUE_FALSE": (
            "- 'cau_hoi_chung' PHẢI có câu dẫn + đoạn mã Python 3-5 dòng chạy được (xuống dòng bằng \\n và thụt lề 4 dấu cách, CẤM viết dính trên 1 dòng).\n"
            "- 4 mệnh đề a, b, c, d độc lập, bám sát mã nguồn, có đủ 'Đúng' và 'Sai'; mỗi ý có 'giai_thich' riêng biệt >= 25 ký tự."
        ),
        "SHORT_ANSWER": (
            "- BẮT BUỘC có đoạn mã Python 3-5 dòng chạy được (gán sẵn giá trị mọi biến, không dùng input(), xuống dòng \\n và thụt 4 dấu cách, chỉ dùng ĐÚNG 1 lệnh print() ở cuối chương trình) và hỏi kết quả in ra màn hình.\n"
            "- 'dap_an_ngan' là 1 giá trị số hoặc xâu ngắn duy nhất."
        ),
        "ESSAY_CODE": (
            "- BẮT BUỘC điền ĐỦ 5 khóa JSON: trich_dan_sgk, tinh_huong (>= 25 ký tự kèm dữ liệu cụ thể như A = [3, 8, 2, 5, 11]), yeu_cau_hoc_sinh, dap_an_mau, tieu_chi_cham_diem.\n"
            "- TUYỆT ĐỐI KHÔNG chép mã giải thuật (`for`, `while`, `def`, `return`, `tong = 0`) vào `tinh_huong` hay `yeu_cau_hoc_sinh` (chỉ ghi mô tả đề và dữ liệu đầu vào); đa dạng hóa bài toán (tìm max/min, đếm theo điều kiện, trung bình cộng, chia hết, xử lý xâu), tránh lặp 'tính tổng các số chẵn'.\n"
            "- 'dap_an_mau' gán trực tiếp dữ liệu từ HẠT GIỐNG ngay dòng đầu (KHÔNG dùng input()), dài 4-6 dòng Python lớp 10 xuống dòng rõ ràng, tên biến không dấu, chạy không lỗi.\n"
            "- KHÔNG dùng open(), class, lambda, try/except hay thư viện ngoài."
        ),
    }.get(loai, "")

    prompt_text = (
        f"NHIỆM VỤ: Soạn ĐÚNG 1 câu hỏi MỚI môn Tin học 10 (Chủ đề F - Python, SGK Kết nối tri thức) "
        f"cho {bai_hoc}, dạng {loai}, mức độ {muc_do}.\n\n"
        f"{ev['formatted_context']}\n"
        f"{one_shot_block}"
        f"{avoid_block}"
        f"{feedback_block}\n"
        f"### QUY TẮC BẮT BUỘC:\n"
        f"{lesson_mandatory_rule}"
        f"- 100% nội dung thuộc {bai_hoc} (Python lớp 10), viết 100% tiếng Việt chuẩn. Cấm HTML/CSS/SQL/open()/thư viện ngoài.\n"
        f"- BẮT BUỘC tự viết đoạn mã Python MỚI dùng đúng tên biến và số liệu từ mục HẠT GIỐNG DỮ LIỆU MỚI ở trên.\n"
        f"- Thân câu hỏi ngắn gọn đúng chuẩn đề thi (không chép 'BÀI ...', 'Hoạt động 1/2', 'Luyện tập', 'Vận dụng' từ SGK). Mã nhiều dòng PHẢI xuống dòng `\\n` và thụt lề 4 dấu cách, CẤM viết dính 1 dòng.\n"
        f"- Viết 'giai_thich' bám sát DUY NHẤT các biến/lệnh có trong đề. Trường 'trich_dan_sgk' chép NGUYÊN VĂN 1 câu từ BẰNG CHỨNG SGK.\n"
        f"{rules_extra}\n"
        f"- CHỈ xuất DUY NHẤT 1 JSON hợp lệ đúng cấu trúc sau (không kèm chữ ngoài JSON):\n"
        f"{schema_hint}"
    )

    tokens = estimate_tokens(prompt_text)
    if tokens >= MAX_PROMPT_TOKENS:
        overflow_chars = int((tokens - (MAX_PROMPT_TOKENS - 60)) * 3.2)
        ctx = ev["formatted_context"]
        seed_marker = "\n\n### HẠT GIỐNG DỮ LIỆU MỚI"
        if seed_marker in ctx:
            body_part, seed_part = ctx.split(seed_marker, 1)
            trimmed_body = body_part[: max(300, len(body_part) - overflow_chars)].rstrip() + "..."
            trimmed_ctx = trimmed_body + seed_marker + seed_part
        else:
            trimmed_ctx = ctx[: max(420, len(ctx) - overflow_chars)].rstrip() + "..."
        prompt_text = prompt_text.replace(ctx, trimmed_ctx)
        tokens = estimate_tokens(prompt_text)

    return prompt_text, tokens


def _auto_sync_mcq_answer_with_sandbox(parsed: dict) -> dict:
    """
    Với câu MCQ có đoạn mã Python chạy trên Sandbox in ra stdout ngắn hợp lệ (VD: 14):
      - Nếu 1 trong 4 phương án đã khớp stdout mà dap_an trỏ sai -> cập nhật dap_an sang phương án đó.
      - Nếu chưa phương án nào chứa stdout và dap_an hợp lệ (A/B/C/D) -> gán stdout vào phương án dap_an
        (chỉ gán khi không trùng 3 phương án còn lại), giúp đúng 100% phép tính ngay lượt đầu.
    """
    if not isinstance(parsed, dict) or not parsed:
        return parsed
    cau_hoi_low = str(parsed.get("cau_hoi", "")).lower()
    if any(cue in cau_hoi_low for cue in _NON_OUTPUT_QUESTION_CUES):
        return parsed
    if not any(cue in cau_hoi_low for cue in _OUTPUT_QUESTION_CUES):
        return parsed

    snippets = _extract_executable_python_snippets(parsed, "MCQ")
    if not snippets:
        return parsed

    has_code, sb_ok, _, sb_stdout = _run_sandbox_verification(snippets)
    stdout_clean = str(sb_stdout or "").strip()
    if not (has_code and sb_ok and stdout_clean and len(stdout_clean) <= 40 and "\n" not in stdout_clean):
        return parsed

    opt_keys = ("A", "B", "C", "D")
    opts = {k: str(parsed.get(k, "")).strip() for k in opt_keys}
    if not all(opts.values()):
        return parsed

    stdout_low = stdout_clean.lower()
    norm_opts = {k: v.strip("'\"").strip().lower() for k, v in opts.items()}
    dap_an = str(parsed.get("dap_an", "")).strip().upper()

    # Kiểm tra đã có phương án nào khớp stdout chưa
    matched_key = next((k for k in opt_keys if norm_opts[k] == stdout_low), None)
    if matched_key:
        if dap_an != matched_key:
            print(
                f"   ⚡ [AUTO-SYNC MCQ] Chuyển dap_an: '{dap_an}' -> '{matched_key}' (khớp stdout='{stdout_clean}').",
                flush=True,
            )
            updated = dict(parsed)
            updated["dap_an"] = matched_key
            return updated
        return parsed

    # Chưa phương án nào chứa stdout -> gán stdout vào phương án dap_an đang trỏ tới (không trùng 3 phương án kia)
    if dap_an in opt_keys:
        other_vals = {norm_opts[k] for k in opt_keys if k != dap_an}
        if stdout_low not in other_vals:
            print(
                f"   ⚡ [AUTO-SYNC MCQ] Gán phương án {dap_an}: '{opts[dap_an]}' -> '{stdout_clean}' (stdout thực).",
                flush=True,
            )
            updated = dict(parsed)
            updated[dap_an] = stdout_clean
            return updated
    return parsed


def _auto_ground_question_json(parsed: dict, loai: str, evidence_package: dict) -> dict:
    """
    Chuẩn hóa hậu xử lý tất định (Deterministic Auto-Grounding) trước khi chạy validate_question:
      (a) Nếu dap_an_mau là list Python -> tự động nối thành chuỗi code sạch bằng '\\n'.
      (b) Nếu trich_dan_sgk rỗng hoặc độ trùng từ vựng với sgk_chunks < 45%, tự động trích câu
          đầu tiên hợp lệ từ evidence_package['sgk_chunks'] gán vào trich_dan_sgk.
      (c) Với SHORT_ANSWER / MCQ có mã Python chạy không lỗi trên Sandbox và trả về stdout ngắn hợp lệ,
          tự động đồng bộ đáp án đúng theo stdout thực tế.
    """
    if not isinstance(parsed, dict) or not parsed:
        return parsed

    result = dict(parsed)

    # (0) Cắt sạch các câu gợi ý/ví dụ/chú ý thừa từ SGK ở đầu đề bài (VD: 'Gợi ý: Công thức Heron...')
    for stem_key in ("cau_hoi", "cau_hoi_chung", "tinh_huong", "yeu_cau_hoc_sinh"):
        if stem_key in result and isinstance(result[stem_key], str):
            result[stem_key] = _strip_sgk_hint_prefix(result[stem_key])

    # (a) Chuẩn hóa dap_an_mau & ánh xạ khóa cho ESSAY_CODE (chống sót khóa do biến thể tên trường của 3B)
    if isinstance(result.get("dap_an_mau"), list):
        result["dap_an_mau"] = _normalize_code_mau(result["dap_an_mau"])
    if loai == "ESSAY_CODE":
        th = str(result.get("tinh_huong", "")).strip()
        yc = str(result.get("yeu_cau_hoc_sinh", "")).strip()
        code_cur = str(result.get("dap_an_mau", ""))

        if len(th) < 20:
            for alias in ("de_bai", "cau_hoi", "mo_ta", "bai_toan"):
                cand = _strip_sgk_hint_prefix(str(result.get(alias, "")).strip())
                if len(cand) >= 20:
                    th = cand
                    result["tinh_huong"] = th
                    break

        # Cắt bỏ dòng mở đầu lặp hạt giống kiểu "Cho hai số nguyên m = ..." khi bài toán thực tế yêu cầu nhập xâu từ bàn phím
        combined_essay_low = f"{th}\n{yc}\n{code_cur}".lower()
        is_string_input_task = (
            any(k in combined_essay_low for k in ("xâu", "chuỗi", "kí tự", "ký tự"))
            and any(k in combined_essay_low for k in ("nhập", "bàn phím", "input("))
        )
        if is_string_input_task and re.match(r"^cho\s+hai\s+số\s+nguyên\b", th, re.IGNORECASE):
            th_stripped = re.sub(r"^cho\s+hai\s+số\s+nguyên[^\n.]*(?:\.\s*|\n+)", "", th, flags=re.IGNORECASE).strip()
            th = th_stripped
            result["tinh_huong"] = th

        # Chuẩn hóa chống nối ghép 2 đề bài và tạo trường cau_hoi_day_du sạch
        th_has_task = bool(re.search(r"\b(?:viết\s+hàm|viết\s+chương\s+trình)\b", th, re.IGNORECASE))
        yc_has_task = bool(re.search(r"\b(?:viết\s+hàm|viết\s+chương\s+trình)\b", yc, re.IGNORECASE))
        yc_has_data = bool(re.search(r"(\[[^\]]+\]|['\"][^'\"]+['\"]|\b[A-Za-z_]\w*\s*=\s*\S+|nhập\s+(?:từ\s+bàn\s+phím|một|xâu|chuỗi|số))", yc, re.IGNORECASE))

        if th_has_task:
            # tinh_huong đã chứa yêu cầu viết hàm/chương trình -> chỉ dùng tinh_huong làm đề đầy đủ, không nối lặp yeu_cau_hoc_sinh
            result["tinh_huong"] = th
            result["cau_hoi_day_du"] = th
            if yc_has_task or len(yc) < 10:
                result["yeu_cau_hoc_sinh"] = "Trình bày mã nguồn Python hoàn chỉnh và kiểm tra kết quả in ra màn hình."
        elif yc_has_task and yc_has_data and len(yc) >= 35 and (
            len(th) < 20
            or re.match(r"^cho\s+hai\s+số\s+nguyên\b", th, re.IGNORECASE)
            or th.lower().rstrip(".") in yc.lower()
        ):
            # yeu_cau_hoc_sinh đã nêu đầy đủ bài toán & dữ liệu đầu vào -> bỏ tinh_huong dư thừa
            result["tinh_huong"] = yc
            result["cau_hoi_day_du"] = yc
            result["yeu_cau_hoc_sinh"] = "Trình bày mã nguồn Python hoàn chỉnh và kiểm tra kết quả in ra màn hình."
        else:
            if len(th) < 20 and len(yc) >= 35:
                result["tinh_huong"] = yc
                result["yeu_cau_hoc_sinh"] = "Trình bày mã nguồn Python hoàn chỉnh và kiểm tra kết quả in ra màn hình."
                result["cau_hoi_day_du"] = yc
            elif len(th) >= 20 and len(yc) < 10 and code_cur.strip():
                result["yeu_cau_hoc_sinh"] = "Trình bày mã nguồn Python hoàn chỉnh và kiểm tra kết quả in ra màn hình."
                result["cau_hoi_day_du"] = th
            else:
                result["cau_hoi_day_du"] = f"{th} {yc}".strip()

        # Nếu tình huống/yêu cầu nhắc đến danh sách nhưng quên ghi dữ liệu cụ thể -> CHỈ chép đúng dòng dữ liệu đầu vào kiểu A = [...] (tuyệt đối không chép code giải thuật)
        th_cur = str(result.get("tinh_huong", "")).strip()
        yc_cur = str(result.get("yeu_cau_hoc_sinh", "")).strip()
        if any(k in (th_cur + " " + yc_cur).lower() for k in ("mảng", "danh sách", "list")) and "[" not in (th_cur + yc_cur):
            m_list = re.search(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\[[^\]]+\])", code_cur, re.MULTILINE)
            if m_list:
                result["tinh_huong"] = f"{th_cur.rstrip('.')} (dữ liệu đầu vào: {m_list.group(1)} = {m_list.group(2)})."
                result["cau_hoi_day_du"] = result["tinh_huong"] if re.search(r"\b(?:viết\s+hàm|viết\s+chương\s+trình)\b", result["tinh_huong"], re.IGNORECASE) else f"{result['tinh_huong']} {yc_cur}".strip()

    # (b) Deterministic Auto-Grounding cho trường trich_dan_sgk
    if isinstance(evidence_package, dict) and evidence_package.get("sgk_chunks"):
        trich_dan = str(result.get("trich_dan_sgk", "")).strip()
        overlap = _compute_sgk_citation_overlap(trich_dan, evidence_package)
        if len(trich_dan) < 15 or overlap < 0.45:
            verbatim_list = _extract_verbatim_sgk_sentences(evidence_package, max_sentences=1)
            if verbatim_list:
                result["trich_dan_sgk"] = verbatim_list[0]
                print(
                    f"   ⚡ [AUTO-GROUNDING SGK] Gắn trích dẫn nguyên văn từ sgk_chunks[0] (overlap cũ={overlap:.0%}).",
                    flush=True,
                )

    # (c) Đồng bộ đáp án thực tế từ Sandbox cho SHORT_ANSWER và MCQ
    if loai == "SHORT_ANSWER":
        result = _auto_sync_short_answer_with_sandbox(result)
    elif loai == "MCQ":
        result = _auto_sync_mcq_answer_with_sandbox(result)

    return result


# ==============================================================================
# CÁC NODE LANGGRAPH (TUẦN TỰ: RETRIEVE -> GENERATE -> VALIDATE -> RETRY<=2)
# ==============================================================================

def retrieve_node(state: AgentState) -> dict:
    bai_hoc = state["bai_hoc"]
    loai = state["loai_cau_hoi"].strip().upper()
    muc_do = state.get("muc_do", "TH")
    chi_tiet = state.get("chu_de_chi_tiet", "")

    # Nếu đã tiền truy xuất ở Pha 1 (Exam Assembler), bỏ qua gọi ChromaDB/Embedding để giữ sạch 4GB VRAM
    pre_pkg = state.get("evidence_package")
    if isinstance(pre_pkg, dict) and pre_pkg.get("sgk_chunks") and pre_pkg.get("formatted_context"):
        print(
            f"\n[NODE 1 - RETRIEVE] Dùng ngữ cảnh tiền truy xuất {pre_pkg.get('bai_hoc', bai_hoc)} "
            f"| Dạng: {loai} | Mức độ: {muc_do} (~{pre_pkg.get('estimated_context_tokens', 0)} ctx tokens, 0ms embed)",
            flush=True,
        )
        return {
            "bai_hoc": pre_pkg.get("bai_hoc", bai_hoc),
            "loai_cau_hoi": loai,
            "evidence_package": pre_pkg,
        }

    print(f"\n[NODE 1 - RETRIEVE] Khóa cứng {bai_hoc} | Dạng: {loai} | Mức độ: {muc_do}", flush=True)
    pkg = retrieve_evidence_package(
        bai_hoc=bai_hoc,
        loai_cau_hoi=loai,
        chu_de_chi_tiet=chi_tiet,
        muc_do=muc_do,
        max_context_tokens=600,
    )
    print(
        f"   -> Truy xuất {len(pkg['sgk_chunks'])} chunks SGK ({pkg['bai_hoc']}), "
        f"{len(pkg['glossary_terms'])} thuật ngữ chuẩn, 1 khuôn mẫu đề + 1-shot "
        f"(~{pkg['estimated_context_tokens']} context tokens).",
        flush=True,
    )
    return {
        "bai_hoc": pkg["bai_hoc"],
        "loai_cau_hoi": loai,
        "evidence_package": pkg,
    }


# ==============================================================================
# NEURO-SYMBOLIC: PROMPT DIỄN ĐẠT SƯ PHẠM + HỢP NHẤT AN TOÀN VỚI KHUNG SANDBOX
# ==============================================================================

def _build_neuro_symbolic_prompt(skeleton: dict, ev: dict, loai: str, muc_do: str) -> tuple[str, int]:
    """
    Dựng prompt siêu gọn (~450-600 tokens) cho llama3.2_tinhoc10:
      - Đưa khung câu hỏi & đáp án đã kiểm chứng toán học/Sandbox từ symbolic_engine.
      - Đưa bằng chứng SGK từ ChromaDB v2.
      - Yêu cầu LLM chỉ diễn đạt giải thích sư phạm tự nhiên và trích dẫn nguyên văn SGK.
    """
    bai_hoc = ev.get("bai_hoc", skeleton.get("bai_hoc", "Bài 19"))
    sgk_chunks = ev.get("sgk_chunks") or []
    sgk_lines = []
    for ch in sgk_chunks[:2]:
        txt = re.sub(r"\s+", " ", str(ch.get("content", "")).strip())[:260]
        if txt:
            sgk_lines.append(f"- [SGK {ch.get('bai_hoc', bai_hoc)}, tr.{ch.get('trang', '')}]: {txt}")
    sgk_block = "\n".join(sgk_lines) if sgk_lines else "- (Theo SGK Tin học 10 Kết nối tri thức)"

    q_skel = skeleton.get("question_json", {})
    if loai == "MCQ":
        skel_summary = (
            f"Câu hỏi: {q_skel.get('cau_hoi', '')}\n"
            f"A: {q_skel.get('A', '')} | B: {q_skel.get('B', '')} | C: {q_skel.get('C', '')} | D: {q_skel.get('D', '')}\n"
            f"Đáp án đúng đã kiểm chứng: {q_skel.get('dap_an', '')}"
        )
        schema_out = (
            '{"giai_thich": "Giải thích ngắn gọn 1-2 câu tiếng Việt bám sát đúng biến/lệnh và đáp án trên", '
            '"trich_dan_sgk": "Chép nguyên văn 1 câu từ BẰNG CHỨNG SGK ở trên"}'
        )
    elif loai == "SHORT_ANSWER":
        skel_summary = (
            f"Câu hỏi: {q_skel.get('cau_hoi', '')}\n"
            f"Đáp án chuẩn Sandbox: {q_skel.get('dap_an_ngan', '')}"
        )
        schema_out = (
            '{"giai_thich": "Giải thích từng bước ngắn gọn vì sao chương trình in ra đúng đáp án trên", '
            '"trich_dan_sgk": "Chép nguyên văn 1 câu từ BẰNG CHỨNG SGK ở trên"}'
        )
    elif loai == "TRUE_FALSE":
        lines_tf = [f"Đề chung: {q_skel.get('cau_hoi_chung', '')}"]
        for k in ("a", "b", "c", "d"):
            it = q_skel.get(k) or {}
            lines_tf.append(f"{k}) {it.get('menh_de', '')} -> [{it.get('dap_an', '')}]")
        skel_summary = "\n".join(lines_tf)
        schema_out = (
            '{"giai_thich_a": "Giải thích ý a", "giai_thich_b": "Giải thích ý b", '
            '"giai_thich_c": "Giải thích ý c", "giai_thich_d": "Giải thích ý d", '
            '"trich_dan_sgk": "Chép nguyên văn 1 câu từ BẰNG CHỨNG SGK ở trên"}'
        )
    else:  # ESSAY_CODE
        skel_summary = (
            f"Tình huống: {q_skel.get('tinh_huong', '')}\n"
            f"Yêu cầu: {q_skel.get('yeu_cau_hoc_sinh', '')}"
        )
        schema_out = (
            '{"tinh_huong_tu_nhien": "Viết lại tình huống mượt mà hơn nhưng GIỮ NGUYÊN 100% số liệu/danh sách/xâu đầu vào, không lộ code giải", '
            '"trich_dan_sgk": "Chép nguyên văn 1 câu từ BẰNG CHỨNG SGK ở trên"}'
        )

    prompt = (
        f"VAI TRÒ: Trợ lý biên tập sư phạm Tin học 10 KNTT ({bai_hoc} - {loai} - {muc_do}).\n"
        f"### BẰNG CHỨNG SGK:\n{sgk_block}\n\n"
        f"### KHUNG CÂU HỎI ĐÃ KIỂM CHỨNG TOÁN HỌC & SANDBOX (KHÔNG ĐỔI CODE/ĐÁP ÁN):\n{skel_summary}\n\n"
        f"### YÊU CẦU:\n"
        f"- Viết lời giải thích tự nhiên, chuẩn thuật ngữ SGK, bám sát DUY NHẤT các biến/lệnh có trong khung.\n"
        f"- Trường trich_dan_sgk chép nguyên văn 1 câu từ BẰNG CHỨNG SGK ở trên.\n"
        f"- CHỈ xuất DUY NHẤT 1 JSON hợp lệ đúng dạng sau:\n{schema_out}"
    )
    return prompt, estimate_tokens(prompt)


def _clean_sgk_citation(text: str) -> str:
    """Cắt bỏ triệt để các tiền tố chỉ thị prompt bị rò rỉ trong trich_dan_sgk."""
    s = str(text or "").strip()
    patterns = [
        (r"^(?:Chép\s+(?:nguyên\s+văn|NGUYÊN\s+VĂN)\s+1\s+câu\s+từ\s+(?:mục\s+)?BẰNG\s+CHỨNG\s+SGK\s*(?:ở\s+trên)?\s*[:\-]*)", re.I),
        (r"^(?:Bằng\s+chứng\s+SGK\s*(?:ở\s+trên)?\s*[:\-]*)", re.I),
        (r"^(?:Trích\s+dẫn\s+SGK\s*[:\-]*)", re.I),
        (r"^(?:Câu\s+hỏi\s*[:\-]*)", re.I),
        (r"^(?:Gợi\s+ý\s*[:\-]*)", re.I),
        (r"^(?:SGK\s*[:\-]*)", re.I),
    ]
    changed = True
    while changed:
        changed = False
        for pat, flags in patterns:
            new_s = re.sub(pat, "", s, flags=flags).strip()
            if new_s != s:
                s = new_s
                changed = True
    s = re.sub(r'^["“”\'«»]+|["“”\'«»]+$', "", s).strip()
    return s


def _ground_sgk_citation_fast(q: dict, ev: dict) -> dict:
    """Gắn trích dẫn nguyên văn từ sgk_chunks (thuần Python 0ms, không gọi lại Sandbox)."""
    out = dict(q)
    if isinstance(ev, dict) and ev.get("sgk_chunks"):
        trich_dan = _clean_sgk_citation(str(out.get("trich_dan_sgk", "")).strip())
        overlap = _compute_sgk_citation_overlap(trich_dan, ev)
        if len(trich_dan) < 15 or overlap < 0.45:
            verbatim_list = _extract_verbatim_sgk_sentences(ev, max_sentences=1)
            if verbatim_list:
                trich_dan = _clean_sgk_citation(verbatim_list[0])
        out["trich_dan_sgk"] = trich_dan
    else:
        out["trich_dan_sgk"] = _clean_sgk_citation(out.get("trich_dan_sgk", ""))
    return out


def _merge_symbolic_and_neural(
    skeleton: dict,
    neural_parsed: dict,
    loai: str,
    ev: dict,
) -> dict:
    """
    Hợp nhất khung Symbolic (đã kiểm chứng 100% toán học/Sandbox) với diễn đạt sư phạm từ LLM:
      - Luôn giữ nguyên 100% mã nguồn Python, phương án, đáp án đúng và rubric từ khung Symbolic.
      - KHÓA CHUẨN 100% lời giải thích từ dữ liệu thật (verified_explanation và verified_tf_explanations),
        triệt tiêu 100% hiện tượng LLM 3B tính nhẩm sai trong lời giải thích.
      - Làm sạch triệt để trường trich_dan_sgk (cắt sạch prompt leaks).
    """
    base_q = copy.deepcopy(skeleton.get("question_json", {}))
    neural_cite = _clean_sgk_citation(str((neural_parsed or {}).get("trich_dan_sgk", "")).strip())
    if neural_cite:
        base_q["trich_dan_sgk"] = neural_cite
    base_q = _ground_sgk_citation_fast(base_q, ev)
    base_q["trich_dan_sgk"] = _clean_sgk_citation(base_q.get("trich_dan_sgk", ""))

    verified_exp = str(skeleton.get("verified_explanation") or base_q.get("giai_thich", "")).strip()
    verified_tf = skeleton.get("verified_tf_explanations") or {}
    if not verified_tf and loai == "TRUE_FALSE":
        verified_tf = {
            k: str(base_q.get(k, {}).get("giai_thich", "")).strip()
            for k in ("a", "b", "c", "d")
            if isinstance(base_q.get(k), dict)
        }

    merged = copy.deepcopy(base_q)

    # 1. Khóa chuẩn 100% lời giải thích từ dữ liệu thật (cấm tuyệt đối LLM 3B tự ý tính nhẩm sai)
    if loai in ("MCQ", "SHORT_ANSWER"):
        merged["giai_thich"] = verified_exp if verified_exp else str(base_q.get("giai_thich", "")).strip()
    elif loai == "TRUE_FALSE":
        for k in ("a", "b", "c", "d"):
            if isinstance(merged.get(k), dict):
                merged[k]["giai_thich"] = verified_tf.get(k) or str(base_q.get(k, {}).get("giai_thich", "")).strip()
    elif loai == "ESSAY_CODE":
        if isinstance(neural_parsed, dict):
            th_llm = _strip_sgk_hint_prefix(str(neural_parsed.get("tinh_huong_tu_nhien", "")).strip())
            orig_th = str(base_q.get("tinh_huong", ""))
            orig_lists = re.findall(r"\[[^\]]+\]", orig_th)
            orig_strs = re.findall(r"'[^']+'", orig_th)
            orig_nums = re.findall(r"\b\d+\b", orig_th)
            if (
                len(th_llm) >= 25
                and all(lst in th_llm for lst in orig_lists)
                and all(st in th_llm for st in orig_strs)
                and all(num in th_llm for num in orig_nums)
            ):
                merged["tinh_huong"] = th_llm
        merged["giai_thich"] = verified_exp if verified_exp else str(base_q.get("giai_thich", "")).strip()

    merged["trich_dan_sgk"] = _clean_sgk_citation(merged.get("trich_dan_sgk", ""))
    return merged


def generate_node(state: AgentState) -> dict:
    attempt_no = state["retry_count"] + 1
    loai = state["loai_cau_hoi"]
    ev = state.get("evidence_package", {})
    bai_hoc = ev.get("bai_hoc", state["bai_hoc"])
    muc_do = state.get("muc_do", "TH")

    # KIẾN TRÚC NEURO-SYMBOLIC (PROGRAM-AIDED QUESTION GENERATION)
    if state.get("use_neuro_symbolic", USE_NEURO_SYMBOLIC):
        skeleton = state.get("symbolic_skeleton")
        if not isinstance(skeleton, dict) or not skeleton.get("question_json"):
            used_set = set(state.get("used_blueprint_ids") or [])
            recent_set = set(state.get("recent_blueprint_ids") or [])
            skeleton = build_verified_skeleton(
                bai_hoc=bai_hoc,
                loai_cau_hoi=loai,
                muc_do=muc_do,
                used_blueprint_ids=used_set,
                recent_blueprint_ids=recent_set,
                chu_de_chi_tiet=state.get("chu_de_chi_tiet", ""),
            )
        prompt_text, prompt_tokens = _build_neuro_symbolic_prompt(skeleton, ev, loai, muc_do)
        max_pred = NEURAL_POLISH_NUM_PREDICT.get(loai, 140)
        print(
            f"[NODE 2 - NEURO-SYMBOLIC] Blueprint={skeleton['blueprint_id']} | Lần {attempt_no}/{MAX_RETRIES + 1} "
            f"(prompt ~{prompt_tokens} tokens, num_predict={max_pred})...",
            flush=True,
        )
        neural_parsed: dict = {}
        try:
            raw_text = call_ollama_json(prompt_text, temperature=0.15, num_predict=max_pred, num_ctx=1536)
            neural_parsed = _parse_llm_json(raw_text)
        except Exception as e:
            print(f"   ⚠️ Ollama phản hồi lỗi ({e}) -> dùng nguyên khung Symbolic + trích dẫn SGK.", flush=True)

        merged_q = _merge_symbolic_and_neural(skeleton, neural_parsed, loai, ev)
        return {
            "bai_hoc": skeleton.get("bai_hoc", bai_hoc),
            "question_json": merged_q,
            "blueprint_id": skeleton.get("blueprint_id", ""),
            "symbolic_skeleton": skeleton,
            "prompt_tokens": prompt_tokens,
        }

    # Chế độ thuần Neural cũ (dự phòng khi tắt USE_NEURO_SYMBOLIC)
    prompt_text, prompt_tokens = _build_prompt(state)
    temp = min(0.35, 0.15 + 0.08 * state["retry_count"])
    max_pred = ADAPTIVE_NUM_PREDICT.get(loai, DEFAULT_NUM_PREDICT)
    print(
        f"[NODE 2 - GENERATE] Lần {attempt_no}/{MAX_RETRIES + 1} "
        f"(prompt ~{prompt_tokens} tokens, num_predict={max_pred}, temp={temp:.2f})...",
        flush=True,
    )

    try:
        raw_text = call_ollama_json(prompt_text, temperature=temp, num_predict=max_pred)
        parsed = _parse_llm_json(raw_text)
        if not parsed:
            print("   ⚠️ Không trích xuất được JSON hợp lệ từ phản hồi LLM.", flush=True)
        else:
            parsed = _auto_ground_question_json(parsed, loai, state.get("evidence_package", {}))
        return {
            "question_json": parsed,
            "prompt_tokens": prompt_tokens,
        }
    except Exception as e:
        print(f"   ❌ Lỗi gọi Ollama: {e}", flush=True)
        return {
            "question_json": {},
            "prompt_tokens": prompt_tokens,
        }


def validate_node(state: AgentState) -> dict:
    q = state.get("question_json", {})
    loai = state["loai_cau_hoi"]
    ev = state["evidence_package"]

    result = validate_question(q, loai, ev)
    # Neuro-Symbolic Guard: nếu phần diễn đạt LLM gây rớt Hard Gate -> khôi phục ngay khung Symbolic + trích dẫn SGK chuẩn (0 retry)
    if not result.get("is_pass") and state.get("use_neuro_symbolic", USE_NEURO_SYMBOLIC):
        skeleton = state.get("symbolic_skeleton")
        if isinstance(skeleton, dict) and skeleton.get("question_json"):
            fallback_q = copy.deepcopy(skeleton["question_json"])
            fallback_q["trich_dan_sgk"] = q.get("trich_dan_sgk", "")
            fallback_q = _ground_sgk_citation_fast(fallback_q, ev)
            fb_res = validate_question(fallback_q, loai, ev)
            if fb_res.get("is_pass"):
                print(
                    "   🛡️ [NEURO-SYMBOLIC GUARD] Khôi phục khung Symbolic đã kiểm chứng + trích dẫn SGK -> PASS lượt đầu!",
                    flush=True,
                )
                q = fallback_q
                result = fb_res

    score = float(result.get("diem_chat_luong", 0.0))
    xep_loai = result.get("xep_loai", "KHÔNG ĐẠT")
    is_pass = bool(result.get("is_pass", False))
    sb_ok = bool(result.get("sandbox_verified", False))

    print(
        f"[NODE 3 - VALIDATE] Tầng 1: {'PASS' if result['tier1']['passed'] else 'FAIL'} | "
        f"Sandbox: {'OK' if sb_ok else 'N/A hoặc Lỗi'} | "
        f"Tầng 2: {xep_loai} ({score:.3f}/1.0)"
    )
    if not is_pass:
        print(f"   -> Phản hồi sửa: {result['feedback'][:240]}")

    best_q = state.get("best_question_json") or {}
    best_val = state.get("best_validation") or result
    best_score = float(state.get("best_score", -1.0))
    if q and (score > best_score or not best_q):
        best_q = q
        best_val = result
        best_score = score

    next_retry = state["retry_count"] if is_pass else state["retry_count"] + 1
    return {
        "question_json": q,
        "validation_result": result,
        "is_pass": is_pass,
        "feedback": result.get("feedback", ""),
        "retry_count": next_retry,
        "best_question_json": best_q,
        "best_validation": best_val,
        "best_score": best_score,
    }


def _router(state: AgentState) -> str:
    if state["is_pass"]:
        return "end"
    if state["retry_count"] >= MAX_RETRIES:
        print(f"   ⚠️ Đã đạt giới hạn {MAX_RETRIES} lần tự sửa lỗi. Trả về phiên bản tốt nhất.")
        return "end"
    return "generate"


workflow = StateGraph(AgentState)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("generate", generate_node)
workflow.add_node("validate", validate_node)
workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "generate")
workflow.add_edge("generate", "validate")
workflow.add_conditional_edges("validate", _router, {"generate": "generate", "end": END})
app = workflow.compile()


def generate_question(
    bai_hoc: str,
    loai_cau_hoi: str,
    chu_de_chi_tiet: str = "",
    muc_do: str = "TH",
    enable_logging: bool = True,
    avoid_snippets: list[str] | None = None,
    pre_retrieved_evidence: dict | None = None,
    used_blueprint_ids: set[str] | list[str] | None = None,
    recent_blueprint_ids: set[str] | list[str] | None = None,
    use_neuro_symbolic: bool = True,
) -> dict:
    """Hàm giao diện chuẩn chạy trọn vòng lặp Neuro-Symbolic Agentic RAG 2 tầng kiểm định + ghi log CSV."""
    t0 = time.time()
    initial_state: AgentState = {
        "bai_hoc": bai_hoc,
        "chu_de_chi_tiet": chu_de_chi_tiet,
        "loai_cau_hoi": loai_cau_hoi.strip().upper(),
        "muc_do": muc_do,
        "use_neuro_symbolic": bool(use_neuro_symbolic),
        "avoid_snippets": list(avoid_snippets) if avoid_snippets else [],
        "used_blueprint_ids": list(used_blueprint_ids) if used_blueprint_ids else [],
        "recent_blueprint_ids": list(recent_blueprint_ids) if recent_blueprint_ids else [],
        "blueprint_id": "",
        "symbolic_skeleton": {},
        "evidence_package": dict(pre_retrieved_evidence) if isinstance(pre_retrieved_evidence, dict) else {},
        "prompt_tokens": 0,
        "question_json": {},
        "best_question_json": {},
        "best_validation": {},
        "best_score": -1.0,
        "validation_result": {},
        "feedback": "",
        "is_pass": False,
        "retry_count": 0,
        "latency_sec": 0.0,
        "log_timestamp": "",
    }
    final_state = app.invoke(initial_state)
    latency_sec = round(time.time() - t0, 2)
    final_state["latency_sec"] = latency_sec

    if not final_state["is_pass"] and final_state.get("best_question_json"):
        final_state["question_json"] = final_state["best_question_json"]
        if final_state.get("best_validation"):
            final_state["validation_result"] = final_state["best_validation"]

    val = final_state.get("validation_result", {})
    rule_pass = bool(val.get("tier1", {}).get("passed", False))
    sb_verified = bool(val.get("sandbox_verified", False))
    fuzzy_score = float(val.get("diem_chat_luong", 0.0))

    if enable_logging:
        logged = log_generation_event(
            bai_hoc=final_state["bai_hoc"],
            muc_do=final_state["muc_do"],
            loai_cau_hoi=final_state["loai_cau_hoi"],
            rule_pass=rule_pass,
            sandbox_verified=sb_verified,
            fuzzy_score=fuzzy_score,
            retry_count=final_state["retry_count"],
            latency_sec=latency_sec,
            trang_thai_duyet="CHO_DUYET",
        )
        final_state["log_timestamp"] = logged["timestamp"]

    return final_state


if __name__ == "__main__":
    print("=== KIỂM THỬ GENERATOR BƯỚC 3 (1-SHOT + CHỐNG GIỮ CHỖ + SANDBOX) ===")

    print("\n================ TEST 1: MCQ - BÀI 19 ================")
    r1 = generate_question("Bài 19: Câu lệnh rẽ nhánh if", "MCQ", muc_do="TH")
    v1 = r1["validation_result"]
    print(f"Xếp loại: {v1.get('xep_loai')} | Điểm: {v1.get('diem_chat_luong')} | Sandbox: {v1.get('sandbox_verified')} | Tokens: {r1['prompt_tokens']} | Retries: {r1['retry_count']} | Latency: {r1['latency_sec']}s")
    print(json.dumps(r1["question_json"], ensure_ascii=False, indent=2))

    print("\n================ TEST 2: TRUE_FALSE - BÀI 20 ================")
    r2 = generate_question("Bài 20: Câu lệnh lặp for", "TRUE_FALSE", muc_do="TH")
    v2 = r2["validation_result"]
    print(f"Xếp loại: {v2.get('xep_loai')} | Điểm: {v2.get('diem_chat_luong')} | Sandbox: {v2.get('sandbox_verified')} | Tokens: {r2['prompt_tokens']} | Retries: {r2['retry_count']} | Latency: {r2['latency_sec']}s")
    print(json.dumps(r2["question_json"], ensure_ascii=False, indent=2))
