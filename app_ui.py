import os
import sys
import html
import json
import time
import inspect
import importlib
import threading
import contextlib
from datetime import datetime

# Đảm bảo stdout/stderr luôn dùng UTF-8 trên Windows (tránh lỗi cp1252 khi chạy ngầm dưới Cloudflare Tunnel)
for _std_stream in (sys.stdout, sys.stderr):
    if hasattr(_std_stream, "reconfigure"):
        try:
            _std_stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

import streamlit as st
import streamlit.components.v1 as components


@st.cache_resource
def _get_gpu_vram_lock() -> threading.Lock:
    """Khóa tuần tự toàn cục (shared giữa mọi phiên truy cập) để bảo vệ GPU 4GB VRAM."""
    return threading.Lock()


@contextlib.contextmanager
def _acquire_vram_slot():
    """Đảm bảo tại mỗi thời điểm chỉ có 1 yêu cầu gọi Ollama/Embedding chạy trên GPU 4GB VRAM."""
    lock = _get_gpu_vram_lock()
    acquired = lock.acquire(blocking=False)
    if not acquired:
        wait_box = st.empty()
        wait_box.warning(
            "⏳ Hệ thống đang xử lý lượt yêu cầu trước đó trên GPU 4GB VRAM, vui lòng đợi trong giây lát..."
        )
        lock.acquire(blocking=True)
        wait_box.empty()
    try:
        yield
    finally:
        lock.release()

# --- TỰ ĐỘNG NẠP LẠI MODULE CORE NẾU TIẾN TRÌNH STREAMLIT CŨ ĐANG CACHE BẢN THUẦN LLM ---
def _ensure_neuro_symbolic_modules_loaded() -> None:
    """Tránh trường hợp Streamlit giữ bản core.generator/core.exam_assembler cũ trong sys.modules sau khi nâng cấp."""
    gen_mod = sys.modules.get("core.generator")
    asm_mod = sys.modules.get("core.exam_assembler")
    need_reload = False
    if gen_mod is not None:
        if not getattr(gen_mod, "USE_NEURO_SYMBOLIC", False):
            need_reload = True
        else:
            try:
                if "use_neuro_symbolic" not in inspect.signature(gen_mod.generate_question).parameters:
                    need_reload = True
            except Exception:
                need_reload = True
    if asm_mod is not None:
        try:
            if "use_neuro_symbolic" not in inspect.signature(asm_mod.assemble_exam).parameters:
                need_reload = True
        except Exception:
            need_reload = True

    if need_reload:
        for mod_name in (
            "core.retriever",
            "core.validator",
            "core.symbolic_engine",
            "core.generator",
            "core.exam_assembler",
        ):
            if mod_name in sys.modules:
                importlib.reload(sys.modules[mod_name])
            else:
                importlib.import_module(mod_name)


_ensure_neuro_symbolic_modules_loaded()

# --- IMPORT MODULE CỐT LÕI KIẾN TRÚC NEURO-SYMBOLIC ---
from core.generator import generate_question
from core.exam_assembler import (
    assemble_exam,
    export_exam_to_docx,
    _is_docx_python_line,
    _extract_compact_code_signature,
    _recompute_exam_summary,
    _get_point_map,
)
from core.retriever import get_exam_matrix
from core.sandbox import cham_code_python
from experiments.logger import update_approval_status, read_logs
from core.exam_importer import import_sample_exams

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BANK_PATH = os.path.join(BASE_DIR, "data", "question_bank.json")

# Danh sách đủ 17 bài học Chủ đề F Tin học 10 - SGK Kết nối tri thức
LESSONS_CHUDE_F = [
    "Bài 16: Ngôn ngữ lập trình bậc cao và Python",
    "Bài 17: Biến và lệnh gán",
    "Bài 18: Các lệnh vào ra đơn giản",
    "Bài 19: Câu lệnh rẽ nhánh if",
    "Bài 20: Câu lệnh lặp for",
    "Bài 21: Câu lệnh lặp while",
    "Bài 22: Kiểu dữ liệu danh sách",
    "Bài 23: Một số lệnh làm việc với dữ liệu danh sách",
    "Bài 24: Xâu kí tự",
    "Bài 25: Một số lệnh làm việc với xâu kí tự",
    "Bài 26: Hàm trong Python",
    "Bài 27: Tham số của hàm",
    "Bài 28: Phạm vi của biến",
    "Bài 29: Nhận biết lỗi chương trình",
    "Bài 30: Kiểm thử và gỡ lỗi chương trình",
    "Bài 31: Thực hành viết chương trình đơn giản",
    "Bài 32: Ôn tập lập trình Python",
]

LOAI_MAP = {
    "Trắc nghiệm 4 lựa chọn (MCQ - 0.25đ)": "MCQ",
    "Đúng/Sai 4 mệnh đề (2025-2026 - tối đa 1.0đ)": "TRUE_FALSE",
    "Trả lời ngắn (0.5đ)": "SHORT_ANSWER",
    "Tự luận lập trình Python (Code - 1.0đ)": "ESSAY_CODE",
}

MUC_DO_MAP = {
    "Nhận biết (NB)": "NB",
    "Thông hiểu (TH)": "TH",
    "Vận dụng (VD)": "VD",
}

TF_STEP_SCORES = {0: 0.0, 1: 0.1, 2: 0.25, 3: 0.5, 4: 1.0}


# ==============================================================================
# QUẢN LÝ NGÂN HÀNG ĐỀ PHÊ DUYỆT (data/question_bank.json)
# ==============================================================================

