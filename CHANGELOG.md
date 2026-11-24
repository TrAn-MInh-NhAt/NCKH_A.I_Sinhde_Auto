# NHẬT KÝ CẬP NHẬT HỆ THỐNG (CHANGELOG)

Tất cả các thay đổi và bản phát hành quan trọng của dự án Nghiên cứu Khoa học **Hệ thống AI Agent cục bộ kết hợp kiến trúc Neuro-Symbolic hỗ trợ sinh và kiểm định đề kiểm tra Tin học 10 – Chủ đề F** được ghi nhận chi tiết tại tài liệu này.

---

## [v2.0.0] – Bản phát hành chính thức: Neuro-Symbolic Agentic RAG Đa Dạng Hóa Đề Thi
*Ngày phát hành: 24/11/2026*

**Đề tài NCKH:** Hệ thống AI Agent cục bộ kết hợp kiến trúc Neuro-Symbolic hỗ trợ sinh và kiểm định đề kiểm tra Tin học 10 – Chủ đề F  
**Nhóm tác giả:** Trần Minh Nhật (Trưởng nhóm), Phạm Kỳ Hải, Nguyễn Hữu Lộc (Lớp 23SPT, Khoa Toán – Tin, Trường Đại học Sư phạm – Đại học Đà Nẵng)  
**Giảng viên hướng dẫn:** ThS. Đoàn Duy Bình  
**Kho mã nguồn:** https://github.com/TrAn-MInh-NhAt/NCKH_A.I_Sinhde_Auto

### Điểm nâng cấp đột phá ở phiên bản 2.0

1. **Mở rộng kho khuôn bài tham số hóa lên 155 Blueprints độc nhất (`core/symbolic_blueprints_ext.py`):**
   - Tăng gấp **2,28 lần** so với bản v1.0 (từ 68 lên **155 Blueprints**, phủ 68 cặp Bài học – Dạng thức và 283 ánh xạ trên toàn bộ 17 bài Chủ đề F, Bài 16–32 SGK Tin học 10 – Kết nối tri thức).
   - Phân bổ chi tiết: **62 MCQ** | **26 Trắc nghiệm Đúng/Sai** | **32 Trả lời ngắn** | **35 Tự luận lập trình Python**.
   - Loại bỏ toàn bộ dữ liệu hằng cố định (hardcode), mở rộng sang các bài toán thực tế đa dạng (tính tiền điện bậc thang, lọc nhiệt độ cảm biến, kiểm tra mật khẩu, số đối xứng, xử lý ma trận và gỡ lỗi chương trình).

2. **Cơ chế chống lặp xuyên đề LRU 90 & Xáo trộn động (`core/exam_assembler.py`):**
   - Tích hợp bộ nhớ đệm lịch sử `data/recent_blueprints.json` lưu **90 blueprint gần nhất** (tương đương 5 mã đề liên tiếp), hạ tỷ lệ trùng lặp dạng bài giữa các đề xuống **0,0% (0/18 câu)**.
   - Bổ sung thuật toán xoay vòng ma trận bài học động (`_rotate_topic_f_specs()`) và xáo trộn ngẫu nhiên thứ tự câu hỏi bên trong từng phần (Phần I, II, III, IV) để tạo các mã đề hoàn toàn độc lập.

3. **Khóa cứng lời giải thích từ Python Sandbox & Làm sạch Prompt Leak (`core/generator.py`, `core/validator.py`):**
   - Sinh sẵn `verified_explanation` và `verified_tf_explanations` trực tiếp từ biến số thực thi và `stdout` của Sandbox cô lập, triệt tiêu **100%** hiện tượng mô hình LLM 3B tính nhẩm sai trong lời giải thích.
   - Bổ sung bộ lọc tự động loại bỏ các chuỗi chỉ thị nội bộ bị rò rỉ trong mục trích dẫn bằng chứng SGK.

4. **Bộ nạp ngân hàng đề mẫu ngoài thông minh (`core/exam_importer.py`):**
   - Khởi tạo thư mục `data/sample_exams/` hỗ trợ nạp đề từ 4 định dạng (`.docx`, `.json`, `.txt`, `.md`) vào `data/question_bank.json` với thuật toán khử trùng lặp Jaccard và nút thao tác trực tiếp trên giao diện Streamlit (`app_ui.py`).
   - Tách biệt hoàn toàn với kho tri thức vector `data/chroma_db_v2` để bảo toàn độ chuẩn xác của trích dẫn SGK.

5. **Chuẩn hóa tài liệu học thuật & Sơ đồ kiến trúc tiếng Việt:**
   - Hoàn thiện bộ **6 sơ đồ kiến trúc Mermaid tiếng Việt** (`docs/system_diagrams.md`) phản ánh chính xác hệ thống thực tế (`Streamlit + Cloudflare Tunnel + VRAM Lock + Neuro-Symbolic + Python Sandbox + Ollama llama3.2_tinhoc10`).
   - Đồng bộ toàn bộ `README.md`, `LICENSE` (MIT) và thông tin nhóm nghiên cứu chính thức.

### Chỉ số kiểm thử nghiệm thu phiên bản 2.0 (Trên GPU RTX 3050 – 4GB VRAM)

- **Tỷ lệ hoàn thành cấu trúc đề chuẩn 2025–2026:** `18/18 câu = 10,0 điểm` (`100%` đạt ngay lượt đầu, `0` vòng backfill).
- **Thời gian sinh trọn bộ đề 18 câu:** `95,8s – 96,2s` (nhanh gấp **~6 lần** kiến trúc Pure-LLM cũ).
- **Tỷ lệ trùng lặp Blueprint giữa 2 mã đề liên tiếp:** `0,0%` (`0/18` câu trùng).
- **Mức chiếm dụng bộ nhớ GPU tối đa:** `3,8 GB VRAM` (vận hành ổn định trên laptop phổ thông 4GB VRAM).

---

## [v1.0.0] – Phiên bản tiền nghiệm: Kiến trúc Agentic RAG Kết hợp Mô hình 3B Biên
*Ngày phát hành: 18/11/2026*
- Xây dựng luồng tiền truy xuất theo lô (Batch Pre-retrieval) trên ChromaDB v2.
- Ghép nối mô hình ngôn ngữ cục bộ `llama3.2_tinhoc10` (3B) qua Ollama.
- Triển khai mô hình kiểm định kép (2-Tier Validator) và cơ chế phản biện toàn đề (Exam Critic).
- Tích hợp 68 Blueprints cơ bản khởi điểm cho Chủ đề F.
