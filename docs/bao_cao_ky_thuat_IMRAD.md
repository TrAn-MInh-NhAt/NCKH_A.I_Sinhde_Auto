# Báo Cáo Kỹ Thuật Chuẩn IMRAD – Hệ Thống Agentic RAG Sinh & Kiểm Định Đề Thi Tin Học 10 (Chủ Đề F – Python)

> **Tài liệu phục vụ hoàn thiện bản thảo bài báo khoa học (NCKH Sinh viên 2025–2026)**  
> **Nguồn số liệu xác minh:** `experiments/ablation_raw_results.json` (thời điểm thực nghiệm: `2026-11-18 17:37:18`, tổng cộng **48 lượt chạy thực tế** = 12 tác vụ × 4 cấu hình, **0 timeout**).  
> **Tài liệu sơ đồ đi kèm:** `docs/system_diagrams.md` | **Biểu đồ:** `experiments/ablation_charts.png` | **Bảng số liệu:** `experiments/ablation_results.xlsx`.

---

## MỤC 1. KIẾN TRÚC HỆ THỐNG (SYSTEM ARCHITECTURE & METHODS)

### 1.1. Tổng quan kiến trúc 3 lớp khóa cứng miền tri thức
Hệ thống được thiết kế theo kiến trúc 3 lớp độc lập nhằm tự động hóa quy trình sinh, kiểm định và ghép đề kiểm tra môn **Tin học 10 – Chủ đề F (Giải quyết vấn đề với sự trợ giúp của máy tính, Bài 16 – Bài 32, SGK Kết nối tri thức với cuộc sống)** theo chuẩn cấu trúc đề thi mới **2025–2026** của Bộ GD&ĐT:

1. **Lớp 1 – Giao diện tương tác 2 phân hệ (`app_ui.py` – Streamlit):**
   - *Phân hệ Giáo viên:* Hỗ trợ sinh câu hỏi đơn lẻ (chọn Bài 16–32, 3 mức độ NB/TH/VD, 4 dạng câu hỏi), sinh đề kiểm tra theo ma trận (`core/exam_assembler.py`), phê duyệt lưu vào ngân hàng đề (`data/question_bank.json`), và xuất đề thi định dạng Word (`.docx`) 2 phần tách trang.
   - *Phân hệ Học sinh:* Tải câu hỏi đã phê duyệt để luyện tập, tự động chấm điểm trắc nghiệm (`0.25đ`), Đúng/Sai bậc thang (`0.1 – 0.25 – 0.5 – 1.0đ`), Trả lời ngắn (`0.5đ`), và chạy kiểm thử mã Python trực tiếp trên Sandbox cô lập cho dạng Tự luận Code.
2. **Lớp 2 – Lõi suy luận Agentic RAG & Khảo thí (`core/`):** Gồm `retriever.py`, `generator.py`, `validator.py`, `sandbox.py`, `exam_assembler.py`, vận hành tuần tự qua đồ thị trạng thái **LangGraph (`StateGraph`)**.
3. **Lớp 3 – Kho tri thức sạch & Dữ liệu chuẩn hóa (`data/` & `experiments/`):**
   - `data/chroma_db_v2`: Cơ sở dữ liệu vector nhúng bằng `nomic-embed-text`, gồm **250 chunks thuần Chủ đề F**: **204 chunks** lý thuyết chuẩn từ `SGK TIN 10 kntt.pdf` (trang 87–156, giải mã font Glyph-ID NXB Giáo Dục sang Unicode chuẩn bằng bảng `cmap` TrueType của Windows + PyMuPDF `TEXT_INHIBIT_SPACES`) và **46 chunks** câu hỏi Python chuẩn lọc sạch từ 3 đề thi tham khảo 2025–2026 (loại bỏ hoàn toàn 45 câu HTML/CSS, SQL/CSDL, Mạng máy tính, Đạo đức số, Đồ họa).
   - `data/grounded_glossary.json`: Bộ **25 thuật ngữ** lập trình Python chuẩn SGK KNTT (`thuat_ngu`, `dinh_nghia_sgk`, `bai_hoc`, `trang`).
   - `data/ma_tran_de.json`: Thang điểm 2025–2026 và bảng ánh xạ **6 chỉ báo năng lực `NLc`** (`CC1, CC2, CC4, CS1, CS2, CS3`) trích xuất từ khung chương trình GDPT 2018.
   - `data/exam_templates.json` (`3,566 bytes < 4 KB`): Khuôn mẫu hình thức trích lọc từ đề gốc kết hợp ví dụ **1-shot** chuẩn Python lớp 10 cho cả 4 dạng câu hỏi.

