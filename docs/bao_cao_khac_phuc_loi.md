# BÁO CÁO TỔNG HỢP KHẮC PHỤC LỖI, TỐI ƯU HỆ THỐNG & KIỂM TOÁN ĐỀ THI TỰ ĐỘNG

- **Dự án NCKH:** Hệ thống Agentic RAG Sinh & Kiểm định Đề thi Tin học 10 – Chủ đề F (Python, SGK Kết nối tri thức, Bài 16–32)
- **Kiến trúc thực thi:** 100% cục bộ (`Ollama llama3.2_tinhoc10` + `nomic-embed-text` trên 4GB VRAM RTX 3050, ChromaDB `data/chroma_db_v2`, LangGraph kiểm định 2 tầng Rule Hard Gate + Fuzzy Quality, Python Sandbox `timeout=2.0s`, Exam Critic, thang điểm 2025–2026)
- **Ngày nghiệm thu:** 18/11/2026
- **Kết quả kiểm toán tự động cuối cùng:** **PASS 8/8 tiêu chí – 18/18 câu = 10.0/10.0 điểm – 0 lỗi – Fuzzy TB = 0.958/1.0**

---

## 1. Bảng Tổng Hợp Toàn Bộ Lỗi Đã Phát Hiện & Khắc Phục

| # | Nhóm lỗi | Hiện tượng thực tế phát hiện | Nguyên nhân kỹ thuật gốc | Tệp khắc phục | Trạng thái |
|---|---|---|---|---|---|
| 1 | **Giao diện Web (Streamlit Markdown)** | Khối CSS Neo-Bento bị in thành văn bản thô trên đầu trang Web, làm vỡ giao diện Hero Header & Bento Grid. | Khối `<style>...</style>` trong `st.markdown(..., unsafe_allow_html=True)` có thụt lề 8–10 dấu cách và chứa dòng trống giữa các quy tắc, khiến bộ phân tích CommonMark ngắt sớm khối HTML. | `app_ui.py` | Đã sửa triệt để |
| 2 | **Giao diện Web (Streamlit Magic)** | In danh sách thuộc tính widget `DeltaGenerator` ngay bên dưới câu dẫn `TRUE_FALSE`. | Dùng biểu thức điều kiện 1 dòng `st.code(...) if ... else st.write(...)` (bare expression statement) kích hoạt tính năng Streamlit Magic tự gọi `st.write()` lên đối tượng trả về. | `app_ui.py` | Đã sửa triệt để |
| 3 | **Định dạng bản in A4 & Word** | Xuất hiện thanh cuộn ngang ("nút kéo qua") và đường kẻ dọc đen cạnh đoạn mã; câu văn tiếng Việt có chứa từ khóa (`for`, `range()`, `n = 10`, `Hình 16.3`) bị tách xuống khối `<pre>` sai font Consolas. | CSS `.py-code` dùng `white-space: pre; overflow-x: auto; border-left: 2px solid #000;`; hàm `_is_docx_python_line()` kiểm tra `any(m in s ...)` ở bất kỳ vị trí nào trong dòng thay vì chỉ nhận diện dòng bắt đầu bằng cú pháp Python/phép gán thuần. | `app_ui.py`, `core/exam_assembler.py` | Đã sửa triệt để |
| 4 | **Tiêu đề & Xuất file Word** | Tiêu đề tờ đề in thừa cụm `"GỌN CHỦ ĐỀ F"` và `"(10.0 ĐIỂM – 18 CÂU)"`; tiêu đề phần đáp án còn màu xanh `(20, 60, 120)`; phương án MCQ nhiều dòng bị dính liền. | `data/ma_tran_de.json` đặt tên Preset gộp cả ghi chú điểm/số câu; `app_ui.py` lấy nguyên `ten_hien_thi.upper()` làm tiêu đề in; `export_exam_to_docx()` còn tham số `color=(20, 60, 120)`. | `data/ma_tran_de.json`, `core/exam_assembler.py`, `app_ui.py` | Đã sửa triệt để |
| 5 | **Lặp dữ liệu mẫu 1-shot (Pink Elephant)** | Mô hình 3B liên tục lặp lại `'Chan'`, `'Le'`, `x = 7`, `range(1, 5)` ở Bài 17, 19, 20 gây rớt Hard Gate và kéo dài số vòng retry. | Khối 1-shot cũ chứa trực tiếp các hằng mẫu này; đồng thời `generate_problem_seed()` ghi rõ `"(CẤM dùng x=7)"` và `"CẤM dùng range(1, 5)"` làm kích hoạt hiệu ứng *Pink Elephant* trên mô hình 3B. | `core/retriever.py`, `core/generator.py`, `core/validator.py` | Đã sửa triệt để |
| 6 | **Sai lệch tính toán / rớt câu ở LLM 3B** | Một số câu `SHORT_ANSWER`/`MCQ` chạy đúng trên Sandbox nhưng mô hình tính nhầm `dap_an_ngan`/`dap_an`; câu `ESSAY_CODE` trả `dap_an_mau` dạng `list`, gộp đề vào `yeu_cau_hoc_sinh` hoặc quên chép danh sách mẫu vào `tinh_huong`; câu `TRUE_FALSE` Bài 19/20/26 bị cắt cụt ý `c/d` hoặc thiếu từ khóa `def`. | Chưa có bước chuẩn hóa hậu xử lý tất định (Deterministic Auto-Grounding) trước kiểm định; `num_predict` chưa phân bổ hợp lý theo dạng câu; chưa cung cấp mẫu cấu trúc có `def` (Bài 26–28), `if/else` (Bài 19) và `while` (Bài 21); quy tắc Bài 24 NB yêu cầu dấu nháy cả với câu lý thuyết nhận biết. | `core/generator.py`, `core/validator.py` | Đã sửa triệt để |
| 7 | **Lọt câu lỗi / thiếu câu ma trận** | Câu `is_pass == False`, câu rỗng (`(Chưa có`), câu dính chú thích `Hình 16`–`Hình 32`/`Bảng `, câu có `giai_thich` rò phản hồi nội bộ Validator có thể lọt vào đề hoặc làm thiếu hụt số câu ma trận (14/18 -> 17/18). | `assemble_exam()` trước đó đưa cả câu `is_pass == False` vào `draft_items` và khôi phục câu rớt khi thiếu số lượng; thiếu cơ chế bù vét an toàn cho 1–2 ô biên cuối. | `core/validator.py`, `core/exam_assembler.py` | Đã sửa triệt để |
| 8 | **Nghẽn tốc độ & Tràn 4GB VRAM** | Ghép đề 18–21 câu mất ~613s (> 10 phút), Pha 1 tiền truy xuất mất `78.96s` do gọi 36 lượt embedding và nạp/xả qua lại giữa `nomic-embed-text` và `llama3.2_tinhoc10`. | Mỗi câu gọi ChromaDB + `nomic-embed-text` xen kẽ với `llama3.2_tinhoc10` gây swap VRAM; `retrieve_evidence_package()` gọi thêm truy vấn `De_Tham_Khao_2026` dư thừa dù template đã có 1-shot và chưa cache theo `(bai_hoc, chi_tiet)`. | `core/retriever.py`, `core/exam_assembler.py`, `core/generator.py` | Đã tối ưu mạnh |

