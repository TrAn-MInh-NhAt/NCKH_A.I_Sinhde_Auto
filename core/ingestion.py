import os
import re
import glob
import struct
import shutil
import unicodedata
import requests

os.environ["ANONYMIZED_TELEMETRY"] = "False"

import pymupdf
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document


class BatchOllamaEmbeddings(OllamaEmbeddings):
    """Tối ưu nhúng theo lô qua Ollama /api/embed cục bộ (nhanh hơn 50x, giữ nguyên vector nomic-embed-text)."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        all_embeddings: list[list[float]] = []
        batch_size = 32
        url = f"{self.base_url.rstrip('/')}/api/embed"
        try:
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                resp = requests.post(
                    url,
                    json={"model": self.model, "input": batch},
                    timeout=120,
                )
                resp.raise_for_status()
                all_embeddings.extend(resp.json()["embeddings"])
            return all_embeddings
        except Exception:
            return super().embed_documents(texts)

# Tự động định vị thư mục gốc dự án (D:\AI_Agent_NCKH)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data_raw")
DATA_DIR = os.path.join(BASE_DIR, "data")
OCR_CACHE_DIR = os.path.join(DATA_DIR, "ocr_cache")
DB_DIR = os.path.join(DATA_DIR, "chroma_db_v2")

# Bảng ánh xạ trang chính xác của Chủ đề F (Python) trong SGK Tin học 10 - Kết nối tri thức
LESSON_PAGE_MAP = [
    (87, 91, "Bài 16"),
    (92, 97, "Bài 17"),
    (98, 101, "Bài 18"),
    (102, 105, "Bài 19"),
    (106, 108, "Bài 20"),
    (109, 111, "Bài 21"),
    (112, 115, "Bài 22"),
    (116, 119, "Bài 23"),
    (120, 123, "Bài 24"),
    (124, 127, "Bài 25"),
    (128, 131, "Bài 26"),
    (132, 136, "Bài 27"),
    (137, 141, "Bài 28"),
    (142, 145, "Bài 29"),
    (146, 149, "Bài 30"),
    (150, 153, "Bài 31"),
    (154, 156, "Bài 32"),
]

# Từ khóa nhận diện câu hỏi Lập trình Python (Chủ đề F lớp 10)
PYTHON_KEYWORDS = [
    "python", "print(", "input(", "range(", "def ", "return ", "while ",
    "for ", "if ", "elif ", "else:", "if-else", "danh sách", "list",
    "xâu", "len(", ".append(", ".insert(", ".pop(", ".find(", ".split(",
    ".join(", ".count(", ".replace(", "phép gán", "lệnh gán", "biến ",
    "hàm ", "tham số", "đối số", "chương trình con", "câu lệnh lặp",
    "câu lệnh rẽ nhánh", "biểu thức logic", "biểu thức lôgic",
    "thụt đầu dòng", "int(", "float(", "str(", "[:", ":]"
]

# Từ khóa loại bỏ tuyệt đối các chủ đề ngoài Chủ đề F Python lớp 10
EXCLUDE_KEYWORDS = [
    # HTML / CSS / Web
    "html", "css", "<style>", "<textarea", "<form", "<input", "border-style",
    "font-size", "thẻ html", "trình duyệt", "siêu liên kết", "trang web", "website",
    # SQL / Cơ sở dữ liệu
    "sql", "cơ sở dữ liệu", "hệ quản trị", "khóa chính", "khóa ngoại",
    "bảng dữ liệu", "truy vấn", "bản ghi", "người quản trị cơ sở dữ liệu",
    # Mạng máy tính / IoT
    "mạng lan", "mạng máy tính", "switch", "bộ chuyển mạch", "địa chỉ ip",
    "địa chỉ mac", "ipv4", "https", "tên miền", "quản trị mạng",
    "internet vạn vật", "iot", "chia sẻ một thư mục", "phạm vi của mạng",
    # Đạo đức số / Pháp luật / Bản quyền
    "đạo đức", "bắt nạt", "không gian mạng", "sở hữu trí tuệ", "quyền tác giả",
    "tính nhân văn", "mạng xã hội", "ngắt lời cô giáo", "học liệu mở",
    # AI / Thiết kế đồ họa / Kiến thức chung ngoài Python
    "trí tuệ nhân tạo", "chatbot", "học máy", "thiết kế đồ họa", "phần mềm đồ họa",
    "tấm thiệp", "logo", "dãy bit", "hệ thập phân", "bảng mã ascii",
    "bảng mã unicode", "hệ màu rgb", "dung lượng bộ nhớ", "đơn vị lưu trữ",
    "thiết bị thông minh", "thiết bị không thông minh", "điện thoại thông minh",
    "google translate", "nhóm nghề dịch vụ", "nghề lập trình"
]

# Cấu hình 3 file đề thi tham khảo trong data_raw/
EXAM_SOURCES = [
    {
        "pdf_name": "Đề thi CK2 trường Xuyên Mộc-TpHCM.pdf",
        "cache_name": "De_thi_CK2_truong_Xuyen_Moc_TpHCM.md",
        "mode": "all_python",
        "min_part1_q": 1,
    },
    {
        "pdf_name": "Đề thi lớp 10.pdf",
        "cache_name": "De_thi_lop_10.md",
        "mode": "lop10_from_15",
        "min_part1_q": 15,
    },
    {
        "pdf_name": "Đề thi THPT quốc gia.pdf",
        "cache_name": "De_thi_THPT_quoc_gia.md",
        "mode": "python_keyword_only",
        "min_part1_q": 1,
    },
]


# ==============================================================================
# PHẦN 1: GIẢI MÃ FONT NXB GIÁO DỤC (TTF GLYPH-ID -> UNICODE TIẾNG VIỆT CHUẨN)
# ==============================================================================

def _parse_ttf_gid_to_unicode(ttf_path: str) -> dict[int, str]:
    """Đọc trực tiếp bảng cmap của file font TrueType để ánh xạ Glyph ID -> ký tự Unicode."""
    if not os.path.exists(ttf_path):
        return {}
    with open(ttf_path, "rb") as f:
        ttf_bytes = f.read()

    num_tables = struct.unpack(">H", ttf_bytes[4:6])[0]
    cmap_offset = None
    for i in range(num_tables):
        off = 12 + i * 16
        if ttf_bytes[off:off + 4] == b"cmap":
            cmap_offset = struct.unpack(">I", ttf_bytes[off + 8:off + 12])[0]
            break
    if cmap_offset is None:
        return {}

    num_sub = struct.unpack(">H", ttf_bytes[cmap_offset + 2:cmap_offset + 4])[0]
    gid_to_uni: dict[int, str] = {}
    for i in range(num_sub):
        rec = cmap_offset + 4 + i * 8
        pid, eid, sub_off = struct.unpack(">HHI", ttf_bytes[rec:rec + 8])
        if (pid, eid) not in ((3, 1), (0, 3)):
            continue
        pos = cmap_offset + sub_off
        fmt = struct.unpack(">H", ttf_bytes[pos:pos + 2])[0]
        if fmt != 4:
            continue
        seg_count = struct.unpack(">H", ttf_bytes[pos + 6:pos + 8])[0] // 2
        end_codes = struct.unpack(f">{seg_count}H", ttf_bytes[pos + 14:pos + 14 + 2 * seg_count])
        start_pos = pos + 16 + 2 * seg_count
        start_codes = struct.unpack(f">{seg_count}H", ttf_bytes[start_pos:start_pos + 2 * seg_count])
        delta_pos = start_pos + 2 * seg_count
        id_deltas = struct.unpack(f">{seg_count}h", ttf_bytes[delta_pos:delta_pos + 2 * seg_count])
        range_pos = delta_pos + 2 * seg_count
        id_ranges = struct.unpack(f">{seg_count}H", ttf_bytes[range_pos:range_pos + 2 * seg_count])
        for s_idx in range(seg_count):
            sc, ec, delta, ro = start_codes[s_idx], end_codes[s_idx], id_deltas[s_idx], id_ranges[s_idx]
            if sc == 0xFFFF:
                continue
            for cp in range(sc, ec + 1):
                if ro == 0:
                    gid = (cp + delta) & 0xFFFF
                else:
                    g_off = range_pos + 2 * s_idx + ro + 2 * (cp - sc)
                    gid = struct.unpack(">H", ttf_bytes[g_off:g_off + 2])[0]
                    if gid != 0:
                        gid = (gid + delta) & 0xFFFF
                if gid != 0 and gid not in gid_to_uni:
                    gid_to_uni[gid] = chr(cp)
    return gid_to_uni


def _load_system_font_maps() -> dict[str, dict[int, str]]:
    fonts_dir = r"C:\Windows\Fonts"
    mapping_files = {
        "ArialMT": "arial.ttf",
        "Arial-BoldMT": "arialbd.ttf",
        "Arial-ItalicMT": "ariali.ttf",
        "Consolas": "consola.ttf",
        "Consolas-Bold": "consolab.ttf",
    }
    return {
        name: _parse_ttf_gid_to_unicode(os.path.join(fonts_dir, fname))
        for name, fname in mapping_files.items()
    }


SYSTEM_FONT_MAPS = _load_system_font_maps()


def _normalize_vietnamese_text(text: str) -> str:
    """Chuẩn hóa ligature (fl, fi) và tổ hợp dấu tiếng Việt sang dạng NFC chuẩn."""
    text = text.replace("ﬂ", "fl").replace("ﬁ", "fi")
    # Sửa lỗi dotless-i + dấu thanh (kı́ -> kí) trong font SGK
    dotless_map = {
        "ı\u0301": "í", "ı\u0300": "ì", "ı\u0309": "ỉ",
        "ı\u0303": "ĩ", "ı\u0323": "ị",
    }
    for bad, good in dotless_map.items():
        text = text.replace(bad, good)
    text = unicodedata.normalize("NFC", text)
    return text


def decode_nxb_vietnamese(text: str) -> str:
    """Fallback giải mã font NXB Giáo Dục dạng chuỗi thuần (khi không có metadata font)."""
    text = re.sub(r"/uni([0-9A-Fa-f]{4})", lambda m: chr(int(m.group(1), 16)), text)
    fmap = SYSTEM_FONT_MAPS.get("ArialMT", {})
    if fmap:
        decoded = "".join(fmap.get(ord(ch), ch) if ch != " " else " " for ch in text)
    else:
        decoded = text
    decoded = _normalize_vietnamese_text(decoded)
    decoded = re.sub(r"\s+", " ", decoded)
    return decoded.strip()


def _is_gid_encoded_span(font_name: str, text: str, line_has_gid_arial: bool = False) -> bool:
    """Xác định chính xác một span văn bản có bị mã hóa Glyph-ID nội bộ của NXB Giáo Dục hay không."""
    if font_name not in SYSTEM_FONT_MAPS or not SYSTEM_FONT_MAPS[font_name]:
        return False
    if not text or not text.strip():
        return False

    if font_name == "Arial-ItalicMT":
        # Nếu đã là tiếng Việt Unicode chuẩn thì giữ nguyên
        if any(0x1E00 <= ord(c) <= 0x1EFF for c in text):
            return False
        return True

    if font_name.startswith("Consolas"):
        for ch in text:
            o = ord(ch)
            if o < 0x20 or (0x80 <= o <= 0x9F) or (0x150 <= o <= 0x3FF):
                return True
        return False

    # Nhóm ArialMT / Arial-BoldMT
    for ch in text:
        o = ord(ch)
        if o < 0x20 or (0x300 <= o <= 0x4FF) or o in (0xFF, 0x108, 0x103, 0x1AD, 0x1CA, 0x1E4, 0x1C9, 0x1E3, 0x1AC):
            return True

    if font_name == "ArialMT":
        if any(c in text for c in ("\\", "{", "}", "~")):
            return True
        if text in ("WKu", "Q", "EjL", "Oj", "Fy", "Yj", "WURQJ"):
            return True

    # Các từ khoá Python in đậm ngắn (như 'ERRO' -> 'bool', 'JOREDO' -> 'global') nằm trên dòng GID
    if font_name == "Arial-BoldMT" and line_has_gid_arial:
        stripped = text.strip()
        if re.fullmatch(r"[A-Z\\\[\]]{2,15}", stripped):
            return True

    return False


def decode_sgk_page(page: pymupdf.Page) -> str:
    """Giải mã trọn vẹn 1 trang SGK Tin học 10 KNTT (cả văn bản tiếng Việt lẫn mã nguồn Python)."""
    lines_out: list[str] = []
    # TEXT_INHIBIT_SPACES ngăn PyMuPDF chèn dấu cách giả 0x20 (vốn trùng GID dấu '=' trong Arial)
    flags = pymupdf.TEXTFLAGS_DICT | pymupdf.TEXT_INHIBIT_SPACES
    page_dict = page.get_text("dict", flags=flags)

    for block in page_dict["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            spans = line["spans"]
            # Kiểm tra trước xem dòng có chứa span Arial GID không (để bắt các từ khoá in đậm ngắn)
            line_has_gid_arial = any(
                s["font"].startswith("Arial")
                and any(ord(c) < 0x20 or (0x300 <= ord(c) <= 0x4FF) for c in s["text"])
                for s in spans
            )

            parts: list[str] = []
            for span in spans:
                fn = span["font"]
                t = span["text"]
                if fn == "SymbolMT":
                    t = (
                        t.replace("\x10", "-")
                        .replace("\x0e", "+")
                        .replace("\x0b", "(")
                        .replace("\x0c", ")")
                        .replace("\x03", " ")
                    )
                    parts.append("- " if t.strip() == "x" else t)
                elif fn == "iCielPanton-Black":
                    parts.append(t.replace("\n", "đ"))
                elif fn == "iCielGotham-Book":
                    parts.append(t.replace("\x03", " "))
                elif fn == "Inter18pt-Regular":
                    parts.append(t.replace("\ue084", "]"))
                elif _is_gid_encoded_span(fn, t, line_has_gid_arial):
                    fmap = SYSTEM_FONT_MAPS[fn]
                    parts.append("".join(fmap.get(ord(ch), ch) for ch in t))
                else:
                    parts.append(t)

            line_str = _normalize_vietnamese_text("".join(parts))
            line_str = re.sub(r"[ \t]+", " ", line_str).strip()
            # Lọc bỏ dòng chỉ chứa số trang đứng một mình ở chân trang
            if line_str and not re.fullmatch(r"\d{2,3}", line_str):
                lines_out.append(line_str)

    return "\n".join(lines_out)


# ==============================================================================
# PHẦN 2: NGUỒN 1 - XỬ LÝ SGK TIN HỌC 10 KNTT (TRANG 87 - 156, BÀI 16 - BÀI 32)
# ==============================================================================

def get_lesson_by_page(page_num: int) -> str | None:
    for start_p, end_p, lesson_name in LESSON_PAGE_MAP:
        if start_p <= page_num <= end_p:
            return lesson_name
    return None


def find_pdf_by_pattern(patterns: list[str]) -> str | None:
    all_pdfs = glob.glob(os.path.join(RAW_DIR, "*.pdf"))
    for pdf in all_pdfs:
        filename_lower = os.path.basename(pdf).lower()
        if any(pat.lower() in filename_lower for pat in patterns):
            return pdf
    return None


def process_sgk_kntt() -> list[Document]:
    pdf_path = find_pdf_by_pattern(["sgk", "kntt", "kết nối"])
    if not pdf_path:
        print(f"[LỖI] Không tìm thấy file SGK Tin học 10 trong thư mục: {RAW_DIR}")
        return []

    print(f"1. [Nguồn 1 - SGK_Tin10_KNTT] Đang đọc & giải mã font NXB Giáo Dục (Trang 87-156):")
    print(f"   -> {pdf_path}")

    doc = pymupdf.open(pdf_path)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=700,
        chunk_overlap=120,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    filtered_docs: list[Document] = []
    lesson_counts: dict[str, int] = {}

    for page_num in range(87, 157):
        if page_num > len(doc):
            break
        lesson_name = get_lesson_by_page(page_num)
        if not lesson_name:
            continue

        clean_content = decode_sgk_page(doc[page_num - 1])
        chunks = splitter.split_text(clean_content)

        for chunk in chunks:
            chunk_clean = chunk.strip()
            if len(chunk_clean) < 80:
                continue
            filtered_docs.append(
                Document(
                    page_content=chunk_clean,
                    metadata={
                        "nguon": "SGK_Tin10_KNTT",
                        "bai_hoc": lesson_name,
                        "vai_tro": "ly_thuyet_chuan",
                        "trang": page_num,
                    },
                )
            )
            lesson_counts[lesson_name] = lesson_counts.get(lesson_name, 0) + 1

    doc.close()
    print(f"   ✅ Trích xuất thành công {len(filtered_docs)} chunks sạch từ {len(lesson_counts)} bài (Bài 16 - Bài 32).")
    summary_str = ", ".join(f"{k}: {v}" for k, v in sorted(lesson_counts.items(), key=lambda x: int(x[0].split()[1])))
    print(f"   📊 Phân bố theo bài: {summary_str}")
    return filtered_docs


# ==============================================================================
# PHẦN 3: NGUỒN 2 - XỬ LÝ & LỌC PYTHON 3 ĐỀ THI THAM KHẢO 2026
# ==============================================================================

def _extract_exam_text(pdf_path: str, cache_path: str) -> str:
    """
    Trích xuất văn bản từ file PDF đề thi (hoàn toàn offline):
    - Ưu tiên đọc lớp text nhúng của PDF nếu có.
    - Nếu PDF là dạng ảnh scan (0 ký tự text), đọc từ bản OCR chuẩn hóa trong data/ocr_cache/.
    - Nếu chưa có cache, tự động chạy EasyOCR offline (download_enabled=False) và lưu cache.
    """
    doc = pymupdf.open(pdf_path)
    embedded_text = "\n".join(page.get_text("text") for page in doc).strip()
    if len(embedded_text) >= 200:
        doc.close()
        return embedded_text

    if os.path.exists(cache_path):
        doc.close()
        with open(cache_path, "r", encoding="utf-8") as f:
            return f.read()

    # Fallback EasyOCR hoàn toàn offline nếu chưa có file cache
    print(f"   🔎 File PDF dạng ảnh scan chưa có cache -> Chạy EasyOCR offline cho {os.path.basename(pdf_path)}...")
    import torch
    import easyocr

    reader = easyocr.Reader(["vi", "en"], gpu=torch.cuda.is_available(), download_enabled=False)
    pages_text = []
    for idx, page in enumerate(doc):
        pix = page.get_pixmap(dpi=150)
        lines = reader.readtext(pix.tobytes("png"), detail=0, paragraph=True)
        pages_text.append(f"\n<!-- Trang {idx + 1} -->\n" + "\n".join(lines))
    doc.close()

    full_text = "\n".join(pages_text)
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(full_text)
    return full_text


def _parse_exam_questions(raw_text: str) -> list[dict]:
    """Tách văn bản đề thi thành danh sách câu hỏi nguyên vẹn kèm phần thi (MCQ / TRUE_FALSE / SHORT_ANSWER)."""
    questions: list[dict] = []
    current_part = "MCQ"
    current_q_num: int | None = None
    current_lines: list[str] = []

    def flush_question():
        if current_q_num is not None and current_lines:
            body = "\n".join(current_lines).strip()
            if len(body) >= 30:
                questions.append({
                    "part": current_part,
                    "q_num": current_q_num,
                    "text": body,
                })

    for line in raw_text.splitlines():
        stripped = line.strip()
        upper = stripped.upper()

        # Nhận diện tiêu đề Phần I / II / III
        if re.match(r"^#{0,3}\s*PHẦN\s+I\b", upper) and "PHẦN II" not in upper and "PHẦN III" not in upper:
            flush_question()
            current_part = "MCQ"
            current_q_num = None
            current_lines = []
            continue
        if re.match(r"^#{0,3}\s*PHẦN\s+II\b", upper) and "PHẦN III" not in upper:
            flush_question()
            current_part = "TRUE_FALSE"
            current_q_num = None
            current_lines = []
            continue
        if re.match(r"^#{0,3}\s*PHẦN\s+III\b", upper):
            flush_question()
            current_part = "SHORT_ANSWER"
            current_q_num = None
            current_lines = []
            continue

        # Nhận diện đầu mỗi câu hỏi: "### Câu 15" hoặc "Câu 15."
        m = re.match(r"^(?:#{1,4}\s*)?Câu\s+(\d+)\s*[\.:]?\s*(.*)$", stripped)
        if m:
            flush_question()
            current_q_num = int(m.group(1))
            rest = m.group(2).strip()
            header = f"Câu {current_q_num}." + (f" {rest}" if rest else "")
            current_lines = [header]
        elif current_q_num is not None:
            current_lines.append(line)

    flush_question()
    return questions


def _has_excluded_topic(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in EXCLUDE_KEYWORDS)


def _python_keyword_score(text: str) -> int:
    t = text.lower()
    return sum(1 for kw in PYTHON_KEYWORDS if kw in t)


def _infer_lesson_from_question(text: str) -> str:
    """Ánh xạ tự động câu hỏi tham khảo về bài học tương ứng trong Chủ đề F (Bài 16 - Bài 32)."""
    t = text.lower()
    if "global" in t or "cục bộ" in t or "toàn cục" in t:
        return "Bài 28"
    if "tham số" in t or "đối số" in t:
        return "Bài 27"
    if "def " in t or "chương trình con" in t or "thành phần bắt buộc phải có trong hàm" in t:
        return "Bài 26"
    if any(k in t for k in [".find(", ".split(", ".join(", ".replace(", ".count("]):
        return "Bài 25"
    if "xâu" in t or "[:3]" in t or "[m:]" in t or "số kí tự" in t:
        return "Bài 24"
    if any(k in t for k in [".insert(", ".pop(", ".remove(", "x+y", "a + b"]):
        return "Bài 23"
    if "danh sách" in t or "list" in t or ".append(" in t or "a[len(" in t or "l = [" in t:
        return "Bài 22"
    if "while" in t or "vòng lặp vô tận" in t or "lặp vô tận" in t:
        return "Bài 21"
    if "for " in t or "range(" in t or "câu lệnh lặp" in t:
        return "Bài 20"
    if "if " in t or "if-else" in t or "rẽ nhánh" in t or "thụt đầu dòng" in t or "logic" in t:
        return "Bài 19"
    if "input(" in t or "int(" in t or "float(" in t:
        return "Bài 18"
    if "phép gán" in t or "lệnh gán" in t or "từ khoá" in t:
        return "Bài 17"
    return "Tong_hop_Python"


def process_de_tham_khao_2026() -> list[Document]:
    print("\n2. [Nguồn 2 - De_Tham_Khao_2026] Đang đọc & lọc CHỈ giữ câu hỏi Lập trình Python từ 3 đề thi:")
    kept_docs: list[Document] = []

    for cfg in EXAM_SOURCES:
        pdf_name = cfg["pdf_name"]
        pdf_path = os.path.join(RAW_DIR, pdf_name)
        cache_path = os.path.join(OCR_CACHE_DIR, cfg["cache_name"])
        mode = cfg["mode"]
        min_p1 = cfg["min_part1_q"]

        if not os.path.exists(pdf_path):
            print(f"   ⚠️ Không tìm thấy file: {pdf_path} (Bỏ qua).")
            continue

        raw_text = _extract_exam_text(pdf_path, cache_path)
        questions = _parse_exam_questions(raw_text)

        kept_count = 0
        dropped_count = 0

        for q in questions:
            q_part = q["part"]
            q_num = q["q_num"]
            q_text = q["text"]

            # Bước lọc 1: Loại bỏ tuyệt đối HTML/CSS, SQL, Mạng máy tính, Đạo đức số, Đồ họa, AI, Bit...
            if _has_excluded_topic(q_text):
                dropped_count += 1
                continue

            # Bước lọc 2: Quy tắc riêng theo từng đề thi
            keep = False
            py_score = _python_keyword_score(q_text)

            if mode == "lop10_from_15":
                # Đề thi lớp 10.pdf: Phần I chỉ giữ từ Câu 15 trở đi; Phần II chỉ giữ câu Python
                if q_part == "MCQ" and q_num >= min_p1 and py_score >= 1:
                    keep = True
                elif q_part != "MCQ" and py_score >= 2:
                    keep = True
            elif mode == "python_keyword_only":
                # Đề thi THPT quốc gia.pdf: CHỈ giữ các câu có từ khóa Python rõ ràng
                if py_score >= 2 and ("python" in q_text.lower() or "def " in q_text.lower() or "while " in q_text.lower() or "for " in q_text.lower()):
                    keep = True
            elif mode == "all_python":
                # Đề thi CK2 trường Xuyên Mộc-TpHCM.pdf: toàn bộ phần Python
                if py_score >= 1:
                    keep = True

            if not keep:
                dropped_count += 1
                continue

            inferred_lesson = _infer_lesson_from_question(q_text)
            q_label = f"{q_part}_Cau_{q_num}"

            kept_docs.append(
                Document(
                    page_content=f"[{pdf_name} | {q_part} - Câu {q_num}]\n{q_text}",
                    metadata={
                        "nguon": "De_Tham_Khao_2026",
                        "file_goc": pdf_name,
                        "bai_hoc": inferred_lesson,
                        "vai_tro": "cau_hoi_tham_khao_2026",
                        "dang_cau_hoi": q_part,
                        "so_cau": q_label,
                    },
                )
            )
            kept_count += 1

        print(f"   ✅ {pdf_name}: giữ {kept_count} câu Python sạch | loại bỏ {dropped_count} câu ngoài phạm vi.")

    print(f"   📊 Tổng Nguồn 2 (De_Tham_Khao_2026): {len(kept_docs)} chunks câu hỏi Python sạch.")
    return kept_docs


# ==============================================================================
# PHẦN 4: XÂY DỰNG VECTOR DB SẠCH (data/chroma_db_v2 - nomic-embed-text)
# ==============================================================================

def build_clean_vectordb():
    print("=== BẮT ĐẦU PIPELINE LÀM SẠCH & NẠP VECTOR DB (BƯỚC 1 - 2 NGUỒN SẠCH) ===\n")

    docs_sgk = process_sgk_kntt()
    docs_exams = process_de_tham_khao_2026()
    all_docs = docs_sgk + docs_exams

    if not all_docs:
        print(f"\n[LỖI] Không có dữ liệu nào được trích xuất. Vui lòng kiểm tra thư mục: {RAW_DIR}")
        return

    os.makedirs(os.path.dirname(DB_DIR), exist_ok=True)
    if os.path.exists(DB_DIR):
        shutil.rmtree(DB_DIR)

    print(f"\n3. Đang nhúng tổng cộng {len(all_docs)} chunks sạch ({len(docs_sgk)} SGK + {len(docs_exams)} Đề tham khảo 2026) bằng nomic-embed-text...")
    embeddings = BatchOllamaEmbeddings(model="nomic-embed-text")
    vectordb = Chroma.from_documents(
        documents=all_docs,
        embedding=embeddings,
        persist_directory=DB_DIR,
    )

    total_stored = vectordb._collection.count()
    print(f"\n🎉 HOÀN TẤT! Cơ sở dữ liệu Vector sạch đã lưu tại: {DB_DIR}")
    print(f"   • Tổng chunks trong ChromaDB : {total_stored}")
    print(f"   • Nguồn SGK_Tin10_KNTT       : {len(docs_sgk)} chunks (Bài 16 - Bài 32)")
    print(f"   • Nguồn De_Tham_Khao_2026    : {len(docs_exams)} chunks (100% Python, đã lọc sạch HTML/CSS/SQL/Mạng/Đạo đức số)")


if __name__ == "__main__":
    build_clean_vectordb()
