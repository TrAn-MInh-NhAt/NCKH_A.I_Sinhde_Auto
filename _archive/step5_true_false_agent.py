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

# Khởi tạo LLM và Parser (Nhiệt độ 0.1 để đảm bảo tính chính xác khoa học)
llm = ChatOllama(model="llama3.2_tinhoc10", temperature=0.1, format="json")
parser = JsonOutputParser()

class AgentState(TypedDict):
    chu_de: str
    context: str
    question_json: dict
    feedback: str      
    is_pass: bool      
    retry_count: int   

# NODE 1: Tìm kiếm tài liệu SGK
def retrieve_node(state: AgentState):
    print("\n[NODE 1] Đang tìm kiếm lý thuyết SGK (Dạng Đúng/Sai)...")
    db = Chroma(persist_directory="./chroma_db_tinhoc10", embedding_function=OllamaEmbeddings(model="nomic-embed-text"))
    docs = db.similarity_search(state["chu_de"], k=2)
    return {"context": "\n".join([d.page_content for d in docs])}

# NODE 2: AI Sinh câu hỏi Đúng/Sai (Áp dụng Few-shot Prompting)
def generate_node(state: AgentState):
    print(f"\n[NODE 2] AI đang soạn câu hỏi Đúng/Sai... (Lần thử thứ {state['retry_count'] + 1})")
    feedback_text = f"\nCẢNH BÁO TỪ GIÁM KHẢO (BẮT BUỘC SỬA LỖI SAU): {state['feedback']}" if state['feedback'] else ""
    
    prompt = PromptTemplate(
        template="""Bạn là chuyên gia ra đề thi Tin học 10. Dựa vào kiến thức SGK sau: 
{context}

Hãy sinh 1 câu hỏi TRẮC NGHIỆM ĐÚNG/SAI (gồm 1 câu dẫn chung và 4 mệnh đề a, b, c, d) về: {chu_de}.

QUY TẮC ĐỀ THI ĐÚNG/SAI 2025 BẮT BUỘC:
1. Phải có chính xác 4 mệnh đề kiến thức độc lập (a, b, c, d).
2. Mỗi mệnh đề chỉ nhận giá trị đáp án là "Đúng" hoặc "Sai".
3. KHÔNG ĐƯỢC để cả 4 mệnh đề cùng Đúng hoặc cùng Sai (phải có sự phân hóa).
4. TUYỆT ĐỐI tuân thủ cấu trúc JSON mẫu dưới đây.

--- VÍ DỤ MẪU CHUẨN MỰC ---
{{
    "cau_hoi_chung": "Khi sử dụng biến và lệnh gán trong Python, các phát biểu sau đây là Đúng hay Sai?",
    "a": {{"menh_de": "Biến phải được khai báo kiểu dữ liệu trước khi sử dụng.", "dap_an": "Sai", "giai_thich": "Theo SGK, Python tự nhận diện kiểu dữ liệu khi gán giá trị, không cần khai báo trước."}},
    "b": {{"menh_de": "Tên biến có thể bắt đầu bằng một chữ số.", "dap_an": "Sai", "giai_thich": "Tên biến không được bắt đầu bằng chữ số."}},
    "c": {{"menh_de": "Lệnh gán có thể gán cùng một giá trị cho nhiều biến trên cùng một dòng.", "dap_an": "Đúng", "giai_thich": "Ví dụ x = y = 1 là hợp lệ trong Python."}},
    "d": {{"menh_de": "Tên biến trong Python phân biệt chữ hoa và chữ thường.", "dap_an": "Đúng", "giai_thich": "Ví dụ biến 'A' và 'a' là hai biến hoàn toàn khác nhau."}}
}}
--------------------------------------------------
{feedback}

CHỈ TRẢ VỀ ĐÚNG 1 BLOCK JSON CHỨA CÂU HỎI MỚI CỦA BẠN (KHÔNG COPY LẠI VÍ DỤ MẪU):""",
        input_variables=["context", "chu_de", "feedback"]
    )
    
    chain = prompt | llm | parser
    try:
        res = chain.invoke({"context": state["context"], "chu_de": state["chu_de"], "feedback": feedback_text})
        return {"question_json": res}
    except:
        return {"question_json": {}}

# NODE 3: Giám khảo AI kiểm định (Rule-based chống All-True / All-False)
def review_node(state: AgentState):
    print("\n[NODE 3] Giám khảo đang chấm thẩm định (Đúng/Sai)...")
    q = state.get("question_json", {})
    
    # Kiểm tra cấu trúc JSON
    if not q or "a" not in q or "d" not in q:
        return {"is_pass": False, "feedback": "JSON không đủ 4 mệnh đề a, b, c, d. Hãy sinh lại đúng định dạng.", "retry_count": state["retry_count"] + 1}

    # Lấy danh sách 4 đáp án của 4 mệnh đề
    answers = [
        str(q.get('a', {}).get('dap_an', '')).strip().capitalize(),
        str(q.get('b', {}).get('dap_an', '')).strip().capitalize(),
        str(q.get('c', {}).get('dap_an', '')).strip().capitalize(),
        str(q.get('d', {}).get('dap_an', '')).strip().capitalize()
    ]
    
    # LUẬT 1: Bắt buộc giá trị chỉ được là "Đúng" hoặc "Sai"
    for ans in answers:
        if ans not in ["Đúng", "Sai"]:
            msg = f"Lỗi định dạng: Đáp án phải là 'Đúng' hoặc 'Sai', nhưng bạn xuất ra '{ans}'."
            print(f"   -> [PHÁT HIỆN LỖI]: {msg}")
            return {"is_pass": False, "feedback": msg, "retry_count": state["retry_count"] + 1}

    # LUẬT 2: Phân hóa độ khó (Chống việc sinh ra 4 câu True hoặc 4 câu False)
    if len(set(answers)) == 1:
        msg = f"Lỗi Sư phạm: Cả 4 mệnh đề đều có đáp án là '{answers[0]}'. Hãy sinh lại sao cho có cả mệnh đề Đúng và mệnh đề Sai để phân hóa học sinh."
        print(f"   -> [PHÁT HIỆN LỖI]: {msg}")
        return {"is_pass": False, "feedback": msg, "retry_count": state["retry_count"] + 1}

    print("   -> [RULE-BASED PASS]: Đủ 4 mệnh đề, định dạng chuẩn và đáp án có tính phân hóa tốt.")
    return {"is_pass": True, "feedback": ""}

# CẦU DAO ĐIỀU HƯỚNG VÒNG LẶP
def router(state: AgentState):
    if state["is_pass"] or state["retry_count"] >= 3:
        return "end"
    return "generate"

# LẮP RÁP ĐỒ THỊ LANGGRAPH
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
    print("KHỞI ĐỘNG HỆ THỐNG AGENTIC RAG (DẠNG ĐÚNG/SAI 4 MỆNH ĐỀ)...")
    
    # Bạn có thể thay đổi chủ đề dưới đây để sinh các câu khác (VD: Bài 19, Bài 20)
    result = app.invoke({
        "chu_de": "Bài 18: Các lệnh vào ra đơn giản trong Python", 
        "retry_count": 0, "is_pass": False, "feedback": ""
    })
    
    print("\n" + "="*60)
    print(f"=== ĐỀ THI ĐÚNG/SAI XUẤT XƯỞNG (Đã sửa lỗi: {result['retry_count']} lần) ===")
    print("="*60)
    if result.get("question_json"):
        print(json.dumps(result["question_json"], ensure_ascii=False, indent=4))
    else:
        print("Không thể sinh câu hỏi hợp lệ.")