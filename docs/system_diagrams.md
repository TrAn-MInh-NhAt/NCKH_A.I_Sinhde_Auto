# Hệ Thống Sơ Đồ Kiến Trúc – AI Agentic RAG Khảo Thí Tin Học 10 (Chủ Đề F – Python)

Tài liệu tổng hợp **6 sơ đồ kiến trúc chuẩn Mermaid** phục vụ báo cáo NCKH, thuyết minh đề tài và trình bày hội đồng khoa học. Hệ thống triển khai 100% cục bộ trên phần cứng biên GPU phổ thông **4GB VRAM – NVIDIA RTX 3050** với mô hình ngôn ngữ `llama3.2_tinhoc10` (Ollama 3B), cơ sở dữ liệu vector `ChromaDB v2`, động cơ ký hiệu `Symbolic Engine` (155 blueprints) và môi trường thực thi cô lập `Python Sandbox`.

---

## Sơ đồ 1: Tổng quan Kiến trúc Hệ thống 3 Lớp Neuro-Symbolic Agentic RAG

```mermaid
flowchart TD
    subgraph L1 ["LỚP 1: GIAO DIỆN & TRIỂN KHAI PHỤC VỤ (app_ui.py & launch_public.py)"]
        GV["Phân hệ Giáo viên<br/>(Cấu hình ma trận, Quick Edit, Duyệt đề, Xuất Word)"]
        HS["Phân hệ Học sinh<br/>(Luyện đề trực tuyến, Chấm điểm tự động, Thực thi Code)"]
        CFT["Cloudflare Tunnel<br/>(Chia sẻ từ xa qua URL bảo mật HTTPS không mở port)"]
        LOCK["threading.Lock VRAM<br/>(Khóa tuần tự GPU 4GB VRAM bảo vệ tài nguyên)"]
    end

    subgraph L2 ["LỚP 2: LÕI SUY LUẬN NEURO-SYMBOLIC & KHẢO THÍ (core/)"]
        SE["Động cơ Ký hiệu Tham số hóa<br/>(core/symbolic_engine.py - 155 Blueprints độc nhất)"]
        SB["Python Sandbox Cô lập<br/>(core/sandbox.py - subprocess -I, timeout=2.0s)"]
        RET["Bộ Truy xuất Ngữ cảnh RAG<br/>(core/retriever.py - Khóa cứng Bài 16-32, Glossary)"]
        GEN["Bộ Điều phối Đồ thị LangGraph<br/>(core/generator.py + Ollama llama3.2_tinhoc10)"]
        VAL["Bộ Kiểm định Chất lượng 2 Tầng<br/>(core/validator.py - Tầng 1 Hard Gate AST + Tầng 2 Fuzzy)"]
        ASM["Bộ Ghép Đề & Phản Biện Toàn Đề<br/>(core/exam_assembler.py - exam_critic & Xáo trộn đề)"]
        IMP["Bộ Nạp Đề Kiểm Tra Mẫu<br/>(core/exam_importer.py - Nạp .docx, .json, .txt)"]
    end

    subgraph L3 ["LỚP 3: KHO TRI THỨC, DỮ LIỆU CHUẨN HÓA & THỰC NGHIỆM (data/ & experiments/)"]
        VDB[("ChromaDB v2<br/>(250 chunks sạch SGK Tin 10 KNTT)")]
        GLOS[("Thuật ngữ Chuẩn<br/>(grounded_glossary.json)")]
        MAT[("Ma trận & Thang điểm 2025-2026<br/>(ma_tran_de.json)")]
        RECENT[("Bộ nhớ Đệm 5 Đề Gần Nhất<br/>(recent_blueprints.json - Chống lặp)")]
        BANK[("Ngân hàng Câu hỏi Phê duyệt<br/>(question_bank.json)")]
        SAMPLE[("Thư mục Đề Kiểm tra Mẫu<br/>(data/sample_exams/)")]
        EXP_DOCX["Tệp Word Đề thi Hoàn chỉnh<br/>(Đề học sinh + Đáp án chi tiết .docx)"]
    end

    CFT --> L1
    GV & HS --> LOCK
    LOCK --> ASM
    LOCK --> GEN

    ASM --> SE
    SE --> SB
    SE --> RET
    RET --> VDB
    RET --> GLOS

    SE & RET --> GEN
    GEN --> VAL
    VAL --> SB
    VAL -->|Đạt chuẩn| ASM
    VAL -->|Cần sửa| GEN

    ASM --> RECENT
    ASM --> EXP_DOCX
    ASM --> BANK
    IMP --> SAMPLE
    IMP --> BANK
```