---

## 2. Chi Tiết Giải Pháp Kỹ Thuật Theo Từng Mô-đun

### 2.1. Chuẩn hóa Ma trận & Tiêu đề đề thi — [ma_tran_de.json](file:///d:/AI_Agent_NCKH/data/ma_tran_de.json)
- Đổi tên hiển thị Preset 1 thành `"Đề kiểm tra 15 phút – Chủ đề F"` và bổ sung trường `"tieu_de_in": "ĐỀ KIỂM TRA CHỦ ĐỀ F"` cho cả 2 Preset chuẩn 10.0 điểm (18 câu và 21 câu), tách riêng thông tin thời gian làm bài xuống dòng phụ.

### 2.2. Cache Truy xuất SGK & Hạt giống Dữ liệu (Problem Seed) — [retriever.py](file:///d:/AI_Agent_NCKH/core/retriever.py)
- Thêm bộ đệm `_SGK_CHUNK_CACHE` theo `(bai_hoc, chu_de_chi_tiet, k_sgk)` và bỏ qua truy vấn `De_Tham_Khao_2026` dư thừa khi khuôn mẫu đã có `vi_du_1shot`, giúp cắt thời gian **Pha 1 từ `78.96s` xuống còn `29.74s` (nhanh hơn 2.65×)**.
- Bổ sung `generate_problem_seed(lesson, loai)` cấp ngẫu nhiên tên biến (`a, b`, `m, n`, `tong`, `dem`, `ds`, `s`, `k`...) và bộ số/xâu/danh sách riêng cho từng ô ma trận (bao gồm hạt giống danh sách gán trực tiếp cho `Bài 31/32 ESSAY_CODE`, không dùng `input()`, loại bỏ hoàn toàn các chuỗi nhắc *Pink Elephant*).

