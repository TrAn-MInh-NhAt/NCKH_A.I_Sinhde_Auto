import io
import os
import re
import sys
import json
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from docx import Document
from docx.shared import RGBColor

from core.retriever import get_exam_matrix
from core.exam_assembler import assemble_exam, export_exam_to_docx
from core.validator import (
    _extract_executable_python_snippets,
    _run_sandbox_verification,
    _check_execution_grounded_answer,
    _flatten_body_without_citation,
    ONESHOT_REUSE_PATTERNS,
    EMPTY_PLACEHOLDER_PATTERNS,
    TEXTBOOK_FIG_REGEX,
    TEXTBOOK_HEADER_REGEX,
    TEXTBOOK_COPY_CUES,
)


def _extract_docx_all_text_and_colors(docx_bytes: bytes) -> tuple[str, list[tuple[str, str]]]:
    doc = Document(io.BytesIO(docx_bytes))
    texts: list[str] = []
    non_black: list[tuple[str, str]] = []
    for p in doc.paragraphs:
        if p.text.strip():
            texts.append(p.text)
        for r in p.runs:
            rgb = r.font.color.rgb
            if rgb is not None and rgb != RGBColor(0, 0, 0):
                non_black.append((r.text[:40], str(rgb)))
    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    if p.text.strip():
                        texts.append(p.text)
                    for r in p.runs:
                        rgb = r.font.color.rgb
                        if rgb is not None and rgb != RGBColor(0, 0, 0):
                            non_black.append((r.text[:40], str(rgb)))
    return "\n".join(texts), non_black


def _build_preview_html_safely(exam_pkg: dict, ten_ky_thi: str, thoi_gian: str) -> str:
    """Import hàm _build_exam_html_preview từ app_ui mà không chạy UI Streamlit."""
    import ast
    import html as html_lib
    from core.exam_assembler import _is_docx_python_line

    # Thực thi riêng 2 hàm thuần HTML từ app_ui.py để kiểm toán chính xác 100% code thực tế
    ui_path = os.path.join(BASE_DIR, "app_ui.py")
    with open(ui_path, "r", encoding="utf-8") as f:
        src = f.read()
    tree = ast.parse(src)
    ns = {"html": html_lib, "_is_docx_python_line": _is_docx_python_line}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in ("_format_mixed_html", "_build_exam_html_preview"):
            mod = ast.Module(body=[node], type_ignores=[])
            exec(compile(mod, ui_path, "exec"), ns)
    return ns["_build_exam_html_preview"](exam_pkg, ten_ky_thi=ten_ky_thi, thoi_gian=thoi_gian)


