import os
import json
os.environ["ANONYMIZED_TELEMETRY"] = "False"
from typing import TypedDict

from langchain_community.chat_models import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph import StateGraph, END

# Khởi tạo LLM và Parser (Nhiệt độ 0.1 để bám sát sự thật)
llm = ChatOllama(model="llama3.2_tinhoc10", temperature=0.1, format="json")
parser = JsonOutputParser()

# 1. Định nghĩa bộ nhớ luân chuyển giữa các Node (State)
class AgentState(TypedDict):
    chu_de: str
    context: str
    question_json: dict
    feedback: str      
    is_pass: bool      
    retry_count: int   

# 2. NODE 1: Tìm kiếm tài liệu
def retrieve_node(state: AgentState):
    print("\n[NODE 1] Đang tìm kiếm lý thuyết SGK...")
    db = Chroma(persist_directory="./chroma_db_tinhoc10", embedding_function=OllamaEmbeddings(model="nomic-embed-text"))
    docs = db.similarity_search(state["chu_de"], k=2)
    return {"context": "\n".join([d.page_content for d in docs])}

# 3. NODE 2: AI Sinh câu hỏi (Áp dụng Few-shot, Luật Sư phạm và Cấm copy)
def generate_node(state: AgentState):
    print(f"\n[NODE 2] AI đang soạn câu hỏi... (Lần thử thứ {state['retry_count'] + 1})")
    
    feedback_text = f"\nCẢNH BÁO TỪ GIÁM KHẢO (BẮT BUỘC SỬA LỖI SAU): {state['feedback']}" if state['feedback'] else ""
    
    prompt = PromptTemplate(
        template="""Bạn là chuyên gia ra đề thi Tin học 10. Dựa vào kiến thức SGK sau: 
{context}

Hãy sinh 1 câu hỏi trắc nghiệm mới về: {chu_de}.

QUY TẮC SƯ PHẠM ĐỀ THI BẮT BUỘC:
1. Bốn phương án A, B, C, D phải khác nhau hoàn toàn. Chỉ có duy nhất 1 đáp án đúng.
2. Bốn phương án A, B, C, D phải có ĐỘ DÀI TƯƠNG ĐƯƠNG NHAU. Tuyệt đối không để đáp án đúng dài hơn hẳn các phương án sai.
3. TUYỆT ĐỐI KHÔNG copy lại nguyên văn câu hỏi trong "VÍ DỤ MẪU CHUẨN MỰC" bên dưới. Hãy sáng tạo câu hỏi khác nhưng giữ nguyên cấu trúc JSON.

--- VÍ DỤ MẪU CHUẨN MỰC VỀ TÍNH SƯ PHẠM ---
{{
    "cau_hoi": "Trong ngôn ngữ lập trình Python, quy tắc nào sau đây là ĐÚNG khi đặt tên biến?",
    "A": "Có thể bắt đầu bằng chữ số",
    "B": "Có chứa dấu cách ở giữa tên",
    "C": "Phân biệt chữ hoa, chữ thường",
    "D": "Được trùng với từ khóa Python",
    "dap_an": "C",
    "giai_thich": "Theo SGK, tên biến trong Python phân biệt chữ hoa và chữ thường. Không được bắt đầu bằng chữ số, không chứa dấu cách và không được trùng từ khóa."
}}
--------------------------------------------------
{feedback}

CHỈ TRẢ VỀ ĐÚNG 1 BLOCK JSON CHỨA CÂU HỎI MỚI CỦA BẠN:""",
        input_variables=["context", "chu_de", "feedback"]
    )
    
    chain = prompt | llm | parser
    try:
        res = chain.invoke({"context": state["context"], "chu_de": state["chu_de"], "feedback": feedback_text})
        return {"question_json": res}
    except:
        return {"question_json": {}}