### 1.2. Luồng Agentic RAG với cơ chế Kiểm định 2 tầng & Vòng lặp tự sửa lỗi
Quá trình sinh mỗi câu hỏi đi qua chu trình 3 node tuần tự trên LangGraph (`retrieve -> generate -> validate`, tối đa **3 vòng tự sửa lỗi**):

1. **Truy xuất `Evidence Package` khóa cứng bài học (`core/retriever.py`):**
   - Áp dụng bộ lọc metadata kép `{"$and": [{"nguon": "SGK_Tin10_KNTT"}, {"bai_hoc": lesson}]}` (khóa cứng từ Bài 16 đến Bài 32), loại trừ triệt để hiện tượng lẫn kiến thức liên môn hay vượt cấp.
   - Kết hợp thuật ngữ chuẩn bài học từ `grounded_glossary.json`, chỉ báo `NLc` từ `ma_tran_de.json`, và duy nhất **1 khuôn mẫu + 1 ví dụ 1-shot** từ `exam_templates.json`, đặt khóa `trich_dan_sgk` lên vị trí đầu tiên của JSON và kiểm soát tổng ngân sách prompt luôn dưới **1.800 tokens** (thực tế trung bình `1,359 tokens`).
2. **Tầng 1 – Rule Validator / Hard Gate (`core/validator.py`):**
   - Kiểm tra cấu trúc JSON hợp lệ và bắt buộc có trường trích dẫn nguyên văn `trich_dan_sgk` đạt độ trùng khớp từ vựng **≥ 45%** so với bằng chứng SGK đã truy xuất; nếu thiếu hoặc < 45%, hệ thống tự động trích 1–2 câu nguyên văn từ `sgk_chunks` đưa vào phản hồi sửa.
   - Chặn tuyệt đối từ khóa ngoài Chủ đề F (`HTML/CSS`, `SQL`, `Mạng LAN/Switch/IP`, `Đạo đức số`, `AI`, `Thiết kế đồ họa`) và cú pháp Python vượt cấp lớp 10 (`open()`, `class`, `lambda`, `yield`, `async/await`, thư viện ngoài `numpy/pandas/os/sys/...`).
   - Kiểm tra đặc thù từng dạng: chặn phương án giữ chỗ chung chung (`"Biểu thức A/B"`, `"Phương án 1"`, `"Đáp án A"`), chỉ rõ cặp phương án trùng lặp `X` và `Y`, kiểm soát cân bằng độ dài 4 phương án MCQ, kiểm tra tính độc lập (`Jaccard < 0.80`) và sự tồn tại đồng thời cả `Đúng` và `Sai` ở 4 mệnh đề `a, b, c, d`, đồng thời đối chiếu từ khóa cốt lõi của bài học (ví dụ: Bài 26 bắt buộc sử dụng hàm `def`).
3. **Tích hợp Python Sandbox cô lập (`core/sandbox.py`):**
   - Mọi đoạn mã Python thực thi được trong câu dẫn (`MCQ`, `TRUE_FALSE`, `SHORT_ANSWER`) hoặc `dap_an_mau` (`ESSAY_CODE`) đều được phân tích cú pháp bằng `ast.parse()` và thực thi thực tế trong tiến trình con cô lập (`python -I -X utf8`, `timeout_sec=2.0`) để chống vòng lặp vô hạn và bắt lỗi runtime (`NameError`, `ZeroDivisionError`, `IndexError`, `IndentationError`). Nếu phát sinh lỗi, toàn bộ thông báo `stderr` được chuyển ngược về `generator` để tự sửa.