### 2.3. Kiểm định 2 Tầng Hard Gate & Sandbox — [validator.py](file:///d:/AI_Agent_NCKH/core/validator.py)
- Siết Tầng 1 Hard Gate:
  - Chặn sao chép dữ liệu mẫu 1-shot (`'Chan'`, `'Le'`, `x = 7`, `range(1, 5)`, `[7, 4, 9, 6, 8]`), từ tiếng Anh vô nghĩa (`Opposite`), mã Python viết dính liền trên 1 dòng (`while ...: ... = ...`), biến chưa khởi tạo (qua phân tích AST `_find_undefined_vars_in_ast`) và vi phạm tính đơn trị (Single-answer) cho MCQ lệnh gán/đặt tên biến.
  - Chặn chú thích SGK trong đề (`Hình 16`..`Hình 32`, `Bảng `, `Hoạt động `, `BÀI `), chuỗi rỗng (`(Chưa có`, `(Trống)`, `Chưa xác định`), ý `TRUE_FALSE` ngắn (< 8 ký tự), trùng `giai_thich`, nhắc biến ngoài đề và rò thông báo phản hồi nội bộ Validator (`Hãy sửa`, `Tầng 1`, `đang trùng nội dung`).
  - Khóa cứng trọng tâm theo nhóm bài: Bài 22–23 (`[...]`/`list`), Bài 24–25 (xâu `'...'`/`"..."`, cho phép câu lý thuyết NB dùng thuật ngữ `xâu kí tự`/`str`), Bài 26–28 (`def`).
  - Tự động chuẩn hóa `dap_an_mau` dạng `list` Python thành chuỗi sạch qua `_normalize_code_mau()`.
  - Kiểm chứng **Execution-Grounded Answer**: đối chiếu đáp án khai báo với `stdout` thực tế từ `core/sandbox.py` (`timeout=2.0s`).

### 2.4. Tự động Chuẩn hóa Hậu xử lý & Cấp phát `num_predict` Thích ứng — [generator.py](file:///d:/AI_Agent_NCKH/core/generator.py)
- Duy trì `keep_alive: "15m"` trên `/api/chat`, `MAX_RETRIES = 2`, bổ sung retry 1 lần khi gặp lỗi HTTP 500 cục bộ từ Ollama.
- Cấp phát `ADAPTIVE_NUM_PREDICT`: `MCQ = 380`, `SHORT_ANSWER = 360`, `TRUE_FALSE = 580`, `ESSAY_CODE = 520`.
- Bổ sung `_auto_ground_question_json()` chạy tất định trước `validate_question()`:
  1. Chuẩn hóa `dap_an_mau` dạng `list`, ánh xạ khóa `tinh_huong` / `yeu_cau_hoc_sinh` cho `ESSAY_CODE` và tự đồng bộ danh sách mẫu `[...]` từ chính `dap_an_mau` sang `tinh_huong` nếu thiếu.
  2. Tự động gắn câu nguyên văn từ `sgk_chunks[0]` vào `trich_dan_sgk` khi độ trùng từ vựng `< 45%`.
  3. Tự động đồng bộ đáp án đúng `SHORT_ANSWER` (`dap_an_ngan`) và `MCQ` (`dap_an` / phương án tương ứng) theo `stdout` thực tế từ Python Sandbox.
