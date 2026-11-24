import os
import json
import shutil
os.environ["ANONYMIZED_TELEMETRY"] = "False"

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma

# 1. Khởi tạo thư mục data và bộ Grounded Glossary chuẩn (Phục vụ RQ3)
os.makedirs("./data", exist_ok=True)

GLOSSARY_DATA = {
    "biến": {
        "chuan_sgk": "Biến (variable) là tên của một vùng nhớ dùng để lưu trữ giá trị và giá trị này có thể thay đổi khi thực hiện chương trình.",
        "cam_dung": ["con trỏ ô nhớ", "hằng số biến thiên", "var"],
        "nguon": "SGK Tin học 10 - Kết nối tri thức, Bài 17, trang 92"
    },
    "lệnh gán": {
        "chuan_sgk": "Lệnh gán trong Python có dạng <tên biến> = <biểu thức>, dùng dấu bằng (=) để gán giá trị bên phải cho biến bên trái.",
        "cam_dung": ["phép so sánh bằng", "toán tử := trong Pascal"],
        "nguon": "SGK Tin học 10 - Kết nối tri thức, Bài 17, trang 93"
    },
    "rẽ nhánh": {
        "chuan_sgk": "Câu lệnh rẽ nhánh if và if-else dùng để kiểm tra điều kiện (biểu thức lôgic) và thực hiện khối lệnh tương ứng khi điều kiện đúng hoặc sai.",
        "cam_dung": ["vòng lặp if", "hàm điều kiện if"],
        "nguon": "SGK Tin học 10 - Kết nối tri thức, Bài 19, trang 102"
    }
}

with open("./data/glossary_chude_f.json", "w", encoding="utf-8") as f:
    json.dump(GLOSSARY_DATA, f, ensure_ascii=False, indent=4)

# 2. Tạo học liệu mẫu chuẩn Markdown có phân mục rõ ràng
SAMPLE_SGK = """# Chủ đề F: Giải quyết vấn đề với sự trợ giúp của máy tính
## Bài 16: Ngôn ngữ lập trình bậc cao và Python
Python là ngôn ngữ lập trình bậc cao do Guido van Rossum tạo ra và ra mắt lần đầu năm 1991. Ngôn ngữ lập trình bậc cao có các câu lệnh gần với ngôn ngữ tự nhiên, giúp người lập trình dễ đọc, dễ viết và dễ hiệu chỉnh. Chương trình viết bằng ngôn ngữ bậc cao cần được chương trình dịch (trình thông dịch hoặc trình biên dịch) chuyển thành ngôn ngữ máy để máy tính thực hiện được. Python sử dụng trình thông dịch (interpreter) để dịch và thực hiện từng câu lệnh. Lệnh print() dùng để in dữ liệu ra màn hình.

## Bài 17: Biến và lệnh gán
Trong Python, biến được tạo ra ngay khi thực hiện lệnh gán giá trị cho nó mà không cần khai báo kiểu dữ liệu trước. Cú pháp lệnh gán là: <tên biến> = <biểu thức>. Quy tắc đặt tên biến trong Python: (1) Chỉ gồm chữ cái tiếng Anh, chữ số và dấu gạch dưới (_); (2) Không được bắt đầu bằng chữ số; (3) Không được chứa dấu cách hoặc ký tự đặc biệt; (4) Phân biệt chữ hoa và chữ thường (ví dụ: biến N và biến n là hai biến khác nhau); (5) Không được trùng với từ khóa của Python (như if, else, for, while, def). Các phép toán số học cơ bản gồm: cộng (+), trừ (-), nhân (*), chia (/), chia lấy thương nguyên (//), chia lấy dư (%) và lũy thừa (**).

## Bài 19: Câu lệnh rẽ nhánh if
Trong lập trình, cấu trúc rẽ nhánh dùng để mô tả việc thực hiện hay không thực hiện một công việc tùy thuộc vào một điều kiện có được thỏa mãn hay không. Biểu thức điều kiện trong Python là biểu thức lôgic nhận giá trị True (Đúng) hoặc False (Sai), thường sử dụng các phép toán so sánh: == (bằng), != (khác), <, <=, >, >=. Câu lệnh rẽ nhánh dạng thiếu có cú pháp: if <điều kiện>: <khối lệnh>. Câu lệnh rẽ nhánh dạng đủ có cú pháp: if <điều kiện>: <khối lệnh 1> else: <khối lệnh 2>. Lưu ý: Sau điều kiện của if và sau từ khóa else bắt buộc phải có dấu hai chấm (:), và khối lệnh bên trong phải được viết lùi vào một số dấu cách đồng nhất (thường là 4 dấu cách).
"""

with open("./data/SGK_TinHoc10_ChuDeF.md", "w", encoding="utf-8") as f:
    f.write(SAMPLE_SGK.strip())

def build_standard_vector_db():
    # Xóa DB cũ để tránh trùng lặp dữ liệu
    if os.path.exists("./chroma_db_tinhoc"):
        shutil.rmtree("./chroma_db_tinhoc")

    with open("./data/SGK_TinHoc10_ChuDeF.md", "r", encoding="utf-8") as f:
        markdown_text = f.read()

    # Tách theo tiêu đề Markdown để tự động lấy Metadata (Chủ đề, Bài học)
    headers_to_split_on = [
        ("#", "chu_de"),
        ("##", "bai_hoc"),
    ]
    md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    md_header_splits = md_splitter.split_text(markdown_text)

    # Phân đoạn ngữ nghĩa chuẩn Đề cương: 500-800 ký tự, chồng lấp 10-15% (chọn 600 và 80)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=80,
        separators=["\n\n", "\n", ". ", " "]
    )
    final_chunks = text_splitter.split_documents(md_header_splits)

    # Gắn thêm ID định danh cho từng đoạn bằng chứng (phục vụ trích dẫn nguồn)
    for idx, chunk in enumerate(final_chunks):
        chunk.metadata["chunk_id"] = f"SGK10_F_CHUNK_{idx+1:02d}"
        chunk.metadata["source"] = "SGK Tin học 10 - Kết nối tri thức"

    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    db = Chroma.from_documents(
        documents=final_chunks,
        embedding=embeddings,
        persist_directory="./chroma_db_tinhoc"
    )
    print(f"[THÀNH CÔNG] Đã nạp {len(final_chunks)} chunks chuẩn (600 ký tự, overlap 80) kèm Metadata bài học vào ChromaDB!")
    return db

if __name__ == "__main__":
    build_standard_vector_db()