---

## Sơ đồ 2: Luồng Triển Khai & Chia Sẻ Công Khai Qua Cloudflare Tunnel

```mermaid
sequenceDiagram
    autonumber
    actor User as Giáo viên / Học sinh từ xa (Điện thoại / Laptop)
    participant CF as Mạng phân phối Cloudflare (Edge CDN)
    participant Bin as Trình nhị phân cloudflared.exe (Local PC)
    participant App as Ứng dụng Streamlit (app_ui.py:8501)
    participant VRAM as Khóa điều phối VRAM (_acquire_vram_slot)
    participant Core as Lõi Neuro-Symbolic Agentic RAG

    Note over Bin,App: Khởi động 1-click qua Start_Share_Web.bat / launch_public.py
    Bin->>CF: Thiết lập đường hầm bảo mật HTTPS (*.trycloudflare.com)
    User->>CF: Truy cập URL công khai https://xxx.trycloudflare.com
    CF->>Bin: Chuyển tiếp luồng dữ liệu HTTP2 qua Tunnel
    Bin->>App: Gửi yêu cầu tới máy chủ cục bộ http://localhost:8501
    App->>VRAM: Yêu cầu quyền truy cập tài nguyên GPU
    VRAM->>Core: Cho phép thực thi tuần tự trên mô hình cục bộ
    Core-->>App: Trả về kết quả sinh đề và kiểm định
    VRAM-->>App: Giải phóng khóa GPU cho phiên làm việc tiếp theo
    App-->>User: Hiển thị giao diện Web tương tác và cho phép tải Word .docx
```

---

## Sơ đồ 3: Chu Trình LangGraph & Vòng Lặp Tự Sửa Lỗi (StateGraph)

```mermaid
stateDiagram-v2
    [*] --> Retrieve_Evidence: Nhận yêu cầu Bài học, Dạng câu hỏi, Mức độ
    
    state Retrieve_Evidence {
        [*] --> Khoa_Bai_Hoc: Khóa cứng metadata bài học từ Bài 16 đến Bài 32
        Khoa_Bai_Hoc --> Lay_Chunk: Lấy top-k chunk từ ChromaDB v2
        Lay_Chunk --> Nap_Glossary: Bổ sung thuật ngữ từ grounded_glossary.json
    }

    Retrieve_Evidence --> Build_Skeleton: Nạp Evidence Package
    
    state Build_Skeleton {
        [*] --> Loc_Recent: Tra cứu recent_blueprints.json (chống lặp 5 đề)
        Loc_Recent --> Random_Param: Sinh biến số, xâu, danh sách ngẫu nhiên
        Random_Param --> Chay_Sandbox: Thực thi mã lệnh qua core/sandbox.py
        Chay_Sandbox --> Khoa_Dap_An: Khóa cứng stdout và verified_explanation
    }

    Build_Skeleton --> Generate_Node: Khung Skeleton hợp lệ
    
    state Generate_Node {
        [*] --> Prompt_Assembly: Ghép khung ký hiệu + Bằng chứng SGK
        Prompt_Assembly --> Call_Ollama: Gửi request tới llama3.2_tinhoc10
        Call_Ollama --> Parse_JSON: Bóc tách cấu trúc câu hỏi JSON
        Parse_JSON --> Merge_Symbolic: Ghi đè đáp án & giải thích từ Skeleton
    }

    Generate_Node --> Validate_Node: Chuyển sang kiểm định 2 tầng
    
    state Validate_Node {
        [*] --> Hard_Gate: Tầng 1 - Cú pháp Python AST, cấm thư viện ngoài, đơn trị
        Hard_Gate --> Sandbox_Check: Thực thi mã câu dẫn / đáp án mẫu
        Sandbox_Check --> Fuzzy_Scoring: Tầng 2 - Chấm điểm chất lượng [0.0 - 1.0]
    }

    Validate_Node --> Success: is_pass == True (Fuzzy >= 0.75)
    Validate_Node --> Generate_Node: is_pass == False & retry < 2 (Kèm phản hồi sửa lỗi)
    Validate_Node --> Backfill_Queue: is_pass == False & retry >= 2 (Đẩy sang bù vét)

    Success --> [*]
    Backfill_Queue --> [*]
```