def load_question_bank() -> list[dict]:
    if not os.path.exists(BANK_PATH):
        return []
    try:
        with open(BANK_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def save_to_question_bank(entries: list[dict]) -> int:
    os.makedirs(os.path.dirname(BANK_PATH), exist_ok=True)
    bank = load_question_bank()
    next_id = len(bank) + 1
    added = 0
    for item in entries:
        record = {
            "id": f"Q{next_id:04d}",
            "approved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "bai_hoc": item.get("bai_hoc", ""),
            "muc_do": item.get("muc_do", "TH"),
            "loai_cau_hoi": item.get("loai_cau_hoi", "MCQ"),
            "question_json": item.get("question_json", {}),
            "fuzzy_score": item.get("fuzzy_score", 0.0),
            "xep_loai": item.get("xep_loai", ""),
            "sandbox_verified": item.get("sandbox_verified", False),
        }
        bank.append(record)
        next_id += 1
        added += 1
        ts = item.get("log_timestamp", "")
        if ts:
            update_approval_status(ts, "DA_DUYET")

    with open(BANK_PATH, "w", encoding="utf-8") as f:
        json.dump(bank, f, ensure_ascii=False, indent=2)
    return added


def delete_from_question_bank(qid: str) -> bool:
    """Xóa 1 câu hỏi khỏi data/question_bank.json theo mã ID."""
    bank = load_question_bank()
    new_bank = [x for x in bank if x.get("id") != qid]
    if len(new_bank) == len(bank):
        return False
    os.makedirs(os.path.dirname(BANK_PATH), exist_ok=True)
    with open(BANK_PATH, "w", encoding="utf-8") as f:
        json.dump(new_bank, f, ensure_ascii=False, indent=2)
    return True


# ==============================================================================
# HÀM HIỂN THỊ AN TOÀN (ĐÁP ÁN KHÔNG BAO GIỜ TRỐNG)
# ==============================================================================

def _safe_mcq_answer(q: dict) -> str:
    raw = str(q.get("dap_an") or q.get("dap_an_dung") or "").strip().upper()
    if raw in ("A", "B", "C", "D"):
        return f"{raw}. {q.get(raw, '')}"
    for k in ("A", "B", "C", "D"):
        if raw and raw == str(q.get(k, "")).strip().upper():
            return f"{k}. {q.get(k, '')}"
    return raw if raw else "A (cần giáo viên kiểm tra lại)"


def _safe_tf_answer(val) -> str:
    s = str(val or "").strip().lower()
    if s in ("đúng", "dung", "true", "đ", "d"):
        return "Đúng"
    if s in ("sai", "false", "s"):
        return "Sai"
    return "Chưa xác định"


def _render_question_card_teacher(item: dict, idx: int | None = None) -> str:
    """Hiển thị 1 câu hỏi đầy đủ cho Giáo viên kiểm duyệt và trả về chuỗi text để xuất file."""
    q = item.get("question_json", {})
    loai = item.get("loai_cau_hoi", "MCQ")
    bai = item.get("bai_hoc", "")
    muc_do = item.get("muc_do", "TH")
    val = item.get("validation_result", {}) or {}
    fuzzy = float(val.get("diem_chat_luong", item.get("fuzzy_score", 0.0)))
    xep_loai = val.get("xep_loai", item.get("xep_loai", "CHƯA CHẤM"))
    retries = item.get("retry_count", 0)
    sb_ok = bool(val.get("sandbox_verified", item.get("sandbox_verified", False)))
    latency = item.get("latency_sec", 0.0)

    title_prefix = f"Câu {idx} | " if idx is not None else ""
    export_lines = [f"=== {title_prefix}{bai} | {loai} | Mức độ: {muc_do} ==="]

    with st.container(border=True):
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Chất lượng Logic mờ", f"{fuzzy:.3f} / 1.0", xep_loai)
        m2.metric("Số vòng tự sửa", f"{retries} lần")
        m3.metric("Kiểm chứng Sandbox", "Đạt" if sb_ok else "Lý thuyết")
        m4.metric("Thời gian sinh", f"{latency}s")

        if loai == "MCQ":
            cau_hoi = q.get("cau_hoi") or "(Không có nội dung câu hỏi)"
            st.markdown(f"**{title_prefix}{cau_hoi}**")
            export_lines.append(str(cau_hoi))
            for opt in ("A", "B", "C", "D"):
                opt_val = q.get(opt, "(Trống)")
                st.write(f"**{opt}.** {opt_val}")
                export_lines.append(f"{opt}. {opt_val}")
            dap_an_str = _safe_mcq_answer(q)
            giai_thich = q.get("giai_thich") or q.get("loi_giai") or "(Chưa có giải thích)"
            st.info(f"**Đáp án đúng:** {dap_an_str}\n\n**Giải thích:** {giai_thich}")
            export_lines.append(f"-> Đáp án: {dap_an_str}\n-> Giải thích: {giai_thich}")

        elif loai == "TRUE_FALSE":
            stem = q.get("cau_hoi_chung") or "(Không có câu dẫn)"
            st.markdown(f"**{title_prefix}Câu dẫn chung:**")
            stem_str = str(stem)
            if "\n" in stem_str and ("for " in stem_str or "while " in stem_str or "if " in stem_str or "def " in stem_str):
                st.code(stem_str, language="python")
            else:
                st.write(stem)
            export_lines.append(str(stem))
            for letter in ("a", "b", "c", "d"):
                obj = q.get(letter) or q.get(letter.upper()) or {}
                md = obj.get("menh_de", "(Trống)") if isinstance(obj, dict) else str(obj)
                da = _safe_tf_answer(obj.get("dap_an") if isinstance(obj, dict) else "")
                gt = obj.get("giai_thich", "(Chưa có giải thích)") if isinstance(obj, dict) else ""
                st.write(f"**{letter})** {md}")
                st.caption(f"➔ Đáp án: **{da}** — Giải thích: {gt}")
                export_lines.append(f"{letter}) {md} -> {da} ({gt})")

        elif loai == "SHORT_ANSWER":
            cau_hoi = q.get("cau_hoi") or "(Không có nội dung câu hỏi)"
            st.markdown(f"**{title_prefix}Câu hỏi Trả lời ngắn:**")
            st.write(cau_hoi)
            ans = str(q.get("dap_an_ngan") or q.get("dap_an") or "(Chưa xác định)").strip()
            gt = q.get("giai_thich") or "(Chưa có giải thích)"
            st.info(f"**Đáp án ngắn:** `{ans}`\n\n**Giải thích:** {gt}")
            export_lines.append(f"{cau_hoi}\n-> Đáp án ngắn: {ans}\n-> Giải thích: {gt}")

        else:  # ESSAY_CODE
            th = q.get("tinh_huong") or "(Chưa có tình huống)"
            yc = q.get("yeu_cau_hoc_sinh") or "(Chưa có yêu cầu)"
            st.markdown(f"**{title_prefix}Tình huống bài toán:** {th}")
            st.markdown(f"**Yêu cầu:** {yc}")
            code_mau = str(q.get("dap_an_mau", "")).replace("```python", "").replace("```", "").strip()
            st.markdown("**Đáp án mẫu Python:**")
            st.code(code_mau or "# (Chưa có mã mẫu)", language="python")
            tc = q.get("tieu_chi_cham_diem", [])
            if isinstance(tc, list) and tc:
                st.markdown("**Tiêu chí chấm điểm:**")
                for line in tc:
                    st.write(f"- {line}")
            export_lines.append(f"Tình huống: {th}\nYêu cầu: {yc}\nMã mẫu:\n{code_mau}")

        trich_dan = q.get("trich_dan_sgk") or "(Chưa có trích dẫn SGK)"
        st.success(f"**Trích dẫn bằng chứng SGK ({bai}):** {trich_dan}")
        export_lines.append(f"Trích dẫn SGK: {trich_dan}\n")

    return "\n".join(export_lines)


def _render_quick_edit_panel(item: dict, idx: int, exam_pkg: dict) -> None:
    """Trình chỉnh sửa nhanh trực tiếp (Quick Edit) + Nút sinh lại riêng 1 câu ngay trên Web."""
    q = item.get("question_json", {}) or {}
    loai = item.get("loai_cau_hoi", "MCQ")
    bai = item.get("bai_hoc", "Bài 19")
    muc_do = item.get("muc_do", "TH")

    c_regen, c_edit = st.columns([1, 2.2])
    with c_regen:
        if st.button(f"Sinh lại riêng Câu {idx}", key=f"regen_q_{idx}", use_container_width=True):
            other_sigs = [
                _extract_compact_code_signature(x)
                for j, x in enumerate(exam_pkg.get("items", []), 1)
                if j != idx
            ]
            # Duy trì tập blueprint_id của toàn bộ các câu còn lại (cộng câu hiện tại) để sinh mới không trùng mô-típ
            used_bp_ids = {
                str(x.get("blueprint_id", "")).strip()
                for x in exam_pkg.get("items", [])
                if str(x.get("blueprint_id", "")).strip()
            }
            with _acquire_vram_slot():
                with st.spinner(f"Đang sinh mới riêng Câu {idx} ({bai} – {loai}) bằng Neuro-Symbolic..."):
                    new_res = generate_question(
                        bai_hoc=bai,
                        loai_cau_hoi=loai,
                        chu_de_chi_tiet=item.get("chu_de_chi_tiet", ""),
                        muc_do=muc_do,
                        enable_logging=True,
                        avoid_snippets=[s for s in other_sigs if s][-5:],
                        used_blueprint_ids=used_bp_ids,
                        use_neuro_symbolic=True,
                    )
            exam_pkg["items"][idx - 1] = {
                "bai_hoc": new_res["bai_hoc"],
                "loai_cau_hoi": new_res["loai_cau_hoi"],
                "muc_do": new_res["muc_do"],
                "chu_de_chi_tiet": item.get("chu_de_chi_tiet", ""),
                "blueprint_id": new_res.get("blueprint_id", ""),
                "question_json": new_res.get("question_json", {}),
                "validation_result": new_res.get("validation_result", {}),
                "retry_count": new_res.get("retry_count", 0),
                "prompt_tokens": new_res.get("prompt_tokens", 0),
                "latency_sec": new_res.get("latency_sec", 0.0),
                "log_timestamp": new_res.get("log_timestamp", ""),
            }
            bd, td = _recompute_exam_summary(exam_pkg["items"], _get_point_map())
            exam_pkg["bang_diem_chi_tiet"] = bd
            exam_pkg["tong_diem"] = td
            exam_pkg["tong_so_cau"] = len(exam_pkg["items"])
            st.session_state.exam_result = exam_pkg
            st.success(f"Đã thay thế Câu {idx} mới ({new_res.get('latency_sec', 0)}s)!")
            st.rerun()

    with c_edit:
        with st.expander(f"Chỉnh sửa nhanh Câu {idx}", expanded=False):
            updated_q = dict(q)
            if loai == "MCQ":
                updated_q["cau_hoi"] = st.text_area("Nội dung câu hỏi:", value=str(q.get("cau_hoi", "")), key=f"qe_ch_{idx}", height=90)
                ea, eb = st.columns(2)
                updated_q["A"] = ea.text_input("Phương án A:", value=str(q.get("A", "")), key=f"qe_a_{idx}")
                updated_q["B"] = eb.text_input("Phương án B:", value=str(q.get("B", "")), key=f"qe_b_{idx}")
                ec, ed = st.columns(2)
                updated_q["C"] = ec.text_input("Phương án C:", value=str(q.get("C", "")), key=f"qe_c_{idx}")
                updated_q["D"] = ed.text_input("Phương án D:", value=str(q.get("D", "")), key=f"qe_d_{idx}")
                cur_ans = str(q.get("dap_an", "A")).strip().upper()
                ans_idx = ["A", "B", "C", "D"].index(cur_ans) if cur_ans in ("A", "B", "C", "D") else 0
                updated_q["dap_an"] = st.selectbox("Đáp án đúng:", ["A", "B", "C", "D"], index=ans_idx, key=f"qe_ans_{idx}")
                updated_q["giai_thich"] = st.text_area("Giải thích:", value=str(q.get("giai_thich", "")), key=f"qe_gt_{idx}", height=70)
            elif loai == "TRUE_FALSE":
                updated_q["cau_hoi_chung"] = st.text_area("Câu dẫn chung:", value=str(q.get("cau_hoi_chung", "")), key=f"qe_tfstem_{idx}", height=100)
                for letter in ("a", "b", "c", "d"):
                    obj = dict(q.get(letter) or {}) if isinstance(q.get(letter), dict) else {}
                    c_m, c_d = st.columns([3, 1])
                    obj["menh_de"] = c_m.text_input(f"Mệnh đề {letter}):", value=str(obj.get("menh_de", "")), key=f"qe_tfmd_{idx}_{letter}")
                    cur_tf = _safe_tf_answer(obj.get("dap_an"))
                    obj["dap_an"] = c_d.selectbox(
                        f"Đáp án {letter}):",
                        ["Đúng", "Sai"],
                        index=0 if cur_tf != "Sai" else 1,
                        key=f"qe_tfda_{idx}_{letter}",
                    )
                    updated_q[letter] = obj
            elif loai == "SHORT_ANSWER":
                updated_q["cau_hoi"] = st.text_area("Nội dung câu hỏi:", value=str(q.get("cau_hoi", "")), key=f"qe_sach_{idx}", height=100)
                updated_q["dap_an_ngan"] = st.text_input("Đáp án ngắn:", value=str(q.get("dap_an_ngan", "")), key=f"qe_saans_{idx}")
                updated_q["giai_thich"] = st.text_area("Giải thích:", value=str(q.get("giai_thich", "")), key=f"qe_sagt_{idx}", height=70)
            else:  # ESSAY_CODE
                updated_q["tinh_huong"] = st.text_area("Tình huống:", value=str(q.get("tinh_huong", "")), key=f"qe_ecth_{idx}", height=80)
                updated_q["yeu_cau_hoc_sinh"] = st.text_input("Yêu cầu học sinh:", value=str(q.get("yeu_cau_hoc_sinh", "")), key=f"qe_ecyc_{idx}")
                raw_mau = q.get("dap_an_mau", "")
                if isinstance(raw_mau, list):
                    raw_mau = "\n".join(str(x) for x in raw_mau)
                updated_q["dap_an_mau"] = st.text_area("Mã nguồn mẫu Python:", value=str(raw_mau), key=f"qe_ecmau_{idx}", height=120)

            if st.button(f"Lưu chỉnh sửa Câu {idx}", key=f"save_qe_{idx}", type="primary"):
                exam_pkg["items"][idx - 1]["question_json"] = updated_q
                st.session_state.exam_result = exam_pkg
                st.success(f"Đã cập nhật Câu {idx} vào đề thi & bản xem trước A4!")
                st.rerun()


def _format_mixed_html(text: str, prefix_bold: str = "") -> str:
    """Chuyển văn bản hỗn hợp (tiếng Việt + mã Python) thành HTML đen trắng chuẩn in ấn A4."""
    cleaned = str(text or "").replace("```python", "").replace("```", "").replace("\r\n", "\n").strip()
    if "\\n" in cleaned and "\n" not in cleaned:
        cleaned = cleaned.replace("\\n", "\n")

    lines = cleaned.split("\n")
    parts: list[str] = []
    code_buf: list[str] = []
    prefix_used = False
    prev_was_code = False

    def _flush_code():
        if code_buf:
            code_escaped = "\n".join(html.escape(c.replace("\t", "    ").rstrip()) for c in code_buf)
            parts.append(f'<pre class="py-code">{code_escaped}</pre>')
            code_buf.clear()

    for raw_line in lines:
        if not raw_line.strip():
            continue
        if _is_docx_python_line(raw_line, prev_was_code=prev_was_code):
            if prefix_bold and not prefix_used:
                parts.append(f'<p class="q-line"><b>{html.escape(prefix_bold.strip())}</b></p>')
                prefix_used = True
            code_buf.append(raw_line)
            prev_was_code = True
        else:
            _flush_code()
            prefix_html = ""
            if prefix_bold and not prefix_used:
                prefix_html = f"<b>{html.escape(prefix_bold)}</b>"
                prefix_used = True
            parts.append(f'<p class="q-line">{prefix_html}{html.escape(raw_line.strip())}</p>')
            prev_was_code = False

    _flush_code()
    if prefix_bold and not prefix_used:
        parts.append(f'<p class="q-line"><b>{html.escape(prefix_bold.strip())}</b></p>')
    return "\n".join(parts)


def _build_exam_html_preview(
    exam_pkg: dict,
    ten_truong: str = "TRƯỜNG THPT (CHƯƠNG TRÌNH GDPT 2018)",
    ten_ky_thi: str = "ĐỀ KIỂM TRA CHỦ ĐỀ F",
    thoi_gian: str = "45 phút (không kể thời gian phát đề)",
) -> str:
    """Dựng bản xem trước Đề thi & Đáp án khổ A4 đen trắng chuẩn in ấn 2025–2026."""
    items = exam_pkg.get("items", [])
    tong_diem = exam_pkg.get("tong_diem", 0.0)
    bang_diem = exam_pkg.get("bang_diem_chi_tiet", {})

    mcq_items = [x for x in items if x.get("loai_cau_hoi") == "MCQ"]
    tf_items = [x for x in items if x.get("loai_cau_hoi") == "TRUE_FALSE"]
    sa_items = [x for x in items if x.get("loai_cau_hoi") == "SHORT_ANSWER"]
    ec_items = [x for x in items if x.get("loai_cau_hoi") == "ESSAY_CODE"]

    body: list[str] = []

    # Quốc hiệu / tiêu đề 2 cột chuẩn đề thi THPT
    body.append(
        f"""
        <table class="hdr-tbl">
          <tr>
            <td style="width:45%; text-align:center; vertical-align:top;">
              <div>SỞ GIÁO DỤC VÀ ĐÀO TẠO</div>
              <div><b>{html.escape(ten_truong)}</b></div>
              <div class="sub-rule">——————</div>
            </td>
            <td style="width:55%; text-align:center; vertical-align:top;">
              <div><b>{html.escape(ten_ky_thi)}</b></div>
              <div><i>Năm học 2025 – 2026 | Thời gian: {html.escape(thoi_gian)}</i></div>
              <div class="sub-rule">——————————</div>
            </td>
          </tr>
        </table>
        <p class="student-info">
          Họ và tên học sinh: ........................................................................ &nbsp;&nbsp; Lớp: 10........
        </p>
        """
    )

    if mcq_items:
        body.append(
            f'<div class="sec-title">PHẦN I. Câu trắc nghiệm nhiều phương án lựa chọn '
            f'({len(mcq_items)} câu – 0.25 điểm/câu). Thí sinh chỉ chọn một phương án đúng nhất.</div>'
        )
        for idx, item in enumerate(mcq_items, 1):
            q = item.get("question_json", {})
            body.append(_format_mixed_html(q.get("cau_hoi", ""), prefix_bold=f"Câu {idx}. "))
            for opt in ("A", "B", "C", "D"):
                opt_clean = str(q.get(opt, "")).replace("```python", "").replace("```", "").replace("\r\n", "\n").strip()
                if "\\n" in opt_clean and "\n" not in opt_clean:
                    opt_clean = opt_clean.replace("\\n", "\n")
                if "\n" in opt_clean:
                    body.append(f'<div class="opt-line"><b>{opt}.</b></div>')
                    body.append(f'<pre class="py-code opt-code">{html.escape(opt_clean)}</pre>')
                else:
                    body.append(f'<div class="opt-line"><b>{opt}.</b> {html.escape(opt_clean)}</div>')

    if tf_items:
        body.append(
            f'<div class="sec-title">PHẦN II. Câu trắc nghiệm Đúng/Sai ({len(tf_items)} câu – tối đa 1.0 điểm/câu; '
            f'chấm bậc thang: đúng 1 ý 0.1đ, 2 ý 0.25đ, 3 ý 0.5đ, 4 ý 1.0đ).</div>'
        )
        for idx, item in enumerate(tf_items, 1):
            q = item.get("question_json", {})
            body.append(_format_mixed_html(q.get("cau_hoi_chung", ""), prefix_bold=f"Câu {idx}. "))
            for letter in ("a", "b", "c", "d"):
                obj = q.get(letter) or {}
                md = obj.get("menh_de", "") if isinstance(obj, dict) else str(obj)
                body.append(f'<div class="opt-line"><b>{letter})</b> {html.escape(str(md))}</div>')

    if sa_items:
        body.append(
            f'<div class="sec-title">PHẦN III. Câu trắc nghiệm Trả lời ngắn ({len(sa_items)} câu – 0.5 điểm/câu).</div>'
        )
        for idx, item in enumerate(sa_items, 1):
            q = item.get("question_json", {})
            body.append(_format_mixed_html(q.get("cau_hoi", ""), prefix_bold=f"Câu {idx}. "))
            body.append('<p class="q-line"><i>Đáp án: ........................................</i></p>')

    if ec_items:
        body.append(
            f'<div class="sec-title">PHẦN IV. Tự luận lập trình Python ({len(ec_items)} câu – 1.0 điểm/câu).</div>'
        )
        for idx, item in enumerate(ec_items, 1):
            q = item.get("question_json", {})
            combined = "\n".join(
                p for p in (str(q.get("tinh_huong", "")).strip(), str(q.get("yeu_cau_hoc_sinh", "")).strip()) if p
            )
            body.append(_format_mixed_html(combined, prefix_bold=f"Câu {idx}. "))

    body.append('<div class="end-mark">--- HẾT ---</div>')

    # Ngắt trang ảo -> Phần Đáp án & Biểu điểm
    body.append('<hr class="page-sep" />')
    body.append('<div class="ans-title">HƯỚNG DẪN CHẤM, BIỂU ĐIỂM CHI TIẾT &amp; BẰNG CHỨNG SGK</div>')
    body.append(
        f'<div class="ans-sub">Phạm vi: Chủ đề F Tin học 10 (SGK Kết nối tri thức) | '
        f'Tổng số câu: {len(items)} | Tổng điểm chuẩn 2025–2026: {tong_diem} điểm</div>'
    )

    if bang_diem:
        rows_html = []
        for loai_k, info in bang_diem.items():
            rows_html.append(
                f"<tr><td>{html.escape(str(loai_k))}</td>"
                f"<td style='text-align:center'>{info['so_cau']}</td>"
                f"<td style='text-align:center'>{info['diem_moi_cau']}đ</td>"
                f"<td style='text-align:center'>{info['tong_diem_phan']}đ</td></tr>"
            )
        body.append(
            '<table class="score-tbl">'
            '<tr><th>Dạng câu hỏi</th><th>Số câu</th><th>Điểm / câu</th><th>Tổng điểm phần</th></tr>'
            + "".join(rows_html)
            + "</table>"
        )

    if mcq_items:
        body.append('<div class="sec-title">I. ĐÁP ÁN PHẦN I – TRẮC NGHIỆM NHIỀU LỰA CHỌN (0.25đ/câu)</div>')
        for idx, item in enumerate(mcq_items, 1):
            q = item.get("question_json", {})
            ans = str(q.get("dap_an", "A")).strip().upper()
            body.append(
                f'<p class="q-line"><b>Câu {idx} ({html.escape(str(item.get("bai_hoc", "")))} – '
                f'{html.escape(str(item.get("muc_do", "")))}): Đáp án {html.escape(ans)} (0.25đ).</b> '
                f'Giải thích: {html.escape(str(q.get("giai_thich", "")))}</p>'
            )

    if tf_items:
        body.append('<div class="sec-title">II. ĐÁP ÁN PHẦN II – TRẮC NGHIỆM ĐÚNG/SAI (Bậc thang 0.1–0.25–0.5–1.0đ)</div>')
        for idx, item in enumerate(tf_items, 1):
            q = item.get("question_json", {})
            body.append(
                f'<p class="q-line"><b>Câu {idx} ({html.escape(str(item.get("bai_hoc", "")))} – '
                f'{html.escape(str(item.get("muc_do", "")))}):</b></p>'
            )
            for letter in ("a", "b", "c", "d"):
                obj = q.get(letter) or {}
                da = obj.get("dap_an", "") if isinstance(obj, dict) else ""
                gt = obj.get("giai_thich", "") if isinstance(obj, dict) else ""
                body.append(f'<div class="opt-line"><b>{letter}) {html.escape(str(da))}:</b> {html.escape(str(gt))}</div>')

    if sa_items:
        body.append('<div class="sec-title">III. ĐÁP ÁN PHẦN III – TRẢ LỜI NGẮN (0.5đ/câu)</div>')
        for idx, item in enumerate(sa_items, 1):
            q = item.get("question_json", {})
            body.append(
                f'<p class="q-line"><b>Câu {idx} ({html.escape(str(item.get("bai_hoc", "")))} – '
                f'{html.escape(str(item.get("muc_do", "")))}): Đáp án = {html.escape(str(q.get("dap_an_ngan", "")))} (0.5đ).</b> '
                f'Giải thích: {html.escape(str(q.get("giai_thich", "")))}</p>'
            )

    if ec_items:
        body.append('<div class="sec-title">IV. ĐÁP ÁN &amp; RUBRIC PHẦN IV – TỰ LUẬN LẬP TRÌNH PYTHON (1.0đ/câu)</div>')
        for idx, item in enumerate(ec_items, 1):
            q = item.get("question_json", {})
            body.append(
                f'<p class="q-line"><b>Câu {idx} ({html.escape(str(item.get("bai_hoc", "")))} – '
                f'{html.escape(str(item.get("muc_do", "")))}) – Mã Python mẫu:</b></p>'
            )
            raw_mau = q.get("dap_an_mau", "")
            if isinstance(raw_mau, list):
                raw_mau = "\n".join(str(x) for x in raw_mau)
            code_mau = str(raw_mau).replace("```python", "").replace("```", "").strip()
            if code_mau:
                body.append(f'<pre class="py-code">{html.escape(code_mau)}</pre>')
            for tc in q.get("tieu_chi_cham_diem", []):
                body.append(f'<div class="opt-line">- {html.escape(str(tc))}</div>')

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8" />
<style>
  body {{
    margin: 0;
    padding: 14px;
    background: #f0f0f0;
    font-family: "Times New Roman", Times, serif;
    color: #000000;
    overflow-x: hidden;
  }}
  .a4-paper {{
    max-width: 794px;
    margin: 0 auto;
    padding: 36px 46px;
    background: #FFFFFF;
    color: #000000;
    border: 1px solid #888888;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
    font-size: 12pt;
    line-height: 1.45;
    box-sizing: border-box;
    overflow-x: hidden;
  }}
  .hdr-tbl {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 10px;
    font-size: 11pt;
  }}
  .sub-rule {{
    font-size: 10pt;
    letter-spacing: 1px;
  }}
  .student-info {{
    margin: 8px 0 14px 0;
    font-size: 11.5pt;
  }}
  .sec-title {{
    font-weight: bold;
    margin: 14px 0 6px 0;
    font-size: 12pt;
  }}
  .q-line {{
    margin: 4px 0;
    overflow-wrap: break-word;
  }}
  .opt-line {{
    margin: 2px 0 2px 24px;
    font-size: 11.5pt;
    overflow-wrap: break-word;
  }}
  .py-code {{
    font-family: "Consolas", "Courier New", monospace;
    font-size: 10.5pt;
    line-height: 1.35;
    margin: 4px 0 6px 0;
    padding: 2px 0 2px 18px;
    background: #FFFFFF;
    color: #000000;
    border: none;
    white-space: pre-wrap;
    overflow-wrap: break-word;
    overflow-x: hidden;
  }}
  .opt-code {{
    padding-left: 36px;
  }}
  .end-mark {{
    text-align: center;
    font-weight: bold;
    margin: 18px 0 6px 0;
  }}
  .page-sep {{
    border: none;
    border-top: 2px dashed #000000;
    margin: 22px 0 18px 0;
  }}
  .ans-title {{
    text-align: center;
    font-weight: bold;
    font-size: 13pt;
    margin-bottom: 4px;
  }}
  .ans-sub {{
    text-align: center;
    font-style: italic;
    font-size: 11pt;
    margin-bottom: 12px;
  }}
  .score-tbl {{
    width: 100%;
    border-collapse: collapse;
    margin: 8px 0 14px 0;
    font-size: 11pt;
  }}
  .score-tbl th, .score-tbl td {{
    border: 1px solid #000000;
    padding: 5px 8px;
    color: #000000;
    background: #FFFFFF;
  }}
