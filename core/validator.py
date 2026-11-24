import ast
import keyword
import re
from typing import Any

from core.sandbox import cham_code_python

# Từ khóa ngoài phạm vi Chủ đề F lớp 10 (cấm tuyệt đối)
OUT_OF_SCOPE_TOPICS = [
    "html", "css", "<style>", "<form", "<textarea", "sql", "cơ sở dữ liệu",
    "khóa chính", "khóa ngoại", "mạng lan", "mạng máy tính", "switch",
    "địa chỉ ip", "ipv4", "https", "đạo đức số", "bắt nạt", "bản quyền",
    "sở hữu trí tuệ", "trí tuệ nhân tạo", "học máy", "thiết kế đồ họa",
    "lập trình hướng đối tượng", "đệ quy quay lui", "cây nhị phân", "đồ thị",
]

# Các hàm / cú pháp / thư viện Python vượt cấp lớp 10 (cấm dùng)
FORBIDDEN_PYTHON_PATTERNS = [
    (r"\bopen\s*\(", "Hàm open() xử lý tệp tin (vượt cấp Chủ đề F lớp 10)"),
    (r"\bimport\s+(numpy|pandas|os|sys|re|json|requests|matplotlib|torch|cv2|scipy|sklearn|sqlite3|csv|pathlib|urllib|http)\b", "Thư viện ngoài chương trình Tin học 10"),
    (r"\bfrom\s+(numpy|pandas|os|sys|re|json|requests|matplotlib|torch|cv2|scipy|sklearn|sqlite3|csv|pathlib)\b", "Thư viện ngoài chương trình Tin học 10"),
    (r"\bclass\s+[A-Za-z_]", "Lập trình hướng đối tượng (class) vượt cấp lớp 10"),
    (r"\blambda\b", "Biểu thức lambda vượt cấp SGK Tin học 10"),
    (r"\byield\b", "Generator yield vượt cấp SGK Tin học 10"),
    (r"\b(async|await)\b", "Lập trình bất đồng bộ async/await vượt cấp lớp 10"),
    (r"\b(eval|exec|__import__)\s*\(", "Hàm không an toàn eval/exec/__import__"),
]

# Cụm từ phương án nhiễu kém chất lượng trong MCQ
LAZY_DISTRACTOR_PATTERNS = [
    "tất cả đều đúng",
    "tất cả đều sai",
    "tất cả các phương án trên",
    "cả a và b",
    "cả a, b và c",
    "không có phương án nào đúng",
    "không có đáp án",
]

# Ký hiệu placeholder bị rò từ khuôn mẫu/prompt (cấm xuất hiện trong đề thi thật)
PLACEHOLDER_LEAK_PATTERNS = [
    "mẫu câu dẫn:",
    "<khái niệm",
    "<mã python",
    "<bài toán",
    "<nội dung",
    "<phương án",
    "<nhận định",
    "<giải thích",
    "<câu dẫn",
    "<1 giá trị",
    "<chép nguyên văn",
]

# Hard Gate chống phương án giữ chỗ chung chung ở mô hình 3B
# Ví dụ: "Biểu thức A", "Biểu thức B", "Phương án 1", "Đáp án A", "Câu lệnh C", "Lựa chọn 2"...
GENERIC_OPTION_REGEX = re.compile(
    r"^(?:biểu\s*thức|phương\s*án|đáp\s*án|câu\s*lệnh|lựa\s*chọn|mệnh\s*đề|kết\s*quả|nội\s*dung|giá\s*trị|lệnh)\s*[a-d1-4]\.?$",
    re.IGNORECASE,
)

# Câu hỏi cố tình đưa mã lỗi cú pháp để hỏi học sinh nhận diện lỗi (không bắt lỗi cú pháp code đề)
INTENTIONAL_SYNTAX_ERROR_CUES = [
    "lỗi cú pháp", "lỗi thụt đầu dòng", "syntaxerror", "indentationerror",
    "sai ở dòng", "không thụt", "dòng lệnh nào bị lỗi", "lỗi gì",
]

# Cụm từ tiêu đề / hoạt động của SGK cấm sao chép thô vào thân câu hỏi (cau_hoi / cau_hoi_chung)
TEXTBOOK_COPY_CUES = [
    "hoạt động 1",
    "hoạt động 2",
    "hoạt động 3",
    "sau bài này",
    "luyện tập",
    "vận dụng",
    "mục tiêu:",
    "khởi động:",
]
TEXTBOOK_HEADER_REGEX = re.compile(r"\bBÀI\s*[123]\d?\b")
TEXTBOOK_FIG_REGEX = re.compile(r"\bHình\s*(?:1[6-9]|2\d|3[0-2])(?:\.\d+)?\b", re.IGNORECASE)

# Tên biến tiếng Việt có dấu chứa dấu gạch dưới (vd: giải_thich, số_chẵn, tổng_số) - cấm tuyệt đối
_VI_ACCENT_CHARS = "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
ACCENTED_IDENTIFIER_REGEX = re.compile(
    rf"(?:\b[A-Za-z0-9{_VI_ACCENT_CHARS}]*[{_VI_ACCENT_CHARS}][A-Za-z0-9{_VI_ACCENT_CHARS}]*_[A-Za-z0-9_{_VI_ACCENT_CHARS}]*\b"
    rf"|\b[A-Za-z0-9_]+_[A-Za-z0-9{_VI_ACCENT_CHARS}]*[{_VI_ACCENT_CHARS}][A-Za-z0-9_{_VI_ACCENT_CHARS}]*\b)",
    re.IGNORECASE,
)

# Cú pháp bịa đặt kiểu C/Java ("{}") trong giải thích về câu lệnh if/khối lệnh Python
FABRICATED_IF_BRACE_REGEX = re.compile(
    r"(?:\{\s*\}|\{\s*\.\.\.\s*\})",
    re.IGNORECASE,
)

# Placeholder rỗng / chưa hoàn thiện cấm tuyệt đối lọt vào đề thi
EMPTY_PLACEHOLDER_PATTERNS = (
    "(chưa có",
    "(trống)",
    "chưa xác định",
    "(không có nội dung",
    "(không có câu dẫn",
)

# Thông báo phản hồi nội bộ của Validator bị LLM chép nhầm vào giai_thich
VALIDATOR_FEEDBACK_LEAK_CUES = (
    "đang trùng nội dung",
    "hãy sửa",
    "tầng 1",
    "hard gate",
    "bắt buộc sửa",
    "lỗi tầng 1",
)
VALIDATOR_DUP_FEEDBACK_REGEX = re.compile(r"phương\s+án\s+[a-d]\s+và\s+[a-d]\s+đang\s+trùng", re.IGNORECASE)

# Các cụm từ cụ thể dễ bị rò từ ví dụ 1-shot hoặc sai nhất quán giữa giai_thich và cau_hoi
CONSISTENCY_KEYWORD_CHECKS = [
    (r"\bnhánh\s+else\b|\bkhối\s+lệnh\s+else\b|\belse\s*:", "else", "nhánh else"),
    (r"\bvòng\s+lặp\s+while\b|\blệnh\s+while\b", "while", "vòng lặp while"),
    (r"\bvòng\s+lặp\s+for\b|\blệnh\s+for\b", "for", "vòng lặp for"),
    (r"\bhàm\s+range\b|\blệnh\s+range\b", "range", "hàm range()"),
    (r"\bphương\s+thức\s+append\b|\blệnh\s+append\b", "append", "phương thức append()"),
]

VIET_STOPWORDS = {
    "là", "và", "của", "các", "trong", "cho", "với", "được", "một", "có", "để",
    "khi", "này", "đó", "từ", "theo", "sau", "đây", "về", "hay", "hoặc", "như",
    "không", "thì", "mà", "những", "bằng", "vào", "ra", "trên", "dưới", "tại",
    "sẽ", "đã", "còn", "nếu", "câu", "lệnh", "chương", "trình", "giá", "trị",
}