4. **Tầng 2 – Fuzzy Quality Validator (`core/validator.py`):**
   - Chấm điểm chất lượng liên tục trong đoạn `[0.0, 1.0]` theo mô hình trọng số 3 trụ cột:
     $$\text{Score}_{\text{fuzzy}} = 0.40 \times S_{\text{SGK}} + 0.30 \times S_{\text{Cognitive}} + 0.30 \times S_{\text{Distractor}}$$
     trong đó $S_{\text{SGK}}$ đánh giá độ khớp nguyên văn & thuật ngữ chuẩn, $S_{\text{Cognitive}}$ đánh giá độ rõ câu dẫn, chất lượng lời giải thích và tính phù hợp cú pháp Python, $S_{\text{Distractor}}$ đánh giá độ cân bằng chiều dài/chất lượng nhiễu (MCQ) hoặc độ độc lập & phân bổ Đúng/Sai (TRUE_FALSE).
   - Ngưỡng phân loại: **`ĐẠT`** ($\ge 0.75$), **`CẦN SỬA`** ($0.50 - 0.74$), **`KHÔNG ĐẠT`** ($< 0.50$). Nếu chưa `ĐẠT` và `retry_count < 3`, đồ thị tăng nhẹ `temperature` (`0.15 -> 0.23 -> 0.31`) và quay lại `generate_node` kèm phản hồi đích danh.
5. **Ghép đề, Phản biện toàn đề (`exam_critic`) & Xuất Word `.docx` (`core/exam_assembler.py`):**
   - Gọi tuần tự `generate_question` theo ma trận đề, sau đó chạy `exam_critic` phát hiện câu hỏi trùng ý (`Jaccard >= 0.62`) hoặc câu này làm lộ đáp án câu kia trong cùng bài học, tính tổng điểm theo thang 2025–2026.
   - Hàm `export_exam_to_docx()` xuất đề Word 2 phần tách trang (`add_page_break()`): Phần 1 (Đề học sinh) tách riêng từng dòng văn bản (Times New Roman 12pt) và từng dòng lệnh Python (`Consolas 10.5pt` giữ nguyên thụt lề bằng `\u00a0`); Phần 2 (Biểu điểm, đáp án, giải thích, trích dẫn SGK).

### 1.3. Giải pháp tối ưu vận hành cục bộ trên phần cứng 4GB VRAM (RTX 3050)
Để triển khai ổn định mô hình cục bộ **`llama3.2_tinhoc10`** (3B tham số, lượng tử hóa ~2.0–2.6 GB VRAM) song song với embedding **`nomic-embed-text`** (~335 MB VRAM) trên GPU phổ thông **4GB VRAM**, hệ thống áp dụng 4 kỹ thuật cốt lõi:
- **Cấu hình `Modelfile` tối ưu:** `num_ctx 4096`, `num_gpu 99`, `temperature 0.15`, `top_p 0.85`, `repeat_penalty 1.15`.
- **Chống treo & tràn sinh token (`core/generator.py`):** Gọi trực tiếp Ollama REST API `/api/chat` với `format="json"`, `num_predict=650`, `stop=["\n\n\n", "```"]` và HTTP `timeout=120s`, loại bỏ hoàn toàn tình trạng kẹt socket hoặc sinh vòng lặp vô hạn.
- **Tách pha & giải phóng VRAM tường minh (`keep_alive=0`):** Trong thực nghiệm hàng loạt (`run_ablation.py`), toàn bộ truy xuất ChromaDB (`nomic-embed-text`) được thực hiện ở Pha 1, sau đó gửi yêu cầu `POST /api/embed` với `"keep_alive": 0` để giải phóng 100% VRAM embedding trước khi nạp `llama3.2_tinhoc10` ở Pha 2. Kỹ thuật này giúp loại bỏ hoàn toàn hiện tượng tráo model (*VRAM thrashing*), giảm thời gian sinh từ timeout > 60s xuống còn **~6.5–8.0 giây/lượt**.
- **Thực thi tuần tự tuyệt đối:** Mọi tác vụ sinh đơn lẻ, ghép đề ma trận và thực nghiệm đều chạy tuần tự từng câu để giữ mức chiếm dụng VRAM ổn định < 3.0 GB / 4.0 GB.