def audit_exam(exam_pkg: dict, ten_ky_thi: str, thoi_gian: str, docx_full_path: str, docx_student_path: str) -> dict:
    """Chạy kiểm toán tự động đủ 8 tiêu chí trên đề thi thật vừa sinh."""
    items = exam_pkg.get("items", [])
    html_preview = _build_preview_html_safely(exam_pkg, ten_ky_thi=ten_ky_thi, thoi_gian=thoi_gian)
    docx_full_bytes = export_exam_to_docx(
        exam_pkg,
        output_path=docx_full_path,
        ten_ky_thi=ten_ky_thi,
        thoi_gian=thoi_gian,
        include_answers=True,
    )
    docx_student_bytes = export_exam_to_docx(
        exam_pkg,
        output_path=docx_student_path,
        ten_ky_thi=ten_ky_thi,
        thoi_gian=thoi_gian,
        include_answers=False,
    )

    docx_full_text, non_black_full = _extract_docx_all_text_and_colors(docx_full_bytes)
    docx_stu_text, non_black_stu = _extract_docx_all_text_and_colors(docx_student_bytes)

    criteria: dict[str, dict] = {}

    # Tiêu chí 1: Tiêu đề đúng ĐỀ KIỂM TRA CHỦ ĐỀ F
    c1_errs = []
    if ten_ky_thi != "ĐỀ KIỂM TRA CHỦ ĐỀ F":
        c1_errs.append(f"ten_ky_thi='{ten_ky_thi}' != 'ĐỀ KIỂM TRA CHỦ ĐỀ F'")
    if "ĐỀ KIỂM TRA CHỦ ĐỀ F" not in html_preview or "ĐỀ KIỂM TRA CHỦ ĐỀ F" not in docx_full_text:
        c1_errs.append("Thiếu tiêu đề 'ĐỀ KIỂM TRA CHỦ ĐỀ F' trong HTML hoặc DOCX.")
    for forbidden_title in ("GỌN CHỦ ĐỀ F", "10.0 ĐIỂM – 18 CÂU", "10.0 ĐIỂM - 18 CÂU"):
        if forbidden_title in html_preview.upper() or forbidden_title in docx_full_text.upper():
            c1_errs.append(f"Còn sót cụm tiêu đề cấm: '{forbidden_title}'.")
    criteria["1_tieu_de_chuan"] = {"pass": len(c1_errs) == 0, "errors": c1_errs}

    # Tiêu chí 2: Đủ 18/18 câu & tổng điểm = 10.0
    c2_errs = []
    if len(items) != 18:
        c2_errs.append(f"Số câu thực tế = {len(items)} != 18.")
    if abs(float(exam_pkg.get("tong_diem", 0.0)) - 10.0) > 1e-6:
        c2_errs.append(f"Tổng điểm thực tế = {exam_pkg.get('tong_diem')} != 10.0.")
    non_pass_items = [i + 1 for i, it in enumerate(items) if not (it.get("validation_result") or {}).get("is_pass", False)]
    if non_pass_items:
        c2_errs.append(f"Phát hiện câu is_pass=False lọt vào đề: STT {non_pass_items}.")
    criteria["2_du_18_cau_10_diem"] = {"pass": len(c2_errs) == 0, "errors": c2_errs}

    # Tiêu chí 3: Không câu/ý nào rỗng
    c3_errs = []
    for idx, it in enumerate(items, 1):
        q = it.get("question_json") or {}
        loai = it.get("loai_cau_hoi", "")
        raw_dump = json.dumps(q, ensure_ascii=False).lower()
        for emp in EMPTY_PLACEHOLDER_PATTERNS:
            if emp in raw_dump:
                c3_errs.append(f"Câu {idx} ({loai}) chứa placeholder rỗng '{emp}'.")
        if loai in ("MCQ", "SHORT_ANSWER") and len(str(q.get("cau_hoi", "")).strip()) < 15:
            c3_errs.append(f"Câu {idx} ({loai}) có cau_hoi rỗng/quá ngắn.")
        elif loai == "TRUE_FALSE":
            if len(str(q.get("cau_hoi_chung", "")).strip()) < 20:
                c3_errs.append(f"Câu {idx} (TRUE_FALSE) thiếu cau_hoi_chung.")
            for lt in ("a", "b", "c", "d"):
                sub = q.get(lt) or {}
                md = str(sub.get("menh_de", "")).strip() if isinstance(sub, dict) else ""
                if len(md) < 8:
                    c3_errs.append(f"Câu {idx} (TRUE_FALSE) ý {lt}) rỗng/ngắn < 8 ký tự ('{md}').")
        elif loai == "ESSAY_CODE":
            if len(str(q.get("tinh_huong", "")).strip()) < 20 or not str(q.get("dap_an_mau", "")).strip():
                c3_errs.append(f"Câu {idx} (ESSAY_CODE) thiếu tình huống hoặc đáp án mẫu.")
    criteria["3_khong_cau_rong"] = {"pass": len(c3_errs) == 0, "errors": c3_errs}

    # Tiêu chí 4: Không trùng câu hay trùng phương án A/B/C/D
    c4_errs = []
    seen_stems = set()
    for idx, it in enumerate(items, 1):
        q = it.get("question_json") or {}
        loai = it.get("loai_cau_hoi", "")
        stem_key = re.sub(
            r"\s+",
            " ",
            str(q.get("cau_hoi") or q.get("cau_hoi_chung") or q.get("tinh_huong") or "").strip().lower(),
        )
        if stem_key in seen_stems:
            c4_errs.append(f"Câu {idx} ({loai}) trùng câu dẫn với câu trước đó.")
        seen_stems.add(stem_key)
        if loai == "MCQ":
            opts = [re.sub(r"\s+", " ", str(q.get(k, "")).strip().lower()).rstrip(".") for k in ("A", "B", "C", "D")]
            if len(set(opts)) < 4:
                c4_errs.append(f"Câu {idx} (MCQ) bị trùng phương án trong A/B/C/D: {opts}.")
    criteria["4_khong_trung_lap"] = {"pass": len(c4_errs) == 0, "errors": c4_errs}

    # Tiêu chí 5: Không chép thô SGK/Hình/Bảng hay mẫu 1-shot cũ
    c5_errs = []
    for idx, it in enumerate(items, 1):
        q = it.get("question_json") or {}
        loai = it.get("loai_cau_hoi", "")
        stem = str(q.get("cau_hoi") or q.get("cau_hoi_chung") or q.get("tinh_huong") or "")
        body = _flatten_body_without_citation(q, loai)
        if TEXTBOOK_FIG_REGEX.search(stem):
            c5_errs.append(f"Câu {idx} chứa chú thích Hình SGK trong đề.")
        if "Bảng " in stem:
            c5_errs.append(f"Câu {idx} chứa 'Bảng ' SGK trong đề.")
        if TEXTBOOK_HEADER_REGEX.search(stem):
            c5_errs.append(f"Câu {idx} chứa tiêu đề 'BÀI ...' SGK trong đề.")
        if any(cue in stem.lower() for cue in TEXTBOOK_COPY_CUES):
            c5_errs.append(f"Câu {idx} chép cụm hoạt động SGK trong đề.")
        for pat, lbl in ONESHOT_REUSE_PATTERNS:
            if re.search(pat, body, re.IGNORECASE):
                c5_errs.append(f"Câu {idx} lặp mẫu 1-shot ({lbl}).")
    criteria["5_khong_sgk_va_1shot"] = {"pass": len(c5_errs) == 0, "errors": c5_errs}

    # Tiêu chí 6: 100% đoạn mã Python chạy không lỗi trên Sandbox và khớp stdout
    c6_errs = []
    sb_total_code_qs = 0
    sb_passed_code_qs = 0
    for idx, it in enumerate(items, 1):
        q = it.get("question_json") or {}
        loai = it.get("loai_cau_hoi", "")
        snippets = _extract_executable_python_snippets(q, loai)
        if snippets:
            sb_total_code_qs += 1
            has_c, sb_ok, sb_errs, sb_out = _run_sandbox_verification(snippets)
            if not sb_ok:
                c6_errs.append(f"Câu {idx} ({loai}) lỗi Sandbox: {sb_errs}")
            else:
                eg_errs = _check_execution_grounded_answer(q, loai, sb_out) if sb_out.strip() else []
                if eg_errs:
                    c6_errs.append(f"Câu {idx} ({loai}) lệch stdout Sandbox: {eg_errs}")
                else:
                    sb_passed_code_qs += 1
    criteria["6_sandbox_100_khop_stdout"] = {
        "pass": len(c6_errs) == 0,
        "code_questions_checked": sb_total_code_qs,
        "code_questions_passed": sb_passed_code_qs,
        "errors": c6_errs,
    }

    # Tiêu chí 7: HTML xem trước không chứa overflow-x: auto hay border-left
    c7_errs = []
    if "overflow-x: auto" in html_preview:
        c7_errs.append("HTML xem trước còn chứa 'overflow-x: auto'.")
    if "border-left:" in html_preview:
        c7_errs.append("HTML xem trước còn chứa 'border-left:'.")
    criteria["7_html_sach_cuon_va_vien"] = {"pass": len(c7_errs) == 0, "errors": c7_errs}

    # Tiêu chí 8: File .docx xuất ra 100% trắng đen sạch lỗi (cả bản đầy đủ & chỉ đề học sinh)
    c8_errs = []
    if non_black_full:
        c8_errs.append(f"DOCX đầy đủ chứa {len(non_black_full)} run có màu: {non_black_full[:3]}")
    if non_black_stu:
        c8_errs.append(f"DOCX học sinh chứa {len(non_black_stu)} run có màu: {non_black_stu[:3]}")
    if "HƯỚNG DẪN CHẤM" in docx_stu_text:
        c8_errs.append("DOCX bản học sinh bị lẫn phần Hướng dẫn chấm!")
    if "HƯỚNG DẪN CHẤM" not in docx_full_text:
        c8_errs.append("DOCX bản đầy đủ bị thiếu phần Hướng dẫn chấm!")
    criteria["8_docx_100_trang_den"] = {"pass": len(c8_errs) == 0, "errors": c8_errs}

    total_errors = sum(len(v["errors"]) for v in criteria.values())
    return {
        "all_passed": total_errors == 0,
        "total_errors": total_errors,
        "criteria": criteria,
        "docx_full_path": docx_full_path,
        "docx_student_path": docx_student_path,
    }