def _tokenize_vi(text: str) -> set[str]:
    tokens = re.findall(r"[0-9a-zA-ZÀ-ỹ_]+", text.lower())
    return {t for t in tokens if len(t) >= 2 and t not in VIET_STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _is_python_code_line(line: str) -> bool:
    """Nhận diện một dòng văn bản có phải dòng mã nguồn Python thực thi được hay không."""
    s = line.strip()
    if not s:
        return False
    # Loại trừ dòng tiếng Việt mô tả/câu hỏi
    if s.endswith("?") or re.match(r"^(?:Cho|Hãy|Trong|Sau|Xét|Kết quả|Giá trị|Với|Nếu|Một|Biết|Câu)\b", s):
        return False
    if any(ch in s for ch in ("<điều kiện>", "<lệnh>", "<biến>", "<khối lệnh>", "<giá trị>")):
        return False
    # Các mẫu dòng mã Python chuẩn lớp 10
    py_line_patterns = [
        r"^(?:for|while|if|elif|else|def|return|print|pass|break|continue|global)\b",
        r"^[A-Za-z_][A-Za-z0-9_,\s]*\s*(?:=|\+=|-=|\*=|//=|/=|%=)\s*.+",
        r"^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*\s*\(",
        r"^[A-Za-z_][A-Za-z0-9_]*\s*\(.*\)\s*$",
    ]
    return any(re.match(p, s) for p in py_line_patterns)


def _normalize_code_mau(val: Any) -> str:
    """Chuẩn hóa dap_an_mau: nếu LLM trả về list dòng code thì tự động nối bằng '\\n' thành chuỗi sạch."""
    if isinstance(val, list):
        raw = "\n".join(str(x) for x in val)
    else:
        raw = str(val or "")
    return raw.replace("```python", "").replace("```", "").strip()


def _extract_executable_python_snippets(question_json: dict, loai: str) -> list[str]:
    """
    Trích xuất các đoạn mã Python thực thi được từ câu hỏi hoặc dap_an_mau để kiểm chứng trên Sandbox:
      1. ESSAY_CODE: luôn lấy dap_an_mau (tự nối list thành str nếu cần).
      2. Các dạng khác: trích các khối ```python ... ``` hoặc cụm dòng mã Python nhúng trong cau_hoi / cau_hoi_chung.
    """
    snippets: list[str] = []

    if loai == "ESSAY_CODE":
        code_mau = _normalize_code_mau(question_json.get("dap_an_mau", ""))
        if code_mau:
            snippets.append(code_mau)
        return snippets

    target_text = (
        str(question_json.get("cau_hoi_chung", ""))
        if loai == "TRUE_FALSE"
        else str(question_json.get("cau_hoi", ""))
    )
    if not target_text.strip():
        return []

    # Nếu đề cố tình hỏi lỗi cú pháp / lỗi thụt đầu dòng -> bỏ qua chạy Sandbox trên mã lỗi cố ý
    low = target_text.lower()
    if any(cue in low for cue in INTENTIONAL_SYNTAX_ERROR_CUES):
        return []

    # 1. Ưu tiên khối ```python ... ```
    fenced = re.findall(r"```(?:python)?\s*\n(.*?)```", target_text, re.DOTALL | re.IGNORECASE)
    for b in fenced:
        b_clean = b.strip()
        if b_clean and not ("<" in b_clean and ">" in b_clean):
            snippets.append(b_clean)
    if snippets:
        return snippets

    # 2. Trích các dòng code Python nhúng trực tiếp (tách theo \n)
    raw_lines = target_text.splitlines()
    code_lines: list[str] = []
    for raw_line in raw_lines:
        # Hỗ trợ trường hợp LLM viết "Cho đoạn chương trình Python sau: n = 5" trên cùng dòng 1
        m_inline = re.match(r"^(?:Cho\s+đoạn\s+(?:chương\s+trình|lệnh).*?:\s*)(.+)$", raw_line.strip(), re.IGNORECASE)
        candidate = m_inline.group(1) if m_inline else raw_line
        if _is_python_code_line(candidate):
            code_lines.append(candidate.rstrip())
        elif code_lines:
            # Kết thúc cụm code khi gặp câu hỏi tiếng Việt phía sau
            break

    # Chỉ chạy Sandbox khi cụm code có ít nhất 2 dòng (hoặc có lệnh print/for/while/if/def)
    if len(code_lines) >= 2 or (len(code_lines) == 1 and re.match(r"^(?:print|for|while|if|def)\b", code_lines[0].strip())):
        # Chuẩn hóa lề chung (dedent) nếu dòng đầu bị thụt thừa
        min_indent = min((len(l) - len(l.lstrip())) for l in code_lines if l.strip())
        dedented = "\n".join(l[min_indent:] if len(l) >= min_indent else l for l in code_lines).strip()
        if dedented and not ("<" in dedented and ">" in dedented):
            snippets.append(dedented)

    return snippets


def _run_sandbox_verification(snippets: list[str]) -> tuple[bool, bool, list[str], str]:
    """
    Kiểm chứng AST + chạy thực tế trên core/sandbox.py (timeout_sec=2.0).
    Trả về: (has_code, all_passed, error_messages, last_stdout)
    """
    if not snippets:
        return False, True, [], ""

    errors: list[str] = []
    last_stdout = ""
    for idx, code in enumerate(snippets, 1):
        # Kiểm tra cú pháp AST trước
        try:
            ast.parse(code)
        except SyntaxError as e:
            errors.append(
                f"Lỗi cú pháp Python (Sandbox/AST) ở đoạn mã #{idx} dòng {e.lineno}: {e.msg}. Hãy sửa đúng thụt lề và dấu hai chấm (:)."
            )
            continue

        # Chạy thực tế trên Sandbox cô lập với timeout 2.0s
        dummy_stdin = "5\n10\n2\n3\n4\n" if "input(" in code else ""
        sb = cham_code_python(code, test_input=dummy_stdin, timeout_sec=2.0)
        if sb.get("trang_thai") != "THÀNH CÔNG":
            stderr_msg = (sb.get("loi_he_thong") or sb.get("trang_thai") or "Lỗi thực thi").strip()
            errors.append(
                f"Mã Python chạy lỗi trên Sandbox ({sb.get('trang_thai')}): {stderr_msg[:220]}"
            )
        else:
            last_stdout = sb.get("ket_qua_in_ra", "")

    return True, len(errors) == 0, errors, last_stdout


def _flatten_question_text(q: dict, loai: str) -> str:
    parts: list[str] = []
    if loai == "MCQ":
        for k in ("cau_hoi", "A", "B", "C", "D", "giai_thich", "trich_dan_sgk"):
            parts.append(str(q.get(k, "")))
    elif loai == "TRUE_FALSE":
        parts.append(str(q.get("cau_hoi_chung", "")))
        parts.append(str(q.get("trich_dan_sgk", "")))
        for k in ("a", "b", "c", "d"):
            item = q.get(k) or {}
            if isinstance(item, dict):
                parts.append(str(item.get("menh_de", "")))
                parts.append(str(item.get("giai_thich", "")))
    elif loai == "SHORT_ANSWER":
        for k in ("cau_hoi", "dap_an_ngan", "giai_thich", "trich_dan_sgk"):
            parts.append(str(q.get(k, "")))
    elif loai == "ESSAY_CODE":
        for k in ("tinh_huong", "yeu_cau_hoc_sinh", "dap_an_mau", "trich_dan_sgk"):
            parts.append(str(q.get(k, "")))
        tc = q.get("tieu_chi_cham_diem", [])
        if isinstance(tc, list):
            parts.extend(str(x) for x in tc)
    return "\n".join(parts)


def _normalize_tf_answer(val: Any) -> str:
    s = str(val).strip().lower()
    if s in ("đúng", "dung", "true", "đ", "d"):
        return "Đúng"
    if s in ("sai", "false", "s"):
        return "Sai"
    return ""


def _check_stem_not_raw_textbook(stem: str, has_code: bool) -> list[str]:
    """Chặn sao chép thô đoạn văn/tiêu đề hoạt động SGK vào thân câu hỏi."""
    errs: list[str] = []
    s = str(stem or "").strip()
    s_low = s.lower()

    for cue in TEXTBOOK_COPY_CUES:
        if cue in s_low:
            errs.append(
                f"Thân câu hỏi sao chép thô cụm từ SGK ('{cue}'). Hãy viết lại câu hỏi ngắn gọn, súc tích đúng chuẩn đề thi."
            )
            break

    m_hdr = TEXTBOOK_HEADER_REGEX.search(s)
    if m_hdr:
        errs.append(
            f"Thân câu hỏi chứa tiêu đề bài học SGK ('{m_hdr.group(0)}'). Cấm chép nguyên đoạn SGK vào đề bài."
        )

    m_fig = TEXTBOOK_FIG_REGEX.search(s)
    if m_fig:
        errs.append(
            f"Thân câu hỏi chứa chú thích hình ảnh SGK ('{m_fig.group(0)}'). Đề thi không có hình minh họa SGK, phải viết câu hỏi độc lập."
        )

    if "Bảng " in s:
        errs.append(
            "Thân câu hỏi chứa chú thích bảng SGK ('Bảng '). Đề thi phải tự cung cấp đủ dữ liệu, không tham chiếu bảng trong SGK."
        )

    if "công thức heron" in s_low:
        errs.append(
            "Thân câu hỏi chứa rác gợi ý SGK ('Công thức Heron'). Bắt buộc xóa bỏ và viết đề bài ngắn gọn, đúng trọng tâm bài học."
        )

    if re.match(r"^liệu\s+có\b", s_low):
        errs.append(
            "Thân câu hỏi mở đầu bằng mẫu câu cấm ('Liệu có...'). Hãy đặt câu hỏi khảo thí trực tiếp, tường minh."
        )

    # Chống nối mảnh vụn / gộp 2 yêu cầu tách rời / văn bản giải thích & dấu '= ?' lọt vào đề
    m_frag = re.search(r"\b(?:gợi\s+ý|câu\s+hỏi)\s*:", s, re.IGNORECASE)
    if m_frag:
        errs.append(
            f"Thân câu hỏi còn sót nhãn mảnh vụn ('{m_frag.group(0)}'). Hãy viết thành một câu dẫn duy nhất, liền mạch."
        )

    m_leak_exp = re.search(r"(?:giả\s*thich|giai\s*thich|giả\s*thích|bước\s*1\s*:)", s_low)
    if m_leak_exp:
        errs.append(
            f"Thân câu hỏi bị lọt văn bản giải thích/gợi ý bước làm ('{m_leak_exp.group(0)}'). Đề bài chỉ được chứa câu dẫn và đoạn mã Python sạch."
        )

    if re.search(r"=\s*\?", s):
        errs.append(
            "Đoạn mã trong thân câu hỏi chứa cú pháp lỗi '= ?' (dấu hỏi chấm lọt vào lệnh gán Python). Hãy sửa thành câu lệnh Python hợp lệ."
        )

    if "viết lệnh find()" in s_low and (s_low.count("?") >= 1 or "cho đoạn" in s_low or "kết quả" in s_low):
        errs.append(
            "Thân câu hỏi bị nối ghép 2 yêu cầu tách rời ('Viết lệnh find()' dính vào câu hỏi khác). Chỉ đặt duy nhất 1 yêu cầu rõ ràng."
        )

    # Đếm số dấu '?' ngoài chuỗi nháy để chặn gộp 2 câu hỏi độc lập vào 1 thân đề
    s_no_quotes = re.sub(r"(['\"]).*?\1", "", s)
    if s_no_quotes.count("?") >= 2:
        errs.append(
            "Thân câu hỏi chứa từ 2 câu hỏi tách rời trở lên (nhiều dấu '?'). Hãy giữ duy nhất 1 yêu cầu khảo thí thống nhất."
        )

    if len(s) > 380 and not has_code:
        errs.append(
            f"Thân câu hỏi quá dài ({len(s)} ký tự > 380 ký tự) mà không có đoạn mã Python, có dấu hiệu chép thô lý thuyết SGK. Hãy tóm gọn thành 1-2 câu hỏi rõ ràng."
        )
    return errs


def _check_explanation_consistency(stem_and_opts: str, explanation: str) -> list[str]:
    """Kiểm tra tính nhất quán giữa cau_hoi (+ phương án) và giai_thich, chống rò từ khóa 1-shot hoặc phản hồi nội bộ Validator."""
    errs: list[str] = []
    ctx_low = str(stem_and_opts or "").lower()
    exp_str = str(explanation or "")
    exp_low = exp_str.lower()

    if not exp_low.strip():
        return errs

    # 0. Cấm rò thông báo phản hồi nội bộ của Validator vào giai_thich
    if VALIDATOR_DUP_FEEDBACK_REGEX.search(exp_str) or any(cue in exp_low for cue in VALIDATOR_FEEDBACK_LEAK_CUES):
        errs.append(
            "Trường 'giai_thich' chứa thông báo phản hồi nội bộ của hệ thống kiểm định ('Hãy sửa' / 'Tầng 1' / 'đang trùng'). "
            "Hãy viết giải thích thuần túy về kiến thức lập trình Python."
        )

    # 0b. Cấm cú pháp bịa đặt ("{}") khi giải thích câu lệnh if / rẽ nhánh Python
    if FABRICATED_IF_BRACE_REGEX.search(exp_str) and any(
        k in exp_low for k in ("if", "else", "rẽ nhánh", "khối lệnh", "cú pháp")
    ):
        errs.append(
            "Giải thích chứa cú pháp bịa đặt ('{}') cho câu lệnh if/khối lệnh Python. Python dùng dấu hai chấm (:) và thụt lề, không dùng cặp ngoặc nhọn '{}'."
        )

    # 1. Kiểm tra các từ khóa lệnh/nhánh đặc trưng được nhắc trong giải thích nhưng vắng mặt trong đề + phương án
    for pattern, required_kw, label in CONSISTENCY_KEYWORD_CHECKS:
        if re.search(pattern, exp_low) and required_kw not in ctx_low:
            errs.append(
                f"Giải thích không nhất quán với đề bài: nhắc tới '{label}' nhưng '{required_kw}' không hề xuất hiện trong câu hỏi hoặc các phương án."
            )

    # 2. Chặn rò kết quả in ra mẫu từ ví dụ 1-shot hoặc chuỗi in ra không có trong đề/phương án
    for m in re.finditer(r"in\s+ra\s+['\"`]([^'\"`]{1,25})['\"`]", exp_str, re.IGNORECASE):
        printed_lit = m.group(1).strip()
        if printed_lit and printed_lit.lower() not in ctx_low:
            errs.append(
                f"Giải thích không nhất quán với đề bài: nhắc tới kết quả in ra '{printed_lit}' nhưng giá trị này không tồn tại trong câu hỏi hoặc các phương án."
            )

    # 3. Chặn rò phép tính/nhãn đặc trưng của ví dụ 1-shot ('in ra le', 'in ra chan', '7 % 2') khi đề không có
    for leaked_cue, required_token in (("in ra le", "le"), ("in ra chan", "chan"), ("7 % 2", "7")):
        if leaked_cue in exp_low and required_token not in ctx_low:
            errs.append(
                f"Giải thích bị rò nội dung từ ví dụ mẫu ('{leaked_cue}') không có trong câu hỏi hiện tại. Hãy giải thích bám sát đúng các biến/lệnh trong đề."
            )

    return errs


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


def _compute_sgk_citation_overlap(trich_dan: str, evidence_package: dict) -> float:
    """Tính tỷ lệ trùng từ vựng (0.0 - 1.0) giữa trich_dan_sgk và bằng chứng SGK/Glossary."""
    cite = _clean_sgk_citation(str(trich_dan or "").strip())
    if len(cite) < 15:
        return 0.0
    ev_text = " ".join(c.get("content", "") for c in evidence_package.get("sgk_chunks", []))
    ev_text += " " + " ".join(g.get("dinh_nghia_sgk", "") for g in evidence_package.get("glossary_terms", []))
    ev_tokens = _tokenize_vi(ev_text)
    cite_tokens = _tokenize_vi(cite) - {"python"}
    if not ev_tokens or not cite_tokens:
        return 0.0
    return len(cite_tokens & ev_tokens) / len(cite_tokens)


def _extract_verbatim_sgk_sentences(evidence_package: dict, max_sentences: int = 2) -> list[str]:
    """Trích xuất tự động 1-2 câu nguyên văn tiêu biểu từ evidence_package['sgk_chunks'] để gợi ý hoặc auto-grounding."""
    results: list[str] = []
    chunks = evidence_package.get("sgk_chunks", [])
    for ch in chunks:
        content = str(ch.get("content", "")).strip()
        for sent in re.split(r"(?<=[.!?])\s+|\n", content):
            s = re.sub(r"\s+", " ", sent).strip(" •-–")
            if 40 <= len(s) <= 170 and not s.endswith("?") and s not in results:
                results.append(s)
                if len(results) >= max_sentences:
                    return results
    # Dự phòng 1: lấy câu đầu tiên từ sgk_chunks[0] (25..200 ký tự) nếu chunk không có câu 40..170
    if not results and chunks:
        raw_first = re.sub(r"\s+", " ", str(chunks[0].get("content", "")).strip()).strip(" •-–")
        for sent in re.split(r"(?<=[.!?])\s+", raw_first):
            s = sent.strip(" •-–")
            if len(s) >= 25 and not s.endswith("?"):
                results.append(s[:170].rstrip())
                break
        if not results and len(raw_first) >= 20:
            results.append(raw_first[:160].rstrip())
    # Dự phòng 2: lấy từ glossary nếu chunk rỗng
    for g in evidence_package.get("glossary_terms", []):
        d = str(g.get("dinh_nghia_sgk", "")).strip()
        if d and d not in results:
            results.append(d[:170])
            if len(results) >= max_sentences:
                break
    return results


# Khóa đối chiếu nội dung cốt lõi của các bài trọng tâm (tránh lạc đề khi mô hình 3B copy nhầm 1-shot)
LESSON_CORE_SIGNATURES: dict[str, tuple[list[str], str]] = {
    "Bài 17": (["biến", "gán", "=", "từ khoá", "từ khóa"], "Bài 17 phải liên quan đến biến, lệnh gán (=) hoặc từ khoá."),
    "Bài 19": (["if", "else", "elif", "rẽ nhánh", "lôgic", "logic", "true", "false"], "Bài 19 phải sử dụng biểu thức lôgic hoặc câu lệnh rẽ nhánh if/if-else."),
    "Bài 20": (["for", "range", "lặp"], "Bài 20 phải sử dụng câu lệnh lặp for và vùng giá trị range()."),
    "Bài 21": (["while", "lặp"], "Bài 21 phải sử dụng câu lệnh lặp while."),
    "Bài 22": (["danh sách", "list", "[", "append", "len("], "Bài 22 phải sử dụng kiểu dữ liệu danh sách (list / dấu ngoặc vuông [])."),
    "Bài 26": (["def ", "hàm", "return", "abs(", "len(", "type(", "round("], "Bài 26 phải liên quan đến hàm trong Python (định nghĩa hàm bằng def hoặc hàm thiết kế sẵn)."),
}


# ==============================================================================
# KIỂM CHỨNG ĐÁP ÁN THỰC THI (EXECUTION-GROUNDED ANSWER)
# ==============================================================================

_NON_OUTPUT_QUESTION_CUES = (
    "kiểu dữ liệu",
    "bao nhiêu lần",
    "số lần lặp",
    "dòng lệnh nào",
    "lỗi gì",
    "lỗi cú pháp",
    "tên hàm",
    "tên biến",
    "tham số",
)

_OUTPUT_QUESTION_CUES = (
    "kết quả",
    "in ra",
    "màn hình",
    "hiển thị",
    "xuất ra",
    "output",
    "giá trị",
)

_PY_BUILTIN_AND_KW = {
    "true", "false", "none", "and", "or", "not", "in", "is",
    "print", "input", "range", "len", "int", "str", "float", "bool",
    "list", "append", "insert", "pop", "remove", "sort", "split", "join", "find",
    "for", "while", "if", "else", "elif", "def", "return", "pass", "break", "continue",
    "abs", "round", "type", "sum", "max", "min", "global",
}


def _norm_output_val(val: str) -> str:
    s = re.sub(r"\s+", " ", str(val or "").strip())
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"', "`"):
        s = s[1:-1].strip()
    return s


def _extract_tf_claimed_output(menh_de: str) -> str | None:
    """
    Trích xuất giá trị đầu ra <X> nếu mệnh đề TRUE_FALSE khẳng định trực tiếp kết quả in ra màn hình
    (VD: 'Kết quả in ra màn hình là 15.', 'Chương trình in ra 'Dat'.', 'In ra 14').
    Bỏ qua câu giả định ('Nếu thay...', 'Khi đổi...') hoặc câu phủ định ('không in ra...').
    """
    md = str(menh_de or "").strip()
    md_low = md.lower()
    if not md:
        return None
    # Bỏ qua câu giả định thay đổi code hoặc câu phủ định
    if re.search(r"\b(?:nếu\s+thay|nếu\s+sửa|nếu\s+đổi|khi\s+thay|giả\s+sử|nếu\s+thêm|nếu\s+bỏ)\b", md_low):
        return None
    if re.search(r"\b(?:không\s+in\s+ra|không\s+hiển\s+thị|không\s+xuất\s+ra|khác|không\s+phải\s+là)\b", md_low):
        return None

    patterns = [
        r"kết\s+quả\s+in\s+ra(?:\s+màn\s+hình)?\s*(?:là|bằng|=|:)\s*(.+?)(?:[.;,]|$)",
        r"in\s+ra(?:\s+màn\s+hình)?\s*(?:là|bằng|=|:)\s*(.+?)(?:[.;,]|$)",
        r"kết\s+quả(?:\s+cuối\s+cùng|\s+của\s+chương\s+trình|\s+của\s+đoạn\s+mã)?\s*(?:là|bằng|=|:)\s*(.+?)(?:[.;,]|$)",
        r"(?:chương\s+trình|đoạn\s+mã|đoạn\s+lệnh|màn\s+hình)\s+(?:in\s+ra|hiển\s+thị|xuất\s+ra)(?:\s+màn\s+hình)?(?:\s+giá\s+trị|\s+kết\s+quả|\s+xâu|\s+số|\s+là)?\s*(.+?)(?:[.;,]|$)",
        r"\bin\s+ra(?:\s+màn\s+hình)?(?:\s+giá\s+trị|\s+kết\s+quả|\s+là)?\s+([`'\"][^`'\"]+[`'\"]|-?\d+(?:\.\d+)?)(?:[.;,\s]|$)",
    ]
    for pat in patterns:
        m = re.search(pat, md, re.IGNORECASE)
        if m:
            raw_val = m.group(1).strip()
            # Cắt phần giải thích phụ sau 'và', 'khi', 'vì' nếu có
            raw_val = re.split(r"\s+(?:và|khi|vì|do|nên|ở|sau)\b", raw_val, maxsplit=1, flags=re.IGNORECASE)[0].strip()
            raw_val = raw_val.rstrip(".,;:")
            # Chỉ xét khi giá trị trích ra ngắn gọn kiểu kết quả in ra (số, chuỗi, danh sách ngắn)
            if raw_val and len(raw_val) <= 35:
                # Loại trừ cụm mô tả chung không phải giá trị cụ thể (VD: "các số chẵn", "một danh sách", "giá trị của biến")
                rv_low = raw_val.lower()
                if any(
                    desc in rv_low
                    for desc in ("các số", "một ", "giá trị của", "biến ", "danh sách các", "lỗi", "không có")
                ):
                    return None
                return raw_val
    return None