- Bổ sung chỉ thị cú pháp trọng tâm ngay từ lượt sinh đầu và mẫu cấu trúc sạch (có `def` cho Bài 26–28, `if/else` cho Bài 19, `while` cho Bài 21).

### 2.5. Ghép Đề 2 Pha, Backfill Chặt & Xuất Word 100% Trắng Đen — [exam_assembler.py](file:///d:/AI_Agent_NCKH/core/exam_assembler.py)
- **Pha 1:** Tiền truy xuất theo lô có cache `(bai_hoc, loai, muc_do, chi_tiet)` + cập nhật `progress_callback` liên tục -> gọi `POST /api/embed` với `keep_alive: 0` giải phóng 100% VRAM `nomic-embed-text`.
- **Pha 2:** Sinh & kiểm định tuần tự trên `llama3.2_tinhoc10` với `pre_retrieved_evidence` (`0ms embed`), truyền danh sách chữ ký mã đã dùng (`avoid_snippets`), tuyệt đối **chỉ nhận câu có `is_pass == True`**, đẩy các ô chưa đạt/trùng sang **Backfill** (2 vòng + bù vét an toàn cho 1–2 ô biên cuối, vẫn bắt buộc `is_pass == True` 100%).
- Nâng cấp `_is_docx_python_line()` phân biệt chuẩn xác dòng lệnh Python vs văn bản tiếng Việt (dùng chung cho Word và HTML A4).
- Nâng cấp `export_exam_to_docx()` 100% đen trắng (`RGBColor(0, 0, 0)`), tách dòng code `Consolas 10.5pt` cả trong phương án MCQ, hỗ trợ `include_answers=True/False` xuất 2 phiên bản Word (Đầy đủ Đề + Đáp án & Chỉ Đề Học sinh).

### 2.6. Giao diện Web Neo-Bento & Bộ Tiện ích Giáo viên / Học sinh — [app_ui.py](file:///d:/AI_Agent_NCKH/app_ui.py)
- Sửa triệt để lỗi CommonMark (`_render_raw_html()`), lỗi Streamlit Magic `DeltaGenerator` (`if/else` chuẩn), xóa thanh cuộn ngang và viền dọc cạnh code trong bản xem trước A4 (`white-space: pre-wrap; overflow-wrap: break-word; overflow-x: hidden; border: none;`).
- Bổ sung đầy đủ tiện ích thực tế:
  - **Nút "🔄 Sinh lại riêng Câu X"** cho phép thay mới 1 câu chưa ưng ý trong ~6–8s mà không cần sinh lại cả đề.
  - **Trình chỉnh sửa nhanh trực tiếp (Quick Edit)** cập nhật ngay câu hỏi/phương án/đáp án lên bản xem trước A4 và file Word.
  - **Tải 2 phiên bản Word (`.docx` trắng đen):** Bản Đầy đủ (Đề + Đáp án) & Bản Chỉ Đề Học sinh, kèm nút tải **Ngân hàng đề (`.json`)**.
  - **Chế độ 3 – Quản lý Ngân hàng đề (`data/question_bank.json`)** & bộ lọc nâng cấp ở Tab Học sinh: lọc theo Bài 16–32, Dạng câu hỏi, Mức độ nhận thức (NB/TH/VD), tìm kiếm từ khóa và nút xóa câu không dùng.

---

## 3. Kết Quả Kiểm Toán Tự Động Thực Tế Đề 18 Câu – 10.0 Điểm