---

## MỤC 2. THIẾT KẾ THỰC NGHIỆM (EXPERIMENTAL DESIGN)

### 2.1. Môi trường thực nghiệm
- **Phần cứng:** PC cục bộ Windows, GPU NVIDIA GeForce RTX 3050 **4GB VRAM**.
- **Phần mềm:** Python 3.11 (`venv`), Ollama local (`llama3.2_tinhoc10` & `nomic-embed-text`), LangGraph `0.0.39`, ChromaDB `1.5.9`, PyMuPDF `2.1`, Streamlit `1.67.0`.

### 2.2. Bộ 12 tác vụ benchmark chuẩn Chủ đề F
Bộ kiểm thử gồm **12 tác vụ đại diện** phủ 5 bài học cốt lõi của Chủ đề F (**Bài 17, 19, 20, 22, 26**), đầy đủ **4 dạng câu hỏi** và **3 mức độ nhận thức (NB, TH, VD)**:

| Mã | Bài học | Dạng câu hỏi | Mức độ | Trọng tâm kiến thức kiểm thử |
| :-: | :--- | :--- | :-: | :--- |
| **T01** | Bài 17 | `MCQ` | NB | Biến, quy tắc đặt tên biến và lệnh gán trong Python |
| **T02** | Bài 19 | `MCQ` | TH | Biểu thức lôgic và câu lệnh rẽ nhánh `if-else` |
| **T03** | Bài 22 | `MCQ` | TH | Khởi tạo danh sách `list`, chỉ số và phương thức `append()` |
| **T04** | Bài 26 | `MCQ` | NB | Hàm thiết kế sẵn và định nghĩa hàm bằng từ khoá `def` |
| **T05** | Bài 19 | `TRUE_FALSE` | TH | Đọc hiểu đoạn mã câu lệnh rẽ nhánh `if-else` |
| **T06** | Bài 20 | `TRUE_FALSE` | TH | Đọc hiểu vòng lặp `for` kết hợp hàm `range()` |
| **T07** | Bài 22 | `TRUE_FALSE` | VD | Duyệt danh sách `list` và xử lý phần tử |
| **T08** | Bài 26 | `TRUE_FALSE` | VD | Đọc hiểu hàm tự định nghĩa `def` và `return` |
| **T09** | Bài 17 | `SHORT_ANSWER` | TH | Tính giá trị biểu thức số học và lệnh gán |
| **T10** | Bài 20 | `SHORT_ANSWER` | VD | Tính tổng bằng vòng lặp `for` và `range()` |
| **T11** | Bài 22 | `ESSAY_CODE` | VD | Viết chương trình xử lý danh sách số cụ thể |
| **T12** | Bài 26 | `ESSAY_CODE` | VD | Viết hàm `def` tính toán trên số hoặc danh sách cụ thể |

### 2.3. Bốn cấu hình đối sánh (Ablation Study)
Mỗi tác vụ trong 12 tác vụ trên được thực thi lần lượt trên 4 cấu hình tăng tiến (**tổng cộng 48 lượt đánh giá độc lập**) và được chấm điểm thống nhất bằng cùng bộ `core/validator.py` trên cùng bằng chứng SGK gốc của bài học:

1. **`Config_1_LLM_Only` (Baseline 1):** Chỉ gọi `llama3.2_tinhoc10` với yêu cầu tác vụ + khung JSON (không RAG, không Glossary, không 1-shot, 1 lượt sinh).
2. **`Config_2_Naive_RAG` (Baseline 2):** Truy xuất top-3 đoạn tương đồng từ toàn bộ `chroma_db_v2` *không khóa bài học*, không Glossary, không 1-shot, 1 lượt sinh.
3. **`Config_3_RAG_Glossary` (Ablation 1):** Truy xuất khóa cứng theo `bai_hoc` (`SGK_Tin10_KNTT`) + `grounded_glossary.json` + khuôn mẫu 1-shot từ `exam_templates.json`, chạy 1 lượt duy nhất (không vòng lặp tự sửa).
4. **`Config_4_Full_Agentic_RAG` (Hệ thống đề xuất):** Đầy đủ `Config_3` + Kiểm định 2 tầng (Hard Gate + Fuzzy Quality) + Python Sandbox (`timeout=2.0s`) + Vòng lặp tự sửa lỗi LangGraph tối đa 3 lần.

---

## MỤC 3. KẾT QUẢ & THẢO LUẬN (RESULTS & DISCUSSION)

### 3.1. Bảng tổng hợp kết quả thực nghiệm 48 lượt
Toàn bộ số liệu dưới đây được trích xuất trực tiếp từ `experiments/ablation_raw_results.json` (0 timeout trên cả 48 lượt):

| Cấu hình | Số câu ($N$) | Đạt Tầng 1 (`Rule Pass`) | ĐẠT chuẩn ($\ge 0.75$) | Sandbox Verified | Điểm Logic mờ TB | Bám nguồn SGK TB | Sư phạm TB | Chất lượng nhiễu TB | Số vòng sửa TB | Prompt TB (tokens) | Độ trễ TB / câu |
| :--- | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| **`Config_1_LLM_Only`** | 12 | 50.0% (6/12) | 50.0% (6/12) | 41.7% (5/12) | 0.458 | 0.418 | 0.500 | 0.470 | 0.00 | 180 | 7.10s |
| **`Config_2_Naive_RAG`** | 12 | 50.0% (6/12) | 50.0% (6/12) | 41.7% (5/12) | 0.461 | 0.464 | 0.473 | 0.444 | 0.00 | 542 | 6.54s |
| **`Config_3_RAG_Glossary`** | 12 | 41.7% (5/12) | 41.7% (5/12) | 75.0% (9/12) | 0.412 | 0.414 | 0.406 | 0.417 | 0.00 | 1,327 | 6.79s |
| **`Config_4_Full_Agentic_RAG`** | 12 | **75.0% (9/12)** | **75.0% (9/12)** | **83.3% (10/12)** | **0.741** | **0.735** | **0.739** | **0.750** | **1.00** | **1,359** | **11.83s** |

### 3.2. Phân tích chi tiết theo 4 dạng câu hỏi (Cấu trúc đề thi 2025–2026)

| Dạng câu hỏi | Số tác vụ | `Config_1` Đạt / Fuzzy / SB | `Config_2` Đạt / Fuzzy / SB | `Config_3` Đạt / Fuzzy / SB | `Config_4` Đạt / Fuzzy / SB |
| :--- | :-: | :---: | :---: | :---: | :---: |
| **`MCQ`** | 4 | 4/4 \| 0.907 \| SB 0/4 | 2/4 \| 0.455 \| SB 0/4 | 1/4 \| 0.250 \| SB 2/4 | 2/4 \| 0.500 \| SB 2/4 |
| **`TRUE_FALSE`** | 4 | 1/4 \| 0.226 \| SB 4/4 | 2/4 \| 0.446 \| SB 3/4 | 1/4 \| 0.250 \| SB 4/4 | **3/4 \| 0.732 \| SB 4/4** |
| **`SHORT_ANSWER`** | 2 | 1/2 \| 0.482 \| SB 1/2 | 2/2 \| 0.963 \| SB 1/2 | 2/2 \| 0.993 \| SB 2/2 | **2/2 \| 1.000 \| SB 2/2** |
| **`ESSAY_CODE`** | 2 | 0/2 \| 0.000 \| SB 0/2 | 0/2 \| 0.000 \| SB 1/2 | 1/2 \| 0.480 \| SB 1/2 | **2/2 \| 0.980 \| SB 2/2** |

### 3.3. Ma trận kết quả từng tác vụ (`T01` – `T12`)