def _check_execution_grounded_answer(question_json: dict, loai: str, sandbox_stdout: str) -> list[str]:
    """
    Execution-Grounded Answer Verification:
      - SHORT_ANSWER / MCQ có mã Python chứa print(...): so sánh đáp án đã khai báo với stdout thực tế từ Sandbox.
      - TRUE_FALSE có mã Python chứa print(...): nếu bất kỳ ý a, b, c, d nào khẳng định 'Kết quả in ra màn hình là <X>'
        hoặc 'in ra <X>', kiểm tra <X> với stdout thật: khớp -> bắt buộc 'Đúng', khác -> bắt buộc 'Sai'.
    """
    errs: list[str] = []
    actual_out = sandbox_stdout.strip()
    if not actual_out:
        return errs

    actual_norm = _norm_output_val(actual_out)
    actual_norm_low = actual_norm.lower()

    if loai == "TRUE_FALSE":
        for k in ("a", "b", "c", "d"):
            item = question_json.get(k)
            if not isinstance(item, dict):
                continue
            md = str(item.get("menh_de", "")).strip()
            declared_lbl = _normalize_tf_answer(item.get("dap_an", ""))
            if not md or not declared_lbl:
                continue
            claimed_x = _extract_tf_claimed_output(md)
            if claimed_x is None:
                continue
            claimed_norm_low = _norm_output_val(claimed_x).lower()
            expected_lbl = "Đúng" if claimed_norm_low == actual_norm_low else "Sai"
            if declared_lbl != expected_lbl:
                if claimed_norm_low != actual_norm_low:
                    errs.append(
                        f"Sai lệch thực thi Sandbox ở ý '{k}' (TRUE_FALSE): "
                        f"Kết quả thực thi thật của Python là {actual_out}, không phải {claimed_x} "
                        f"(nhãn bắt buộc là 'Sai', hiện ghi '{declared_lbl}')."
                    )
                else:
                    errs.append(
                        f"Sai lệch thực thi Sandbox ở ý '{k}' (TRUE_FALSE): "
                        f"Kết quả thực thi thật của Python là {actual_out}, khớp với mệnh đề '{claimed_x}' "
                        f"(nhãn bắt buộc là 'Đúng', hiện ghi '{declared_lbl}')."
                    )
        return errs

    cau_hoi_low = str(question_json.get("cau_hoi", "")).lower()
    if any(cue in cau_hoi_low for cue in _NON_OUTPUT_QUESTION_CUES):
        return errs

    if loai == "SHORT_ANSWER":
        claimed = str(question_json.get("dap_an_ngan", "")).strip()
        claimed_norm = _norm_output_val(claimed)
        if claimed and claimed_norm.lower() != actual_norm_low:
            errs.append(
                f"Đáp án '{claimed}' không khớp với kết quả thực tế chạy code "
                f"(stdout thực = '{actual_out}'). Sửa lại dap_an_ngan thành '{actual_out}'."
            )

    elif loai == "MCQ":
        dap_an_key = str(question_json.get("dap_an", "")).strip().upper()
        if dap_an_key not in ("A", "B", "C", "D"):
            return errs

        opts_map = {k: str(question_json.get(k, "")).strip() for k in ("A", "B", "C", "D")}
        claimed_opt = opts_map[dap_an_key]
        asks_output = any(cue in cau_hoi_low for cue in _OUTPUT_QUESTION_CUES)
        any_opt_matches = any(
            actual_norm_low == _norm_output_val(v).lower()
            for v in opts_map.values()
            if v
        )
        if not asks_output and not any_opt_matches:
            return errs

        if claimed_opt and len(claimed_opt) <= 50:
            claimed_norm_low = _norm_output_val(claimed_opt).lower()
            # Cho phép khớp chính xác hoặc chứa rõ giá trị stdout (VD: "s = 10" khi stdout="10")
            matched = (
                claimed_norm_low == actual_norm_low
                or re.search(rf"(?<![0-9a-zA-Z_]){re.escape(actual_norm_low)}(?![0-9a-zA-Z_])", claimed_norm_low) is not None
            )
            if not matched:
                errs.append(
                    f"Đáp án MCQ khai báo là {dap_an_key}='{claimed_opt}' nhưng "
                    f"kết quả thực tế chạy code là '{actual_out}'. "
                    f"Hãy sửa lại phương án hoặc chọn lại dap_an cho khớp stdout thực ('{actual_out}')."
                )
    return errs