</style>
</head>
<body>
  <div class="a4-paper">
    {"".join(body)}
  </div>
</body>
</html>"""


def _render_raw_html(markup: str) -> None:
    """Xuất HTML/CSS gọn không dòng trống, không thụt lề để CommonMark trong Streamlit không bao giờ ngắt khối HTML thành văn bản thô."""
    compact = "\n".join(line.strip() for line in markup.splitlines() if line.strip())
    st.markdown(compact, unsafe_allow_html=True)


def _inject_neo_bento_theme() -> None:
    """Nhúng Google Fonts & bộ CSS hiện đại bo tròn, tối ưu đồng thời máy tính và điện thoại (khóa nền sáng rõ chữ)."""
    _render_raw_html(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:ital,wght@0,400;0,500;0,600;0,700;1,400&family=Bricolage+Grotesque:wght@600;700;800&display=swap');
        :root {
            color-scheme: light !important;
            --nb-bg: #F4F6FA;
            --nb-card: #FFFFFF;
            --nb-ink: #0F172A;
            --nb-body: #1E293B;
            --nb-muted: #475569;
            --nb-accent: #4F46E5;
            --nb-accent-hover: #4338CA;
            --nb-accent-soft: #EEF2FF;
            --nb-border: #E2E8F0;
            --nb-border-strong: #CBD5E1;
        }
        html, body, [data-testid="stAppViewContainer"], .stApp {
            background-color: var(--nb-bg) !important;
            background-image: none !important;
            color: var(--nb-ink) !important;
            font-family: 'Be Vietnam Pro', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
            font-size: 16px !important;
            -webkit-font-smoothing: antialiased;
        }
        [data-testid="stHeader"] {
            background: rgba(244, 246, 250, 0.9) !important;
            backdrop-filter: blur(10px);
        }
        [data-testid="stHeader"] button,
        [data-testid="stHeader"] svg {
            color: var(--nb-ink) !important;
            fill: var(--nb-ink) !important;
        }
        .block-container {
            padding-top: 1.4rem !important;
            padding-bottom: 3rem !important;
            max-width: 1220px !important;
        }
        h1, h2, h3, h4, .nb-font-display {
            font-family: 'Bricolage Grotesque', 'Be Vietnam Pro', sans-serif !important;
            color: var(--nb-ink) !important;
            letter-spacing: -0.02em;
        }
        h2, h3 {
            font-size: 1.32rem !important;
            font-weight: 700 !important;
            margin-top: 0.2rem !important;
            margin-bottom: 0.75rem !important;
        }
        /* Khóa màu chữ đậm rõ nét cho toàn bộ widget Streamlit kể cả khi điện thoại bật Dark Mode */
        [data-testid="stMarkdownContainer"],
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li,
        [data-testid="stMarkdownContainer"] strong,
        [data-testid="stWidgetLabel"],
        [data-testid="stWidgetLabel"] p,
        [data-testid="stWidgetLabel"] label,
        .stRadio label,
        .stRadio label p,
        .stRadio div[role="radiogroup"] label,
        .stRadio div[role="radiogroup"] p,
        .stCheckbox label,
        .stCheckbox label p {
            color: var(--nb-ink) !important;
            opacity: 1 !important;
            font-family: 'Be Vietnam Pro', sans-serif !important;
        }
        [data-testid="stWidgetLabel"] p {
            font-size: 0.98rem !important;
            font-weight: 600 !important;
            margin-bottom: 0.25rem !important;
        }
        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] p {
            color: var(--nb-muted) !important;
            font-size: 0.92rem !important;
            opacity: 1 !important;
        }
        code, pre, .stCodeBlock code {
            font-family: 'Consolas', 'Courier New', monospace !important;
        }
        /* Khối tiêu đề Hero gọn gàng, bo tròn sâu */
        .nb-hero {
            background: var(--nb-card);
            border: 1px solid var(--nb-border);
            border-radius: 24px;
            padding: 26px 30px;
            box-shadow: 0 8px 28px -14px rgba(15, 23, 42, 0.1);
            margin-bottom: 16px;
        }
        .nb-eyebrow {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 14px;
            border-radius: 999px;
            background: var(--nb-accent-soft);
            color: var(--nb-accent);
            font-size: 0.8rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-bottom: 12px;
        }
        .nb-eyebrow-dot {
            width: 7px;
            height: 7px;
            border-radius: 999px;
            background: var(--nb-accent);
        }
        .nb-hero-title {
            font-family: 'Bricolage Grotesque', 'Be Vietnam Pro', sans-serif !important;
            font-size: clamp(1.48rem, 2.5vw, 2.15rem);
            font-weight: 800;
            line-height: 1.24;
            color: var(--nb-ink);
            margin: 0 0 10px 0;
        }
        .nb-hero-accent {
            color: var(--nb-accent);
        }
        .nb-hero-sub {
            color: var(--nb-muted);
            font-size: 0.98rem;
            line-height: 1.62;
            margin: 0;
            max-width: 900px;
        }
        /* Lưới 4 thẻ thông số tối giản, chữ to rõ, không rối mắt */
        .nb-bento-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 14px;
            margin-bottom: 18px;
        }
        .nb-bento-card {
            background: var(--nb-card);
            border: 1px solid var(--nb-border);
            border-radius: 22px;
            padding: 18px 20px;
            box-shadow: 0 6px 20px -12px rgba(15, 23, 42, 0.09);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            gap: 6px;
        }
        .nb-bento-card.nb-gradient {
            background: linear-gradient(135deg, #4F46E5 0%, #6366F1 100%);
            border-color: transparent;
            color: #FFFFFF !important;
        }
        .nb-bento-pill {
            width: 28px;
            height: 4px;
            border-radius: 999px;
            margin-bottom: 6px;
        }
        .nb-pill-indigo { background: #4F46E5; }
        .nb-pill-emerald { background: #10B981; }
        .nb-pill-amber { background: #F59E0B; }
        .nb-pill-white { background: rgba(255, 255, 255, 0.55); }
        .nb-bento-label {
            font-size: 0.88rem;
            font-weight: 600;
            color: var(--nb-muted);
            line-height: 1.35;
        }
        .nb-bento-card.nb-gradient .nb-bento-label {
            color: rgba(255, 255, 255, 0.9);
        }
        .nb-bento-val {
            font-family: 'Bricolage Grotesque', 'Be Vietnam Pro', sans-serif !important;
            font-size: clamp(1.3rem, 2vw, 1.65rem);
            font-weight: 800;
            color: var(--nb-ink);
            line-height: 1.2;
            white-space: nowrap;
        }
        .nb-bento-card.nb-gradient .nb-bento-val {
            color: #FFFFFF;
        }
        .nb-bento-meta {
            font-size: 0.84rem;
            color: var(--nb-muted);
            line-height: 1.4;
        }
        .nb-bento-card.nb-gradient .nb-bento-meta {
            color: rgba(255, 255, 255, 0.86);
        }
        /* Khối nội dung bo tròn chuẩn Card */
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--nb-card) !important;
            border: 1px solid var(--nb-border) !important;
            border-radius: 22px !important;
            padding: 18px 22px !important;
            box-shadow: 0 6px 20px -12px rgba(15, 23, 42, 0.08) !important;
        }
        /* Thanh Tab dạng Segmented Control bo tròn 50/50 không bao giờ tràn trên điện thoại */
        .stTabs [data-baseweb="tab-list"] {
            display: flex !important;
            width: 100% !important;
            gap: 6px !important;
            background: var(--nb-card) !important;
            padding: 6px !important;
            border-radius: 18px !important;
            border: 1px solid var(--nb-border) !important;
            box-shadow: 0 4px 16px -8px rgba(15, 23, 42, 0.08) !important;
            overflow: hidden !important;
        }
        .stTabs [data-baseweb="tab"] {
            flex: 1 1 0 !important;
            justify-content: center !important;
            border-radius: 13px !important;
            padding: 11px 14px !important;
            min-height: 46px !important;
            font-size: 0.98rem !important;
            font-weight: 700 !important;
            color: var(--nb-muted) !important;
            background: transparent !important;
            transition: background 0.16s ease, color 0.16s ease !important;
        }
        .stTabs [data-baseweb="tab"] p {
            color: inherit !important;
            font-size: 0.98rem !important;
            font-weight: 700 !important;
            margin: 0 !important;
        }
        .stTabs [aria-selected="true"] {
            background: var(--nb-accent) !important;
            color: #FFFFFF !important;
            box-shadow: 0 4px 12px -4px rgba(79, 70, 229, 0.45) !important;
        }
        .stTabs [aria-selected="true"] p {
            color: #FFFFFF !important;
        }
        .stTabs [data-baseweb="tab-highlight"],
        .stTabs [data-baseweb="tab-border"] {
            display: none !important;
        }
        /* Khối chọn chế độ (Radio) nằm trong thẻ trắng bo tròn, chữ đậm rõ */
        [data-testid="stRadio"] {
            background: var(--nb-card) !important;
            border: 1px solid var(--nb-border) !important;
            border-radius: 20px !important;
            padding: 16px 20px !important;
            box-shadow: 0 6px 18px -12px rgba(15, 23, 42, 0.08) !important;
            margin-top: 4px !important;
            margin-bottom: 8px !important;
        }
        [data-testid="stRadio"] div[role="radiogroup"] {
            gap: 10px 18px !important;
            margin-top: 6px !important;
        }
        [data-testid="stRadio"] label[data-baseweb="radio"] {
            background: #F8FAFC !important;
            border: 1px solid var(--nb-border) !important;
            border-radius: 14px !important;
            padding: 10px 14px !important;
            margin: 0 !important;
            min-height: 44px !important;
            display: flex !important;
            align-items: center !important;
            transition: border-color 0.15s ease, background 0.15s ease !important;
        }
        [data-testid="stRadio"] label[data-baseweb="radio"]:hover {
            border-color: var(--nb-accent) !important;
            background: var(--nb-accent-soft) !important;
        }
        [data-testid="stRadio"] label[data-baseweb="radio"] p {
            font-size: 0.97rem !important;
            font-weight: 600 !important;
            color: var(--nb-ink) !important;
        }
        /* Nút bấm bo tròn hiện đại, dễ chạm trên điện thoại */
        .stButton > button[kind="primary"],
        .stButton > button[data-testid="stBaseButton-primary"] {
            background: var(--nb-accent) !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 14px !important;
            box-shadow: 0 6px 16px -6px rgba(79, 70, 229, 0.55) !important;
            font-family: 'Be Vietnam Pro', sans-serif !important;
            font-size: 0.98rem !important;
            font-weight: 700 !important;
            min-height: 48px !important;
            padding: 0.65rem 1.3rem !important;
            transition: background 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease !important;
        }
        .stButton > button[kind="primary"] p,
        .stButton > button[data-testid="stBaseButton-primary"] p {
            color: #FFFFFF !important;
            font-weight: 700 !important;
        }
        .stButton > button[kind="primary"]:hover,
        .stButton > button[data-testid="stBaseButton-primary"]:hover {
            background: var(--nb-accent-hover) !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 10px 20px -8px rgba(79, 70, 229, 0.6) !important;
        }
        .stDownloadButton > button,
        .stButton > button[kind="secondary"],
        .stButton > button[data-testid="stBaseButton-secondary"] {
            background: var(--nb-card) !important;
            color: var(--nb-ink) !important;
            border: 1.5px solid var(--nb-border-strong) !important;
            border-radius: 14px !important;
            box-shadow: 0 2px 8px -4px rgba(15, 23, 42, 0.08) !important;
            font-family: 'Be Vietnam Pro', sans-serif !important;
            font-size: 0.95rem !important;
            font-weight: 600 !important;
            min-height: 46px !important;
            padding: 0.6rem 1.15rem !important;
            transition: border-color 0.15s ease, background 0.15s ease !important;
        }
        .stDownloadButton > button p,
        .stButton > button[kind="secondary"] p,
        .stButton > button[data-testid="stBaseButton-secondary"] p {
            color: var(--nb-ink) !important;
            font-weight: 600 !important;
        }
        .stDownloadButton > button:hover,
        .stButton > button[kind="secondary"]:hover,
        .stButton > button[data-testid="stBaseButton-secondary"]:hover {
            border-color: var(--nb-accent) !important;
            background: var(--nb-accent-soft) !important;
        }
        /* Metric, Input, Select, Expander, Alert bo tròn thống nhất */
        [data-testid="stMetric"] {
            background: var(--nb-card) !important;
            border: 1px solid var(--nb-border) !important;
            border-radius: 18px !important;
            padding: 14px 16px !important;
            box-shadow: 0 4px 14px -8px rgba(15, 23, 42, 0.08) !important;
        }
        [data-testid="stMetricLabel"],
        [data-testid="stMetricLabel"] p {
            color: var(--nb-muted) !important;
            font-size: 0.88rem !important;
            font-weight: 600 !important;
        }
        [data-testid="stMetricValue"] {
            font-family: 'Bricolage Grotesque', 'Be Vietnam Pro', sans-serif !important;
            color: var(--nb-ink) !important;
            font-weight: 800 !important;
        }
        [data-baseweb="select"] > div,
        [data-baseweb="input"] > div,
        [data-baseweb="textarea"] > div,
        [data-testid="stNumberInput"] > div {
            background-color: #FFFFFF !important;
            border-radius: 14px !important;
            border: 1.5px solid var(--nb-border-strong) !important;
            color: var(--nb-ink) !important;
            font-size: 1rem !important;
        }
        [data-baseweb="select"] span,
        [data-baseweb="select"] input,
        [data-baseweb="input"] input,
        [data-baseweb="textarea"] textarea {
            color: var(--nb-ink) !important;
            -webkit-text-fill-color: var(--nb-ink) !important;
            font-size: 1rem !important;
        }
        [data-baseweb="popover"],
        [data-baseweb="menu"],
        ul[role="listbox"] {
            background-color: #FFFFFF !important;
            border: 1px solid var(--nb-border) !important;
            border-radius: 16px !important;
            color: var(--nb-ink) !important;
            box-shadow: 0 12px 32px -12px rgba(15, 23, 42, 0.18) !important;
        }
        ul[role="listbox"] li,
        [role="option"] {
            background-color: #FFFFFF !important;
            color: var(--nb-ink) !important;
            font-size: 0.96rem !important;
        }
        ul[role="listbox"] li:hover,
        [role="option"][aria-selected="true"] {
            background-color: var(--nb-accent-soft) !important;
            color: var(--nb-accent) !important;
            font-weight: 600 !important;
        }
        [data-testid="stRadio"] [data-baseweb="radio"] > div:first-child {
            background-color: #FFFFFF !important;
            border-color: var(--nb-accent) !important;
        }
        [data-testid="stExpander"] {
            background: var(--nb-card) !important;
            border: 1px solid var(--nb-border) !important;
            border-radius: 18px !important;
            overflow: hidden !important;
        }
        [data-testid="stExpander"] summary,
        [data-testid="stExpander"] summary p {
            color: var(--nb-ink) !important;
            font-weight: 600 !important;
            font-size: 0.96rem !important;
        }
        [data-testid="stAlert"] {
            border-radius: 18px !important;
            border: 1px solid var(--nb-border) !important;
            color: var(--nb-ink) !important;
        }
        [data-testid="stAlert"] p {
            color: var(--nb-ink) !important;
            font-size: 0.96rem !important;
            line-height: 1.55 !important;
        }
        hr {
            border-color: var(--nb-border) !important;
            margin: 1rem 0 !important;
        }
        /* Responsive tối ưu riêng cho Tablet & Điện thoại */
        @media (max-width: 900px) {
            .nb-bento-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 12px;
            }
        }
        @media (max-width: 640px) {
            .block-container {
                padding-top: 0.85rem !important;
                padding-left: 0.9rem !important;
                padding-right: 0.9rem !important;
                padding-bottom: 2.5rem !important;
            }
            .nb-hero {
                padding: 18px 18px;
                border-radius: 20px;
                margin-bottom: 12px;
            }
            .nb-eyebrow {
                font-size: 0.74rem;
                padding: 5px 12px;
            }
            .nb-hero-title {
                font-size: 1.42rem;
            }
            .nb-hero-sub {
                font-size: 0.94rem;
            }
            .nb-bento-grid {
                gap: 10px;
                margin-bottom: 14px;
            }
            .nb-bento-card {
                padding: 14px 14px;
                border-radius: 18px;
            }
            .nb-bento-label {
                font-size: 0.84rem;
            }
            .nb-bento-val {
                font-size: 1.28rem;
            }
            .nb-bento-meta {
                font-size: 0.8rem;
            }
            .stTabs [data-baseweb="tab"] {
                padding: 10px 8px !important;
                font-size: 0.94rem !important;
            }
            .stTabs [data-baseweb="tab"] p {
                font-size: 0.94rem !important;
            }
            [data-testid="stRadio"] {
                padding: 14px 14px !important;
                border-radius: 18px !important;
            }
            [data-testid="stRadio"] div[role="radiogroup"] {
                flex-direction: column !important;
                align-items: stretch !important;
                gap: 8px !important;
            }
            [data-testid="stRadio"] label[data-baseweb="radio"] {
                width: 100% !important;
            }
            [data-testid="stVerticalBlockBorderWrapper"] {
                padding: 14px 14px !important;
                border-radius: 18px !important;
            }
        }
        </style>
        """
    )


