import os
import json

# Tắt cảnh báo Telemetry của ChromaDB
os.environ["ANONYMIZED_TELEMETRY"] = "False"

from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

def generate_mcq(chu_de_bai_hoc, muc_do):
    print(f"\n--- ĐANG XỬ LÝ YÊU CẦU: {chu_de_bai_hoc} ({muc_do}) ---")
    
    # 1. RETRIEVE: Lục tìm tài liệu trong Vector Database
    print("1. Đang truy xuất kiến thức từ Sách giáo khoa...")
    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    # Trỏ đúng vào thư mục DB vừa tạo ở Bước 2
    db = Chroma(persist_directory="./chroma_db_tinhoc10", embedding_function=embeddings)
    
    # Tìm 2 đoạn văn bản liên quan nhất với chủ đề
    docs = db.similarity_search(chu_de_bai_hoc, k=2)
    context_text = "\n\n".join([doc.page_content for doc in docs])
    print(f"   -> Đã tìm thấy {len(docs)} đoạn tài liệu liên quan.")

    # 2. GENERATE: Gọi mô hình AI chuyên gia để sinh câu hỏi
    print(f"2. Đang gửi yêu cầu cho AI sinh câu hỏi (JSON)... (Vui lòng chờ vài giây)")
    
    # Gọi đúng mô hình bạn đã train ở Bước 1
    llm = ChatOllama(model="llama3.2_tinhoc10", temperature=0.1, format="json")
    
    prompt = PromptTemplate(
        template="""Dựa vào đoạn kiến thức Sách giáo khoa dưới đây, hãy sinh ra 1 câu hỏi trắc nghiệm môn Tin học.
Mức độ nhận thức: {muc_do}
Chủ đề: {chu_de_bai_hoc}

KIẾN THỨC SÁCH GIÁO KHOA BẮT BUỘC SỬ DỤNG:
{context}

YÊU CẦU BẮT BUỘC:
1. Bốn phương án A, B, C, D phải HOÀN TOÀN KHÁC NHAU.
2. Chỉ trả về đúng 1 đối tượng JSON theo mẫu bên dưới, không kèm bất kỳ văn bản nào khác.

MẪU JSON KẾT QUẢ:
{{
    "cau_hoi": "Nội dung câu hỏi?",
    "A": "Phương án A",
    "B": "Phương án B",
    "C": "Phương án C",
    "D": "Phương án D",
    "dap_an": "A",
    "giai_thich": "Giải thích ngắn gọn lý do chọn đáp án này dựa trên đoạn SGK."
}}""",
        input_variables=["chu_de_bai_hoc", "muc_do", "context"]
    )
    
    # Tạo chuỗi xử lý: Prompt -> LLM -> Ép kiểu JSON
    chain = prompt | llm | JsonOutputParser()
    
    try:
        # Kích hoạt chuỗi xử lý
        result = chain.invoke({
            "chu_de_bai_hoc": chu_de_bai_hoc,
            "muc_do": muc_do,
            "context": context_text
        })
        print("\n=== KẾT QUẢ CÂU HỎI TRẮC NGHIỆM ĐÃ SINH ===")
        print(json.dumps(result, ensure_ascii=False, indent=4))
    except Exception as e:
        print("\n[LỖI] Quá trình sinh câu hỏi thất bại:", str(e))

if __name__ == "__main__":
    # Test thử sinh 1 câu hỏi về Bài 17: Biến và lệnh gán
    generate_mcq(
        chu_de_bai_hoc="Bài 17: Biến và lệnh gán trong Python", 
        muc_do="Thông hiểu"
    )