| Mã | Bài học – Dạng – Mức | `Config_1` | `Config_2` | `Config_3` | `Config_4` (Số retry, Latency) |
| :-: | :--- | :-: | :-: | :-: | :--- |
| **T01** | Bài 17 – MCQ – NB | 0.910 | 0.000 | 0.000 (SB OK) | **1.000** (SB OK, `r=0`, `5.3s`) |
| **T02** | Bài 19 – MCQ – TH | 0.901 | 0.000 | 0.000 | 0.000 (`r=3`, `25.5s` – lệch độ dài & lỗi code) |
| **T03** | Bài 22 – MCQ – TH | 0.932 | 0.880 | 1.000 (SB OK) | **1.000** (SB OK, `r=0`, `5.1s`) |
| **T04** | Bài 26 – MCQ – NB | 0.885 | 0.941 | 0.000 | 0.000 (`r=3`, `18.4s` – trùng phương án & lỗi code) |
| **T05** | Bài 19 – TRUE_FALSE – TH | 0.000 | 0.000 | 1.000 (SB OK) | **1.000** (SB OK, `r=0`, `6.8s`) |
| **T06** | Bài 20 – TRUE_FALSE – TH | 0.900 | 0.000 | 0.000 (SB OK) | **0.926** (SB OK, `r=0`, `6.4s`) |
| **T07** | Bài 22 – TRUE_FALSE – VD | 0.000 | 0.880 | 0.000 (SB OK) | **1.000** (SB OK, `r=0`, `7.4s`) |
| **T08** | Bài 26 – TRUE_FALSE – VD | 0.000 | 0.900 | 0.000 (SB OK) | 0.000 (`r=3`, `27.4s` – thiếu từ khóa `def`) |
| **T09** | Bài 17 – SHORT_ANSWER – TH | 0.965 | 1.000 | 1.000 (SB OK) | **1.000** (SB OK, `r=0`, `5.4s`) |
| **T10** | Bài 20 – SHORT_ANSWER – VD | 0.000 | 0.925 | 0.986 (SB OK) | **1.000** (SB OK, `r=0`, `4.6s`) |
| **T11** | Bài 22 – ESSAY_CODE – VD | 0.000 | 0.000 | 0.961 (SB OK) | **0.961** (SB OK, `r=0`, `5.5s`) |
| **T12** | Bài 26 – ESSAY_CODE – VD | 0.000 | 0.000 | 0.000 | **1.000** (SB OK, `r=3`, `24.3s` – tự sửa thành công!) |

### 3.4. Thảo luận & Trả lời trực tiếp 4 câu hỏi nghiên cứu (RQ1 – RQ4)

- **RQ1 – Khả năng triển khai cục bộ trên phần cứng giới hạn 4GB VRAM và hiệu năng thời gian thực:**  
  Thực nghiệm chứng minh hệ thống vận hành hoàn toàn ổn định trên RTX 3050 4GB VRAM với **0/48 lượt timeout**. Nhờ kiểm soát ngữ cảnh dưới ngưỡng trần (trung bình `1,359 tokens < 1,800`), giới hạn `num_predict=650`, `stop tokens` và giải phóng embedding bằng `keep_alive=0`, độ trễ trung bình ở cấu hình đầy đủ `Config_4` chỉ đạt **`11.83s/câu`** (tối đa `27.4s`, thấp hơn nhiều so với ngưỡng `35s/câu`), hoàn toàn khả thi cho môi trường trường phổ thông không có hạ tầng GPU đắt tiền.

