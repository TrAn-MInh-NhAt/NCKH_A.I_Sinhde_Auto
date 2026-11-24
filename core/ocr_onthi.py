import os
import re
os.environ["ANONYMIZED_TELEMETRY"] = "False"

import fitz  # PyMuPDF
import easyocr
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

# Định vị đường dẫn chuẩn theo cấu trúc dự án
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_ONTHI = os.path.join(BASE_DIR, "data_raw", "Huong_dan_on_thi_tot_nghiep_mon_Tin_Hoc_2018.pdf")
MD_OUTPUT = os.path.join(BASE_DIR, "data_raw", "on_thi_2025_python_ocr.md")
DB_DIR = os.path.join(BASE_DIR, "data", "chroma_db_v2")

# Bộ từ khóa nhận diện phần Lập trình Python (loại bỏ phần Mạng, CSDL, HTML lớp 12)
PYTHON_KEYWORDS = [
    "python", "biến", "lệnh gán", "input(", "print(", "if ", "else:", "elif ",
    "for ", "while ", "range(", "danh sách", "list", "xâu kí tự", "def ", "return"
]

EXCLUDE_KEYWORDS = [
    "html", "css", "sql", "cơ sở dữ liệu", "truy vấn", "mạng máy tính",
    "giao thức tcp", "địa chỉ ip", "bảng quan hệ", "khóa chính"
]

def is_python_grade10_page(text: str) -> bool:
    """Lọc chỉ giữ các trang thuộc chủ đề Lập trình Python, loại bỏ kiến thức lớp 12"""
    t = text.lower()
    py_score = sum(1 for kw in PYTHON_KEYWORDS if kw in t)
    ex_score = sum(1 for kw in EXCLUDE_KEYWORDS if kw in t)
    return py_score >= 2 and ex_score == 0

def run_ocr_to_markdown() -> str:
    """Giai đoạn 1: Quét OCR các trang Python và lưu thành file Markdown trung gian"""
    if not os.path.exists(PDF_ONTHI):
        print(f"[LỖI] Không tìm thấy file: {PDF_ONTHI}")
        return ""

    print("1. Đang khởi tạo bộ nhận diện chữ tiếng Việt + Python (EasyOCR)...")
    reader = easyocr.Reader(['vi', 'en'], gpu=True)

    doc = fitz.open(PDF_ONTHI)
    total_pages = len(doc)
    print(f"2. Bắt đầu quét {total_pages} trang từ sách Hướng dẫn ôn thi 2025...")

    md_sections = ["# DỮ LIỆU OCR - CHỦ ĐỀ LẬP TRÌNH PYTHON (ÔN THI 2025)\n"]
    kept_pages = 0

    for page_idx in range(total_pages):
        page_num = page_idx + 1
        page = doc[page_idx]

        # Chuyển trang PDF sang ảnh PNG độ phân giải 200 DPI
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")

        # Nhận diện văn bản trên trang
        lines = reader.readtext(img_bytes, detail=0, paragraph=True)
        page_text = "\n".join(lines).strip()

        if is_python_grade10_page(page_text):
            kept_pages += 1
            md_sections.append(f"\n## Trang {page_num}\n{page_text}\n")
            print(f"   ✅ [Trang {page_num}/{total_pages}] Khớp chủ đề Python -> Đã lưu.")
        else:
            print(f"   ⏭️ [Trang {page_num}/{total_pages}] Ngoài phạm vi Python lớp 10 -> Bỏ qua.")

    full_md = "\n".join(md_sections)
    with open(MD_OUTPUT, "w", encoding="utf-8") as f:
        f.write(full_md)

    print(f"\n📄 Đã xuất {kept_pages} trang Python ra file Markdown tại:\n   -> {MD_OUTPUT}")
    return full_md

def ingest_markdown_to_chromadb():
    """Giai đoạn 2: Băm nhỏ file Markdown đã OCR và nạp bổ sung vào ChromaDB hiện có"""
    if not os.path.exists(MD_OUTPUT):
        print("[LỖI] Chưa có file Markdown OCR. Hãy chạy giai đoạn 1 trước.")
        return

    with open(MD_OUTPUT, "r", encoding="utf-8") as f:
        content = f.read()

    # Tách theo từng trang để giữ chính xác số trang nguồn
    page_blocks = re.split(r'\n## Trang (\d+)\n', content)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=750,
        chunk_overlap=100,
        separators=["\n\n", "\n", "Câu ", ". ", " "]
    )

    docs_to_add = []
    # page_blocks[0] là tiêu đề đầu file; từ index 1 trở đi là cặp (số_trang, nội_dung)
    for i in range(1, len(page_blocks), 2):
        page_num = int(page_blocks[i])
        page_text = page_blocks[i + 1].strip()

        for chunk in splitter.split_text(page_text):
            if len(chunk) < 100:
                continue
            docs_to_add.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "nguon": "OnThi_THPT_2025_OCR",
                        "bai_hoc": "Tong_hop_Python",
                        "vai_tro": "cau_hoi_mau_2025",
                        "trang": page_num
                    }
                )
            )

    if not docs_to_add:
        print("⚠️ Không trích xuất được chunk nào đủ độ dài từ file Markdown.")
        return

    print(f"\n3. Đang nhúng bổ sung {len(docs_to_add)} chunks vào {DB_DIR}...")
    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    db = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
    db.add_documents(docs_to_add)
    print(f"🎉 HOÀN TẤT! Đã nạp thêm {len(docs_to_add)} chunks đề mẫu 2025 vào Vector DB.")

if __name__ == "__main__":
    # Bước 1: Quét OCR và lọc ra file Markdown (chỉ chạy 1 lần)
    run_ocr_to_markdown()

    # Bước 2: Nạp từ Markdown vào ChromaDB (có thể chạy lại sau khi sửa tay file .md)
    ingest_markdown_to_chromadb()