def _render_hero_and_bento_stats() -> None:
    """Hiển thị Hero Header tối giản và cụm 4 thẻ thống kê rõ chữ, gọn gàng trên cả PC và điện thoại."""
    bank_cnt = len(load_question_bank())
    log_cnt = len(read_logs())

    _render_raw_html(
        f"""
        <div class="nb-hero">
          <div class="nb-eyebrow">
            <span class="nb-eyebrow-dot"></span>
            Chủ đề F &bull; Tin học 10 &bull; GDPT 2018
          </div>
          <h1 class="nb-hero-title">
            Hệ Thống Agentic RAG <span class="nb-hero-accent">Sinh &amp; Kiểm Định Đề Thi</span> Python 10
          </h1>
          <p class="nb-hero-sub">
            Bám sát SGK Kết nối tri thức (Bài 16 – Bài 32), chuẩn cấu trúc đề <b>2025–2026</b>,
            kiểm định 2 tầng kết hợp thực thi Sandbox và xuất bản in Word <b>100% Trắng Đen</b>.
          </p>
        </div>
        <div class="nb-bento-grid">
          <div class="nb-bento-card nb-gradient">
            <div class="nb-bento-pill nb-pill-white"></div>
            <div class="nb-bento-label">Ngân hàng câu hỏi</div>
            <div class="nb-bento-val">{bank_cnt} câu</div>
            <div class="nb-bento-meta">Đã phê duyệt &amp; sẵn sàng</div>
          </div>
          <div class="nb-bento-card">
            <div class="nb-bento-pill nb-pill-indigo"></div>
            <div class="nb-bento-label">Phạm vi tri thức</div>
            <div class="nb-bento-val">17 bài học</div>
            <div class="nb-bento-meta">Bài 16 – 32 &bull; SGK KNTT</div>
          </div>
          <div class="nb-bento-card">
            <div class="nb-bento-pill nb-pill-emerald"></div>
            <div class="nb-bento-label">Lượt sinh kiểm định</div>
            <div class="nb-bento-val">{log_cnt} lượt</div>
            <div class="nb-bento-meta">Lưu tự động trong nhật ký</div>
          </div>
          <div class="nb-bento-card">
            <div class="nb-bento-pill nb-pill-amber"></div>
            <div class="nb-bento-label">Mô hình cục bộ</div>
            <div class="nb-bento-val">Llama 3.2</div>
            <div class="nb-bento-meta">Offline &bull; An toàn 4GB VRAM</div>
          </div>
        </div>
        """
    )