---

## Sơ đồ 4: Cơ Chế Kiểm Định 2 Tầng (Two-Tier Validator & Sandbox)

```mermaid
flowchart TD
    In["Câu hỏi dự thảo từ Generator"] --> T1{"TẦNG 1: RULE HARD GATE\n(Cắt đứt ngay nếu vi phạm)"}
    
    subgraph G1 ["Kiểm tra Quy tắc Bắt buộc"]
        R1["1. Cấu trúc JSON đầy đủ các trường"]
        R2["2. Phân tích AST đoạn mã Python (ast.parse)"]
        R3["3. Chặn thư viện ngoài chương trình (os, sys, numpy...)"]
        R4["4. Chặn rò rỉ đề bài & lộ đáp án chéo"]
        R5["5. Đảm bảo tính đơn trị (Single Answer) của 4 phương án"]
    end
    
    T1 --> G1
    G1 -->|Có lỗi| Fail1["ĐÁNH RỚT NGAY (is_pass = False)\nTạo phản hồi đích danh để LLM tự sửa"]
    G1 -->|Hợp lệ| SB_Exec["Thực thi trên Python Sandbox cô lập\n(subprocess -I, timeout=2.0s)"]
    
    SB_Exec -->|RuntimeError / Timeout| Fail1
    SB_Exec -->|Khớp stdout 100%| T2{"TẦNG 2: FUZZY QUALITY SCORING\n(Đánh giá chất lượng liên tục [0.0, 1.0])"}
    
    subgraph G2 ["Mô hình 3 Trụ Cột Trọng Số"]
        P1["S_SGK (40%): Độ trùng khớp thuật ngữ & bằng chứng SGK"]
        P2["S_Pedagogy (30%): Tính rõ ràng câu dẫn, giải thích chuẩn xác"]
        P3["S_Distractor (30%): Độ cân bằng chiều dài, chất lượng phương án nhiễu"]
    end
    
    T2 --> G2
    G2 --> Calc["Fuzzy_Score = 0.4*S_SGK + 0.3*S_Pedagogy + 0.3*S_Distractor"]
    
    Calc --> Thresh{Fuzzy_Score >= 0.75 ?}
    Thresh -->|Đạt| Pass["XẾP LOẠI: ĐẠT CHUẨN (is_pass = True)\nLưu vào đề thi chính thức"]
    Thresh -->|Chưa đạt| NeedFix["XẾP LOẠI: CẦN SỬA (is_pass = False)\nTăng temperature và quay lại vòng lặp"]
```

---

## Sơ đồ 5: Quản Trị Bộ Nhớ Biên GPU 4GB VRAM & Tách Pha Xử Lý