# 4. NODE 3: Giám khảo AI kiểm định (Trị ảo giác LLM)
def review_node(state: AgentState):
    print("\n[NODE 3] Giám khảo đang chấm thẩm định (Độ dài & Logic)...")
    q = state.get("question_json", {})
    
    if not q or "A" not in q:
        return {"is_pass": False, "feedback": "JSON rỗng hoặc sai cấu trúc. Hãy sinh lại.", "retry_count": state["retry_count"] + 1}

    # Lấy nội dung 4 phương án
    options = [str(q.get('A', '')), str(q.get('B', '')), str(q.get('C', '')), str(q.get('D', ''))]
    
    # LUẬT 1: Chống trùng đáp án
    if len(set(options)) < 4:
        msg = f"Lỗi: Các phương án bị trùng lặp. Hãy tạo 4 phương án khác biệt hoàn toàn."
        print(f"   -> [PHÁT HIỆN LỖI]: {msg}")
        return {"is_pass": False, "feedback": msg, "retry_count": state["retry_count"] + 1}
        
    # LUẬT 2: Rà soát Tính sư phạm (Chênh lệch độ dài)
    lengths = [len(opt) for opt in options]
    max_len, min_len = max(lengths), min(lengths)
    
    if max_len > 2.5 * min_len and (max_len - min_len) > 15:
        msg = f"Lỗi Sư phạm: Các đáp án chênh lệch độ dài quá lớn (Ngắn nhất: {min_len}, Dài nhất: {max_len} ký tự). Hãy sinh lại sao cho A, B, C, D dài ngang nhau."
        print(f"   -> [PHÁT HIỆN LỖI]: {msg}")
        return {"is_pass": False, "feedback": msg, "retry_count": state["retry_count"] + 1}

    print("   -> [RULE-BASED PASS]: Bốn phương án không bị trùng và có độ dài sư phạm hợp lý.")

    # LUẬT 3: Kiểm định Logic (Ép chặt vào SGK để chống ảo giác)
    review_prompt = PromptTemplate(
        template="""Đóng vai giám khảo chuyên môn Tin học 10. Nhiệm vụ của bạn là thẩm định câu hỏi trắc nghiệm sau đây dựa TRÊN CƠ SỞ DUY NHẤT LÀ ĐOẠN SGK DƯỚI ĐÂY.
Tuyệt đối KHÔNG DÙNG kiến thức lập trình nâng cao bên ngoài để bắt bẻ (Ví dụ: SGK dạy lệnh gán là '=' thì không được bắt bẻ về toán tử ':=').

Kiến thức chuẩn SGK: {context}
Câu hỏi: {question}
Đáp án người ra đề chọn: {dap_an}

Chỉ báo lỗi khi đáp án được chọn đi ngược lại hoàn toàn với SGK, hoặc câu hỏi không nằm trong SGK.
Chỉ trả về JSON: {{"hop_le": true/false, "nhan_xet": "Ghi rõ lý do nếu từ chối"}}""",
        input_variables=["context", "question", "dap_an"]
    )
    
    chain = review_prompt | llm | parser
    check = chain.invoke({"context": state["context"], "question": json.dumps(q, ensure_ascii=False), "dap_an": q.get("dap_an")})
    
    if check.get("hop_le"):
        print("   -> [LLM-JUDGE PASS]: Câu hỏi chính xác về mặt logic SGK!")
        return {"is_pass": True, "feedback": ""}
    else:
        print(f"   -> [PHÁT HIỆN LỖI LOGIC]: {check.get('nhan_xet')}")
        return {"is_pass": False, "feedback": check.get('nhan_xet'), "retry_count": state["retry_count"] + 1}

# 5. CẦU DAO ĐIỀU HƯỚNG
def router(state: AgentState):
    if state["is_pass"] or state["retry_count"] >= 3:
        return "end"
    return "generate"

# 6. LẮP RÁP ĐỒ THỊ LANGGRAPH
workflow = StateGraph(AgentState)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("generate", generate_node)
workflow.add_node("review", review_node)

workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "generate")
workflow.add_edge("generate", "review")
workflow.add_conditional_edges("review", router, {"generate": "generate", "end": END})
app = workflow.compile()

if __name__ == "__main__":
    print("KHỞI ĐỘNG HỆ THỐNG AGENTIC RAG CÓ KIỂM ĐỊNH SƯ PHẠM...")
    
    result = app.invoke({
        "chu_de": "Bài 17: Biến và lệnh gán trong Python", 
        "retry_count": 0, "is_pass": False, "feedback": ""
    })
    
    print("\n" + "="*50)
    print(f"=== ĐỀ THI CUỐI CÙNG XUẤT XƯỞNG (Đã sửa lỗi: {result['retry_count']} lần) ===")
    print("="*50)
    if result["question_json"]:
        print(json.dumps(result["question_json"], ensure_ascii=False, indent=4))
    else:
        print("Không thể sinh câu hỏi hợp lệ sau 3 lần thử.")