- **RQ2 – Đóng góp của từng thành phần kiến trúc (RAG khóa bài học, Glossary, 1-shot và Vòng lặp tự sửa LangGraph):**  
  Dữ liệu đối sánh chỉ ra hai phát hiện quan trọng trên mô hình ngôn ngữ nhỏ (3B):
  1. Ở các dạng câu hỏi có cấu trúc phức tạp và mã nguồn (`TRUE_FALSE`, `SHORT_ANSWER`, `ESSAY_CODE`), `Config_1` và `Config_2` thất bại hoàn toàn trên `ESSAY_CODE` (`0/2`) và rất yếu trên `TRUE_FALSE` (`1/4` và `2/4`).
  2. Khi chỉ đưa ngữ cảnh giàu thông tin + 1-shot mà *không* có vòng lặp phản biện (`Config_3`), tỉ lệ mã Python chạy đúng tăng vọt từ `41.7%` lên **`75.0%`**, nhưng vẫn dễ trượt Hard Gate ở một chi tiết nhỏ trong lượt sinh đầu (tỉ lệ đạt chỉ `41.7%`). Khi kích hoạt vòng lặp kiểm định 2 tầng + tự sửa lỗi có phản hồi đích danh ở **`Config_4`**, tỉ lệ đạt chuẩn tăng nhảy vọt **+33.3 điểm phần trăm** (từ `41.7%` lên **`75.0%`**), điểm Logic mờ trung bình tăng từ `0.458` (`Config_1`) và `0.412` (`Config_3`) lên **`0.741`**, đạt **`100%` (2/2)** trên cả `SHORT_ANSWER` (`Fuzzy = 1.000`) và `ESSAY_CODE` (`Fuzzy = 0.980`, điển hình tác vụ `T12` Bài 26 tự sửa thành công ở vòng 3 đạt `1.000`), và **`75%` (3/4)** trên dạng mới `TRUE_FALSE`.

- **RQ3 – Hiệu quả chống ảo giác, bám sát SGK KNTT và đảm bảo độ chính xác thực thi mã nguồn:**  
  Độ bám nguồn SGK trung bình tăng từ `0.418` (`Config_1`) lên **`0.735`** (`Config_4`, cải thiện **+75.8% tương đối**); **100%** câu hỏi sinh ra không vi phạm phạm vi Chủ đề F (không rò rỉ HTML/CSS/SQL/Mạng/lớp 11–12). Đặc biệt, tỉ lệ câu hỏi có mã Python thực thi được và vượt qua Sandbox tăng gấp đôi từ **`41.7%`** (`Config_1`/`Config_2`) lên **`83.3%`** (`Config_4`, gồm `4/4` ở `TRUE_FALSE`, `2/2` ở `SHORT_ANSWER`, `2/2` ở `ESSAY_CODE`). Lưu ý thú vị: `Config_1` đạt `4/4` ở `MCQ` nhưng `SB = 0/4` vì chỉ sinh câu hỏi lý thuyết thuần văn bản không có đoạn mã Python, trong khi `Config_4` sinh câu hỏi đọc hiểu mã Python thực thi có giá trị phân loại cao hơn (`SB = 2/4`).

- **RQ4 – Tính ứng dụng khảo thí 2025–2026 và phân tích hạn chế của mô hình 3B:**  
  Hệ thống đã đáp ứng trọn vẹn chuỗi nghiệp vụ khảo thí từ sinh đơn lẻ/ma trận, kiểm định toàn đề (`exam_critic`), chấm điểm chuẩn bậc thang 2025–2026, luyện tập học sinh trên Sandbox cho tới xuất đề Word `.docx` 2 phần tách trang chuẩn in ấn. Tuy nhiên, phân tích 3 trường hợp chưa đạt ở `Config_4` (`T02`, `T04`, `T08`) cho thấy hạn chế cố hữu của mô hình 3B cục bộ: (i) ở dạng `MCQ` có mã Python (`T02`, `T04`), mô hình 3B đôi khi sao chép phương án `'Le'` từ ví dụ 1-shot dẫn đến trùng phương án hoặc lệch độ dài; (ii) ở `T08` (Bài 26 `TRUE_FALSE`), mô hình có xu hướng sinh đoạn mã vòng lặp tổng quát thay vì định nghĩa hàm `def`. Đây là cơ sở khoa học quan trọng cho hướng mở rộng tiếp theo: tách riêng 1-shot theo nhóm bài (cấu trúc điều khiển vs hàm `def`) hoặc thử nghiệm mô hình 7B–8B lượng tử hóa 4-bit trên phần cứng 6–8GB VRAM.