```mermaid
sequenceDiagram
    autonumber
    participant App as Ứng dụng Streamlit (app_ui.py)
    participant Lock as threading.Lock (_acquire_vram_slot)
    participant Ollama as Dịch vụ Ollama Local (Port 11434)
    participant VRAM as Bộ nhớ Video GPU (NVIDIA RTX 3050 4GB)

    Note over VRAM: Mức chiếm dụng cơ sở: Hệ thống & Desktop (~0.8 GB VRAM)
    
    App->>Lock: Yêu cầu cấp slot xử lý sinh đề thi
    Lock->>App: Cấp quyền thành công (đảm bảo đơn luồng GPU)
    
    rect rgb(230, 245, 255)
        Note over App,Ollama: PHA 1: TIỀN TRUY XUẤT HÀNG LOẠT (BATCH PRE-RETRIEVAL)
        App->>Ollama: Gửi văn bản truy vấn tới nomic-embed-text
        Ollama->>VRAM: Nạp mô hình embedding (~0.33 GB VRAM)
        Ollama-->>App: Trả về vector nhúng & kết quả truy xuất ChromaDB
        App->>Ollama: POST /api/embed với keep_alive: 0
        Ollama->>VRAM: Giải phóng hoàn toàn 100% VRAM embedding
        Note over VRAM: VRAM trống trở lại mức ~0.8 GB (Loại bỏ VRAM Thrashing)
    end

    rect rgb(255, 245, 230)
        Note over App,Ollama: PHA 2: SINH KÝ HIỆU & HIỆU CHỈNH NEURAL TUẦN TỰ
        App->>Ollama: Gửi prompt câu hỏi tới llama3.2_tinhoc10 (num_predict=360-580)
        Ollama->>VRAM: Nạp mô hình ngôn ngữ 3B (~2.2 GB VRAM)
        Note over VRAM: Tổng chiếm dụng VRAM: ~3.0 GB / 4.0 GB (Hoàn toàn an toàn)
        Ollama-->>App: Trả về câu hỏi dạng JSON đã chuẩn hóa
    end

    App->>Lock: Giải phóng slot GPU
    Note over Lock: Sẵn sàng phục vụ yêu cầu tiếp theo
```

---

## Sơ đồ 6: Luồng Ghép Đề Ma Trận, Chống Trùng Xuyên 5 Mã Đề & Xáo Trộn Đề Thi

```mermaid
flowchart TD
    Start["Bắt đầu Sinh đề theo Ma trận"] --> Load_Recent["Tải data/recent_blueprints.json\n(Lịch sử tối đa 90 blueprint_id của 5 đề gần nhất)"]
    Load_Recent --> Rotate["Xoay vòng Ngẫu nhiên Danh sách Bài học\n(Phủ đều Bài 16 - Bài 32, đa dạng bài toán Tự luận)"]
    
    Rotate --> Loop_Gen["Vòng lặp sinh từng câu theo Ma trận (18 câu = 10.0 điểm)"]
    
    subgraph Gen_Step ["Sinh & Kiểm Tra Độc Lập"]
        S1["Bốc Blueprint không trùng với recent_blueprints"]
        S2["Sinh khung ký hiệu & chạy Sandbox lấy stdout"]
        S3["Hiệu chỉnh sư phạm qua llama3.2_tinhoc10"]
        S4["Kiểm định 2 tầng: chỉ nhận is_pass == True"]
    end
    
    Loop_Gen --> Gen_Step
    Gen_Step --> Critic{"Hội đồng Phản biện exam_critic"}
    
    Critic -->|Trùng ý Jaccard >= 0.62 hoặc lộ đáp án| Backfill["Đẩy sang hàng đợi Backfill bù bài mới"]
    Critic -->|Đạt chuẩn độc lập| Kept["Giữ lại trong danh sách đề chính thức"]
    
    Backfill --> Loop_Gen
    Kept --> Check_Full{Đủ 18 câu đạt chuẩn 10.0 điểm?}
    Check_Full -->|Chưa đủ| Loop_Gen
    
    Check_Full -->|Đã đủ 18 câu| Shuffle["XÁO TRỘN NGẪU NHIÊN THỨ TỰ BÊN TRONG TỪNG PHẦN:\n- Xáo trộn ngẫu nhiên 8 câu MCQ (Phần I)\n- Xáo trộn ngẫu nhiên 3 câu Đúng/Sai (Phần II)\n- Xáo trộn ngẫu nhiên 4 câu Trả lời ngắn (Phần III)\n- Xáo trộn ngẫu nhiên 3 câu Tự luận Code (Phần IV)"]
    
    Shuffle --> ReIndex["Đánh số thứ tự lại từ Câu 1 đến Câu 18"]
    ReIndex --> Save_Recent["Cập nhật data/recent_blueprints.json\n(Lưu 18 blueprint_id mới, giữ tối đa 90 ID)"]
    Save_Recent --> Export["Xuất Đề thi File Word .docx 2 phần tách trang\n(Phần 1: Đề học sinh | Phần 2: Đáp án & Hướng dẫn chấm)"]
    Export --> End["Hoàn tất đề thi đạt chuẩn"]
```
