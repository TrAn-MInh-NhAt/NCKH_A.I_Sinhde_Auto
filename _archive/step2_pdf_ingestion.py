import os
# Tắt cảnh báo Telemetry của ChromaDB
os.environ["ANONYMIZED_TELEMETRY"] = "False"

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma

def build_vector_db_from_pdf():
    print("1. Đang đọc file SGK TIN 10 kntt.pdf...")
    # Đảm bảo file PDF đang nằm trong cùng thư mục D:\AI_Agent_NCKH
    loader = PyPDFLoader("SGK TIN 10 kntt.pdf")
    documents = loader.load()
    print(f"   -> Đã đọc thành công {len(documents)} trang sách.")

    print("2. Đang băm nhỏ dữ liệu (Chunking)...")
    # Phân đoạn 600 ký tự, chồng lấp 100 ký tự để giữ mạch văn cảnh
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=100,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    chunks = text_splitter.split_documents(documents)
    print(f"   -> Đã băm sách thành {len(chunks)} đoạn (chunks).")

    print("3. Đang nhúng Vector bằng nomic-embed-text và lưu vào ChromaDB...")
    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    
    # Lưu vào thư mục chroma_db_tinhoc10
    db = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory="./chroma_db_tinhoc10"
    )
    print("Hoàn tất! Cơ sở dữ liệu Vector đã được lưu tại ./chroma_db_tinhoc10")

if __name__ == "__main__":
    build_vector_db_from_pdf()