def _check_true_false_explanations(question_json: dict) -> list[str]:
    """
    Kiểm tra TRUE_FALSE:
      1. Chặn 2 ý có giai_thich trùng lặp nhau (normalized).
      2. Chặn giai_thich nhắc tường minh tới tên biến không tồn tại trong đoạn mã cau_hoi_chung.
    """
    errs: list[str] = []
    stem = str(question_json.get("cau_hoi_chung", ""))

    # Thu thập toàn bộ tên biến / hàm hợp lệ xuất hiện trong cau_hoi_chung
    code_vars: set[str] = set()
    code_vars.update(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*(?:=|\+=|-=|\*=|//=|/=|%=)", stem))
    code_vars.update(re.findall(r"\bfor\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\b", stem))
    for fn_name, params in re.findall(r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)", stem):
        code_vars.add(fn_name)
        for p in params.split(","):
            p_name = p.strip().split("=")[0].strip()
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", p_name):
                code_vars.add(p_name)

    stem_words = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", stem))
    allowed_names_low = {v.lower() for v in (code_vars | stem_words)} | _PY_BUILTIN_AND_KW

    keys = ("a", "b", "c", "d")
    explanations: dict[str, str] = {}
    for k in keys:
        item = question_json.get(k)
        if isinstance(item, dict):
            gt = str(item.get("giai_thich", "")).strip()
            explanations[k] = gt

    # 1. Trùng lặp giai_thich giữa các ý a/b/c/d
    norm_map: dict[str, str] = {
        k: re.sub(r"\s+", " ", v.lower()).rstrip(".") for k, v in explanations.items() if v
    }
    for idx1, k1 in enumerate(keys):
        for k2 in keys[idx1 + 1:]:
            if k1 in norm_map and k2 in norm_map and norm_map[k1] == norm_map[k2]:
                errs.append(
                    f"Giải thích ý '{k1}' và '{k2}' bị trùng lặp. "
                    f"Mỗi ý phải có lời giải thích riêng biệt."
                )

    # 2. Nhắc tường minh biến không tồn tại trong code (chỉ khi đề có khai báo biến/hàm rõ ràng)
    if code_vars:
        for k, gt in explanations.items():
            if not gt:
                continue
            explicit_refs: set[str] = set()
            # Mẫu 1: "biến x", "biến 'x'", "biến `tong`"
            for m in re.finditer(r"\bbiến\s+[`'\"]([A-Za-z_][A-Za-z0-9_]*)[`'\"]", gt, re.IGNORECASE):
                explicit_refs.add(m.group(1))
            for m in re.finditer(r"\bbiến\s+([A-Za-z_][A-Za-z0-9_]*)\b", gt, re.IGNORECASE):
                cand = m.group(1)
                # Bỏ qua từ tiếng Việt phổ biến sau chữ "biến" (vd: "biến này", "biến đó", "biến cục", "biến toàn", "biến đếm")
                if cand.lower() not in {"nay", "do", "cuc", "toan", "dem", "nho", "tam", "so", "moi", "sau", "khi", "co", "duoc", "la", "va", "se", "da", "bi"}:
                    explicit_refs.add(cand)
            # Mẫu 2: biểu thức gán/so sánh tường minh trong giải thích (vd: "k = 5", "n > 0")
            for m in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*(?:==|!=|<=|>=|\+=|-=|\*=|=\s*[-0-9'\"\[])", gt):
                explicit_refs.add(m.group(1))

            missing_vars = [v for v in sorted(explicit_refs) if v.lower() not in allowed_names_low]
            if missing_vars:
                errs.append(
                    f"Giải thích ý '{k}' nhắc tới biến '{missing_vars[0]}' "
                    f"không tồn tại trong đoạn mã câu hỏi chung. "
                    f"Hãy viết giai_thich bám sát đúng các biến trong đề ({', '.join(sorted(code_vars))})."
                )
    return errs


# ==============================================================================
# CÁC HARD GATE MỚI: CHỐNG SAO CHÉP 1-SHOT, THIẾU CODE, BIẾN CHƯA KHỞI TẠO & ĐƠN TRỊ
# ==============================================================================

ONESHOT_REUSE_PATTERNS = [
    (r"['\"]\s*chan\s*['\"]", "chuỗi mẫu 1-shot 'Chan'"),
    (r"['\"]\s*le\s*['\"]", "chuỗi mẫu 1-shot 'Le'"),
    (r"\bx\s*=\s*7\b", "dữ liệu mẫu 1-shot 'x = 7'"),
    (r"\brange\s*\(\s*1\s*,\s*5\s*\)", "vùng lặp mẫu 1-shot 'range(1, 5)'"),
    (r"\[\s*7\s*,\s*4\s*,\s*9\s*,\s*6\s*,\s*8\s*\]", "danh sách mẫu 1-shot '[7, 4, 9, 6, 8]'"),
]

NONSENSE_ENGLISH_REGEX = re.compile(r"\bopposite\b", re.IGNORECASE)

SINGLE_LINE_COMPOUND_CODE_REGEX = re.compile(
    r"\b(?:while|for|if|elif|else|def)\b[^\n:]*:[ \t]*(?:[A-Za-z_][A-Za-z0-9_]*[ \t]*(?:=|\+=|-=|\*=|//=|/=|%=)|print[ \t]*\(|return\b|pass\b|break\b|continue\b)"
)

_RESULT_REQUIRING_CODE_CUES = (
    "kết quả in ra",
    "kết quả của đoạn",
    "đoạn chương trình sau",
    "đoạn mã sau",
    "đoạn lệnh sau",
    "giá trị in ra",
    "giá trị của biến",
    "giá trị của biểu thức",
    "chương trình trên in ra",
    "chương trình sau in ra",
)


def _flatten_body_without_citation(q: dict, loai: str) -> str:
    """Gom nội dung câu hỏi KHÔNG tính trường trich_dan_sgk để kiểm tra chống lặp 1-shot & ràng buộc bài học."""
    parts: list[str] = []
    if loai == "MCQ":
        for k in ("cau_hoi", "A", "B", "C", "D", "giai_thich"):
            parts.append(str(q.get(k, "")))
    elif loai == "TRUE_FALSE":
        parts.append(str(q.get("cau_hoi_chung", "")))
        for k in ("a", "b", "c", "d"):
            item = q.get(k) or {}
            if isinstance(item, dict):
                parts.append(str(item.get("menh_de", "")))
                parts.append(str(item.get("giai_thich", "")))
    elif loai == "SHORT_ANSWER":
        for k in ("cau_hoi", "dap_an_ngan", "giai_thich"):
            parts.append(str(q.get(k, "")))
    elif loai == "ESSAY_CODE":
        for k in ("tinh_huong", "yeu_cau_hoc_sinh", "dap_an_mau"):
            parts.append(str(q.get(k, "")))
        tc = q.get("tieu_chi_cham_diem", [])
        if isinstance(tc, list):
            parts.extend(str(x) for x in tc)
    return "\n".join(parts)


def _check_oneshot_and_format_quality(question_json: dict, loai: str) -> list[str]:
    """Chặn sao chép dữ liệu 1-shot cũ, từ tiếng Anh vô nghĩa ('Opposite') và code dính 1 dòng."""
    errs: list[str] = []
    body_text = _flatten_body_without_citation(question_json, loai)

    # 1. Cấm sao chép dữ liệu mẫu 1-shot cũ
    for pat, label in ONESHOT_REUSE_PATTERNS:
        if re.search(pat, body_text, re.IGNORECASE):
            errs.append(
                f"Câu hỏi tái sử dụng nguyên văn {label} từ ví dụ 1-shot. "
                "Bắt buộc dùng tên biến và dữ liệu mới từ mục HẠT GIỐNG DỮ LIỆU MỚI."
            )
            break

    if loai == "MCQ":
        opts_clean = [str(question_json.get(k, "")).strip().strip("'\"").lower() for k in ("A", "B", "C", "D")]
        if "chan" in opts_clean and "le" in opts_clean:
            errs.append(
                "Các phương án MCQ tái sử dụng cặp nhãn mẫu 1-shot 'Chan'/'Le'. "
                "Hãy tạo bài toán và bộ nhãn/dữ liệu hoàn toàn mới."
            )

    # 2. Cấm từ tiếng Anh vô nghĩa ("Opposite")
    if NONSENSE_ENGLISH_REGEX.search(body_text):
        errs.append("Phát hiện từ tiếng Anh vô nghĩa ('Opposite') trong nội dung câu hỏi. Bắt buộc viết 100% tiếng Việt chuẩn.")

    # 2b. Cấm tên biến tiếng Việt có dấu chứa gạch dưới (vd: giải_thich, số_, tổng_số)
    m_acc = ACCENTED_IDENTIFIER_REGEX.search(body_text)
    if m_acc:
        errs.append(
            f"Phát hiện tên biến/định danh tiếng Việt có dấu ('{m_acc.group(0)}'). "
            "Tên biến/hàm Python bắt buộc viết không dấu (ASCII thuần, VD: tong, dem, ket_qua)."
        )

    # 3. Cấm code dính liền trên 1 dòng (vd: while x < 5: x += 2)
    code_holder = (
        str(question_json.get("cau_hoi_chung", ""))
        if loai == "TRUE_FALSE"
        else str(question_json.get("dap_an_mau", ""))
        if loai == "ESSAY_CODE"
        else str(question_json.get("cau_hoi", ""))
    )
    if SINGLE_LINE_COMPOUND_CODE_REGEX.search(code_holder):
        errs.append(
            "Đoạn mã Python bị viết dính liền trên 1 dòng (ví dụ 'while ...: ... = ...'). "
            "Bắt buộc xuống dòng (\\n) và thụt lề 4 dấu cách cho thân khối lệnh."
        )

    return errs


def _find_undefined_vars_in_ast(code: str) -> list[str]:
    """Phân tích AST tìm các biến được đọc (Load) khi chưa từng được gán/định nghĩa (Store/Param/FunctionDef)."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    defined: set[str] = set(dir(__builtins__)) if isinstance(__builtins__, dict) else set(dir(__builtins__))
    defined.update(_PY_BUILTIN_AND_KW)
    undefined: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined.add(node.name)
            for arg in node.args.args:
                defined.add(arg.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            defined.add(node.id)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                defined.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                defined.add(alias.asname or alias.name)

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id not in defined and node.id not in undefined:
                undefined.append(node.id)
    return undefined


def _check_missing_code_or_uninit_var(question_json: dict, loai: str, snippets: list[str]) -> list[str]:
    """
    Kiểm tra:
      1. Câu hỏi tính giá trị biểu thức/code bắt buộc phải có đoạn mã hoặc biểu thức cụ thể trong đề.
      2. Không được hỏi kết quả của biến chưa được khởi tạo giá trị trong đề/code.
    """
    errs: list[str] = []
    if loai == "ESSAY_CODE":
        return errs

    stem = str(question_json.get("cau_hoi_chung", "") if loai == "TRUE_FALSE" else question_json.get("cau_hoi", "")).strip()
    stem_low = stem.lower()

    # 1. Hỏi kết quả chạy code/biểu thức nhưng thiếu mã nguồn hoặc biểu thức cụ thể
    asks_eval = any(cue in stem_low for cue in _RESULT_REQUIRING_CODE_CUES)
    has_concrete_expr = bool(snippets) or bool(
        re.search(
            r"([A-Za-z_][A-Za-z0-9_]*\s*=|\d+\s*(?:\*\*|//|[+\-*/%])\s*\d+|print\s*\(|range\s*\(|\[[^\]]+\]|\bdef\s+|['\"][^'\"]+['\"]\s*[+\[])",
            stem,
        )
    )
    if asks_eval and not has_concrete_expr:
        errs.append(
            "Câu hỏi yêu cầu tính giá trị biểu thức hoặc kết quả chạy code nhưng thiếu đoạn mã Python/giá trị cụ thể trong đề bài."
        )
        return errs

    # 2. Kiểm tra biến chưa được khởi tạo trong AST của snippet
    for sn in snippets:
        undef_vars = _find_undefined_vars_in_ast(sn)
        if undef_vars:
            errs.append(
                f"Đoạn mã Python sử dụng biến chưa được khởi tạo giá trị ('{undef_vars[0]}'). "
                "Bắt buộc gán giá trị cụ thể cho mọi biến trước khi dùng."
            )
            return errs

    # 3. Kiểm tra đề bài hỏi trực tiếp "giá trị của biến X" nhưng X chưa từng được gán trong đề
    defined_in_stem: set[str] = set()
    defined_in_stem.update(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*(?:=|\+=|-=|\*=|//=|/=|%=)", stem))
    defined_in_stem.update(re.findall(r"\bfor\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\b", stem))
    for fn_name, params in re.findall(r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)", stem):
        defined_in_stem.add(fn_name)
        for p in params.split(","):
            pn = p.strip().split("=")[0].strip()
            if pn:
                defined_in_stem.add(pn)

    for m in re.finditer(
        r"(?:giá\s+trị\s+(?:của\s+)?biến|kết\s+quả\s+(?:của\s+)?biến)\s+[`'\"]?([A-Za-z_][A-Za-z0-9_]*)[`'\"]?",
        stem,
        re.IGNORECASE,
    ):
        asked_var = m.group(1)
        if asked_var.lower() in {"sau", "khi", "nao", "nay", "do", "la", "trong", "cua", "co", "duoc", "nhu"}:
            continue
        if asked_var not in defined_in_stem:
            errs.append(
                f"Câu hỏi hỏi kết quả của biến '{asked_var}' nhưng biến '{asked_var}' chưa được khởi tạo giá trị trong đề bài."
            )
            break

    return errs


def _check_single_answer_mcq(cau_hoi: str, opts: list[str]) -> list[str]:
    """
    Kiểm tra tính đơn trị (Single-answer) cho MCQ:
      - Câu hỏi 'lệnh gán / câu lệnh nào sau đây đúng cú pháp / hợp lệ': dùng ast.parse() trên 4 phương án,
        nếu có >= 2 phương án đều parse thành công hợp lệ thì đánh rớt ngay.
      - Câu hỏi 'tên biến nào đúng / hợp lệ': không được để >= 2 phương án đều là định danh hợp lệ.
    """
    errs: list[str] = []
    q_low = cau_hoi.lower()

    is_negative_q = bool(re.search(r"(?:không\s+đúng|không\s+hợp\s+lệ|bị\s+sai|viết\s+sai|\bsai\b|\blỗi\b)", q_low))

    # 1. Hỏi lệnh gán / câu lệnh nào đúng cú pháp
    asks_valid_assign = bool(
        re.search(r"(?:lệnh\s+gán|cách\s+gán|phép\s+gán|câu\s+lệnh\s+gán)[^\n.?]*(?:đúng|hợp\s+lệ)", q_low)
    ) and not is_negative_q

    asks_valid_syntax_cmd = bool(
        re.search(
            r"(?:câu\s+lệnh|lệnh\s+nào|đoạn\s+lệnh|viết\s+lệnh|cú\s+pháp\s+nào)[^\n.?]*(?:đúng\s+cú\s+pháp|viết\s+đúng|hợp\s+lệ)",
            q_low,
        )
    ) and not is_negative_q

    if asks_valid_assign or asks_valid_syntax_cmd:
        valid_parsed: list[str] = []
        for o in opts:
            o_clean = o.strip().strip("`")
            if not o_clean:
                continue
            try:
                tree = ast.parse(o_clean)
                if not tree.body:
                    continue
                if asks_valid_assign:
                    if len(tree.body) == 1 and isinstance(tree.body[0], (ast.Assign, ast.AugAssign)):
                        valid_parsed.append(o_clean)
                else:
                    # Chỉ tính các phương án thực sự có cú pháp lệnh/biểu thức Python (tránh câu chữ tiếng Việt 1 từ)
                    has_code_token = any(ch in o_clean for ch in ("=", "(", ":", "[", "+", "-", "*", "/", "%"))
                    if has_code_token:
                        valid_parsed.append(o_clean)
            except SyntaxError:
                continue
        if len(valid_parsed) >= 2:
            errs.append(
                f"Vi phạm tính đơn trị (Single-answer): có {len(valid_parsed)}/4 phương án đều hợp lệ cú pháp Python qua ast.parse() "
                f"({', '.join(valid_parsed[:3])}). Chỉ được để DUY NHẤT 1 phương án đúng cú pháp, 3 phương án nhiễu phải sai cú pháp rõ ràng (VD: 2a = 5, if = 3, a == 5)."
            )

    # 2. Hỏi tên biến nào đúng/hợp lệ
    asks_valid_var = bool(
        re.search(r"(?:tên\s+biến|đặt\s+tên\s+biến)[^\n.?]*(?:đúng|hợp\s+lệ)", q_low)
    ) and not is_negative_q

    if asks_valid_var:
        valid_idents: list[str] = []
        for o in opts:
            o_clean = o.strip().strip("`'\"")
            if o_clean.isidentifier() and not keyword.iskeyword(o_clean):
                valid_idents.append(o_clean)
        if len(valid_idents) >= 2:
            errs.append(
                f"Vi phạm tính đơn trị (Single-answer): có {len(valid_idents)}/4 phương án tên biến đều hợp lệ trong Python "
                f"({', '.join(valid_idents[:3])}). Chỉ được có DUY NHẤT 1 tên biến hợp lệ."
            )

    return errs


def _extract_prompt_area_for_lesson_check(q: dict, loai: str) -> str:
    """
    Chỉ trích phần ĐỀ BÀI (+ phương án đối với MCQ) để kiểm tra từ khóa chuyên biệt theo Bài học,
    tuyệt đối KHÔNG tìm trong giai_thich, trich_dan_sgk hay các ý trả lời a/b/c/d của TRUE_FALSE.
    """
    if loai == "MCQ":
        return "\n".join(str(q.get(k, "")) for k in ("cau_hoi", "A", "B", "C", "D"))
    if loai == "TRUE_FALSE":
        parts = [str(q.get("cau_hoi_chung", ""))]
        for k in ("a", "b", "c", "d"):
            obj = q.get(k)
            if isinstance(obj, dict):
                parts.append(str(obj.get("menh_de", "")))
            elif isinstance(obj, str):
                parts.append(obj)
        return "\n".join(parts)
    if loai == "SHORT_ANSWER":
        return str(q.get("cau_hoi", ""))
    if loai == "ESSAY_CODE":
        return f"{q.get('tinh_huong', '')}\n{q.get('yeu_cau_hoc_sinh', '')}"
    return ""


def _check_lesson_specific_requirements(question_json: dict, loai: str, bai_hoc_target: str) -> list[str]:
    """
    Khóa cứng kiến thức đặc thù theo từng Bài học ngay trên phần đề bài (và phương án MCQ):
      - Bài 18: input, int(, float( hoặc print
      - Bài 19: if, else, and, or, not hoặc phép so sánh
      - Bài 20: for hoặc range(
      - Bài 21: while
      - Bài 22–23: danh sách [...] hoặc list, append
      - Bài 24–25: xâu kí tự '...' / "..." hoặc len(, find(, str
      - Bài 26–28: với câu có code (TRUE_FALSE, SHORT_ANSWER, ESSAY_CODE), đoạn mã trong đề hoặc dap_an_mau bắt buộc có `def `
      - Bài 29–30: lỗi cú pháp, ngoại lệ, lỗi logic, SyntaxError, TypeError, IndexError, ZeroDivisionError, NameError, kiểm thử
    """
    errs: list[str] = []
    if not bai_hoc_target:
        return errs

    prompt_text = _extract_prompt_area_for_lesson_check(question_json, loai)
    prompt_low = prompt_text.lower()

    if bai_hoc_target == "Bài 18":
        has_io = bool(re.search(r"\b(?:input|print)\b|\bint\s*\(|\bfloat\s*\(", prompt_low))
        if not has_io:
            errs.append(
                "Nội dung đề bài chưa khớp Bài 18 (Các lệnh vào ra đơn giản): "
                "đề/phương án bắt buộc nhắc tới `input`, `int(`, `float(` hoặc `print`."
            )

    elif bai_hoc_target == "Bài 19":
        code_mau = _normalize_code_mau(question_json.get("dap_an_mau", "")) if loai == "ESSAY_CODE" else ""
        has_branch_or_cmp = bool(
            re.search(r"\b(?:if|else|elif|and|or|not)\b|==|!=|<=|>=|(?:[A-Za-z0-9_)\]]\s*[<>]\s*[A-Za-z0-9_(\[])", prompt_text)
            or (code_mau and re.search(r"\b(?:if|else|elif|and|or|not)\b|==|!=|<=|>=|(?:[A-Za-z0-9_)\]]\s*[<>]\s*[A-Za-z0-9_(\[])", code_mau))
        )
        if not has_branch_or_cmp:
            errs.append(
                "Nội dung đề bài chưa khớp Bài 19 (Câu lệnh rẽ nhánh if): "
                "đề/phương án bắt buộc có `if`, `else`, `and`, `or`, `not` hoặc phép so sánh."
            )

    elif bai_hoc_target == "Bài 20":
        code_mau = _normalize_code_mau(question_json.get("dap_an_mau", "")) if loai == "ESSAY_CODE" else ""
        has_for = bool(
            re.search(r"\bfor\s+|\brange\s*\(", prompt_text)
            or (code_mau and re.search(r"\bfor\s+|\brange\s*\(", code_mau))
        )
        if not has_for:
            errs.append(
                "Nội dung đề bài chưa khớp Bài 20 (Câu lệnh lặp for): "
                "đề/phương án bắt buộc có `for ` hoặc `range(`."
            )

    elif bai_hoc_target == "Bài 21":
        code_mau = _normalize_code_mau(question_json.get("dap_an_mau", "")) if loai == "ESSAY_CODE" else ""
        has_while = bool(
            re.search(r"\bwhile\s+", prompt_text)
            or (code_mau and re.search(r"\bwhile\s+", code_mau))
        )
        if not has_while:
            errs.append(
                "Nội dung đề bài chưa khớp Bài 21 (Câu lệnh lặp while): "
                "đề/phương án bắt buộc có `while `."
            )

    elif bai_hoc_target in ("Bài 22", "Bài 23"):
        has_list = bool(re.search(r"\[[^\]]*\]|\blist\b|\bappend\b", prompt_text, re.IGNORECASE))
        if not has_list:
            errs.append(
                f"Nội dung đề bài chưa khớp {bai_hoc_target} (Kiểu dữ liệu danh sách): "
                "đề/phương án bắt buộc có danh sách `[...]` hoặc `list`, `append`."
            )

    elif bai_hoc_target in ("Bài 24", "Bài 25"):
        has_str = bool(
            re.search(r"['\"][^'\"]+['\"]|\blen\s*\(|\bfind\s*\(|\bstr\b", prompt_text, re.IGNORECASE)
        )
        if not has_str:
            errs.append(
                f"Nội dung đề bài chưa khớp {bai_hoc_target} (Xâu kí tự): "
                "đề/phương án bắt buộc có xâu kí tự `'...'`/`\"...\"` hoặc `len(`, `find(`, `str`."
            )
        if bai_hoc_target == "Bài 24" and re.search(r"\bsum\s*\(", prompt_text):
            errs.append(
                "Nội dung Bài 24 (Xâu kí tự) không được sử dụng hàm `sum(` (thuộc bài tính tổng số/danh sách)."
            )

    elif bai_hoc_target in ("Bài 26", "Bài 27", "Bài 28"):
        if loai in ("TRUE_FALSE", "SHORT_ANSWER"):
            # Với TRUE_FALSE và SHORT_ANSWER, đoạn mã NGAY TRONG ĐỀ BÀI bắt buộc có `def `
            if not re.search(r"\bdef\s+[A-Za-z_]", prompt_text):
                errs.append(
                    f"Nội dung đề bài chưa khớp {bai_hoc_target} (Hàm & Phạm vi biến): "
                    f"đoạn mã trong đề ({loai}) bắt buộc phải có định nghĩa hàm bằng từ khóa `def `."
                )
        elif loai == "ESSAY_CODE":
            code_mau = _normalize_code_mau(question_json.get("dap_an_mau", ""))
            if not (re.search(r"\bdef\s+[A-Za-z_]", prompt_text) or re.search(r"\bdef\s+[A-Za-z_]", code_mau)):
                errs.append(
                    f"Nội dung chưa khớp {bai_hoc_target} (Hàm & Phạm vi biến): "
                    "đề hoặc `dap_an_mau` của ESSAY_CODE bắt buộc phải có từ khóa `def `."
                )
        else:  # MCQ Bài 26-28
            has_func_concept = bool(
                re.search(r"\bdef\s+|\breturn\b|hàm|tham\s+số|đối\s+số|cục\s+bộ|toàn\s+cục|phạm\s+vi", prompt_low)
            )
            if not has_func_concept:
                errs.append(
                    f"Nội dung đề bài chưa khớp {bai_hoc_target} (Hàm & Phạm vi biến): "
                    "đề/phương án phải liên quan đến `def`, hàm, tham số, `return` hoặc phạm vi biến."
                )

    elif bai_hoc_target in ("Bài 29", "Bài 30"):
        err_cues = (
            "lỗi cú pháp", "ngoại lệ", "lỗi logic", "lỗi ngữ nghĩa",
            "syntaxerror", "typeerror", "indexerror", "zerodivisionerror",
            "nameerror", "kiểm thử", "gỡ lỗi", "sửa lỗi", "lỗi", "test case", "bộ thử", "thử nghiệm",
        )
        if not any(cue in prompt_low for cue in err_cues):
            errs.append(
                f"Nội dung đề bài chưa khớp {bai_hoc_target} (Lỗi & Kiểm thử): "
                "đề/phương án bắt buộc nhắc tới khái niệm lỗi (lỗi cú pháp, ngoại lệ, lỗi logic, SyntaxError, TypeError, IndexError, ZeroDivisionError, NameError, kiểm thử)."
            )
        if bai_hoc_target == "Bài 29":
            body_no_cite = _flatten_body_without_citation(question_json, loai)
            if re.search(r"\{\s*\}|ngoặc\s+nhọn", body_no_cite, re.IGNORECASE):
                errs.append(
                    "Nội dung Bài 29 (Nhận biết lỗi chương trình Python) không được nhắc tới cặp ngoặc nhọn '{}' (nhầm cú pháp C/Java sang Python)."
                )

    elif bai_hoc_target in LESSON_CORE_SIGNATURES:
        sig_kws, sig_msg = LESSON_CORE_SIGNATURES[bai_hoc_target]
        if not any(kw in prompt_low for kw in sig_kws):
            errs.append(f"Nội dung đề bài chưa khớp đúng trọng tâm {bai_hoc_target}: {sig_msg}")

    return errs


_TF_ALLOWED_END_TOKENS = {
    "true", "false", "none", "int", "str", "float", "bool", "list", "python",
    "print", "input", "range", "len", "append", "find", "return", "def", "for", "while", "if", "else", "thi",
}
_TF_PREDICATE_CUES = (
    "là", "có", "nhận", "bằng", "dùng", "thuộc", "chạy", "lặp", "in", "trả",
    "tạo", "gán", "khai báo", "lưu", "thực hiện", "thực thi", "kiểm tra", "hiển thị",
    "kết thúc", "xác định", "gây", "báo", "tăng", "giảm", "được", "không",
    "chỉ", "gồm", "chứa", "xuất", "duyệt", "thêm", "xóa", "tách", "nối", "tính",
    "lớn hơn", "nhỏ hơn", "chia hết", "cần", "phải", "phát sinh", "xảy ra", "xuất hiện", "bị lỗi", "lỗi", "==", "!=", "<=", ">=",
)


def _check_tf_statement_completeness(k: str, md: str) -> list[str]:
    """Chống mệnh đề TRUE_FALSE bị cắt cụt ý (VD: 'Biểu thức điều kiện a', kết thúc bằng tên biến đơn lẻ hoặc giới từ cụt)."""
    errs: list[str] = []
    s = str(md or "").strip()
    s_no_dot = s.rstrip(".!?;:, ")
    s_low = s_no_dot.lower()
    if not s_no_dot:
        return errs

    # 1. Cụm danh từ bị cắt cụt ngay sau tên biến đơn lẻ (VD: "Biểu thức điều kiện a", "Giá trị của biến k")
    if re.match(
        r"^(?:biểu\s+thức(?:\s+điều\s+kiện)?|câu\s+lệnh|vòng\s+lặp|giá\s+trị(?:\s+của)?|biến|hàm|tham\s+số|điều\s+kiện|kết\s+quả(?:\s+của)?)\s+(?:biến\s+)?[A-Za-z_][A-Za-z0-9_]{0,14}$",
        s_no_dot,
        re.IGNORECASE,
    ):
        errs.append(
            f"Mệnh đề '{k}' bị cụt ý ('{s}'). Mọi mệnh đề Đúng/Sai phải là câu khẳng định trọn vẹn có chủ ngữ và vị ngữ rõ ràng."
        )
        return errs

    # 2. Kết thúc bằng tên biến/ký danh đơn lẻ mà câu chưa hề có vị ngữ
    m_end_var = re.search(r"\s([A-Za-z_][A-Za-z0-9_]{0,12})$", s_no_dot)
    if m_end_var:
        end_tok = m_end_var.group(1)
        has_pred = any(
            (cue in s_low if not cue.isalpha() else re.search(rf"\b{re.escape(cue)}\b", s_low) is not None)
            for cue in _TF_PREDICATE_CUES
        )
        if end_tok.lower() not in _TF_ALLOWED_END_TOKENS and not has_pred:
            errs.append(
                f"Mệnh đề '{k}' bị cụt ý, kết thúc bằng tên biến đơn lẻ '{end_tok}' mà thiếu vị ngữ ('{s}')."
            )
            return errs

    # 3. Bị cắt cụt giữa chừng ở giới từ / liên từ cuối câu (bỏ qua 'bên trong', 'phía trong', 'ở trong')
    if re.search(r"\b(?:là|của|và|hoặc|khi|nếu|với|bằng|thì|nên|từ|để)\s*$|(?<!\bbên\s)(?<!\bphía\s)(?<!\bở\s)\btrong\s*$", s_low):
        errs.append(
            f"Mệnh đề '{k}' bị cắt cụt giữa chừng ('{s}'). Hãy viết đầy đủ câu khẳng định hoàn chỉnh."
        )

    return errs


def _check_mcq_option_python_syntax(cau_hoi: str, opts: list[str], dap_an: str) -> list[str]:
    """
    Kiểm tra cú pháp Python trong các phương án MCQ:
      - Phát hiện lỗi cú pháp phổ biến như thiếu từ khóa `for` trước `in range(` (VD: 'k in range(1, 5):').
      - Với phương án đáp án đúng dạng lệnh Python thuần (`for `, `while `, `if `, `def `, `print(`),
        kiểm tra cú pháp bằng ast.parse() (trừ khi câu hỏi cố tình hỏi câu lệnh bị lỗi/sai cú pháp).
    """
    errs: list[str] = []
    q_low = str(cau_hoi or "").lower()
    if any(cue in q_low for cue in INTENTIONAL_SYNTAX_ERROR_CUES) or re.search(
        r"(?:không\s+đúng|không\s+hợp\s+lệ|bị\s+sai|viết\s+sai|sai\s+cú\s+pháp)", q_low
    ):
        return errs

    opt_labels = ("A", "B", "C", "D")
    asks_valid_syntax = bool(
        re.search(r"(?:lệnh|cú\s+pháp)[^\n.?]*(?:đúng|hợp\s+lệ)", q_low)
    )

    for lbl, raw_opt in zip(opt_labels, opts):
        o = str(raw_opt or "").strip().strip("`")
        if not o:
            continue

        # 1. Thiếu 'for' trước '<var> in range(' (lỗi rất phổ biến ở LLM 3B)
        if re.search(r"\b[A-Za-z_][A-Za-z0-9_]*\s+in\s+range\s*\(", o) and not re.search(r"\bfor\s+[A-Za-z_]", o):
            # Nếu câu hỏi hỏi "chọn câu lệnh đúng cú pháp" và đây KHÔNG phải đáp án đúng thì coi là phương án nhiễu hợp lệ;
            # ngược lại (đây là đáp án đúng HOẶC câu hỏi không hỏi tìm lỗi cú pháp) -> đánh rớt ngay!
            if not asks_valid_syntax or lbl == dap_an:
                errs.append(
                    f"Phương án {lbl} ('{o}') sai cú pháp Python: thiếu từ khóa `for` trước `in range(...)`."
                )

        # 2. Với phương án chứa mã Python (`for `, `if `, `def `, `while `), kiểm tra từng phương án qua ast.parse()
        has_py_kw = bool(re.search(r"\b(?:for|if|def|while)\s+", o))
        is_jammed_one_line = bool(re.search(r"=\s*[^\n]+\s+(?:for|if|def|while)\s+", o))
        if is_jammed_one_line:
            errs.append(
                f"Phương án {lbl} ('{o}') viết dính liền nhiều lệnh Python trên 1 dòng gây SyntaxError. Phải tách dòng hoặc viết đúng cú pháp Python 3."
            )
            continue

        if has_py_kw or (lbl == dap_an and re.match(r"^(?:elif\s+|print\s*\()", o)):
            o_no_quotes = re.sub(r"(['\"]).*?\1", "", o)
            if not re.search(rf"[{_VI_ACCENT_CHARS}]", o_no_quotes.lower()):
                code_to_parse = f"{o}\n    pass" if o.rstrip().endswith(":") else o
                try:
                    ast.parse(code_to_parse)
                except SyntaxError as e:
                    # Nếu đề hỏi "chọn lệnh đúng cú pháp" thì chỉ bắt lỗi cú pháp trên đáp án đúng; ngược lại bắt trên mọi phương án chứa code
                    if (not asks_valid_syntax) or lbl == dap_an:
                        errs.append(
                            f"Phương án {lbl} ('{o}') bị lỗi cú pháp Python qua ast.parse() ({e.msg}). Hãy sửa đúng cú pháp Python 3."
                        )

    return errs


# ==============================================================================
# TẦNG 1: RULE VALIDATOR (HARD GATE + SANDBOX VERIFICATION)
# ==============================================================================

def rule_validate(
    question_json: dict,
    loai_cau_hoi: str,
    evidence_package: dict,
) -> dict:
    """
    Tầng 1 (Hard Gate): Kiểm tra nghiêm ngặt cấu trúc JSON, trích dẫn SGK,
    phạm vi Chủ đề F lớp 10, chống phương án giữ chỗ ('Biểu thức A/B', 'Phương án 1'...),
    chỉ rõ cặp phương án trùng lặp, khớp đúng bài học và kiểm chứng thực thi mã Python trên Sandbox (timeout 2.0s).
    """
    errors: list[str] = []
    loai = loai_cau_hoi.strip().upper()
    sandbox_verified = False
    sandbox_stdout = ""

    # 1. Kiểm tra JSON hợp lệ & chuẩn hóa dap_an_mau nếu LLM trả về dạng list dòng code
    if not isinstance(question_json, dict) or not question_json:
        return {
            "passed": False,
            "errors": ["Đầu ra không phải JSON hợp lệ hoặc JSON rỗng."],
            "sandbox_verified": False,
            "sandbox_stdout": "",
        }
    if isinstance(question_json.get("dap_an_mau"), list):
        question_json["dap_an_mau"] = _normalize_code_mau(question_json["dap_an_mau"])

    # 2. Kiểm tra trường trích dẫn nguyên văn SGK (trich_dan_sgk) + gợi ý 1-2 câu nguyên văn nếu chưa khớp
    trich_dan = _clean_sgk_citation(str(question_json.get("trich_dan_sgk", "")).strip())
    question_json["trich_dan_sgk"] = trich_dan
    verbatim_hints = _extract_verbatim_sgk_sentences(evidence_package, max_sentences=2)
    hint_str = (
        " Hãy sao chép chính xác 1 trong các câu nguyên văn SGK sau vào 'trich_dan_sgk': "
        + " HOẶC ".join(f'"{s}"' for s in verbatim_hints)
        if verbatim_hints
        else ""
    )
    if len(trich_dan) < 15:
        errors.append(
            "Thiếu hoặc quá ngắn trường 'trich_dan_sgk' (bắt buộc trích dẫn nguyên văn từ bằng chứng SGK Chủ đề F)."
            + hint_str
        )
    else:
        ev_text = " ".join(c.get("content", "") for c in evidence_package.get("sgk_chunks", []))
        ev_text += " " + " ".join(g.get("dinh_nghia_sgk", "") for g in evidence_package.get("glossary_terms", []))
        ev_tokens = _tokenize_vi(ev_text)
        cite_tokens = _tokenize_vi(trich_dan) - {"python"}
        if ev_tokens and cite_tokens:
            overlap_ratio = len(cite_tokens & ev_tokens) / len(cite_tokens)
            if overlap_ratio < 0.45:
                errors.append(
                    f"Trường 'trich_dan_sgk' không khớp từ vựng bằng chứng SGK (chỉ đạt {overlap_ratio:.0%}, cần >= 45%)."
                    + hint_str
                )

    # 3. Kiểm tra phạm vi Chủ đề F, khớp bài học trọng tâm & chống rò placeholder
    full_text = _flatten_question_text(question_json, loai)
    full_lower = full_text.lower()
    for bad_topic in OUT_OF_SCOPE_TOPICS:
        if bad_topic in full_lower:
            errors.append(f"Vi phạm phạm vi Chủ đề F Tin học 10: chứa nội dung ngoài chương trình ('{bad_topic}').")
            break
    for leak in PLACEHOLDER_LEAK_PATTERNS:
        if leak in full_lower:
            errors.append(f"Đề sinh ra còn sót ký hiệu khuôn mẫu/placeholder ('{leak}'). Phải viết thành câu hỏi hoàn chỉnh, cụ thể.")
            break
    for emp in EMPTY_PLACEHOLDER_PATTERNS:
        if emp in full_lower:
            errors.append(f"Đề sinh ra chứa chuỗi rỗng/chưa hoàn thiện ('{emp}'). Bắt buộc sinh nội dung đầy đủ.")
            break

    # Kiểm tra khóa cứng kiến thức đặc thù theo từng Bài học (kiểm tra trực tiếp trên phần đề bài / phương án)
    bai_hoc_target = str(evidence_package.get("bai_hoc", "")).strip()
    errors.extend(_check_lesson_specific_requirements(question_json, loai, bai_hoc_target))

    # 3b. Chống sao chép mẫu 1-shot cũ, từ tiếng Anh vô nghĩa ('Opposite') & code dính liền 1 dòng
    errors.extend(_check_oneshot_and_format_quality(question_json, loai))

    # 4. Kiểm tra hàm/thư viện Python vượt cấp lớp 10
    for pattern, reason in FORBIDDEN_PYTHON_PATTERNS:
        if re.search(pattern, full_text):
            errors.append(f"Vi phạm giới hạn Python lớp 10: {reason}.")

    # 5. Kiểm tra riêng từng dạng câu hỏi
    snippets = _extract_executable_python_snippets(question_json, loai)
    has_code_in_stem = bool(snippets) or ("```" in full_text)

    # 5a. Chặn thiếu code khi hỏi tính giá trị biểu thức/kết quả & biến chưa khởi tạo
    errors.extend(_check_missing_code_or_uninit_var(question_json, loai, snippets))

    if loai == "MCQ":
        cau_hoi = str(question_json.get("cau_hoi", "")).strip()
        cau_hoi_low = cau_hoi.lower()
        if len(cau_hoi) < 15:
            errors.append("Câu hỏi MCQ ('cau_hoi') bị trống hoặc quá ngắn.")
        else:
            errors.extend(_check_stem_not_raw_textbook(cau_hoi, has_code=has_code_in_stem))
            if "câu hỏi là gì?" in cau_hoi_low or re.match(r"^gọi\s+các\s+biến\b.*câu\s+hỏi\s+là\s+gì", cau_hoi_low, re.DOTALL):
                errors.append(
                    "Thân câu hỏi MCQ chứa cụm vô nghĩa ('Câu hỏi là gì?' / 'Gọi các biến ... Câu hỏi là gì?'). Hãy viết câu hỏi khảo thí rõ ràng, cụ thể."
                )

        opt_labels = ("A", "B", "C", "D")
        opts = [str(question_json.get(k, "")).strip() for k in opt_labels]
        if any(not o for o in opts):
            errors.append("Thiếu nội dung ở một hoặc nhiều phương án A, B, C, D.")
        else:
            # Chặn thuật ngữ sai SGK "Biểu thức if" trong câu hỏi hoặc 4 phương án
            if "biểu thức if" in cau_hoi_low or any("biểu thức if" in o.lower() for o in opts):
                errors.append(
                    "Phát hiện thuật ngữ sai SGK ('Biểu thức if'). Chuẩn SGK Tin học 10 dùng 'biểu thức điều kiện' hoặc 'biểu thức lôgic'."
                )

            # Chặn phương án chỉ liệt kê chuỗi phép so sánh rời rạc ngăn cách bởi ';' mà thiếu lệnh điều khiển (if, for, while, print)
            for lbl, o in zip(opt_labels, opts):
                if ";" in o and not re.search(r"\b(?:if|for|while|print)\b", o):
                    parts = [p.strip() for p in o.split(";") if p.strip()]
                    cmp_parts = sum(
                        1 for p in parts if re.search(r"(?:==|!=|<=|>=|[<>])", p)
                    )
                    if cmp_parts >= 2:
                        errors.append(
                            f"Phương án {lbl} ('{o}') chỉ liệt kê chuỗi phép so sánh rời rạc ngăn cách bởi dấu ';' mà không có câu lệnh điều khiển (if, for, while, print)."
                        )
                        break
            # Chốt chặn phương án giữ chỗ chung chung ("Biểu thức A", "Phương án 1", "Đáp án A"...)
            bad_placeholders = [
                f"{lbl}='{o}'"
                for lbl, o in zip(opt_labels, opts)
                if GENERIC_OPTION_REGEX.match(o) or o in ("...", "?", "A", "B", "C", "D")
            ]
            if bad_placeholders:
                errors.append(
                    f"Phương án MCQ là cụm giữ chỗ chung chung ({', '.join(bad_placeholders)}). "
                    "Bắt buộc viết nội dung/giá trị/cú pháp Python cụ thể cho cả 4 phương án A, B, C, D."
                )

            # Chỉ rõ chính xác cặp phương án trùng lặp để LLM 3B sửa trúng đích
            norm_opts = [re.sub(r"\s+", " ", o.lower()).rstrip(".") for o in opts]
            dup_pairs: list[str] = []
            for i in range(4):
                for j in range(i + 1, 4):
                    if norm_opts[i] == norm_opts[j]:
                        dup_pairs.append(
                            f"Phương án {opt_labels[i]} và {opt_labels[j]} đang trùng nội dung '{opts[i]}', bắt buộc đổi 1 phương án thành phương án nhiễu khác."
                        )
            if dup_pairs:
                errors.extend(dup_pairs)

            if any(len(o) > 160 for o in opts):
                errors.append("Phương án MCQ quá dài (> 160 ký tự, không được chép cả đoạn định nghĩa SGK làm phương án). Hãy viết 4 phương án ngắn gọn, súc tích.")

            if any(re.search(r"\(bài\s*\d+\s*,\s*tr\.", o.lower()) for o in opts):
                errors.append("Không được chép nhãn nguồn '(Bài ..., tr....)' từ glossary vào phương án A, B, C, D.")

            # Kiểm tra cân bằng độ dài 4 phương án
            lens = [len(o) for o in opts]
            max_len, min_len = max(lens), min(lens)
            if max_len > 25 and (max_len / max(min_len, 1) > 3.2):
                errors.append(
                    f"Độ dài 4 phương án A, B, C, D chênh lệch quá lớn (ngắn nhất {min_len} ký tự, dài nhất {max_len} ký tự). Hãy viết lại 4 phương án có độ dài tương đương."
                )

            # Kiểm tra tính đơn trị (Single-answer) cho câu hỏi lệnh gán / đặt tên biến
            errors.extend(_check_single_answer_mcq(cau_hoi, opts))

        dap_an = str(question_json.get("dap_an", "")).strip().upper()
        if dap_an not in ("A", "B", "C", "D"):
            errors.append(f"Trường 'dap_an' phải là một trong A, B, C, D (hiện tại: '{dap_an}').")
        elif all(opts):
            ans_idx = ["A", "B", "C", "D"].index(dap_an)
            ans_len = len(opts[ans_idx])
            other_avg = sum(len(opts[i]) for i in range(4) if i != ans_idx) / 3.0
            if ans_len > 30 and ans_len > other_avg * 1.9:
                errors.append(
                    f"Đáp án đúng ({dap_an}: {ans_len} ký tự) dài vượt trội so với trung bình 3 phương án nhiễu ({other_avg:.0f} ký tự). Hãy cân bằng độ dài."
                )
            errors.extend(_check_mcq_option_python_syntax(cau_hoi, opts, dap_an))

        giai_thich_mcq = str(question_json.get("giai_thich", "")).strip()
        if len(giai_thich_mcq) < 15:
            errors.append("Thiếu giải thích ('giai_thich') rõ ràng cho đáp án MCQ.")
        else:
            errors.extend(_check_explanation_consistency(cau_hoi + "\n" + "\n".join(opts), giai_thich_mcq))

    elif loai == "TRUE_FALSE":
        stem = str(question_json.get("cau_hoi_chung", "")).strip()
        if len(stem) < 20:
            errors.append("Câu dẫn chung ('cau_hoi_chung') cho dạng Đúng/Sai bị trống hoặc quá ngắn.")
        else:
            errors.extend(_check_stem_not_raw_textbook(stem, has_code=has_code_in_stem))

        statements: list[str] = []
        answers: list[str] = []
        for k in ("a", "b", "c", "d"):
            item = question_json.get(k)
            if not isinstance(item, dict):
                errors.append(f"Thiếu đối tượng mệnh đề '{k}' trong câu hỏi Đúng/Sai.")
                continue
            md = str(item.get("menh_de", "")).strip()
            da = _normalize_tf_answer(item.get("dap_an", ""))
            gt = str(item.get("giai_thich", "")).strip()
            if len(md) < 10 or GENERIC_OPTION_REGEX.match(md):
                errors.append(f"Mệnh đề '{k}' bị trống, quá ngắn hoặc là cụm giữ chỗ chung chung.")
            else:
                statements.append(md)
                errors.extend(_check_tf_statement_completeness(k, md))
            if not da:
                errors.append(f"Đáp án mệnh đề '{k}' phải là 'Đúng' hoặc 'Sai' (hiện tại: '{item.get('dap_an')}').")
            else:
                answers.append(da)
            if len(gt) < 10:
                errors.append(f"Thiếu giải thích cho mệnh đề '{k}'.")
            else:
                errors.extend(_check_explanation_consistency(stem + "\n" + md, gt))

        if len(answers) == 4 and len(set(answers)) < 2:
            errors.append("4 mệnh đề Đúng/Sai phải có đủ cả nhận định Đúng và nhận định Sai (không được toàn Đúng hoặc toàn Sai).")

        if len(statements) == 4:
            norm_stmts = [re.sub(r"\s+", " ", s.lower()).rstrip(".") for s in statements]
            if len(set(norm_stmts)) < 4:
                errors.append("Các mệnh đề a, b, c, d có nội dung bị trùng lặp.")
            else:
                tok_sets = [_tokenize_vi(s) for s in statements]
                for i in range(4):
                    for j in range(i + 1, 4):
                        if _jaccard(tok_sets[i], tok_sets[j]) >= 0.80:
                            errors.append(
                                f"Mệnh đề '{'abcd'[i]}' và '{'abcd'[j]}' quá giống nhau, chưa đảm bảo tính độc lập."
                            )

    elif loai == "SHORT_ANSWER":
        cau_hoi_sa = str(question_json.get("cau_hoi", "")).strip()
        if len(cau_hoi_sa) < 15:
            errors.append("Câu hỏi Trả lời ngắn ('cau_hoi') bị trống hoặc quá ngắn.")
        else:
            errors.extend(_check_stem_not_raw_textbook(cau_hoi_sa, has_code=has_code_in_stem))
            # BẮT BUỘC SHORT_ANSWER phải có đoạn mã Python thực thi được kèm lệnh print(...) (cấm câu lý thuyết thuần văn bản)
            if not snippets or not re.search(r"\bprint\s*\(", cau_hoi_sa):
                errors.append(
                    "Câu hỏi SHORT_ANSWER bắt buộc phải chứa đoạn mã Python thực thi được có lệnh print(...) để hỏi kết quả in ra (cấm câu hỏi lý thuyết thuần văn bản không có code)."
                )
        ans = str(question_json.get("dap_an_ngan", "")).strip()
        if not ans or GENERIC_OPTION_REGEX.match(ans):
            errors.append("Thiếu trường 'dap_an_ngan' hoặc đáp án còn chung chung.")
        elif len(ans) > 80:
            errors.append("Đáp án ngắn ('dap_an_ngan') quá dài (> 80 ký tự); cần kết quả ngắn gọn, tường minh.")
        gt_sa = str(question_json.get("giai_thich", "")).strip()
        if len(gt_sa) < 15:
            errors.append("Thiếu giải thích ('giai_thich') cho câu Trả lời ngắn.")
        else:
            errors.extend(_check_explanation_consistency(cau_hoi_sa + "\n" + ans, gt_sa))

    elif loai == "ESSAY_CODE":
        tinh_huong = str(question_json.get("tinh_huong", "")).strip()
        yeu_cau = str(question_json.get("yeu_cau_hoc_sinh", "")).strip()
        code_mau = _normalize_code_mau(question_json.get("dap_an_mau", ""))
        tieu_chi = question_json.get("tieu_chi_cham_diem", [])

        if len(tinh_huong) < 20:
            errors.append("Thiếu tình huống bài toán ('tinh_huong').")
        else:
            errors.extend(_check_stem_not_raw_textbook(tinh_huong, has_code=bool(code_mau)))
        if len(yeu_cau) < 10:
            errors.append("Thiếu yêu cầu học sinh ('yeu_cau_hoc_sinh').")
        if not code_mau:
            errors.append("Thiếu mã nguồn Python mẫu ('dap_an_mau').")
        if not isinstance(tieu_chi, list) or len(tieu_chi) < 2:
            errors.append("Thiếu tiêu chí chấm điểm ('tieu_chi_cham_diem', cần danh sách ít nhất 2 tiêu chí).")

        # Chống lộ mã lời giải ngay trong đề bài ESSAY_CODE (tinh_huong / yeu_cau_hoc_sinh)
        essay_prompt_combined = f"{tinh_huong}\n{yeu_cau}"
        if re.search(r"\bfor\s+[A-Za-z_][A-Za-z0-9_]*\s+in\b", essay_prompt_combined) or re.search(
            r"\bwhile\s+[^:\n]+:", essay_prompt_combined
        ):
            errors.append(
                "Đề bài ESSAY_CODE bị lộ lời giải (chứa vòng lặp for/while ngay trong 'tinh_huong' hoặc 'yeu_cau_hoc_sinh'). "
                "Chỉ được mô tả bài toán và dữ liệu đầu vào, không chép thuật toán vào đề."
            )
        if re.search(r"\breturn\s+[^\n]+", essay_prompt_combined) or re.search(
            r"\b(?:tong|ong|dem|kq)\s*=|\bs\s*=\s*0\b", essay_prompt_combined
        ):
            errors.append(
                "Đề bài ESSAY_CODE bị lộ thân hàm/biến giải thuật ('return ...', 'ong =' hoặc khởi tạo biến tổng/đếm) ngay trong đề. "
                "Hãy giữ đề bài thuần mô tả yêu cầu + dữ liệu mẫu."
            )

        # Chống gộp 2 bài toán khác nhau & chống lộ câu trả lời ngay trong đề ESSAY_CODE
        essay_low = essay_prompt_combined.lower()
        if re.search(r"tổng\s+các\s+số\s+chẵn(?:\s+trong\s+[A-Za-z_]\w*)?\s+là", essay_low):
            errors.append(
                "Đề bài ESSAY_CODE bị lộ lời giải/câu in kết quả ('Tổng các số chẵn trong ... là') ngay trong đề bài."
            )

        # Chống phép chia làm thay đổi kiểu dữ liệu sai thuật toán (/= trên biến tổng/tích lũy trong dap_an_mau)
        if code_mau and re.search(r"\b(?:tong|sum|total|s|kq|dem)\s*/=", code_mau, re.IGNORECASE):
            errors.append(
                "Mã mẫu 'dap_an_mau' chứa phép toán '/=' trên biến tổng/tích lũy làm sai kiểu dữ liệu và sai thuật toán. Hãy sửa thành '+=' hoặc phép toán đúng."
            )

        if (
            len(re.findall(r"\bviết\s+hàm\b", essay_low)) >= 2
            or len(re.findall(r"\bviết\s+chương\s+trình\b", essay_low)) >= 2
            or len(re.findall(r"\bcho\s+hai\s+số\s+nguyên\b", essay_low)) >= 2
            or (bool(re.search(r"\bviết\s+hàm\b", essay_low)) and bool(re.search(r"\bviết\s+chương\s+trình\b", essay_low)))
            or re.search(r"\b(?:bài\s*2|câu\s*2|câu\s+hỏi)\s*:", essay_low)
        ):
            errors.append(
                "Đề bài ESSAY_CODE bị nối ghép nhiều đề bài khác nhau (lặp từ 2 lần cụm 'Viết hàm' / 'Viết chương trình' / 'Cho hai số nguyên'). Chỉ giữ duy nhất 1 bài toán thống nhất."
            )

        if "ky_sut" in f"{essay_low}\n{code_mau.lower()}":
            errors.append(
                "Đề bài hoặc mã mẫu ESSAY_CODE chứa từ bịa sai chính tả ('ky_sut'). Hãy sửa thành tên biến/từ tiếng Việt đúng chuẩn."
            )

        # Kiểm tra nếu đề nhắc xử lý danh sách (vd: danh sách A) thì bắt buộc phải khai báo giá trị cụ thể dạng [...]
        if any(k in essay_low for k in ("mảng", "danh sách", "list")):
            if "[" not in essay_prompt_combined:
                errors.append(
                    "Đề bài ESSAY_CODE yêu cầu xử lý danh sách nhưng chưa khai báo giá trị cụ thể (ví dụ: A = [3, 8, 2, 5, 11])."
                )

    # 6. Tích hợp Sandbox (timeout_sec=2.0) kiểm chứng MỌI đoạn mã Python thực thi được trong câu hỏi / dap_an_mau
    has_code, sb_ok, sb_errors, sandbox_stdout = _run_sandbox_verification(snippets)
    if has_code:
        sandbox_verified = sb_ok
        if not sb_ok:
            errors.extend(sb_errors)

    # 6b. Bắt buộc SHORT_ANSWER phải sinh ra stdout khác rỗng khi chạy trên Sandbox
    if loai == "SHORT_ANSWER" and has_code and sb_ok and not sandbox_stdout.strip():
        errors.append(
            "Câu hỏi SHORT_ANSWER có đoạn mã chạy trên Sandbox nhưng stdout bị rỗng (không in ra kết quả). Bắt buộc có lệnh print(...) in ra giá trị cụ thể."
        )

    # 7. Execution-Grounded Answer: kiểm chứng đáp án khớp với stdout thực tế (MCQ & SHORT_ANSWER)
    if has_code and sb_ok and sandbox_stdout.strip():
        errors.extend(_check_execution_grounded_answer(question_json, loai, sandbox_stdout))

    # 8. TRUE_FALSE: chặn giai_thich trùng lặp giữa 4 ý & biến không tồn tại trong code
    if loai == "TRUE_FALSE":
        errors.extend(_check_true_false_explanations(question_json))

    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "sandbox_verified": sandbox_verified,
        "sandbox_stdout": sandbox_stdout,
    }


# ==============================================================================
# TẦNG 2: FUZZY QUALITY VALIDATOR (CHẤM ĐIỂM 0.0 - 1.0)
# ==============================================================================

def _score_sgk_grounding(question_json: dict, evidence_package: dict) -> tuple[float, list[str]]:
    """Chấm điểm độ bám nguồn SGK & thuật ngữ chuẩn (0.0 - 1.0)."""
    notes: list[str] = []
    trich_dan = str(question_json.get("trich_dan_sgk", "")).strip()
    sgk_text = " ".join(c.get("content", "") for c in evidence_package.get("sgk_chunks", []))
    glossary_terms = evidence_package.get("glossary_terms", [])
    glossary_text = " ".join(
        f"{g.get('thuat_ngu', '')} {g.get('dinh_nghia_sgk', '')}" for g in glossary_terms
    )

    ev_tokens = _tokenize_vi(sgk_text + " " + glossary_text)
    cite_tokens = _tokenize_vi(trich_dan)

    if not cite_tokens or not ev_tokens:
        cite_score = 0.0
    else:
        overlap = len(cite_tokens & ev_tokens) / len(cite_tokens)
        cite_clean = re.sub(r"\s+", " ", trich_dan.lower())
        sgk_clean = re.sub(r"\s+", " ", (sgk_text + " " + glossary_text).lower())
        words = cite_clean.split()
        trigram_hit = any(" ".join(words[i:i + 3]) in sgk_clean for i in range(max(0, len(words) - 2)))
        cite_score = min(0.65, overlap * 0.55 + (0.15 if trigram_hit else 0.0))
        if overlap < 0.50:
            notes.append("Trích dẫn 'trich_dan_sgk' nên chép sát nguyên văn hơn từ đoạn bằng chứng SGK.")

    full_lower = _flatten_question_text(question_json, evidence_package.get("loai_cau_hoi", "MCQ")).lower()
    term_hits = 0
    for g in glossary_terms:
        t_name = g.get("thuat_ngu", "").lower()
        t_core = re.sub(r"\(.*?\)", "", t_name).strip()
        if (t_core and t_core in full_lower) or any(w in full_lower for w in _tokenize_vi(t_name)):
            term_hits += 1

    if glossary_terms:
        term_score = 0.35 if term_hits >= 1 else 0.15
    else:
        term_score = 0.30

    if term_hits == 0 and glossary_terms:
        notes.append("Nên sử dụng rõ thuật ngữ chuẩn SGK của bài học trong câu hỏi và lời giải thích.")

    return round(min(1.0, cite_score + term_score), 3), notes


def _score_cognitive_pedagogy(question_json: dict, loai: str, evidence_package: dict) -> tuple[float, list[str]]:
    """Chấm điểm mức độ nhận thức, tính sư phạm & chất lượng giải thích (0.0 - 1.0)."""
    notes: list[str] = []
    score = 0.0
    full_text = _flatten_question_text(question_json, loai)

    stem = (
        str(question_json.get("cau_hoi", ""))
        if loai in ("MCQ", "SHORT_ANSWER")
        else str(question_json.get("cau_hoi_chung", ""))
        if loai == "TRUE_FALSE"
        else str(question_json.get("tinh_huong", ""))
    ).strip()
    if len(stem) >= 35:
        score += 0.35
    elif len(stem) >= 20:
        score += 0.22
        notes.append("Câu dẫn còn hơi ngắn, nên làm rõ ngữ cảnh lập trình Python.")
    else:
        score += 0.10

    if loai == "TRUE_FALSE":
        exps = [str((question_json.get(k) or {}).get("giai_thich", "")).strip() for k in ("a", "b", "c", "d")]
        good_exps = sum(1 for e in exps if len(e) >= 20)
        score += 0.35 * (good_exps / 4.0)
        if good_exps < 4:
            notes.append("Một số mệnh đề Đúng/Sai có giải thích quá ngắn (< 20 ký tự).")
    elif loai == "ESSAY_CODE":
        tc = question_json.get("tieu_chi_cham_diem", [])
        score += 0.35 if isinstance(tc, list) and len(tc) >= 3 else 0.22
    else:
        gt = str(question_json.get("giai_thich", "")).strip()
        if len(gt) >= 35:
            score += 0.35
        elif len(gt) >= 18:
            score += 0.22
            notes.append("Giải thích đáp án nên nêu rõ bản chất câu lệnh/quy tắc Python hơn.")
        else:
            score += 0.10

    has_python_syntax = bool(
        re.search(r"(`|\bprint\s*\(|\binput\s*\(|\bif\b|\belse\b|\bfor\b|\bwhile\b|\brange\s*\(|\bdef\b|==|!=|<=|>=|=)", full_text)
    )
    if has_python_syntax:
        score += 0.30
    else:
        score += 0.15
        notes.append("Nên gắn ví dụ cú pháp hoặc đoạn mã Python cụ thể để tăng tính phân loại.")

    return round(min(1.0, score), 3), notes


def _score_distractor_quality(question_json: dict, loai: str) -> tuple[float, list[str]]:
    """Chấm điểm chất lượng phương án nhiễu (MCQ) / 4 mệnh đề (TRUE_FALSE) / đáp án (0.0 - 1.0)."""
    notes: list[str] = []

    if loai == "MCQ":
        opts = [str(question_json.get(k, "")).strip() for k in ("A", "B", "C", "D")]
        dap_an = str(question_json.get("dap_an", "A")).strip().upper()
        ans_idx = ["A", "B", "C", "D"].index(dap_an) if dap_an in ("A", "B", "C", "D") else 0

        has_lazy = any(pat in o.lower() for o in opts for pat in LAZY_DISTRACTOR_PATTERNS)
        s_lazy = 0.0 if has_lazy else 0.35
        if has_lazy:
            notes.append("Tránh dùng phương án nhiễu kiểu 'Tất cả đều đúng' / 'Cả A và B'.")

        lens = [len(o) for o in opts]
        max_l, min_l = max(lens), max(min(lens), 1)
        if max_l <= 25:
            s_bal = 0.40
        else:
            ratio = max_l / min_l
            ans_ratio = lens[ans_idx] / max(sum(lens[i] for i in range(4) if i != ans_idx) / 3.0, 1.0)
            if ratio <= 1.6 and ans_ratio <= 1.35:
                s_bal = 0.40
            elif ratio <= 2.3 and ans_ratio <= 1.6:
                s_bal = 0.30
            else:
                s_bal = 0.15
                notes.append("Độ dài 4 phương án A, B, C, D chưa thật sự đồng đều.")

        toks = [_tokenize_vi(o) for o in opts]
        max_sim = 0.0
        for i in range(4):
            for j in range(i + 1, 4):
                max_sim = max(max_sim, _jaccard(toks[i], toks[j]))
        s_div = 0.25 if max_sim < 0.85 else 0.12
        return round(s_lazy + s_bal + s_div, 3), notes

    elif loai == "TRUE_FALSE":
        ans = [_normalize_tf_answer((question_json.get(k) or {}).get("dap_an", "")) for k in ("a", "b", "c", "d")]
        stmts = [str((question_json.get(k) or {}).get("menh_de", "")).strip() for k in ("a", "b", "c", "d")]

        n_true = ans.count("Đúng")
        if n_true == 2:
            s_bal = 0.45
        elif n_true in (1, 3):
            s_bal = 0.38
        else:
            s_bal = 0.0
            notes.append("Cần phân bổ hợp lý cả mệnh đề Đúng và mệnh đề Sai (tốt nhất 2 Đúng - 2 Sai).")

        toks = [_tokenize_vi(s) for s in stmts]
        max_sim = 0.0
        for i in range(4):
            for j in range(i + 1, 4):
                max_sim = max(max_sim, _jaccard(toks[i], toks[j]))
        s_indep = 0.35 if max_sim < 0.55 else (0.25 if max_sim < 0.72 else 0.10)
        if max_sim >= 0.65:
            notes.append("Nên đa dạng hóa góc hỏi giữa 4 mệnh đề a, b, c, d để tăng tính độc lập.")

        s_len = 0.20 if all(len(s) >= 18 for s in stmts) else 0.12
        return round(s_bal + s_indep + s_len, 3), notes

    elif loai == "SHORT_ANSWER":
        ans = str(question_json.get("dap_an_ngan", "")).strip()
        s_ans = 0.60 if 1 <= len(ans) <= 25 else 0.35
        has_num_or_val = bool(re.search(r"[0-9A-Za-zÀ-ỹ]", ans))
        return round(s_ans + (0.40 if has_num_or_val else 0.0), 3), notes

    else:  # ESSAY_CODE
        code_mau = str(question_json.get("dap_an_mau", "")).replace("```python", "").replace("```", "").strip()
        lines = [l for l in code_mau.splitlines() if l.strip()]
        s_code = 0.60 if len(lines) >= 3 else 0.35
        tc = question_json.get("tieu_chi_cham_diem", [])
        s_rubric = 0.40 if isinstance(tc, list) and len(tc) >= 3 else 0.25
        return round(s_code + s_rubric, 3), notes


def fuzzy_quality_validate(
    question_json: dict,
    loai_cau_hoi: str,
    evidence_package: dict,
) -> dict:
    """
    Tầng 2 (Fuzzy Quality Validator): Chấm điểm chất lượng từ 0.0 đến 1.0 theo 3 trụ cột:
      - Độ bám nguồn SGK & thuật ngữ chuẩn (40%)
      - Mức độ nhận thức & chất lượng sư phạm (30%)
      - Chất lượng phương án nhiễu / mệnh đề (30%)
    Phân loại chuẩn: >= 0.75 (ĐẠT), 0.50 - 0.74 (CẦN SỬA), < 0.50 (KHÔNG ĐẠT).
    """
    loai = loai_cau_hoi.strip().upper()
    s_sgk, n_sgk = _score_sgk_grounding(question_json, evidence_package)
    s_cog, n_cog = _score_cognitive_pedagogy(question_json, loai, evidence_package)
    s_dis, n_dis = _score_distractor_quality(question_json, loai)

    diem_tong = round(0.40 * s_sgk + 0.30 * s_cog + 0.30 * s_dis, 3)

    if diem_tong >= 0.75:
        xep_loai = "ĐẠT"
    elif diem_tong >= 0.50:
        xep_loai = "CẦN SỬA"
    else:
        xep_loai = "KHÔNG ĐẠT"

    return {
        "diem_tong": diem_tong,
        "xep_loai": xep_loai,
        "chi_tiet": {
            "bam_nguon_sgk": s_sgk,
            "nhan_thuc_su_pham": s_cog,
            "chat_luong_nhieu": s_dis,
        },
        "goi_y_sua": n_sgk + n_cog + n_dis,
    }


def validate_question(
    question_json: dict,
    loai_cau_hoi: str,
    evidence_package: dict,
) -> dict:
    """Chạy đầy đủ quy trình kiểm định 2 tầng (Tầng 1 Hard Gate + Sandbox -> Tầng 2 Fuzzy Quality)."""
    if isinstance(question_json, dict) and "trich_dan_sgk" in question_json:
        question_json["trich_dan_sgk"] = _clean_sgk_citation(question_json["trich_dan_sgk"])
    tier1 = rule_validate(question_json, loai_cau_hoi, evidence_package)
    sandbox_verified = bool(tier1.get("sandbox_verified", False))

    if not tier1["passed"]:
        feedback = "LỖI TẦNG 1 (HARD GATE - BẮT BUỘC SỬA): " + " | ".join(tier1["errors"])
        return {
            "is_pass": False,
            "xep_loai": "KHÔNG ĐẠT",
            "diem_chat_luong": 0.0,
            "sandbox_verified": sandbox_verified,
            "sandbox_stdout": tier1.get("sandbox_stdout", ""),
            "tier1": tier1,
            "tier2": None,
            "feedback": feedback,
        }

    tier2 = fuzzy_quality_validate(question_json, loai_cau_hoi, evidence_package)
    is_pass = tier2["xep_loai"] == "ĐẠT"
    feedback = ""
    if not is_pass:
        suggestions = tier2["goi_y_sua"] or ["Tăng độ bám nguyên văn trích dẫn SGK và cải thiện chất lượng phương án nhiễu."]
        feedback = (
            f"XẾP LOẠI TẦNG 2: {tier2['xep_loai']} (điểm {tier2['diem_tong']}/1.0, cần >= 0.75). "
            f"CẦN CẢI THIỆN: " + " | ".join(suggestions)
        )

    return {
        "is_pass": is_pass,
        "xep_loai": tier2["xep_loai"],
        "diem_chat_luong": tier2["diem_tong"],
        "sandbox_verified": sandbox_verified,
        "sandbox_stdout": tier1.get("sandbox_stdout", ""),
        "tier1": tier1,
        "tier2": tier2,
        "feedback": feedback,
    }


if __name__ == "__main__":
    print("=== KIỂM THỬ NHANH CORE/VALIDATOR.PY (HARD GATE + SANDBOX) ===\n")
    mock_ev = {
        "bai_hoc": "Bài 19",
        "loai_cau_hoi": "MCQ",
        "sgk_chunks": [{
            "bai_hoc": "Bài 19",
            "trang": 102,
            "content": "Trong Python, biểu thức lôgic là biểu thức chỉ nhận giá trị True (đúng) hoặc False (sai). Câu lệnh rẽ nhánh if thể hiện cấu trúc rẽ nhánh trong Python.",
        }],
        "glossary_terms": [{
            "thuat_ngu": "Biểu thức lôgic",
            "dinh_nghia_sgk": "Trong Python, biểu thức lôgic là biểu thức chỉ nhận giá trị True (đúng) hoặc False (sai), thuộc kiểu bool.",
            "bai_hoc": "Bài 19",
            "trang": 102,
        }],
    }

    # Test 1: MCQ có phương án giữ chỗ "Biểu thức A/B/C" -> PHẢI RỚT Tầng 1
    bad_mcq = {
        "cau_hoi": "Trong câu lệnh rẽ nhánh if, điều kiện phải là gì?",
        "A": "Biểu thức A",
        "B": "Biểu thức B",
        "C": "Phương án 1",
        "D": "Đáp án A",
        "dap_an": "A",
        "giai_thich": "Điều kiện trong câu lệnh if phải là biểu thức lôgic nhận giá trị True hoặc False.",
        "trich_dan_sgk": "Trong Python, biểu thức lôgic là biểu thức chỉ nhận giá trị True (đúng) hoặc False (sai).",
    }
    res_bad_mcq = validate_question(bad_mcq, "MCQ", mock_ev)
    print(f"[TEST 1 - MCQ giữ chỗ] PASS={res_bad_mcq['is_pass']} | Errors={res_bad_mcq['tier1']['errors']}")
    assert not res_bad_mcq["is_pass"], "PHẢI chặn phương án giữ chỗ!"

    # Test 2: MCQ chuẩn có code Python chạy được (dữ liệu mới, không trùng 1-shot) -> Sandbox VERIFIED + ĐẠT
    good_mcq = {
        "cau_hoi": "Cho đoạn chương trình Python sau:\nm = 11\nif m > 10:\n    print('Lon')\nelse:\n    print('Nho')\nKết quả in ra màn hình là gì?",
        "A": "Lon",
        "B": "Nho",
        "C": "11",
        "D": "10",
        "dap_an": "A",
        "giai_thich": "Vì biểu thức lôgic 11 > 10 nhận giá trị True nên thực hiện nhánh if in ra 'Lon'.",
        "trich_dan_sgk": "Trong Python, biểu thức lôgic là biểu thức chỉ nhận giá trị True (đúng) hoặc False (sai).",
    }
    res_good_mcq = validate_question(good_mcq, "MCQ", mock_ev)
    print(f"[TEST 2 - MCQ code đúng] PASS={res_good_mcq['is_pass']} | Score={res_good_mcq['diem_chat_luong']} | Sandbox={res_good_mcq['sandbox_verified']} | Out='{res_good_mcq['sandbox_stdout']}'")
    assert res_good_mcq["is_pass"] and res_good_mcq["sandbox_verified"], f"MCQ chuẩn phải PASS & Sandbox verified! {res_good_mcq}"

    # Test 3: TRUE_FALSE có code Python bị lỗi Runtime (chia cho 0 / NameError) -> Sandbox BẮT LỖI
    mock_ev_tf = dict(mock_ev, loai_cau_hoi="TRUE_FALSE")
    bad_tf_code = {
        "cau_hoi_chung": "Cho đoạn chương trình Python sau:\na = 5\nprint(a / 0)\nXét các phát biểu sau:",
        "a": {"menh_de": "Biến a có kiểu số nguyên int.", "dap_an": "Đúng", "giai_thich": "a được gán giá trị 5 thuộc kiểu int."},
        "b": {"menh_de": "Chương trình in ra giá trị 5.", "dap_an": "Sai", "giai_thich": "Phép chia cho 0 gây lỗi ZeroDivisionError."},
        "c": {"menh_de": "Biểu thức a > 0 nhận giá trị True.", "dap_an": "Đúng", "giai_thich": "Vì 5 > 0 là đúng nên trả về True."},
        "d": {"menh_de": "Biến a thuộc kiểu xâu kí tự str.", "dap_an": "Sai", "giai_thich": "5 không nằm trong dấu nháy nên là int."},
        "trich_dan_sgk": "Trong Python, biểu thức lôgic là biểu thức chỉ nhận giá trị True (đúng) hoặc False (sai).",
    }
    res_bad_tf = validate_question(bad_tf_code, "TRUE_FALSE", mock_ev_tf)
    print(f"[TEST 3 - TRUE_FALSE code lỗi runtime] PASS={res_bad_tf['is_pass']} | Sandbox={res_bad_tf['sandbox_verified']} | Errors={res_bad_tf['tier1']['errors']}")
    assert not res_bad_tf["is_pass"] and not res_bad_tf["sandbox_verified"], "Sandbox phải chặn code lỗi runtime!"

    # Test 4: TRUE_FALSE Bài 20 có code Python chạy chuẩn (dữ liệu mới) -> Sandbox VERIFIED + ĐẠT
    mock_ev_b20_tf = {
        "bai_hoc": "Bài 20",
        "loai_cau_hoi": "TRUE_FALSE",
        "sgk_chunks": [{
            "bai_hoc": "Bài 20",
            "trang": 106,
            "content": "Trong Python, câu lệnh lặp for kết hợp hàm range() dùng để thực hiện lặp với số lần biết trước.",
        }],
        "glossary_terms": [{
            "thuat_ngu": "Câu lệnh lặp for",
            "dinh_nghia_sgk": "Câu lệnh lặp for kết hợp hàm range() dùng để duyệt qua vùng giá trị nguyên trong Python.",
            "bai_hoc": "Bài 20",
            "trang": 106,
        }],
    }
    good_tf = {
        "cau_hoi_chung": "Cho đoạn chương trình Python sau:\ntong = 0\nfor k in range(2, 6):\n    tong = tong + k\nprint(tong)\nXét các phát biểu sau:",
        "a": {"menh_de": "Vòng lặp for duyệt biến k lần lượt qua các giá trị 2, 3, 4, 5.", "dap_an": "Đúng", "giai_thich": "Hàm range(2, 6) sinh dãy số từ 2 đến 5."},
        "b": {"menh_de": "Vòng lặp thực hiện đúng 5 lần lặp.", "dap_an": "Sai", "giai_thich": "range(2, 6) gồm 4 số 2, 3, 4, 5 nên lặp 4 lần."},
        "c": {"menh_de": "Kết quả in ra màn hình là 14.", "dap_an": "Đúng", "giai_thich": "Tổng tong = 0 + 2 + 3 + 4 + 5 = 14."},
        "d": {"menh_de": "Biến tong thuộc kiểu xâu kí tự str.", "dap_an": "Sai", "giai_thich": "tong được khởi tạo bằng 0 và cộng số nguyên nên có kiểu int."},
        "trich_dan_sgk": "Trong Python, câu lệnh lặp for kết hợp hàm range() dùng để thực hiện lặp với số lần biết trước.",
    }
    res_good_tf = validate_question(good_tf, "TRUE_FALSE", mock_ev_b20_tf)
    print(f"[TEST 4 - TRUE_FALSE Bài 20 chuẩn] PASS={res_good_tf['is_pass']} | Score={res_good_tf['diem_chat_luong']} | Sandbox={res_good_tf['sandbox_verified']} | Out='{res_good_tf['sandbox_stdout']}'")
    assert res_good_tf["is_pass"] and res_good_tf["sandbox_verified"], f"TRUE_FALSE chuẩn phải PASS & Sandbox verified! {res_good_tf}"

    # Test 5: Chặn sao chép dữ liệu mẫu 1-shot cũ (x = 7, 'Chan'/'Le', range(1, 5))
    oneshot_mcq = {
        "cau_hoi": "Cho đoạn chương trình Python sau:\nx = 7\nif x % 2 == 0:\n    print('Chan')\nelse:\n    print('Le')\nKết quả in ra màn hình là gì?",
        "A": "Chan", "B": "Le", "C": "7", "D": "0", "dap_an": "B",
        "giai_thich": "Vì 7 % 2 == 0 là False nên thực hiện nhánh else in ra 'Le'.",
        "trich_dan_sgk": "Trong Python, biểu thức lôgic là biểu thức chỉ nhận giá trị True (đúng) hoặc False (sai).",
    }
    res_oneshot = validate_question(oneshot_mcq, "MCQ", mock_ev)
    print(f"[TEST 5 - Chặn trùng mẫu 1-shot] PASS={res_oneshot['is_pass']} | Errors={res_oneshot['tier1']['errors']}")
    assert not res_oneshot["is_pass"], "PHẢI chặn câu sao chép dữ liệu mẫu 1-shot!"

    # Test 6: Chặn câu hỏi tính kết quả nhưng thiếu đoạn mã Python trong đề
    missing_code_sa = {
        "cau_hoi": "Kết quả in ra màn hình của đoạn chương trình trên là bao nhiêu?",
        "dap_an_ngan": "10",
        "giai_thich": "Chương trình in ra giá trị 10.",
        "trich_dan_sgk": "Trong Python, biểu thức lôgic là biểu thức chỉ nhận giá trị True (đúng) hoặc False (sai).",
    }
    res_missing = validate_question(missing_code_sa, "SHORT_ANSWER", dict(mock_ev, loai_cau_hoi="SHORT_ANSWER"))
    print(f"[TEST 6 - Chặn thiếu code] PASS={res_missing['is_pass']} | Errors={res_missing['tier1']['errors']}")
    assert not res_missing["is_pass"], "PHẢI chặn câu hỏi thiếu đoạn mã Python!"

    # Test 7: Chặn hỏi kết quả biến chưa khởi tạo
    uninit_sa = {
        "cau_hoi": "Cho đoạn mã Python:\na = 3\nprint(a + b)\nGiá trị của biến b sau khi chạy là bao nhiêu?",
        "dap_an_ngan": "5",
        "giai_thich": "Biến b cộng với a cho ra 5.",
        "trich_dan_sgk": "Trong Python, biểu thức lôgic là biểu thức chỉ nhận giá trị True (đúng) hoặc False (sai).",
    }
    res_uninit = validate_question(uninit_sa, "SHORT_ANSWER", dict(mock_ev, loai_cau_hoi="SHORT_ANSWER"))
    print(f"[TEST 7 - Chặn biến chưa khởi tạo] PASS={res_uninit['is_pass']} | Errors={res_uninit['tier1']['errors']}")
    assert not res_uninit["is_pass"], "PHẢI chặn biến chưa khởi tạo giá trị!"

    # Test 8 (Audit Case 5): Chặn MCQ có 4 phương án đều đúng cú pháp (ast.parse)
    ev_b17 = {
        "bai_hoc": "Bài 17",
        "loai_cau_hoi": "MCQ",
        "sgk_chunks": [{"bai_hoc": "Bài 17", "trang": 90, "content": "Trong Python, lệnh gán dùng dấu = để gán giá trị cho biến."}],
        "glossary_terms": [],
    }
    ambiguous_mcq = {
        "cau_hoi": "Trong Python, câu lệnh gán nào sau đây viết đúng cú pháp?",
        "A": "a = 5", "B": "b = 10", "C": "c = 15", "D": "d = 20", "dap_an": "A",
        "giai_thich": "Lệnh gán dùng dấu = để gán giá trị cho biến.",
        "trich_dan_sgk": "Trong Python, lệnh gán dùng dấu = để gán giá trị cho biến.",
    }
    res_ambig = validate_question(ambiguous_mcq, "MCQ", ev_b17)
    print(f"[AUDIT CASE 5 / TEST 8 - MCQ 4 phương án đều đúng cú pháp] PASS={res_ambig['is_pass']} | Errors={res_ambig['tier1']['errors']}")
    assert not res_ambig["is_pass"], "PHẢI chặn MCQ lệnh gán có >= 2 phương án đúng cú pháp!"

    # Audit Case 1: TRUE_FALSE Bài 26 thiếu `def` trong đề (cau_hoi_chung) dù ý trả lời có nhắc 'def'
    ev_b26_tf = {
        "bai_hoc": "Bài 26",
        "loai_cau_hoi": "TRUE_FALSE",
        "sgk_chunks": [{"bai_hoc": "Bài 26", "trang": 130, "content": "Trong Python, hàm được định nghĩa bằng từ khóa def theo sau là tên hàm và danh sách tham số."}],
        "glossary_terms": [],
    }
    tf_b26_no_def = {
        "cau_hoi_chung": "Cho đoạn chương trình Python sau:\ns = 0\nfor i in range(2, 5):\n    s = s + i\nprint(s)\nXét các phát biểu sau:",
        "a": {"menh_de": "Từ khóa def dùng để định nghĩa hàm trong Python.", "dap_an": "Đúng", "giai_thich": "Trong Python, hàm được khai báo bằng từ khóa def."},
        "b": {"menh_de": "Kết quả in ra màn hình là 9.", "dap_an": "Đúng", "giai_thich": "Tổng 2 + 3 + 4 = 9."},
        "c": {"menh_de": "Vòng lặp chạy 5 lần.", "dap_an": "Sai", "giai_thich": "range(2, 5) chỉ có 3 phần tử là 2, 3, 4."},
        "d": {"menh_de": "Biến s thuộc kiểu str.", "dap_an": "Sai", "giai_thich": "Biến s lưu số nguyên nên thuộc kiểu int."},
        "trich_dan_sgk": "Trong Python, hàm được định nghĩa bằng từ khóa def theo sau là tên hàm và danh sách tham số.",
    }
    res_audit1 = validate_question(tf_b26_no_def, "TRUE_FALSE", ev_b26_tf)
    print(f"[AUDIT CASE 1 - TRUE_FALSE Bài 26 thiếu def trong đề] PASS={res_audit1['is_pass']} | Errors={res_audit1['tier1']['errors']}")
    assert not res_audit1["is_pass"], "PHẢI chặn TRUE_FALSE Bài 26 thiếu từ khóa def trong đề!"

    # Audit Case 2: TRUE_FALSE Bài 20 chọn 'Đúng' cho kết quả in sai (15 != 14)
    tf_b20_wrong_out = {
        "cau_hoi_chung": "Cho đoạn chương trình Python sau:\ntong = 0\nfor k in range(2, 6):\n    tong = tong + k\nprint(tong)\nXét các phát biểu sau:",
        "a": {"menh_de": "Vòng lặp for duyệt biến k qua các giá trị 2, 3, 4, 5.", "dap_an": "Đúng", "giai_thich": "range(2, 6) tạo ra các số nguyên 2, 3, 4, 5."},
        "b": {"menh_de": "Vòng lặp chạy đúng 5 lần.", "dap_an": "Sai", "giai_thich": "Chỉ có 4 giá trị nên lặp 4 lần."},
        "c": {"menh_de": "Kết quả in ra màn hình là 15.", "dap_an": "Đúng", "giai_thich": "Cộng dồn các giá trị k được 15."},
        "d": {"menh_de": "Biến tong có kiểu xâu str.", "dap_an": "Sai", "giai_thich": "Biến tong khởi tạo bằng 0 nên có kiểu int."},
        "trich_dan_sgk": "Trong Python, câu lệnh lặp for kết hợp hàm range() dùng để thực hiện lặp với số lần biết trước.",
    }
    res_audit2 = validate_question(tf_b20_wrong_out, "TRUE_FALSE", mock_ev_b20_tf)
    print(f"[AUDIT CASE 2 - TRUE_FALSE Bài 20 in sai 15 != 14] PASS={res_audit2['is_pass']} | Errors={res_audit2['tier1']['errors']}")
    assert not res_audit2["is_pass"], "PHẢI chặn TRUE_FALSE chọn Đúng cho kết quả in sai 15 != 14!"

    # Audit Case 3: SHORT_ANSWER không có print() (câu hỏi lý thuyết thuần văn bản)
    ev_b21_sa = {
        "bai_hoc": "Bài 21",
        "loai_cau_hoi": "SHORT_ANSWER",
        "sgk_chunks": [{"bai_hoc": "Bài 21", "trang": 110, "content": "Câu lệnh lặp while thực hiện lặp khi điều kiện còn đúng."}],
        "glossary_terms": [],
    }
    sa_no_print = {
        "cau_hoi": "Câu lệnh lặp while trong Python được sử dụng như thế nào khi chưa biết trước số lần lặp?",
        "dap_an_ngan": "while",
        "giai_thich": "Vòng lặp while dùng để lặp với số lần chưa biết trước dựa trên điều kiện.",
        "trich_dan_sgk": "Câu lệnh lặp while thực hiện lặp khi điều kiện còn đúng.",
    }
    res_audit3 = validate_question(sa_no_print, "SHORT_ANSWER", ev_b21_sa)
    print(f"[AUDIT CASE 3 - SHORT_ANSWER thiếu print()] PASS={res_audit3['is_pass']} | Errors={res_audit3['tier1']['errors']}")
    assert not res_audit3["is_pass"], "PHẢI chặn SHORT_ANSWER không có đoạn mã Python kèm print()!"

    # Audit Case 4: ESSAY_CODE lộ code lời giải ngay trong đề bài
    ev_b22_ec = {
        "bai_hoc": "Bài 22",
        "loai_cau_hoi": "ESSAY_CODE",
        "sgk_chunks": [{"bai_hoc": "Bài 22", "trang": 114, "content": "Kiểu dữ liệu danh sách (list) trong Python được biểu diễn bằng cặp dấu ngoặc vuông []."}],
        "glossary_terms": [],
    }
    ec_leaked = {
        "tinh_huong": "Cho danh sách A = [3, 8, 2, 5, 11]. Ta viết tong = 0 rồi dùng for v in A: tong += v để tính tổng.",
        "yeu_cau_hoc_sinh": "Hãy viết chương trình Python tính tổng các phần tử của danh sách A.",
        "dap_an_mau": "A = [3, 8, 2, 5, 11]\ntong = 0\nfor v in A:\n    tong += v\nprint(tong)",
        "tieu_chi_cham_diem": ["Khởi tạo danh sách A đúng (0.3đ)", "Duyệt danh sách và tính tổng đúng (0.4đ)", "In kết quả đúng (0.3đ)"],
        "trich_dan_sgk": "Kiểu dữ liệu danh sách (list) trong Python được biểu diễn bằng cặp dấu ngoặc vuông [].",
    }
    res_audit4 = validate_question(ec_leaked, "ESSAY_CODE", ev_b22_ec)
    print(f"[AUDIT CASE 4 - ESSAY_CODE lộ code trong đề] PASS={res_audit4['is_pass']} | Errors={res_audit4['tier1']['errors']}")
    assert not res_audit4["is_pass"], "PHẢI chặn ESSAY_CODE lộ lời giải (for/while/tong = 0) ngay trong đề!"

    # Check Case (a): TRUE_FALSE ghi kết quả 21 là 'Đúng' khi Sandbox stdout = 20
    tf_21_vs_20 = {
        "cau_hoi_chung": "Cho đoạn chương trình Python sau:\ntong = 0\nfor k in range(2, 10, 2):\n    tong = tong + k\nprint(tong)\nXét các phát biểu sau:",
        "a": {"menh_de": "Vòng lặp for duyệt biến k qua các giá trị 2, 4, 6, 8.", "dap_an": "Đúng", "giai_thich": "range(2, 10, 2) sinh 4 số chẵn 2, 4, 6, 8."},
        "b": {"menh_de": "Vòng lặp chạy đúng 5 lần.", "dap_an": "Sai", "giai_thich": "Chỉ có 4 phần tử nên lặp 4 lần."},
        "c": {"menh_de": "Kết quả in ra màn hình là 21.", "dap_an": "Đúng", "giai_thich": "Cộng dồn các giá trị được 21."},
        "d": {"menh_de": "Biến tong thuộc kiểu xâu str.", "dap_an": "Sai", "giai_thich": "tong lưu số nguyên nên thuộc kiểu int."},
        "trich_dan_sgk": "Trong Python, câu lệnh lặp for kết hợp hàm range() dùng để thực hiện lặp với số lần biết trước.",
    }
    res_check_a = validate_question(tf_21_vs_20, "TRUE_FALSE", mock_ev_b20_tf)
    err_a_str = " | ".join(res_check_a["tier1"]["errors"])
    print(f"[CHECK (a) - TRUE_FALSE 21 != 20] PASS={res_check_a['is_pass']} | Errors={res_check_a['tier1']['errors']}")
    assert not res_check_a["is_pass"] and "Kết quả thực thi thật của Python là 20, không phải 21" in err_a_str

    # Check Case (b): TRUE_FALSE bị cụt ý "Biểu thức điều kiện a"
    tf_truncated = {
        "cau_hoi_chung": "Cho đoạn chương trình Python sau:\na = 12\nif a >= 10:\n    print('Dat')\nelse:\n    print('Chua')\nXét các phát biểu sau:",
        "a": {"menh_de": "Biểu thức điều kiện a", "dap_an": "Đúng", "giai_thich": "Biến a có giá trị 12."},
        "b": {"menh_de": "Chương trình thực hiện nhánh else và in ra 'Chua'.", "dap_an": "Sai", "giai_thich": "Điều kiện đúng nên chạy nhánh if."},
        "c": {"menh_de": "Kết quả in ra màn hình là 'Dat'.", "dap_an": "Đúng", "giai_thich": "Vì 12 >= 10 là True nên in ra 'Dat'."},
        "d": {"menh_de": "Biến a thuộc kiểu xâu kí tự str.", "dap_an": "Sai", "giai_thich": "a = 12 là số nguyên kiểu int."},
        "trich_dan_sgk": "Trong Python, biểu thức lôgic là biểu thức chỉ nhận giá trị True (đúng) hoặc False (sai).",
    }
    res_check_b = validate_question(tf_truncated, "TRUE_FALSE", mock_ev_tf)
    print(f"[CHECK (b) - TRUE_FALSE cụt ý] PASS={res_check_b['is_pass']} | Errors={res_check_b['tier1']['errors']}")
    assert not res_check_b["is_pass"] and any("cụt ý" in e for e in res_check_b["tier1"]["errors"])

    # Check Case (c): SHORT_ANSWER thiếu print() (có code nhưng không in ra)
    sa_code_no_print = {
        "cau_hoi": "Cho đoạn chương trình Python sau:\nk = 1\nwhile k < 4:\n    k = k + 1\nGiá trị cuối cùng của k là bao nhiêu?",
        "dap_an_ngan": "4",
        "giai_thich": "Sau vòng lặp while, biến k có giá trị bằng 4.",
        "trich_dan_sgk": "Câu lệnh lặp while thực hiện lặp khi điều kiện còn đúng.",
    }
    res_check_c = validate_question(sa_code_no_print, "SHORT_ANSWER", ev_b21_sa)
    print(f"[CHECK (c) - SHORT_ANSWER thiếu print()] PASS={res_check_c['is_pass']} | Errors={res_check_c['tier1']['errors']}")
    assert not res_check_c["is_pass"]

    # Check Case (d): ESSAY_CODE lộ code 'for x in A:' và 'ong = 0' trong đề
    ec_leaked_d = {
        "tinh_huong": "Cho danh sách A = [5, 12, 7, 15, 9]. Khởi tạo ong = 0 và duyệt for x in A: để xử lý.",
        "yeu_cau_hoc_sinh": "Viết chương trình Python đếm các phần tử lớn hơn 8 trong danh sách A.",
        "dap_an_mau": "A = [5, 12, 7, 15, 9]\ndem = 0\nfor x in A:\n    if x > 8:\n        dem += 1\nprint(dem)",
        "tieu_chi_cham_diem": ["Khởi tạo A và biến đếm đúng (0.3đ)", "Duyệt danh sách đúng (0.4đ)", "In kết quả đúng (0.3đ)"],
        "trich_dan_sgk": "Kiểu dữ liệu danh sách (list) trong Python được biểu diễn bằng cặp dấu ngoặc vuông [].",
    }
    res_check_d = validate_question(ec_leaked_d, "ESSAY_CODE", ev_b22_ec)
    print(f"[CHECK (d) - ESSAY_CODE lộ for x in A: & ong = 0] PASS={res_check_d['is_pass']} | Errors={res_check_d['tier1']['errors']}")
    assert not res_check_d["is_pass"] and len(res_check_d["tier1"]["errors"]) >= 2

    # Bonus Check (e): MCQ thiếu 'for' trước 'in range(', Bài 24 chứa sum(, Bài 29 chứa {}
    mcq_missing_for = {
        "cau_hoi": "Trong Python, đoạn lệnh nào sau đây dùng để lặp với biến k chạy từ 1 đến 4?",
        "A": "k in range(1, 5):",
        "B": "for k in range(1, 5):",
        "C": "while k in range(1, 5):",
        "D": "loop k in range(1, 5):",
        "dap_an": "A",
        "giai_thich": "Dùng range(1, 5) để lặp từ 1 đến 4.",
        "trich_dan_sgk": "Trong Python, câu lệnh lặp for kết hợp hàm range() dùng để thực hiện lặp với số lần biết trước.",
    }
    res_mcq_for = validate_question(mcq_missing_for, "MCQ", dict(mock_ev_b20_tf, loai_cau_hoi="MCQ"))
    print(f"[CHECK (e) - MCQ thiếu for trước in range(] PASS={res_mcq_for['is_pass']} | Errors={res_mcq_for['tier1']['errors']}")
    assert not res_mcq_for["is_pass"]

    # Check (f): MCQ chứa cụm vô nghĩa "Câu hỏi là gì?"
    mcq_nonsense = {
        "cau_hoi": "Gọi các biến a = 5, b = 8 với lệnh if a < b. Câu hỏi là gì?",
        "A": "5", "B": "8", "C": "True", "D": "False", "dap_an": "C",
        "giai_thich": "Biểu thức a < b đúng vì 5 < 8.",
        "trich_dan_sgk": "Trong Python, biểu thức lôgic là biểu thức chỉ nhận giá trị True (đúng) hoặc False (sai).",
    }
    res_check_f = validate_question(mcq_nonsense, "MCQ", mock_ev)
    print(f"[CHECK (f) - MCQ 'Câu hỏi là gì?'] PASS={res_check_f['is_pass']} | Errors={res_check_f['tier1']['errors']}")
    assert not res_check_f["is_pass"] and any("Câu hỏi là gì?" in e for e in res_check_f["tier1"]["errors"])

    # Check (g): MCQ chứa thuật ngữ sai SGK "Biểu thức if" & phương án phép so sánh rời rạc ngăn bởi ';'
    mcq_bad_term_and_semi = {
        "cau_hoi": "Trong câu lệnh rẽ nhánh Python, Biểu thức if dùng để làm gì?",
        "A": "ds[0] > 5; ds[1] > 5; ds[2] > 5",
        "B": "Kiểm tra điều kiện lôgic True hoặc False",
        "C": "Khai báo danh sách mới",
        "D": "Lặp lại khối lệnh nhiều lần",
        "dap_an": "B",
        "giai_thich": "Câu lệnh if kiểm tra biểu thức điều kiện lôgic.",
        "trich_dan_sgk": "Trong Python, biểu thức lôgic là biểu thức chỉ nhận giá trị True (đúng) hoặc False (sai).",
    }
    res_check_g = validate_question(mcq_bad_term_and_semi, "MCQ", mock_ev)
    e_g = " | ".join(res_check_g["tier1"]["errors"])
    print(f"[CHECK (g) - MCQ 'Biểu thức if' & ';'] PASS={res_check_g['is_pass']} | Errors={res_check_g['tier1']['errors']}")
    assert not res_check_g["is_pass"] and "Biểu thức if" in e_g and "dấu ';'" in e_g

    # Check (h): ESSAY_CODE nối ghép 2 đề bài + từ bịa "ky_sut"
    ec_merged_and_typo = {
        "tinh_huong": "Cho hai số nguyên m = 4 và n = 9. Viết hàm tính tổng m + n.",
        "yeu_cau_hoc_sinh": "Cho hai số nguyên p = 3, q = 7. Viết hàm đếm ky_sut trong xâu.",
        "dap_an_mau": "def tinh(m, n):\n    return m + n\nprint(tinh(4, 9))",
        "tieu_chi_cham_diem": ["Định nghĩa hàm đúng (0.5đ)", "In kết quả đúng (0.5đ)"],
        "trich_dan_sgk": "Trong Python, hàm được định nghĩa bằng từ khóa def theo sau là tên hàm và danh sách tham số.",
    }
    res_check_h = validate_question(ec_merged_and_typo, "ESSAY_CODE", dict(ev_b26_tf, loai_cau_hoi="ESSAY_CODE"))
    e_h = " | ".join(res_check_h["tier1"]["errors"])
    print(f"[CHECK (h) - ESSAY_CODE nối 2 đề & ky_sut] PASS={res_check_h['is_pass']} | Errors={res_check_h['tier1']['errors']}")
    assert not res_check_h["is_pass"] and "nối ghép" in e_h and "ky_sut" in e_h

    print("\n✅ TẤT CẢ 20 CA KIỂM THỬ VALIDATOR + HARD GATE + SANDBOX ĐỀU ĐẠT 100%!")