# ==============================================================================
# CẤU HÌNH TRANG & GIAO DIỆN 2 PHÂN HỆ (GIÁO VIÊN / HỌC SINH)
# ==============================================================================

st.set_page_config(page_title="Khảo Thí Tin Học 10 - Chủ đề F", layout="wide")
_inject_neo_bento_theme()

if "single_result" not in st.session_state:
    st.session_state.single_result = None
if "exam_result" not in st.session_state:
    st.session_state.exam_result = None

_render_hero_and_bento_stats()

# --- THANH BÊN (SIDEBAR): TIỆN ÍCH NẠP ĐỀ MẪU VÀO NGÂN HÀNG ---
with st.sidebar:
    st.markdown("### 🗄️ Ngân Hàng Đề Thi")
    st.caption("Quét và nạp thêm đề kiểm tra từ thư mục `data/sample_exams/`")
    if st.button("📥 Nạp thêm đề từ thư mục data/sample_exams", use_container_width=True, type="secondary"):
        with st.spinner("Đang quét và bóc tách câu hỏi từ data/sample_exams/ ..."):
            res_import = import_sample_exams()
            if res_import["questions_imported"] > 0:
                st.success(f"✅ Đã nạp **{res_import['questions_imported']}** câu hỏi mới vào Ngân hàng! (Trùng lặp bỏ qua: {res_import['duplicates_skipped']}). Tổng hiện có: {res_import['total_in_bank']} câu.")
                time.sleep(1.2)
                st.rerun()
            elif res_import["files_processed"] == 0:
                st.info("ℹ️ Thư mục `data/sample_exams/` hiện chưa có tệp đề nào. Vui lòng thả tệp `.docx`, `.json`, `.txt` vào thư mục để nạp.")
            else:
                st.warning(f"⚠️ Đã quét {res_import['files_processed']} tệp nhưng không phát hiện câu hỏi mới (bỏ qua {res_import['duplicates_skipped']} câu đã có trong ngân hàng).")

    cur_bank_count = len(load_question_bank())
    st.info(f"📊 Hiện có **{cur_bank_count}** câu hỏi trong Ngân hàng đề.")