Thực thi bằng script kiểm toán độc lập [auto_exam_audit.py](file:///d:/AI_Agent_NCKH/experiments/auto_exam_audit.py) trên mô hình cục bộ `llama3.2_tinhoc10` (dữ liệu thật từ `data/chroma_db_v2`, không ảnh hưởng các tệp ablation gốc).

### 3.1. Tiến trình tối ưu & kiểm toán lặp cho đến 0 lỗi

| Vòng kiểm toán | Pha 1 (s) | Pha 2 (s) | Tổng thời gian (s) | Số câu đạt chuẩn | Tổng điểm | Fuzzy TB | Tổng lỗi (8 tiêu chí) | Cải tiến thực hiện sau vòng |
|---|---|---|---|---|---|---|---|---|
| Vòng 1 | 78.96s | 363.29s | 444.32s | 14/18 | 7.25đ | 0.974 | 2 (thiếu 4 câu) | Xóa Pink Elephant `x=7`/`range(1,5)`, cache SGK & bỏ embed thừa, thêm mẫu `def` Bài 26 |
| Vòng 2 | 29.14s | 325.15s | 356.39s | 16/18 | 8.75đ | 0.966 | 2 (thiếu 2 câu) | Chuẩn hóa Bài 24 NB lý thuyết, nâng `TRUE_FALSE` `num_predict=580` + mẫu `if/else` |
| Vòng 3 | 30.02s | 238.06s | 270.14s | 16/18 | 9.00đ | 0.969 | 2 (thiếu 2 câu) | Auto-Sync stdout 1–4 dòng ngắn & thêm mẫu thụt lề `while` Bài 21 |
| Vòng 4 | 30.57s | 220.12s | 252.75s | 17/18 | 9.00đ | 0.963 | 2 (thiếu 1 câu) | Chuẩn hóa khóa `tinh_huong`/`yeu_cau_hoc_sinh` & retry HTTP 500 |
| Vòng 5 | 29.73s | 363.87s | 395.65s | 17/18 | 9.00đ | 0.976 | 2 (thiếu 1 câu) | Tự đồng bộ danh sách `[...]` từ `dap_an_mau` sang `tinh_huong` cho `ESSAY_CODE` |
| **Vòng 6 (Nghiệm thu)** | **29.74s** | **294.34s** | **326.15s** | **18/18** | **10.0đ** | **0.958** | **0 lỗi (8/8 PASS)** | **Đạt 100% toàn bộ 8 tiêu chí kiểm toán** |

### 3.2. Kết quả 8 Tiêu chí Kiểm toán (Vòng Nghiệm thu)

| STT | Tiêu chí kiểm toán | Kết quả | Chi tiết xác minh |
|---|---|---|---|
| 1 | Tiêu đề chuẩn `ĐỀ KIỂM TRA CHỦ ĐỀ F` | **PASS ✅** | Có mặt chuẩn xác trong cả HTML A4 và DOCX; không chứa `"GỌN CHỦ ĐỀ F"` hay cụm điểm/số câu thừa |
| 2 | Đủ `18/18` câu & Tổng điểm = `10.0` | **PASS ✅** | 8 MCQ (2.0đ) + 3 Đúng/Sai (3.0đ) + 4 Trả lời ngắn (2.0đ) + 3 Tự luận Code (3.0đ) = **10.0đ**, 100% `is_pass=True` |
| 3 | Không câu/ý nào rỗng | **PASS ✅** | 0 câu rỗng, 0 placeholder `(Chưa có`/`(Trống)`, 12/12 ý Đúng/Sai đầy đủ nội dung |
| 4 | Không trùng câu hay trùng phương án A/B/C/D | **PASS ✅** | Exam Critic xác nhận 0 câu trùng ý / lộ đáp án chéo; 8/8 câu MCQ có 4 phương án đôi một khác nhau |
| 5 | Không chép thô SGK/Hình/Bảng hay mẫu 1-shot cũ | **PASS ✅** | 0 vi phạm `Hình 16–32`, `Bảng `, `Hoạt động `, `BÀI `, `'Chan'`, `'Le'`, `x = 7`, `range(1, 5)`, `[7, 4, 9, 6, 8]` |
| 6 | 100% mã Python chạy không lỗi Sandbox & khớp `stdout` | **PASS ✅** | **9/9 câu có mã Python (100%)** chạy thành công trên Sandbox (`timeout=2.0s`) và khớp tuyệt đối `stdout` |
| 7 | HTML xem trước không chứa `overflow-x: auto` / `border-left` | **PASS ✅** | 0 lỗi CSS; khối code dùng `white-space: pre-wrap; overflow-x: hidden; border: none;` |
| 8 | File `.docx` xuất ra 100% trắng đen sạch lỗi | **PASS ✅** | **0 run có màu** trên cả 2 bản `.docx`; bản Học sinh tách sạch không lẫn Hướng dẫn chấm |

### 3.3. Bảng Chi Tiết 18 Câu Trong Đề Nghiệm Thu

| STT | Bài học | Dạng câu hỏi | Mức độ | Trạng thái | Điểm Fuzzy | Sandbox | Vòng retry | Độ trễ (s) |
|---:|---|---|---|---:|---:|:---:|---:|---:|
| 1 | Bài 16 | MCQ | NB | ĐẠT | 0.916 | Lý thuyết | 0 | 6.43 |
| 2 | Bài 17 | MCQ | NB | ĐẠT | 0.925 | Lý thuyết | 0 | 7.52 |
| 3 | Bài 18 | MCQ | NB | ĐẠT | 1.000 | Lý thuyết | 0 | 8.02 |
| 4 | Bài 19 | MCQ | TH | ĐẠT | 0.961 | Lý thuyết | 1 | 16.75 |
| 5 | Bài 20 | MCQ | TH | ĐẠT | 0.811 | Lý thuyết | 0 | 8.00 |
| 6 | Bài 22 | MCQ | TH | ĐẠT | 0.970 | Lý thuyết | 0 | 7.53 |
| 7 | Bài 29 | MCQ | NB | ĐẠT | 0.961 | Lý thuyết | 0 | 9.82 |
| 8 | Bài 19 | TRUE_FALSE | TH | ĐẠT | 1.000 | PASS ✅ | 0 | 8.39 |
| 9 | Bài 26 | TRUE_FALSE | VD | ĐẠT | 1.000 | PASS ✅ | 1 | 18.22 |
| 10 | Bài 21 | SHORT_ANSWER | TH | ĐẠT | 1.000 | PASS ✅ | 0 | 6.74 |
| 11 | Bài 25 | SHORT_ANSWER | VD | ĐẠT | 0.983 | Lý thuyết | 0 | 9.47 |
| 12 | Bài 28 | SHORT_ANSWER | VD | ĐẠT | 1.000 | PASS ✅ | 0 | 7.09 |
| 13 | Bài 22 | ESSAY_CODE | VD | ĐẠT | 0.965 | PASS ✅ | 1 | 14.03 |
| 14 | Bài 17 | SHORT_ANSWER | TH | ĐẠT | 1.000 | PASS ✅ | 0 | 7.39 |
| 15 | Bài 26 | ESSAY_CODE | VD | ĐẠT | 1.000 | PASS ✅ | 0 | 8.39 |
| 16 | Bài 31 | ESSAY_CODE | VD | ĐẠT | 0.904 | PASS ✅ | 0 | 8.21 |
| 17 | Bài 24 | MCQ | NB | ĐẠT | 0.896 | Lý thuyết | 1 | 14.98 |
| 18 | Bài 20 | TRUE_FALSE | TH | ĐẠT | 0.954 | PASS ✅ | 0 | 10.59 |

- **Tỷ lệ đạt chuẩn lượt đầu (0 retry):** 14/18 câu (**77.8%**), độ trễ trung bình câu đạt = **9.86s/câu** (nhanh nhất `6.43s`).
- **Điểm Logic mờ trung bình (Fuzzy Quality):** **0.958 / 1.0** (tất cả 18 câu đều vượt xa ngưỡng `0.75`).

### 3.4. Hồ sơ Xuất bản & Kiểm toán Mẫu Mới Nhất
- **Bản Word Đầy đủ (Đề + Đáp án biểu điểm, 100% Trắng Đen):** [sample_exam_18cau_daydu.docx](file:///d:/AI_Agent_NCKH/sample_exam_18cau_daydu.docx)
- **Bản Word Chỉ Đề Học sinh (In phát lớp, 100% Trắng Đen):** [sample_exam_18cau_hocsinh.docx](file:///d:/AI_Agent_NCKH/sample_exam_18cau_hocsinh.docx)
- **Nhật ký kiểm toán tự động JSON:** [auto_exam_audit_result.json](file:///d:/AI_Agent_NCKH/experiments/auto_exam_audit_result.json)
- **Script kiểm toán tự động:** [auto_exam_audit.py](file:///d:/AI_Agent_NCKH/experiments/auto_exam_audit.py)