def main():
    matrix = get_exam_matrix()
    preset1 = matrix["presets_ma_tran_10_diem"][0]
    specs = preset1["specs"]
    ten_ky_thi = preset1.get("tieu_de_in", "ĐỀ KIỂM TRA CHỦ ĐỀ F")
    thoi_gian = preset1.get("thoi_gian", "15 phút")

    print(f"=== BẮT ĐẦU TỰ ĐỘNG SINH & KIỂM TOÁN ĐỀ 18 CÂU – 10.0 ĐIỂM ({ten_ky_thi}) ===", flush=True)
    t0 = time.time()
    exam_pkg = assemble_exam(specs=specs, enable_logging=False, max_backfill_rounds=2)
    total_elapsed = round(time.time() - t0, 2)

    docx_full_path = os.path.join(BASE_DIR, "sample_exam_18cau_daydu.docx")
    docx_student_path = os.path.join(BASE_DIR, "sample_exam_18cau_hocsinh.docx")
    audit = audit_exam(exam_pkg, ten_ky_thi, thoi_gian, docx_full_path, docx_student_path)

    fuzzy_scores = [
        float((it.get("validation_result") or {}).get("diem_chat_luong", 0.0))
        for it in exam_pkg.get("items", [])
    ]
    avg_fuzzy = round(sum(fuzzy_scores) / max(len(fuzzy_scores), 1), 3)

    summary = {
        "ten_ky_thi": ten_ky_thi,
        "tong_so_cau": exam_pkg["tong_so_cau"],
        "target_so_cau": exam_pkg.get("target_so_cau", 18),
        "tong_diem": exam_pkg["tong_diem"],
        "phase1_retrieve_sec": exam_pkg.get("phase1_retrieve_sec", 0.0),
        "phase2_generate_sec": exam_pkg.get("phase2_generate_sec", 0.0),
        "tong_thoi_gian_sec": total_elapsed,
        "backfill_rounds_used": exam_pkg.get("backfill_rounds_used", 0),
        "avg_fuzzy_score": avg_fuzzy,
        "bang_diem_chi_tiet": exam_pkg.get("bang_diem_chi_tiet", {}),
        "audit": audit,
        "chi_tiet_18_cau": [
            {
                "stt": it.get("so_thu_tu"),
                "bai_hoc": it.get("bai_hoc"),
                "loai": it.get("loai_cau_hoi"),
                "muc_do": it.get("muc_do"),
                "is_pass": bool((it.get("validation_result") or {}).get("is_pass", False)),
                "fuzzy": (it.get("validation_result") or {}).get("diem_chat_luong", 0.0),
                "sandbox": bool((it.get("validation_result") or {}).get("sandbox_verified", False)),
                "retries": it.get("retry_count", 0),
                "latency_sec": it.get("latency_sec", 0.0),
            }
            for it in exam_pkg.get("items", [])
        ],
    }

    out_json = os.path.join(BASE_DIR, "experiments", "auto_exam_audit_result.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n================ KẾT QUẢ KIỂM TOÁN 8 TIÊU CHÍ ================", flush=True)
    for k, v in audit["criteria"].items():
        status = "PASS ✅" if v["pass"] else f"FAIL ❌ ({len(v['errors'])} lỗi)"
        print(f"  - {k}: {status}", flush=True)
        for err in v["errors"]:
            print(f"      * {err}", flush=True)
    print(
        f"\nTỔNG KẾT: {exam_pkg['tong_so_cau']}/18 câu | {exam_pkg['tong_diem']}/10.0 điểm | "
        f"Fuzzy TB={avg_fuzzy} | Thời gian={total_elapsed}s | Tổng lỗi={audit['total_errors']}",
        flush=True,
    )
    sys.exit(0 if audit["all_passed"] else 1)


if __name__ == "__main__":
    main()