tab_teacher, tab_student = st.tabs([
    "Giáo viên",
    "Học sinh",
])


# ==============================================================================
# TAB 1: GIÁO VIÊN (SINH CÂU HỎI ĐƠN LẺ / SINH ĐỀ THEO MA TRẬN / PHÊ DUYỆT)
# ==============================================================================
with tab_teacher:
    mode = st.radio(
        "Chọn chế độ làm việc",
        [
            "1. Sinh câu hỏi đơn lẻ",
            "2. Sinh đề theo Ma trận",
            "3. Quản lý Ngân hàng đề",
        ],
        horizontal=True,
    )

    if mode.startswith("1."):
        col_cfg, col_out = st.columns([1, 2.2], gap="medium")
        with col_cfg:
            with st.container(border=True):
                st.subheader("Cấu hình câu hỏi")
                bai_hoc_sel = st.selectbox("Bài học (Chủ đề F, Bài 16–32)", LESSONS_CHUDE_F, index=3)
                muc_do_label = st.selectbox("Mức độ nhận thức", list(MUC_DO_MAP.keys()), index=1)
                loai_label = st.selectbox("Dạng câu hỏi", list(LOAI_MAP.keys()), index=0)
                chi_tiet = st.text_input("Trọng tâm bổ sung (tùy chọn)", placeholder="VD: câu lệnh if-else kiểm tra số chẵn lẻ")

                if st.button("Sinh câu hỏi", type="primary", use_container_width=True):
                    with _acquire_vram_slot():
                        with st.spinner("Đang chạy Neuro-Symbolic Agentic RAG 2 tầng kiểm định (an toàn 4GB VRAM)..."):
                            res = generate_question(
                                bai_hoc=bai_hoc_sel,
                                loai_cau_hoi=LOAI_MAP[loai_label],
                                chu_de_chi_tiet=chi_tiet,
                                muc_do=MUC_DO_MAP[muc_do_label],
                                enable_logging=True,
                                use_neuro_symbolic=True,
                            )
                            st.session_state.single_result = res

                logs = read_logs()
                if logs:
                    st.caption(f"Đã ghi nhận **{len(logs)}** lượt sinh câu hỏi trong nhật ký thực nghiệm.")

        with col_out:
            with st.container(border=True):
                st.subheader("Kết quả kiểm định & Phê duyệt")
                res = st.session_state.single_result
                if res and res.get("question_json"):
                    export_txt = _render_question_card_teacher(res)
                    single_pkg = {
                        "items": [res],
                        "tong_diem": {"MCQ": 0.25, "TRUE_FALSE": 1.0, "SHORT_ANSWER": 0.5, "ESSAY_CODE": 1.0}.get(res.get("loai_cau_hoi", "MCQ"), 0.25),
                        "bang_diem_chi_tiet": {
                            res.get("loai_cau_hoi", "MCQ"): {
                                "so_cau": 1,
                                "diem_moi_cau": {"MCQ": 0.25, "TRUE_FALSE": 1.0, "SHORT_ANSWER": 0.5, "ESSAY_CODE": 1.0}.get(res.get("loai_cau_hoi", "MCQ"), 0.25),
                                "tong_diem_phan": {"MCQ": 0.25, "TRUE_FALSE": 1.0, "SHORT_ANSWER": 0.5, "ESSAY_CODE": 1.0}.get(res.get("loai_cau_hoi", "MCQ"), 0.25),
                            }
                        },
                    }
                    single_docx = export_exam_to_docx(single_pkg)
                    c_btn1, c_btn2, c_btn3 = st.columns(3)
                    with c_btn1:
                        if st.button("Phê duyệt & Lưu", type="primary", use_container_width=True, key="approve_single"):
                            val = res.get("validation_result", {}) or {}
                            added = save_to_question_bank([{
                                "bai_hoc": res.get("bai_hoc"),
                                "muc_do": res.get("muc_do"),
                                "loai_cau_hoi": res.get("loai_cau_hoi"),
                                "question_json": res.get("question_json"),
                                "fuzzy_score": val.get("diem_chat_luong", 0.0),
                                "xep_loai": val.get("xep_loai", ""),
                                "sandbox_verified": val.get("sandbox_verified", False),
                                "log_timestamp": res.get("log_timestamp", ""),
                            }])
                            st.success(f"Đã phê duyệt và lưu {added} câu vào ngân hàng đề.")
                    with c_btn2:
                        st.download_button(
                            "Tải Word (.docx)",
                            data=single_docx,
                            file_name=f"DeThi_{res.get('bai_hoc', 'Python').replace(' ', '_')}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True,
                            key="dl_single_docx",
                        )
                    with c_btn3:
                        st.download_button(
                            "Xuất văn bản (.txt)",
                            data=export_txt,
                            file_name=f"CauHoi_{res.get('bai_hoc', 'Python').replace(' ', '_')}.txt",
                            mime="text/plain",
                            use_container_width=True,
                        )
                else:
                    st.info("Chọn Bài học, Mức độ và Dạng câu hỏi rồi nhấn **Sinh câu hỏi** để bắt đầu.")

    elif mode.startswith("2."):  # Chế độ 2: Sinh đề thi theo Ma trận (hỗ trợ 2 Preset chuẩn 10.0 điểm + Tùy chỉnh)
        with st.container(border=True):
            st.subheader("Cấu hình Ma trận Đề kiểm tra")
            matrix_cfg = get_exam_matrix()
            presets = matrix_cfg.get("presets_ma_tran_10_diem", [])
            preset_map = {p["ten_hien_thi"]: p for p in presets}
            preset_options = list(preset_map.keys()) + ["Tùy chỉnh thủ công (tự chọn số câu & bài học)"]

            chosen_preset_name = st.selectbox(
                "Chọn Preset Ma trận chuẩn 2025–2026",
                preset_options,
                index=0,
            )

            active_specs: list[dict] = []
            active_time_str = "45 phút"
            active_exam_title = "ĐỀ KIỂM TRA CHỦ ĐỀ F"

            if chosen_preset_name in preset_map:
                p_obj = preset_map[chosen_preset_name]
                active_specs = p_obj.get("specs", [])
                active_time_str = p_obj.get("thoi_gian", active_time_str)
                active_exam_title = p_obj.get("tieu_de_in", "ĐỀ KIỂM TRA CHỦ ĐỀ F")
                st.info(f"**{p_obj['ten_hien_thi']}** — {p_obj.get('mo_ta', '')}")
                ct = p_obj.get("cau_truc", {})
                pm1, pm2, pm3, pm4, pm5 = st.columns(5)
                pm1.metric("MCQ (0.25đ)", f"{ct.get('MCQ', 0)} câu")
                pm2.metric("Đúng/Sai (1.0đ)", f"{ct.get('TRUE_FALSE', 0)} câu")
                pm3.metric("Trả lời ngắn (0.5đ)", f"{ct.get('SHORT_ANSWER', 0)} câu")
                pm4.metric("Tự luận Code (1.0đ)", f"{ct.get('ESSAY_CODE', 0)} câu")
                pm5.metric(
                    f"Tổng chuẩn ({p_obj.get('tong_diem', 10.0):g}đ)",
                    f"{p_obj.get('tong_so_cau', len(active_specs))} câu",
                )
            else:
                c1, c2, c3, c4 = st.columns(4)
                n_mcq = c1.number_input("Số câu MCQ (0.25đ)", min_value=0, max_value=16, value=3)
                n_tf = c2.number_input("Số câu Đúng/Sai (1.0đ)", min_value=0, max_value=6, value=1)
                n_sa = c3.number_input("Số câu Trả lời ngắn (0.5đ)", min_value=0, max_value=6, value=1)
                n_ec = c4.number_input("Số câu Tự luận Code (1.0đ)", min_value=0, max_value=4, value=1)

                selected_lessons = st.multiselect(
                    "Chọn các bài học đưa vào đề (Bài 16–32)",
                    LESSONS_CHUDE_F,
                    default=[
                        LESSONS_CHUDE_F[1],  # Bài 17
                        LESSONS_CHUDE_F[3],  # Bài 19
                        LESSONS_CHUDE_F[4],  # Bài 20
                        LESSONS_CHUDE_F[6],  # Bài 22
                    ],
                )
                default_level = st.selectbox("Mức độ nhận thức mặc định", list(MUC_DO_MAP.keys()), index=1, key="matrix_lvl")

                total_req = int(n_mcq + n_tf + n_sa + n_ec)
                est_points = round(n_mcq * 0.25 + n_tf * 1.0 + n_sa * 0.5 + n_ec * 1.0, 2)
                st.caption(f"Tổng số câu dự kiến: **{total_req} câu** | Thang điểm chuẩn 2025–2026: **{est_points} điểm**")

                if total_req > 0 and selected_lessons:
                    lesson_cycle = [l.split(":")[0].strip() for l in selected_lessons]
                    cursor = 0
                    for loai_code, cnt in [("MCQ", int(n_mcq)), ("TRUE_FALSE", int(n_tf)), ("SHORT_ANSWER", int(n_sa)), ("ESSAY_CODE", int(n_ec))]:
                        for _ in range(cnt):
                            active_specs.append({
                                "bai_hoc": lesson_cycle[cursor % len(lesson_cycle)],
                                "loai_cau_hoi": loai_code,
                                "muc_do": MUC_DO_MAP[default_level],
                            })
                            cursor += 1

            st.success("⚡ Engine: Neuro-Symbolic Agentic RAG (155 Blueprints Active)")
            if st.button("Sinh đề thi theo Ma trận & Chạy kiểm định", type="primary", use_container_width=True):
                if not active_specs:
                    st.warning("Vui lòng chọn Preset hoặc chọn ít nhất 1 bài học và tổng số câu > 0.")
                else:
                    with _acquire_vram_slot():
                        prog_bar = st.progress(0, text="Đang khởi tạo pipeline Neuro-Symbolic 2 pha (an toàn 4GB VRAM)...")

                        def _on_progress(cur, tot, bh, ltype):
                            if str(bh).startswith("Pha 1"):
                                pct = min(15, int((cur / max(tot, 1)) * 15))
                                prog_bar.progress(pct, text=f"{bh} ({cur}/{tot} – {ltype})...")
                            else:
                                pct = min(99, 15 + int(((cur - 1) / max(tot, 1)) * 84))
                                prog_bar.progress(pct, text=f"Pha 2 – Neuro-Symbolic đang sinh câu {cur}/{tot}: {bh} ({ltype})...")

                        exam_pkg = assemble_exam(
                            specs=active_specs,
                            enable_logging=True,
                            progress_callback=_on_progress,
                            use_neuro_symbolic=True,
                        )
                        exam_pkg["meta_ten_ky_thi"] = active_exam_title
                        exam_pkg["meta_thoi_gian"] = active_time_str
                        prog_bar.progress(100, text=f"Hoàn tất ghép đề ({exam_pkg['tong_so_cau']} câu | {exam_pkg['tong_diem']} điểm).")
                        st.session_state.exam_result = exam_pkg

        exam_pkg = st.session_state.exam_result
        if exam_pkg:
            st.write("")
            removed_cnt = len(exam_pkg.get("removed_items", []))
            bf_rounds = int(exam_pkg.get("backfill_rounds_used", 0))
            target_cnt = int(exam_pkg.get("target_so_cau", exam_pkg["tong_so_cau"]))
            _render_raw_html(
                f"""
                <div class="nb-bento-grid">
                  <div class="nb-bento-card nb-gradient">
                    <div class="nb-bento-pill nb-pill-white"></div>
                    <div class="nb-bento-label">Tổng điểm chuẩn 2025–2026</div>
                    <div class="nb-bento-val">{exam_pkg['tong_diem']} điểm</div>
                    <div class="nb-bento-meta">Đủ cấu trúc 4 dạng câu hỏi</div>
                  </div>
                  <div class="nb-bento-card">
                    <div class="nb-bento-pill nb-pill-indigo"></div>
                    <div class="nb-bento-label">Số câu đạt chuẩn</div>
                    <div class="nb-bento-val">{exam_pkg['tong_so_cau']}/{target_cnt} câu</div>
                    <div class="nb-bento-meta">100% câu đạt kiểm định</div>
                  </div>
                  <div class="nb-bento-card">
                    <div class="nb-bento-pill nb-pill-emerald"></div>
                    <div class="nb-bento-label">Vòng sinh bù (Backfill)</div>
                    <div class="nb-bento-val">{bf_rounds} vòng</div>
                    <div class="nb-bento-meta">Loại trùng còn lại: {removed_cnt} câu</div>
                  </div>
                  <div class="nb-bento-card">
                    <div class="nb-bento-pill nb-pill-amber"></div>
                    <div class="nb-bento-label">Thời gian ghép đề</div>
                    <div class="nb-bento-val">{exam_pkg['tong_thoi_gian_sec']}s</div>
                    <div class="nb-bento-meta">Pha 1: {exam_pkg.get('phase1_retrieve_sec', 0)}s &bull; Pha 2: {exam_pkg.get('phase2_generate_sec', 0)}s</div>
                  </div>
                </div>
                """
            )

            with st.expander("Báo cáo Kiểm định Toàn đề (Exam Critic) & Phân bổ điểm", expanded=False):
                for note in exam_pkg.get("critic_notes", []):
                    st.write(f"- {note}")
                st.json(exam_pkg.get("bang_diem_chi_tiet", {}))

            meta_title = exam_pkg.get("meta_ten_ky_thi", "ĐỀ KIỂM TRA CHỦ ĐỀ F")
            meta_time = exam_pkg.get("meta_thoi_gian", "45 phút")

            preview_tab, detail_tab = st.tabs([
                "Bản xem trước A4",
                "Chi tiết & Chỉnh sửa",
            ])
            with preview_tab:
                preview_html = _build_exam_html_preview(
                    exam_pkg,
                    ten_ky_thi=meta_title,
                    thoi_gian=meta_time,
                )
                components.html(preview_html, height=720, scrolling=True)

            full_export = [f"{meta_title} (Tổng điểm: {exam_pkg['tong_diem']}đ)\n"]
            with detail_tab:
                for idx, item in enumerate(exam_pkg.get("items", []), 1):
                    full_export.append(_render_question_card_teacher(item, idx=idx))
                    _render_quick_edit_panel(item, idx=idx, exam_pkg=exam_pkg)

            exam_docx_full = export_exam_to_docx(
                exam_pkg,
                ten_ky_thi=meta_title,
                thoi_gian=meta_time,
                include_answers=True,
            )
            exam_docx_student = export_exam_to_docx(
                exam_pkg,
                ten_ky_thi=meta_title,
                thoi_gian=meta_time,
                include_answers=False,
            )
            bank_json_bytes = json.dumps(load_question_bank(), ensure_ascii=False, indent=2).encode("utf-8")

            b1, b2, b3, b4 = st.columns(4)
            with b1:
                if st.button("Phê duyệt & Lưu cả đề", type="primary", use_container_width=True, key="approve_exam"):
                    payload = []
                    for item in exam_pkg.get("items", []):
                        val = item.get("validation_result", {}) or {}
                        payload.append({
                            "bai_hoc": item.get("bai_hoc"),
                            "muc_do": item.get("muc_do"),
                            "loai_cau_hoi": item.get("loai_cau_hoi"),
                            "question_json": item.get("question_json"),
                            "fuzzy_score": val.get("diem_chat_luong", 0.0),
                            "xep_loai": val.get("xep_loai", ""),
                            "sandbox_verified": val.get("sandbox_verified", False),
                            "log_timestamp": item.get("log_timestamp", ""),
                        })
                    cnt = save_to_question_bank(payload)
                    st.success(f"Đã phê duyệt và lưu {cnt} câu hỏi vào ngân hàng đề.")
            with b2:
                st.download_button(
                    "Tải Word (Đề + Đáp án)",
                    data=exam_docx_full,
                    file_name="De_Kiem_Tra_ChuDeF_DayDu_2025_2026.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    key="dl_exam_docx_full",
                )
            with b3:
                st.download_button(
                    "Tải Word (Chỉ đề HS)",
                    data=exam_docx_student,
                    file_name="De_Kiem_Tra_ChuDeF_HocSinh_2025_2026.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    key="dl_exam_docx_student",
                )
            with b4:
                st.download_button(
                    "Tải Ngân hàng (.json)",
                    data=bank_json_bytes,
                    file_name="question_bank_tinhoc10_chudeF.json",
                    mime="application/json",
                    use_container_width=True,
                    key="dl_bank_json_m2",
                )

    else:  # Chế độ 3: Quản lý Ngân hàng đề (Lọc, Tìm kiếm, Xóa & Xuất JSON)
        with st.container(border=True):
            st.subheader("Quản lý Ngân hàng Đề đã Phê duyệt")
            bank_all = load_question_bank()
            c_dl, c_stat = st.columns([1.2, 2.8])
            with c_dl:
                st.download_button(
                    "Tải Ngân hàng đề (.json)",
                    data=json.dumps(bank_all, ensure_ascii=False, indent=2).encode("utf-8"),
                    file_name="question_bank_tinhoc10_chudeF.json",
                    mime="application/json",
                    use_container_width=True,
                    key="dl_bank_json_m3",
                )
            with c_stat:
                st.caption(f"Tổng số câu hỏi đã lưu: **{len(bank_all)} câu** (phạm vi Chủ đề F, Bài 16–32).")

            if not bank_all:
                st.info("Ngân hàng đề đang trống. Hãy sinh câu hỏi ở chế độ 1 hoặc chế độ 2 rồi nhấn **Phê duyệt & Lưu**.")
            else:
                bf1, bf2, bf3, bf4 = st.columns([1.2, 1.1, 0.9, 1.8])
                lesson_opts = ["Tất cả"] + [f"Bài {i}" for i in range(16, 33)]
                type_opts = ["Tất cả", "MCQ", "TRUE_FALSE", "SHORT_ANSWER", "ESSAY_CODE"]
                lvl_opts = ["Tất cả", "NB", "TH", "VD"]
                b_sel_l = bf1.selectbox("Bài học (16–32)", lesson_opts, key="bank_flt_l")
                b_sel_t = bf2.selectbox("Dạng câu hỏi", type_opts, key="bank_flt_t")
                b_sel_m = bf3.selectbox("Mức độ", lvl_opts, key="bank_flt_m")
                b_kw = bf4.text_input("Tìm kiếm từ khóa", placeholder="VD: range, append, def, if...", key="bank_flt_kw").strip().lower()

                bank_filtered = []
                for entry in bank_all:
                    if b_sel_l != "Tất cả" and entry.get("bai_hoc") != b_sel_l:
                        continue
                    if b_sel_t != "Tất cả" and entry.get("loai_cau_hoi") != b_sel_t:
                        continue
                    if b_sel_m != "Tất cả" and entry.get("muc_do") != b_sel_m:
                        continue
                    if b_kw and b_kw not in json.dumps(entry.get("question_json", {}), ensure_ascii=False).lower():
                        continue
                    bank_filtered.append(entry)

                st.caption(f"Khớp bộ lọc: **{len(bank_filtered)} / {len(bank_all)}** câu hỏi.")
                for entry in bank_filtered:
                    eid = entry.get("id", "Q")
                    col_card, col_del = st.columns([5.2, 1])
                    with col_card:
                        _render_question_card_teacher(entry)
                    with col_del:
                        st.write("")
                        st.write("")
                        if st.button(f"Xóa {eid}", key=f"del_bank_{eid}", use_container_width=True):
                            if delete_from_question_bank(eid):
                                st.success(f"Đã xóa câu {eid} khỏi ngân hàng đề.")
                                st.rerun()


# ==============================================================================
# TAB 2: HỌC SINH (LUYỆN TẬP TỪ NGÂN HÀNG ĐỀ & CHẤM CODE SANDBOX)
# ==============================================================================
with tab_student:
    bank = load_question_bank()
    with st.container(border=True):
        st.subheader(f"Khu vực Học sinh luyện tập ({len(bank)} câu đã phê duyệt)")

        if not bank:
            st.info(
                "Hiện chưa có câu hỏi nào trong ngân hàng đề. "
                "Giáo viên vui lòng chuyển sang mục **Giáo viên**, sinh câu hỏi và nhấn **Phê duyệt & Lưu**."
            )
        else:
            f1, f2, f3, f4 = st.columns([1.2, 1.1, 0.9, 1.8])
            all_lessons = ["Tất cả"] + sorted({x.get("bai_hoc", "") for x in bank if x.get("bai_hoc")})
            all_types = ["Tất cả"] + sorted({x.get("loai_cau_hoi", "") for x in bank if x.get("loai_cau_hoi")})
            all_lvls = ["Tất cả", "NB", "TH", "VD"]
            sel_l = f1.selectbox("Lọc theo Bài học", all_lessons, key="stu_flt_l")
            sel_t = f2.selectbox("Lọc theo Dạng câu hỏi", all_types, key="stu_flt_t")
            sel_m = f3.selectbox("Mức độ", all_lvls, key="stu_flt_m")
            stu_kw = f4.text_input("Tìm kiếm", placeholder="Nhập từ khóa Python...", key="stu_flt_kw").strip().lower()

            filtered = [
                x for x in bank
                if (sel_l == "Tất cả" or x.get("bai_hoc") == sel_l)
                and (sel_t == "Tất cả" or x.get("loai_cau_hoi") == sel_t)
                and (sel_m == "Tất cả" or x.get("muc_do") == sel_m)
                and (not stu_kw or stu_kw in json.dumps(x.get("question_json", {}), ensure_ascii=False).lower())
            ]

            st.caption(f"Đang hiển thị **{len(filtered)}** câu hỏi luyện tập.")
            for item in filtered:
                qid = item.get("id", "Q")
                loai = item.get("loai_cau_hoi", "MCQ")
                bai = item.get("bai_hoc", "")
                muc_do = item.get("muc_do", "")
                q = item.get("question_json", {})

                with st.container(border=True):
                    st.markdown(f"#### [{qid}] {bai} — `{loai}` ({muc_do})")

                    if loai == "MCQ":
                        st.write(q.get("cau_hoi", ""))
                        choices = [f"{k}. {q.get(k, '')}" for k in ("A", "B", "C", "D")]
                        pick = st.radio("Chọn 1 phương án:", choices, key=f"stu_mcq_{qid}", index=None)
                        if st.button("Chấm câu này", key=f"grade_mcq_{qid}"):
                            if not pick:
                                st.warning("Bạn chưa chọn phương án nào.")
                            else:
                                picked_letter = pick.split(".")[0].strip().upper()
                                true_letter = str(q.get("dap_an", "A")).strip().upper()
                                if picked_letter == true_letter:
                                    st.success(f"Chính xác (+0.25 điểm) — Đáp án đúng: **{true_letter}**")
                                else:
                                    st.error(f"Chưa đúng (0.0 điểm). Đáp án đúng là: **{true_letter}**")
                                st.info(f"**Giải thích:** {q.get('giai_thich', '')}\n\n**SGK:** {q.get('trich_dan_sgk', '')}")

                    elif loai == "TRUE_FALSE":
                        st.write(q.get("cau_hoi_chung", ""))
                        stu_ans = {}
                        for letter in ("a", "b", "c", "d"):
                            obj = q.get(letter) or {}
                            md = obj.get("menh_de", "") if isinstance(obj, dict) else ""
                            stu_ans[letter] = st.radio(
                                f"**{letter})** {md}",
                                ["Đúng", "Sai"],
                                horizontal=True,
                                key=f"stu_tf_{qid}_{letter}",
                                index=None,
                            )
                        if st.button("Chấm điểm bậc thang (0.1 - 0.25 - 0.5 - 1.0đ)", key=f"grade_tf_{qid}"):
                            correct_cnt = 0
                            details = []
                            for letter in ("a", "b", "c", "d"):
                                obj = q.get(letter) or {}
                                true_v = _safe_tf_answer(obj.get("dap_an") if isinstance(obj, dict) else "")
                                gt = obj.get("giai_thich", "") if isinstance(obj, dict) else ""
                                is_ok = stu_ans[letter] == true_v
                                if is_ok:
                                    correct_cnt += 1
                                status_txt = "[Đúng]" if is_ok else "[Sai]"
                                details.append(f"- {status_txt} **{letter})** Đáp án chuẩn: **{true_v}** — {gt}")
                            score = TF_STEP_SCORES.get(correct_cnt, 0.0)
                            st.info(f"Đúng **{correct_cnt}/4 ý** — Điểm bậc thang 2025–2026: **{score} / 1.0 điểm**")
                            st.markdown("\n".join(details))

                    elif loai == "SHORT_ANSWER":
                        st.write(q.get("cau_hoi", ""))
                        user_ans = st.text_input("Nhập đáp án ngắn của bạn:", key=f"stu_sa_{qid}")
                        if st.button("Kiểm tra đáp án", key=f"grade_sa_{qid}"):
                            true_ans = str(q.get("dap_an_ngan", "")).strip()
                            if user_ans.strip().lower() == true_ans.lower():
                                st.success(f"Chính xác (+0.5 điểm) — Đáp án: `{true_ans}`")
                            else:
                                st.error(f"Chưa đúng (0.0 điểm). Đáp án đúng là: `{true_ans}`")
                            st.info(f"**Giải thích:** {q.get('giai_thich', '')}\n\n**SGK:** {q.get('trich_dan_sgk', '')}")

                    else:  # ESSAY_CODE + Sandbox trực tiếp
                        st.write(f"**Tình huống:** {q.get('tinh_huong', '')}")
                        st.markdown(f"**Yêu cầu:** {q.get('yeu_cau_hoc_sinh', '')}")
                        student_code = st.text_area(
                            "Viết mã nguồn Python của bạn tại đây:",
                            value="# Viết chương trình Python lớp 10 của bạn...\n",
                            height=180,
                            key=f"stu_code_{qid}",
                        )
                        test_stdin = st.text_input(
                            "Dữ liệu đầu vào bàn phím (nếu dùng input(), mỗi giá trị cách nhau bằng dấu xuống dòng):",
                            value="",
                            key=f"stu_in_{qid}",
                        )
                        if st.button("Chạy & Chấm Code trên Sandbox", type="primary", key=f"run_sb_{qid}"):
                            with st.spinner("Đang thực thi trên Sandbox cô lập (timeout 2.0s)..."):
                                sb_res = cham_code_python(student_code, test_input=test_stdin, timeout_sec=2.0)
                            if sb_res["trang_thai"] == "THÀNH CÔNG":
                                st.success(f"{sb_res['trang_thai']} ({sb_res['thoi_gian_chay']})")
                                st.code(sb_res["ket_qua_in_ra"] or "(Chương trình không in ra gì)", language="plaintext")
                            else:
                                st.error(f"{sb_res['trang_thai']} ({sb_res['thoi_gian_chay']})")
                                st.code(sb_res["loi_he_thong"], language="plaintext")

                        with st.expander("Xem tiêu chí chấm điểm & Đáp án mẫu"):
                            for tc in q.get("tieu_chi_cham_diem", []):
                                st.write(f"- {tc}")
                            code_mau = str(q.get("dap_an_mau", "")).replace("```python", "").replace("```", "").strip()
                            st.code(code_mau, language="python")
