# -*- coding: utf-8 -*-
import random
import re
from typing import Any, Callable

from core.sandbox import cham_code_python


# ==============================================================================
# DANH SÁCH LỜI DẪN MỞ ĐẦU SƯ PHẠM ĐA DẠNG (TRÁNH LẶP ĐƠN ĐIỆU)
# ==============================================================================

STEM_MCQ_LEADINS = [
    "Cho đoạn chương trình Python sau:",
    "Xét đoạn mã nguồn Python dưới đây:",
    "Trong quá trình thực hành lập trình Python, một học sinh thực thi đoạn mã sau:",
    "Quan sát đoạn chương trình Python sau:",
]

STEM_SA_LEADINS = [
    "Cho đoạn chương trình Python sau:",
    "Xét đoạn mã Python thực hiện thuật toán dưới đây:",
    "Quan sát đoạn chương trình Python sau:",
    "Trong quá trình chạy thử nghiệm, đoạn mã Python sau được thực thi:",
]

STEM_TF_LEADINS = [
    "Cho đoạn chương trình Python sau:\n{code}\nXét các phát biểu sau:",
    "Xét đoạn mã nguồn Python dưới đây:\n{code}\nQuan sát và đánh giá tính Đúng/Sai của các phát biểu sau:",
    "Trong giờ thực hành, học sinh chạy đoạn chương trình Python sau:\n{code}\nXét các nhận định dưới đây:",
]


# ==============================================================================
# TIỆN ÍCH THỰC THI SANDBOX & TẠO PHƯƠNG ÁN NHIỄU SƯ PHẠM
# ==============================================================================

def _run_code_get_stdout(code: str) -> str:
    """Thực thi đoạn mã Python thuần lớp 10 trên core/sandbox.py để lấy stdout chính xác 100%."""
    sb = cham_code_python(code, test_input="", timeout_sec=2.0)
    if sb.get("trang_thai") != "THÀNH CÔNG":
        raise RuntimeError(f"Symbolic blueprint code error: {sb.get('loi_he_thong') or sb.get('trang_thai')}\n{code}")
    return str(sb.get("ket_qua_in_ra", "")).strip()


def _shuffle_mcq_options(correct_val: str, distractors: list[str]) -> tuple[dict[str, str], str]:
    """
    Xáo trộn 1 đáp án đúng + 3 phương án nhiễu thành A, B, C, D,
    đảm bảo 4 phương án khác nhau 100% (không phân biệt hoa thường/khoảng trắng).
    """
    corr = str(correct_val).strip()
    seen = {corr.lower()}
    clean_dist: list[str] = []
    for d in distractors:
        ds = str(d).strip()
        if ds and ds.lower() not in seen:
            seen.add(ds.lower())
            clean_dist.append(ds)
        if len(clean_dist) == 3:
            break

    # Dự phòng nếu đáp án là số nguyên mà danh sách nhiễu bị trùng
    if len(clean_dist) < 3:
        try:
            base_num = int(corr)
            for delta in (1, -1, 2, -2, 3, 4, 5):
                cand = str(base_num + delta)
                if cand.lower() not in seen:
                    seen.add(cand.lower())
                    clean_dist.append(cand)
                if len(clean_dist) == 3:
                    break
        except ValueError:
            for extra in ("0", "1", "None", "False", "True"):
                if extra.lower() not in seen:
                    seen.add(extra.lower())
                    clean_dist.append(extra)
                if len(clean_dist) == 3:
                    break

    pool = [corr] + clean_dist[:3]
    random.shuffle(pool)
    labels = ("A", "B", "C", "D")
    opts_map = {lbl: val for lbl, val in zip(labels, pool)}
    correct_key = next(lbl for lbl, val in opts_map.items() if val == corr)
    return opts_map, correct_key


def _make_numeric_distractors(ans: int, custom: list[int] | None = None) -> list[str]:
    """Tạo 3 phương án nhiễu số học mô phỏng lỗi lệch 1 / lệch cận / nhầm phép toán của học sinh."""
    cands: list[int] = []
    if custom:
        cands.extend(custom)
    cands.extend([ans + 1, ans - 1, ans + 2, ans - 2, ans + 3, max(0, ans // 2)])
    out: list[str] = []
    seen = {ans}
    for v in cands:
        if v not in seen:
            seen.add(v)
            out.append(str(v))
        if len(out) == 3:
            break
    return out


def _normalize_lesson_num(bai_hoc: str) -> int:
    m = re.search(r"(1[6-9]|2\d|3[0-2])", str(bai_hoc or ""))
    return int(m.group(1)) if m else 19


def _pack_skeleton(
    blueprint_id: str,
    motif_tag: str,
    bai_hoc: str,
    loai: str,
    question_json: dict[str, Any],
    sandbox_stdout: str = "",
    sandbox_verified: bool = False,
    verified_explanation: str = "",
    verified_tf_explanations: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Đóng gói khung câu hỏi kèm bản sao bất biến các trường cốt lõi (locked_fields) và giải thích đã kiểm chứng 100%."""
    if not verified_explanation:
        verified_explanation = str(question_json.get("giai_thich", "")).strip()
        if not verified_explanation and loai == "ESSAY_CODE":
            tc = question_json.get("tieu_chi_cham_diem", [])
            if isinstance(tc, list) and tc:
                verified_explanation = "Tiêu chí chấm điểm:\n" + "\n".join(f"- {x}" for x in tc)
            elif question_json.get("dap_an_mau"):
                verified_explanation = f"Đáp án mẫu thực thi trên Python:\n{question_json.get('dap_an_mau')}"

    if loai == "ESSAY_CODE" and not question_json.get("giai_thich"):
        question_json["giai_thich"] = verified_explanation

    if verified_tf_explanations is None and loai == "TRUE_FALSE":
        verified_tf_explanations = {
            k: str(question_json.get(k, {}).get("giai_thich", "")).strip()
            for k in ("a", "b", "c", "d")
            if isinstance(question_json.get(k), dict)
        }

    locked: dict[str, Any] = {}
    if loai == "MCQ":
        for k in ("cau_hoi", "A", "B", "C", "D", "dap_an"):
            locked[k] = question_json[k]
        locked["giai_thich"] = verified_explanation
    elif loai == "TRUE_FALSE":
        locked["cau_hoi_chung"] = question_json["cau_hoi_chung"]
        for k in ("a", "b", "c", "d"):
            gt_k = (verified_tf_explanations or {}).get(k, question_json[k]["giai_thich"])
            locked[k] = {
                "menh_de": question_json[k]["menh_de"],
                "dap_an": question_json[k]["dap_an"],
                "giai_thich": gt_k,
            }
    elif loai == "SHORT_ANSWER":
        locked["cau_hoi"] = question_json["cau_hoi"]
        locked["dap_an_ngan"] = question_json["dap_an_ngan"]
        locked["giai_thich"] = verified_explanation
    else:  # ESSAY_CODE
        for k in ("tinh_huong", "yeu_cau_hoc_sinh", "dap_an_mau", "tieu_chi_cham_diem"):
            locked[k] = question_json[k]
        locked["giai_thich"] = verified_explanation

    return {
        "blueprint_id": blueprint_id,
        "motif_tag": motif_tag,
        "bai_hoc": bai_hoc,
        "loai_cau_hoi": loai,
        "question_json": question_json,
        "locked_fields": locked,
        "sandbox_stdout": sandbox_stdout,
        "sandbox_verified": sandbox_verified,
        "verified_explanation": verified_explanation,
        "verified_tf_explanations": verified_tf_explanations or {},
    }


# ==============================================================================
# NHÓM 1: LÝ THUYẾT & GỠ LỖI (BÀI 16, 17, 18, 29, 30)
# ==============================================================================

def _bp_b16_mcq_script_mode() -> dict:
    opts, ans = _shuffle_mcq_options(
        "Chế độ soạn thảo lưu tệp đuôi .py",
        [
            "Chế độ dòng lệnh chỉ chạy một biểu thức",
            "Chế độ biên dịch thẳng sang tệp .exe",
            "Chế độ chỉnh sửa hình ảnh và văn bản",
        ],
    )
    lead = random.choice([
        "Trong môi trường lập trình Python, để viết và lưu lại chương trình gồm nhiều dòng lệnh nhằm chạy lại nhiều lần, người lập trình sử dụng chế độ nào?",
        "Khi cần soạn thảo một chương trình Python hoàn chỉnh lưu trong tệp để tái sử dụng, ta chọn chế độ làm việc nào?",
        "Để lưu trữ mã nguồn Python dưới dạng tệp script (.py), chế độ thực thi nào sau đây được sử dụng?",
    ])
    gt = "Chế độ soạn thảo cho phép viết nhiều dòng lệnh, lưu thành tệp có phần mở rộng .py và chạy lại chương trình nhiều lần."
    q = {
        "cau_hoi": lead,
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B16_MCQ_SCRIPT_MODE", "b16_script_mode", "Bài 16", "MCQ", q, verified_explanation=gt)


def _bp_b16_mcq_high_level() -> dict:
    opts, ans = _shuffle_mcq_options(
        "Ngôn ngữ lập trình bậc cao dễ đọc, dễ hiểu và gần với ngôn ngữ tự nhiên",
        [
            "Ngôn ngữ máy chỉ gồm các chuỗi nhị phân 0 và 1",
            "Hợp ngữ phụ thuộc hoàn toàn vào phần cứng vi xử lý",
            "Ngôn ngữ lập trình chỉ chạy được trên điện thoại thông minh",
        ],
    )
    lead = random.choice([
        "Phát biểu nào sau đây nêu đúng nhất về đặc điểm của ngôn ngữ lập trình Python?",
        "Python là ngôn ngữ lập trình bậc cao nổi bật nhờ đặc tính nào sau đây?",
        "Đặc điểm tiêu biểu giúp Python trở thành ngôn ngữ lập trình phổ biến trong giáo dục là gì?",
    ])
    gt = "Python là ngôn ngữ lập trình bậc cao, có cú pháp sáng sủa, dễ đọc, dễ hiểu và gần gũi với ngôn ngữ tự nhiên tiếng Anh."
    q = {
        "cau_hoi": lead,
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B16_MCQ_HIGH_LEVEL", "b16_high_level", "Bài 16", "MCQ", q, verified_explanation=gt)


def _bp_b16_mcq_print_expr() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    a = random.randint(3, 9)
    b = random.randint(2, 6)
    c = random.randint(2, 5)
    code = f"print({a} + {b} * {c})"
    out = _run_code_get_stdout(code)
    val = int(out)
    wrong1 = (a + b) * c
    wrong2 = a * b + c
    opts, ans = _shuffle_mcq_options(out, _make_numeric_distractors(val, [wrong1, wrong2]))
    gt = f"Theo thứ tự ưu tiên toán tử trong Python, phép nhân thực hiện trước: {b} * {c} = {b * c}, sau đó cộng với {a} thu được {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là gì?",
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B16_MCQ_PRINT_EXPR", "b16_print_expr", "Bài 16", "MCQ", q, out, True, verified_explanation=gt)


def _bp_b17_mcq_valid_var() -> dict:
    valid_name = random.choice(["tong_diem", "diem_trung_binh", "so_hoc_sinh", "tong_tien_10"])
    opts, ans = _shuffle_mcq_options(
        valid_name,
        [
            "10_diem",       # Bắt đầu bằng số
            "tong diem",     # Chứa khoảng trắng
            "if",            # Trùng từ khóa
        ],
    )
    lead = random.choice([
        "Trong các tên biến sau đây của Python, tên biến nào đặt đúng quy tắc?",
        "Tên biến nào sau đây là hợp lệ trong ngôn ngữ lập trình Python?",
        "Quy tắc đặt tên biến của Python chấp nhận tên biến nào sau đây?",
    ])
    gt = f"Tên biến '{valid_name}' hợp lệ vì bắt đầu bằng chữ cái, chỉ chứa chữ cái, chữ số và dấu gạch dưới, không trùng từ khóa."
    q = {
        "cau_hoi": lead,
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B17_MCQ_VALID_VAR", "b17_valid_var", "Bài 17", "MCQ", q, verified_explanation=gt)


def _bp_b17_mcq_assign_valid() -> dict:
    var_name = random.choice(["x", "y", "p", "tong", "dem"])
    val_num = random.randint(10, 50)
    opts, ans = _shuffle_mcq_options(
        f"{var_name} = {val_num}",
        [
            f"{val_num} = {var_name}",
            f"{var_name} + 1 = {val_num}",
            f"if = {val_num}",
        ],
    )
    lead = random.choice([
        "Trong Python, câu lệnh gán nào sau đây viết đúng cú pháp?",
        "Cú pháp câu lệnh gán giá trị cho biến nào sau đây là hợp lệ trong Python?",
        "Xét các câu lệnh gán sau trong Python, lệnh nào viết đúng cú pháp?",
    ])
    gt = f"Câu lệnh '{var_name} = {val_num}' đúng cú pháp gán giá trị cho biến: bên trái là tên biến đơn, bên phải là biểu thức/giá trị."
    q = {
        "cau_hoi": lead,
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B17_MCQ_ASSIGN_VALID", "b17_assign_valid", "Bài 17", "MCQ", q, verified_explanation=gt)


def _bp_b17_sa_div_mod() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    a = random.randint(15, 39)
    b = random.randint(4, 7)
    code = f"a = {a}\nb = {b}\nkq = (a // b) + (a % b)\nprint(kq)"
    out = _run_code_get_stdout(code)
    gt = f"Thực hiện phép chia: {a} // {b} = {a // b} (chia lấy phần nguyên) và {a} % {b} = {a % b} (chia lấy phần dư). Tổng kq = {a // b} + {a % b} = {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là bao nhiêu?",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B17_SA_DIV_MOD", "b17_div_mod", "Bài 17", "SHORT_ANSWER", q, out, True, verified_explanation=gt)


def _bp_b17_sa_swap_update() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    x = random.randint(5, 12)
    y = random.randint(15, 25)
    code = f"x = {x}\ny = {y}\nx = x + y\ny = x - y\nprint(y)"
    out = _run_code_get_stdout(code)
    gt = f"Sau lệnh x = x + y, x = {x + y}. Sau lệnh y = x - y, y = {x + y} - {y} = {out}. Do đó lệnh print(y) in ra {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là bao nhiêu?",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B17_SA_SWAP_UPDATE", "b17_swap_update", "Bài 17", "SHORT_ANSWER", q, out, True, verified_explanation=gt)


def _bp_b18_mcq_type_cast() -> dict:
    opts, ans = _shuffle_mcq_options(
        "float(input())",
        ["int(input())", "str(input())", "type(input())"],
    )
    lead = random.choice([
        "Trong Python, để nhập một số thực từ bàn phím, câu lệnh chuyển đổi kiểu dữ liệu nào sau đây là phù hợp nhất?",
        "Muốn nhập một giá trị số thực từ bàn phím gán cho biến, ta sử dụng cú pháp nào?",
        "Câu lệnh nào sau đây chuyển đổi trực tiếp dữ liệu nhập từ bàn phím sang kiểu số thực (float)?",
    ])
    gt = "Hàm input() trả về xâu kí tự str, hàm float() chuyển đổi xâu đó thành số thực kiểu float."
    q = {
        "cau_hoi": lead,
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B18_MCQ_TYPE_CAST", "b18_type_cast", "Bài 18", "MCQ", q, verified_explanation=gt)


def _bp_b18_mcq_int_print() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    n1 = random.randint(12, 28)
    n2 = random.randint(3, 9)
    code = f"a = int('{n1}')\nb = {n2}\nprint(a + b)"
    out = _run_code_get_stdout(code)
    val = int(out)
    opts, ans = _shuffle_mcq_options(out, [f"{n1}{n2}", str(val + 1), str(val - 2)])
    gt = f"Hàm int('{n1}') chuyển xâu thành số nguyên {n1}, sau đó cộng với b = {n2} nên lệnh print(a + b) in ra {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là gì?",
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B18_MCQ_INT_PRINT", "b18_int_print", "Bài 18", "MCQ", q, out, True, verified_explanation=gt)


def _bp_b18_sa_cast_calc() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    s_num = random.randint(14, 35)
    k = random.randint(2, 6)
    code = f"x = int('{s_num}')\ny = float('{k}.5')\nprint(int(x + y))"
    out = _run_code_get_stdout(code)
    gt = f"int('{s_num}') bằng {s_num}, float('{k}.5') bằng {k}.5, tổng là {s_num + k}.5 và int() lấy phần nguyên là {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là bao nhiêu?",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B18_SA_CAST_CALC", "b18_cast_calc", "Bài 18", "SHORT_ANSWER", q, out, True, verified_explanation=gt)


def _bp_b18_tf_io() -> dict:
    code = "a = int('18')\nb = float('2.5')\nprint(int(a + b))"
    out = _run_code_get_stdout(code)
    gt_tf = {
        "a": "Hàm int() chuyển đổi xâu biểu diễn số nguyên '18' sang kiểu số nguyên int.",
        "b": "Hàm float('2.5') chuyển xâu thành số thực 2.5 thuộc kiểu float, không còn là kiểu str.",
        "c": f"Tổng a + b = 18 + 2.5 = 20.5 và int(20.5) lấy phần nguyên là {out}.",
        "d": "Hàm input() trong Python luôn trả về dữ liệu kiểu xâu kí tự str, cần gọi int() hoặc float() để chuyển sang kiểu số.",
    }
    q = {
        "cau_hoi_chung": f"Cho đoạn chương trình Python minh họa lệnh chuyển đổi kiểu và print() sau:\n{code}\nXét các phát biểu sau:",
        "a": {
            "menh_de": "Lệnh int('18') chuyển xâu kí tự '18' sang số nguyên kiểu int.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["a"],
        },
        "b": {
            "menh_de": "Biến b sau lệnh float('2.5') thuộc kiểu xâu kí tự str.",
            "dap_an": "Sai",
            "giai_thich": gt_tf["b"],
        },
        "c": {
            "menh_de": f"Kết quả in ra màn hình là {out}.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["c"],
        },
        "d": {
            "menh_de": "Hàm input() trong Python luôn trả về trực tiếp dữ liệu kiểu số nguyên int.",
            "dap_an": "Sai",
            "giai_thich": gt_tf["d"],
        },
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B18_TF_IO", "b18_tf_io", "Bài 18", "TRUE_FALSE", q, out, True, verified_tf_explanations=gt_tf)


def _bp_b18_tf_input_cast() -> dict:
    lead_tmpl = random.choice(STEM_TF_LEADINS)
    a = random.choice([10, 15, 20, 25])
    b_num = random.choice([2, 3, 4, 5])
    code = f"x = {a}\ns = '{b_num}'\nkq = x + int(s)\nprint(kq)"
    out = _run_code_get_stdout(code)
    c_claim_true = random.choice([True, False])
    c_shown = out if c_claim_true else str(int(out) + 5)
    gt_tf = {
        "a": f"Giá trị {a} là số nguyên nên biến x có kiểu dữ liệu int.",
        "b": f"Giá trị '{b_num}' được đặt trong cặp dấu nháy đơn nên biến s thuộc kiểu xâu kí tự str.",
        "c": f"Biến s được ép kiểu bằng int('{b_num}') = {b_num}, cộng với x = {a} được kết quả {out}.",
        "d": "Trong Python, phép cộng trực tiếp giữa kiểu số nguyên int và kiểu xâu str (x + s) sẽ báo lỗi TypeError.",
    }
    q = {
        "cau_hoi_chung": lead_tmpl.format(code=code),
        "a": {
            "menh_de": f"Biến x được gán giá trị {a} thuộc kiểu số nguyên int.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["a"],
        },
        "b": {
            "menh_de": f"Biến s lưu giá trị '{b_num}' thuộc kiểu số nguyên int.",
            "dap_an": "Sai",
            "giai_thich": gt_tf["b"],
        },
        "c": {
            "menh_de": f"Kết quả in ra màn hình là {c_shown}.",
            "dap_an": "Đúng" if c_claim_true else "Sai",
            "giai_thich": gt_tf["c"],
        },
        "d": {
            "menh_de": "Nếu viết trực tiếp x + s mà không ép kiểu thì Python tự động cộng thành số mà không báo lỗi.",
            "dap_an": "Sai",
            "giai_thich": gt_tf["d"],
        },
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B18_TF_INPUT_CAST", "b18_tf_cast", "Bài 18", "TRUE_FALSE", q, out, True, verified_tf_explanations=gt_tf)


# ==============================================================================
# NHÓM 2: BIẾN, RẼ NHÁNH, VÒNG LẶP (BÀI 19, 20, 21)
# ==============================================================================

def _bp_b19_mcq_if_elif() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    val = random.choice([5, 7, 8, 9])
    code = (
        f"diem = {val}\n"
        f"if diem >= 8:\n"
        f"    print('Gioi')\n"
        f"elif diem >= 6.5:\n"
        f"    print('Kha')\n"
        f"else:\n"
        f"    print('Dat')"
    )
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, ["Gioi", "Kha", "Dat", str(val)])
    gt = f"Với diem = {val}: kiểm tra điều kiện từ trên xuống, chương trình thỏa nhánh tương ứng và in ra '{out}'."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là gì?",
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B19_MCQ_IF_ELIF", "b19_if_elif", "Bài 19", "MCQ", q, out, True, verified_explanation=gt)


def _bp_b19_mcq_logic_expr() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    a = random.choice([6, 8, 12, 14])
    b = random.choice([3, 4, 5])
    code = (
        f"a = {a}\n"
        f"b = {b}\n"
        f"if a < 10 and b % 2 == 0:\n"
        f"    print('Nhanh_1')\n"
        f"else:\n"
        f"    print('Nhanh_2')"
    )
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, ["Nhanh_1", "Nhanh_2", "True", "False"])
    gt = f"Kiểm tra biểu thức lôgic (a < 10 and b % 2 == 0) với a = {a}, b = {b}: chương trình chọn đúng nhánh tương ứng và in ra {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là gì?",
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B19_MCQ_LOGIC_EXPR", "b19_logic_expr", "Bài 19", "MCQ", q, out, True, verified_explanation=gt)


def _bp_b19_sa_branch() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    a = random.randint(6, 15)
    b = random.randint(4, 12)
    code = f"a = {a}\nb = {b}\nif a > b:\n    kq = a - b\nelse:\n    kq = b - a\nprint(kq)"
    out = _run_code_get_stdout(code)
    gt = f"So sánh a = {a} và b = {b}: điều kiện {'a > b là True nên kq = a - b' if a > b else 'a > b là False nên thực hiện else kq = b - a'}, lệnh print(kq) in ra {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là bao nhiêu?",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B19_SA_BRANCH", "b19_sa_branch", "Bài 19", "SHORT_ANSWER", q, out, True, verified_explanation=gt)


def _bp_b19_sa_elif_grade() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    score = random.choice([6.0, 7.0, 8.0, 8.5, 9.0])
    code = (
        f"d = {score}\n"
        f"if d >= 8.0:\n"
        f"    thuong = 100\n"
        f"elif d >= 6.5:\n"
        f"    thuong = 50\n"
        f"else:\n"
        f"    thuong = 0\n"
        f"print(thuong)"
    )
    out = _run_code_get_stdout(code)
    gt = f"Với d = {score}: điều kiện {'d >= 8.0 thỏa mãn nên thuong = 100' if score >= 8.0 else ('d >= 6.5 thỏa mãn nên thuong = 50' if score >= 6.5 else 'không thỏa mãn 2 nhánh đầu nên thuong = 0')}. Kết quả in ra là {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là bao nhiêu?",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B19_SA_ELIF_GRADE", "b19_sa_grade", "Bài 19", "SHORT_ANSWER", q, out, True, verified_explanation=gt)


def _bp_b19_tf_branch() -> dict:
    lead_tmpl = random.choice(STEM_TF_LEADINS)
    v = random.choice(["p", "n", "diem", "nhiet_do", "so_luong"])
    if v == "diem":
        val = random.choice([7.0, 8.0, 8.5, 9.0])
        nguong = 8.0
        code = f"{v} = {val}\nif {v} >= {nguong}:\n    print('DatChuan')\nelse:\n    print('ChuaDat')"
        lbl_t, lbl_f = "DatChuan", "ChuaDat"
    elif v == "nhiet_do":
        val = random.choice([36, 37, 38, 39])
        nguong = 37
        code = f"{v} = {val}\nif {v} > {nguong}:\n    print('VuotMuc')\nelse:\n    print('AnToan')"
        lbl_t, lbl_f = "VuotMuc", "AnToan"
    else:
        val = random.choice([12, 15, 18, 21, 24])
        nguong = 14
        lbl_t, lbl_f = random.choice([("DatChuan", "ChuaDat"), ("HopLe", "KhongHopLe"), ("XuatSac", "Dat")])
        code = f"{v} = {val}\nif {v} >= {nguong} and {v} % 3 == 0:\n    print('{lbl_t}')\nelse:\n    print('{lbl_f}')"

    out = _run_code_get_stdout(code)
    cond_is_true = (out == lbl_t)
    wrong_out = lbl_f if cond_is_true else lbl_t
    c_claim_true = random.choice([True, False])
    c_shown = out if c_claim_true else wrong_out

    gt_tf = {
        "a": f"Lệnh gán {v} = {val} xác định biến {v} mang kiểu {'float' if isinstance(val, float) else 'int'}.",
        "b": f"Với {v} = {val}, biểu thức điều kiện nhận giá trị {'True' if cond_is_true else 'False'}.",
        "c": f"Khi chạy thực tế đoạn mã với {v} = {val}, chương trình in ra '{out}'.",
        "d": "Theo cú pháp Python chuẩn, dòng điều kiện if và dòng else đều bắt buộc kết thúc bằng dấu hai chấm (:).",
    }
    q = {
        "cau_hoi_chung": lead_tmpl.format(code=code),
        "a": {
            "menh_de": f"Biến {v} được gán giá trị {val} thuộc kiểu {'float' if isinstance(val, float) else 'int'}.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["a"],
        },
        "b": {
            "menh_de": f"Biểu thức điều kiện nhận giá trị {'False' if cond_is_true else 'True'}.",
            "dap_an": "Sai",
            "giai_thich": gt_tf["b"],
        },
        "c": {
            "menh_de": f"Kết quả in ra màn hình là '{c_shown}'.",
            "dap_an": "Đúng" if c_claim_true else "Sai",
            "giai_thich": gt_tf["c"],
        },
        "d": {
            "menh_de": (
                "Câu lệnh if trong Python bắt buộc có dấu hai chấm (:) cuối dòng điều kiện."
                if not c_claim_true
                else "Câu lệnh if trong Python có thể bỏ dấu hai chấm (:) ở cuối dòng điều kiện."
            ),
            "dap_an": "Đúng" if not c_claim_true else "Sai",
            "giai_thich": gt_tf["d"],
        },
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B19_TF_BRANCH", "b19_tf_branch", "Bài 19", "TRUE_FALSE", q, out, True, verified_tf_explanations=gt_tf)


def _bp_b20_mcq_for_sum() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    start = random.choice([2, 3, 4])
    stop = start + random.choice([4, 5])
    step = random.choice([1, 2])
    var_acc = random.choice(["tong", "kq", "t"])
    var_i = random.choice(["k", "j"])
    code = (
        f"{var_acc} = 0\n"
        f"for {var_i} in range({start}, {stop}, {step}):\n"
        f"    {var_acc} = {var_acc} + {var_i}\n"
        f"print({var_acc})"
    )
    out = _run_code_get_stdout(code)
    val = int(out)
    opts, ans = _shuffle_mcq_options(out, _make_numeric_distractors(val, [val + stop, val - start, val + step]))
    gt = f"Vòng lặp for duyệt {var_i} qua range({start}, {stop}, {step}) gồm các giá trị {list(range(start, stop, step))} nên tổng {var_acc} bằng {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là bao nhiêu?",
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B20_MCQ_FOR_SUM", "b20_for_sum", "Bài 20", "MCQ", q, out, True, verified_explanation=gt)


def _bp_b20_mcq_for_count_mult3() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    start = random.choice([1, 2, 3])
    stop = random.choice([11, 13, 15, 17, 20, 22])
    uoc = random.choice([2, 3, 4, 5])
    var_k = random.choice(["k", "i", "x"])
    var_dem = random.choice(["dem", "cnt", "so_luong"])
    code = (
        f"{var_dem} = 0\n"
        f"for {var_k} in range({start}, {stop}):\n"
        f"    if {var_k} % {uoc} == 0:\n"
        f"        {var_dem} += 1\n"
        f"print({var_dem})"
    )
    out = _run_code_get_stdout(code)
    val = int(out)
    vals_div = [x for x in range(start, stop) if x % uoc == 0]
    opts, ans = _shuffle_mcq_options(out, _make_numeric_distractors(val, [val + 1, max(1, val - 1), (stop - start) // uoc + 1]))
    gt = f"Hàm range({start}, {stop}) sinh các số từ {start} đến {stop - 1}. Các số chia hết cho {uoc} là {vals_div} (gồm {out} số) nên {var_dem} bằng {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nGiá trị in ra màn hình là bao nhiêu?",
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B20_MCQ_FOR_MULT3", "b20_for_mult3", "Bài 20", "MCQ", q, out, True, verified_explanation=gt)


def _bp_b20_tf_for_range() -> dict:
    lead_tmpl = random.choice(STEM_TF_LEADINS)
    start = random.choice([2, 3])
    stop = start + random.choice([5, 6])
    step = random.choice([1, 2])
    vals = list(range(start, stop, step))
    cnt = len(vals)
    code = (
        f"tong = 0\n"
        f"for k in range({start}, {stop}, {step}):\n"
        f"    tong = tong + k\n"
        f"print(tong)"
    )
    out = _run_code_get_stdout(code)
    val = int(out)
    c_claim_true = random.choice([True, False])
    c_shown = str(val) if c_claim_true else str(val + stop)

    gt_tf = {
        "a": f"Hàm range({start}, {stop}, {step}) tạo các giá trị {vals}, không bao gồm cận trên {stop}.",
        "b": f"Vùng giá trị {vals} có đúng {cnt} phần tử nên vòng lặp for chỉ thực hiện đúng {cnt} lần lặp.",
        "c": f"Cộng dồn các giá trị {vals} ta thu được tong = {out}.",
        "d": "Biến tong khởi tạo bằng 0 và chỉ cộng các số nguyên nên sau vòng lặp luôn mang kiểu int.",
    }
    q = {
        "cau_hoi_chung": lead_tmpl.format(code=code),
        "a": {
            "menh_de": f"Hàm range({start}, {stop}, {step}) sinh dãy các giá trị nguyên bắt đầu từ {start} và nhỏ hơn {stop}.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["a"],
        },
        "b": {
            "menh_de": f"Vòng lặp for trong đoạn mã thực hiện đúng {cnt + 2} lần lặp.",
            "dap_an": "Sai",
            "giai_thich": gt_tf["b"],
        },
        "c": {
            "menh_de": f"Kết quả in ra màn hình là {c_shown}.",
            "dap_an": "Đúng" if c_claim_true else "Sai",
            "giai_thich": gt_tf["c"],
        },
        "d": {
            "menh_de": (
                "Biến tong sau khi kết thúc vòng lặp thuộc kiểu số nguyên int."
                if not c_claim_true
                else "Biến tong sau khi kết thúc vòng lặp thuộc kiểu xâu kí tự str."
            ),
            "dap_an": "Đúng" if not c_claim_true else "Sai",
            "giai_thich": gt_tf["d"],
        },
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B20_TF_FOR_RANGE", "b20_tf_for_range", "Bài 20", "TRUE_FALSE", q, out, True, verified_tf_explanations=gt_tf)


def _bp_b20_sa_for_odd_sum() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    start = random.choice([1, 3])
    stop = random.choice([10, 12, 14])
    code = (
        f"kq = 0\n"
        f"for k in range({start}, {stop}, 2):\n"
        f"    kq += k\n"
        f"print(kq)"
    )
    out = _run_code_get_stdout(code)
    gt = f"Vòng lặp for duyệt k qua các số lẻ {list(range(start, stop, 2))} nên tổng kq in ra bằng {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là bao nhiêu?",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B20_SA_FOR_ODD", "b20_for_odd", "Bài 20", "SHORT_ANSWER", q, out, True, verified_explanation=gt)


def _bp_b20_sa_for_if_sum() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    start = random.choice([1, 2])
    stop = random.choice([7, 9, 11])
    code = (
        f"s = 0\n"
        f"for i in range({start}, {stop}):\n"
        f"    if i % 2 == 0:\n"
        f"        s += i\n"
        f"print(s)"
    )
    out = _run_code_get_stdout(code)
    evens = [x for x in range(start, stop) if x % 2 == 0]
    gt = f"Dãy số trong range({start}, {stop}) gồm các số chẵn là {evens}. Tổng s = {' + '.join(map(str, evens)) or '0'} = {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là bao nhiêu?",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B20_SA_FOR_IF", "b20_for_if_sa", "Bài 20", "SHORT_ANSWER", q, out, True, verified_explanation=gt)


def _bp_b21_mcq_while_steps() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    limit = random.choice([10, 12, 15, 18])
    step = random.choice([3, 4])
    code = (
        f"k = 1\n"
        f"dem = 0\n"
        f"while k < {limit}:\n"
        f"    dem += 1\n"
        f"    k += {step}\n"
        f"print(dem)"
    )
    out = _run_code_get_stdout(code)
    val = int(out)
    opts, ans = _shuffle_mcq_options(out, _make_numeric_distractors(val, [val + 1, max(1, val - 1), limit // 2]))
    gt = f"Bắt đầu từ k = 1 và mỗi lần lặp tăng k thêm {step} khi k < {limit}, vòng lặp while thực hiện đúng {out} lần nên dem bằng {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là bao nhiêu?",
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B21_MCQ_WHILE_STEPS", "b21_while_steps", "Bài 21", "MCQ", q, out, True, verified_explanation=gt)


def _bp_b21_mcq_while_condition() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    threshold = random.choice([12, 15, 20])
    code = (
        f"s = 0\n"
        f"k = 1\n"
        f"while s < {threshold}:\n"
        f"    s += k\n"
        f"    k += 1\n"
        f"print(k)"
    )
    out = _run_code_get_stdout(code)
    val = int(out)
    opts, ans = _shuffle_mcq_options(out, _make_numeric_distractors(val, [val - 1, val + 1, val + 2]))
    gt = f"Vòng lặp while cộng dồn k vào s đến khi s >= {threshold}. Sau khi dừng lặp và tăng k, biến k có giá trị bằng {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là bao nhiêu?",
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B21_MCQ_WHILE_COND", "b21_while_cond", "Bài 21", "MCQ", q, out, True, verified_explanation=gt)


def _bp_b21_sa_while_acc() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    limit = random.choice([5, 6, 7])
    step = random.choice([1, 2])
    code = (
        f"k = 2\n"
        f"tong = 0\n"
        f"while k <= {limit + 2}:\n"
        f"    tong = tong + k\n"
        f"    k = k + {step}\n"
        f"print(tong)"
    )
    out = _run_code_get_stdout(code)
    gt = f"Vòng lặp while cộng dồn k bắt đầu từ 2 với bước tăng {step} đến khi k > {limit + 2}, thu được tong = {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là bao nhiêu?",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B21_SA_WHILE_ACC", "b21_while_acc", "Bài 21", "SHORT_ANSWER", q, out, True, verified_explanation=gt)


def _bp_b21_tf_while() -> dict:
    lead_tmpl = random.choice(STEM_TF_LEADINS)
    limit = random.choice([9, 11, 13])
    code = (
        f"k = 1\n"
        f"tong = 0\n"
        f"while k < {limit}:\n"
        f"    tong += k\n"
        f"    k += 3\n"
        f"print(tong)"
    )
    out = _run_code_get_stdout(code)
    steps = len(list(range(1, limit, 3)))
    gt_tf = {
        "a": f"Câu lệnh while kiểm tra điều kiện k < {limit} trước mỗi lượt lặp và lặp khi điều kiện còn True.",
        "b": f"Biến k nhận các giá trị {list(range(1, limit, 3))} nên vòng lặp chỉ chạy đúng {steps} lượt.",
        "c": f"Cộng dồn k qua các lượt lặp ta thu được tong = {out}.",
        "d": "Nếu trong thân vòng lặp while không có câu lệnh tăng biến k (k += 3) thì điều kiện lặp luôn đúng gây ra vòng lặp vô hạn.",
    }
    q = {
        "cau_hoi_chung": lead_tmpl.format(code=code),
        "a": {
            "menh_de": f"Vòng lặp while tiếp tục thực hiện khi điều kiện k < {limit} còn đúng.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["a"],
        },
        "b": {
            "menh_de": f"Vòng lặp thực hiện đúng {steps + 2} lượt trước khi dừng.",
            "dap_an": "Sai",
            "giai_thich": gt_tf["b"],
        },
        "c": {
            "menh_de": f"Kết quả in ra màn hình là {out}.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["c"],
        },
        "d": {
            "menh_de": "Nếu bỏ dòng lệnh 'k += 3' thì vòng lặp while sẽ bị lặp vô hạn.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["d"],
        },
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B21_TF_WHILE", "b21_tf_while", "Bài 21", "TRUE_FALSE", q, out, True, verified_tf_explanations=gt_tf)


def _bp_b21_tf_while_condition() -> dict:
    lead_tmpl = random.choice(STEM_TF_LEADINS)
    start = random.choice([8, 10, 12, 14])
    step = random.choice([2, 3])
    code = (
        f"n = {start}\n"
        f"dem = 0\n"
        f"while n > 0:\n"
        f"    dem += 1\n"
        f"    n -= {step}\n"
        f"print(dem, n)"
    )
    out = _run_code_get_stdout(code)
    parts = out.split()
    dem_val, n_val = parts[0], parts[1]
    gt_tf = {
        "a": "Điều kiện lặp n > 0 được kiểm tra ở đầu mỗi lượt lặp trước khi thực hiện các lệnh trong thân vòng lặp.",
        "b": f"Mỗi lượt n giảm {step} nên sau {dem_val} lượt thì n = {n_val} (<= 0), vòng lặp dừng lại.",
        "c": f"Kết quả in ra gồm hai giá trị lần lượt là dem = {dem_val} và n = {n_val}.",
        "d": "Vòng lặp while trong Python luôn chạy ít nhất 1 lần bất kể điều kiện ban đầu đúng hay sai.",
    }
    q = {
        "cau_hoi_chung": lead_tmpl.format(code=code),
        "a": {
            "menh_de": "Điều kiện n > 0 được kiểm tra trước mỗi lượt lặp.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["a"],
        },
        "b": {
            "menh_de": f"Số lượt lặp của vòng lặp while trong đoạn mã là {dem_val}.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["b"],
        },
        "c": {
            "menh_de": f"Kết quả in ra màn hình là '{out}'.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["c"],
        },
        "d": {
            "menh_de": "Vòng lặp while luôn luôn chạy ít nhất một lần kể cả khi điều kiện ban đầu là False.",
            "dap_an": "Sai",
            "giai_thich": gt_tf["d"],
        },
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B21_TF_WHILE_COND", "b21_tf_cond", "Bài 21", "TRUE_FALSE", q, out, True, verified_tf_explanations=gt_tf)


# ==============================================================================
# NHÓM 3: DANH SÁCH & XÂU KÍ TỰ (BÀI 22, 23, 24, 25)
# ==============================================================================

def _bp_b22_mcq_list_index() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    nums = random.sample([3, 7, 12, 18, 25, 30], 5)
    idx = random.choice([1, 2, 3])
    code = f"A = {nums}\nprint(A[{idx}])"
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, [str(nums[idx - 1]), str(nums[(idx + 1) % len(nums)]), str(nums[0])])
    gt = f"Chỉ số danh sách trong Python đánh số từ 0. Phần tử A[{idx}] là phần tử thứ {idx + 1} có giá trị {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là gì?",
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B22_MCQ_LIST_INDEX", "b22_list_index", "Bài 22", "MCQ", q, out, True, verified_explanation=gt)


def _bp_b22_mcq_list_modify() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    nums = random.sample([2, 4, 6, 8, 10], 4)
    idx = random.choice([0, 1, 2])
    val = random.choice([15, 25, 35])
    code = f"a = {nums}\na[{idx}] = {val}\nprint(a[{idx}] + a[-1])"
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, _make_numeric_distractors(int(out)))
    gt = f"Sau lệnh gán a[{idx}] = {val}, phần tử a[{idx}] có giá trị {val}. Phần tử cuối a[-1] = {nums[-1]}. Tổng in ra là {val} + {nums[-1]} = {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là bao nhiêu?",
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B22_MCQ_LIST_MODIFY", "b22_list_mod", "Bài 22", "MCQ", q, out, True, verified_explanation=gt)


def _bp_b22_tf_list_filter() -> dict:
    lead_tmpl = random.choice(STEM_TF_LEADINS)
    nums = random.sample([3, 6, 9, 12, 15, 18], 5)
    cnt_even = len([x for x in nums if x % 2 == 0])
    code = (
        f"A = {nums}\n"
        f"dem = 0\n"
        f"for x in A:\n"
        f"    if x % 2 == 0:\n"
        f"        dem += 1\n"
        f"print(dem)"
    )
    out = _run_code_get_stdout(code)
    val = int(out)
    gt_tf = {
        "a": f"Danh sách A được khai báo trong ngoặc vuông và có đúng {len(nums)} phần tử.",
        "b": "Vòng lặp 'for x in A:' duyệt lần lượt từng giá trị phần tử x trong danh sách A.",
        "c": f"Trong danh sách A có đúng {val} số chẵn nên print(dem) in ra {out}.",
        "d": "Trong Python, danh sách (list) là kiểu dữ liệu có thể thay đổi (mutable), cho phép gán lại hoặc xóa phần tử.",
    }
    q = {
        "cau_hoi_chung": lead_tmpl.format(code=code),
        "a": {
            "menh_de": f"Biến A lưu trữ một danh sách gồm {len(nums)} phần tử số nguyên.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["a"],
        },
        "b": {
            "menh_de": "Vòng lặp for chỉ duyệt qua các chỉ số của danh sách A thay vì các phần tử.",
            "dap_an": "Sai",
            "giai_thich": gt_tf["b"],
        },
        "c": {
            "menh_de": f"Kết quả in ra màn hình là {out}.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["c"],
        },
        "d": {
            "menh_de": "Danh sách trong Python là kiểu dữ liệu không thể thay đổi giá trị của các phần tử.",
            "dap_an": "Sai",
            "giai_thich": gt_tf["d"],
        },
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B22_TF_LIST_FILTER", "b22_list_filter", "Bài 22", "TRUE_FALSE", q, out, True, verified_tf_explanations=gt_tf)


def _bp_b22_tf_list_indexing_slice() -> dict:
    lead_tmpl = random.choice(STEM_TF_LEADINS)
    nums = random.sample([5, 12, 18, 24, 30, 36], 5)
    code = f"ds = {nums}\nds[1] = ds[0] + ds[-1]\nprint(ds[1], len(ds))"
    out = _run_code_get_stdout(code)
    parts = out.split()
    sum_val, len_val = parts[0], parts[1]
    gt_tf = {
        "a": f"Hàm len(ds) đếm tổng số phần tử ban đầu trong danh sách, bằng {len(nums)}.",
        "b": f"Chỉ số âm -1 trỏ đến phần tử cuối cùng ds[-1] = {nums[-1]}.",
        "c": f"Lệnh ds[1] = ds[0] + ds[-1] cập nhật ds[1] = {nums[0]} + {nums[-1]} = {sum_val}.",
        "d": "Danh sách trong Python là kiểu dữ liệu mutable nên cho phép thay đổi phần tử qua phép gán chỉ số.",
    }
    q = {
        "cau_hoi_chung": lead_tmpl.format(code=code),
        "a": {
            "menh_de": f"Hàm len(ds) trả về số lượng phần tử của danh sách là {len(nums)}.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["a"],
        },
        "b": {
            "menh_de": f"Chỉ số ds[-1] truy xuất phần tử đầu tiên của danh sách là {nums[0]}.",
            "dap_an": "Sai",
            "giai_thich": gt_tf["b"],
        },
        "c": {
            "menh_de": f"Giá trị in ra màn hình là '{out}'.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["c"],
        },
        "d": {
            "menh_de": "Lệnh gán 'ds[1] = ...' báo lỗi vì danh sách không cho phép thay đổi phần tử.",
            "dap_an": "Sai",
            "giai_thich": gt_tf["d"],
        },
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B22_TF_LIST_SLICE", "b22_list_slice", "Bài 22", "TRUE_FALSE", q, out, True, verified_tf_explanations=gt_tf)


def _bp_b23_mcq_list_append() -> dict:
    opts, ans = _shuffle_mcq_options(
        "A.append(x)",
        ["A.add(x)", "A.insert_end(x)", "A.push(x)"],
    )
    lead = random.choice([
        "Trong Python, phương thức nào sau đây dùng để thêm một phần tử x vào cuối danh sách A?",
        "Để bổ sung một phần tử vào vị trí cuối cùng của danh sách trong Python, ta dùng lệnh nào?",
        "Phương thức chuẩn của kiểu danh sách (list) để chèn phần tử vào cuối là gì?",
    ])
    gt = "Phương thức A.append(x) có sẵn trong kiểu dữ liệu list của Python để thêm phần tử x vào cuối danh sách."
    q = {
        "cau_hoi": lead,
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B23_MCQ_LIST_APPEND", "b23_list_append", "Bài 23", "MCQ", q, verified_explanation=gt)


def _bp_b23_mcq_list_slice() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    nums = random.sample([3, 6, 9, 12, 15, 18], 5)
    code = f"a = {nums}\nsub = a[1:4]\nprint(len(sub))"
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, ["4", "2", "5", "1"])
    gt = f"Cắt lát a[1:4] lấy các phần tử từ chỉ số 1 đến 3 gồm 3 phần tử ({nums[1:4]}) nên len(sub) in ra {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là bao nhiêu?",
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B23_MCQ_LIST_SLICE", "b23_list_slice", "Bài 23", "MCQ", q, out, True, verified_explanation=gt)


def _bp_b23_sa_list_ops() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    base = random.sample([2, 5, 8], 3)
    extra = random.randint(10, 20)
    code = f"A = {base}\nA.append({extra})\nA.remove({base[0]})\nprint(len(A))"
    out = _run_code_get_stdout(code)
    gt = f"Ban đầu A có {len(base)} phần tử, sau append thêm 1 phần tử thành {len(base) + 1}, sau đó remove xóa 1 phần tử nên len(A) bằng {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là bao nhiêu?",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B23_SA_LIST_OPS", "b23_list_ops", "Bài 23", "SHORT_ANSWER", q, out, True, verified_explanation=gt)


def _bp_b23_sa_list_methods() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    nums = random.sample([3, 7, 12, 15, 20], 3)
    add_val = random.randint(25, 40)
    code = f"ds = {nums}\nds.append({add_val})\nx = ds.pop(0)\nprint(len(ds) + ds[-1])"
    out = _run_code_get_stdout(code)
    gt = f"ds ban đầu có 3 phần tử, append({add_val}) thành 4 phần tử, pop(0) xóa phần tử đầu {nums[0]} còn lại 3 phần tử với ds[-1] = {add_val}. Kết quả len(ds) + ds[-1] = 3 + {add_val} = {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là bao nhiêu?",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B23_SA_LIST_METHODS", "b23_list_methods", "Bài 23", "SHORT_ANSWER", q, out, True, verified_explanation=gt)


def _bp_b24_mcq_str_index() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    s = random.choice(["Python", "TinHoc10", "LapTrinh"])
    idx = random.randint(1, len(s) - 2)
    code = f"s = '{s}'\nprint(s[{idx}])"
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, [s[idx - 1], s[idx + 1], s[0]])
    gt = f"Chỉ số xâu kí tự trong Python bắt đầu từ 0. Kí tự tại vị trí s[{idx}] của xâu '{s}' là '{out}'."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là gì?",
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B24_MCQ_STR_INDEX", "b24_str_index", "Bài 24", "MCQ", q, out, True, verified_explanation=gt)


def _bp_b24_mcq_str_len() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    s = random.choice(["Chao_Mung_2026", "Tin_Hoc_10_KNTT", "Lap_Trinh_Python"])
    code = f"s = '{s}'\nprint(len(s))"
    out = _run_code_get_stdout(code)
    val = int(out)
    opts, ans = _shuffle_mcq_options(out, _make_numeric_distractors(val))
    gt = f"Hàm len(s) đếm tổng số kí tự trong xâu '{s}', bao gồm cả chữ cái, chữ số và dấu gạch dưới, thu được {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là bao nhiêu?",
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B24_MCQ_STR_LEN", "b24_str_len", "Bài 24", "MCQ", q, out, True, verified_explanation=gt)


def _bp_b24_tf_str() -> dict:
    sample = random.choice(["TinHoc10", "DaNang2026", "Python10"])
    code = f"s = '{sample}'\nn = len(s)\nprint(n)"
    out = _run_code_get_stdout(code)
    gt_tf = {
        "a": f"Giá trị '{sample}' nằm trong dấu nháy đơn nên biến s có kiểu str.",
        "b": f"Chỉ số 0 là kí tự đầu tiên '{sample[0]}', không phải '{sample[-1]}'.",
        "c": f"Hàm len(s) đếm đủ {out} kí tự trong xâu '{sample}'.",
        "d": "Hàm len() luôn trả về độ dài dạng số nguyên kiểu int.",
    }
    q = {
        "cau_hoi_chung": f"Cho đoạn chương trình Python sau:\n{code}\nXét các phát biểu sau:",
        "a": {
            "menh_de": f"Biến s thuộc kiểu xâu kí tự str với giá trị '{sample}'.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["a"],
        },
        "b": {
            "menh_de": f"Kí tự s[0] của xâu s là '{sample[-1]}'.",
            "dap_an": "Sai",
            "giai_thich": gt_tf["b"],
        },
        "c": {
            "menh_de": f"Kết quả in ra màn hình là {out}.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["c"],
        },
        "d": {
            "menh_de": "Biến n sau khi gọi hàm len(s) thuộc kiểu số thực float.",
            "dap_an": "Sai",
            "giai_thich": gt_tf["d"],
        },
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B24_TF_STR", "b24_tf_str", "Bài 24", "TRUE_FALSE", q, out, True, verified_tf_explanations=gt_tf)


def _bp_b24_tf_str_immutable() -> dict:
    lead_tmpl = random.choice(STEM_TF_LEADINS)
    sample = random.choice(["Python10", "TinHoc2026", "LapTrinhKNTT", "GiaiThuat10"])
    code = f"s = '{sample}'\nkq = s[0] + s[-1]\nprint(kq)"
    out = _run_code_get_stdout(code)
    gt_tf = {
        "a": f"Chỉ số 0 là kí tự đầu tiên '{sample[0]}' và chỉ số -1 là kí tự cuối cùng '{sample[-1]}'.",
        "b": f"Phép cộng hai xâu kí tự s[0] và s[-1] ghép thành '{out}'.",
        "c": "Trong Python, xâu kí tự là kiểu dữ liệu bất biến (immutable) nên lệnh gán thay thế s[0] = 'X' sẽ báo lỗi TypeError.",
        "d": f"Toán tử 'in' dùng để kiểm tra xem một xâu con có xuất hiện trong xâu hay không, ví dụ '{sample[:3]}' in s cho kết quả True.",
    }
    q = {
        "cau_hoi_chung": lead_tmpl.format(code=code),
        "a": {
            "menh_de": f"Kí tự đầu tiên của xâu s là '{sample[0]}' và kí tự cuối cùng là '{sample[-1]}'.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["a"],
        },
        "b": {
            "menh_de": f"Kết quả in ra màn hình là '{out}'.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["b"],
        },
        "c": {
            "menh_de": "Câu lệnh 's[0] = \"X\"' hợp lệ và thay đổi được kí tự đầu tiên của xâu s.",
            "dap_an": "Sai",
            "giai_thich": gt_tf["c"],
        },
        "d": {
            "menh_de": "Toán tử 'in' cho phép kiểm tra sự xuất hiện của xâu con trong xâu kí tự.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["d"],
        },
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B24_TF_STR_IMMUTABLE", "b24_tf_immutable", "Bài 24", "TRUE_FALSE", q, out, True, verified_tf_explanations=gt_tf)


def _bp_b25_mcq_str_find() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    text = random.choice(["Chao_Mung_2026", "Tin_Hoc_10_KNTT", "Lap_Trinh_Python"])
    sub = "10" if "10" in text else ("2026" if "2026" in text else "Trinh")
    code = f"s = '{text}'\nprint(s.find('{sub}'))"
    out = _run_code_get_stdout(code)
    val = int(out)
    opts, ans = _shuffle_mcq_options(out, _make_numeric_distractors(val))
    gt = f"Phương thức find('{sub}') trả về chỉ số xuất hiện đầu tiên (đánh số từ 0) của xâu con '{sub}' trong '{text}', tức là {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là bao nhiêu?",
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B25_MCQ_STR_FIND", "b25_str_find", "Bài 25", "MCQ", q, out, True, verified_explanation=gt)


def _bp_b25_sa_str_find_count() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    CAMPUS_STRINGS = [
        ("TinHoc10_KNTT", "KNTT"),
        ("TinHoc10_KNTT", "Tin"),
        ("DaNang_2026", "2026"),
        ("DaNang_2026", "DaNang"),
        ("LapTrinhPython", "Python"),
        ("LapTrinhPython", "Trinh"),
        ("ThuatToan_AI", "AI"),
        ("ThuatToan_AI", "Thuat"),
        ("KiemTra_HK2", "HK2"),
        ("KiemTra_HK2", "Kiem"),
        ("HaNoi_TinHoc10", "HaNoi"),
        ("HaNoi_TinHoc10", "Tin"),
        ("Python_CanBan", "CanBan"),
        ("HocSinh_Gioi10", "Gioi"),
        ("HocSinh_Gioi10", "Sinh"),
        ("DuLieu_Mang", "Mang"),
        ("BienVaHam_Python", "Ham"),
        ("ChuoiKiTu_Str", "Str"),
        ("GiaiThuat_2026", "2026"),
        ("GiaoDuc_STEM", "STEM"),
        ("TriTue_NhanTao", "NhanTao"),
    ]
    text, sub = random.choice(CAMPUS_STRINGS)
    op = random.choice(["add_len", "add_const", "mul"])
    if op == "add_len":
        code = f"s = '{text}'\nv = s.find('{sub}')\nprint(v + len('{sub}'))"
        out = _run_code_get_stdout(code)
        gt = f"s.find('{sub}') trả về vị trí {text.find(sub)}, cộng thêm độ dài len('{sub}') = {len(sub)} cho kết quả in ra là {out}."
    elif op == "add_const":
        c = random.randint(2, 5)
        code = f"s = '{text}'\nv = s.find('{sub}')\nprint(v + {c})"
        out = _run_code_get_stdout(code)
        gt = f"s.find('{sub}') trả về vị trí {text.find(sub)}, cộng thêm {c} cho kết quả in ra là {out}."
    else:
        code = f"s = '{text}'\nv = s.find('{sub}')\nprint(v * 2)"
        out = _run_code_get_stdout(code)
        gt = f"s.find('{sub}') trả về vị trí {text.find(sub)}, nhân 2 cho kết quả in ra là {out}."

    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là bao nhiêu?",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B25_SA_STR_FIND", "b25_str_find_sa", "Bài 25", "SHORT_ANSWER", q, out, True, verified_explanation=gt)


def _bp_b25_sa_str_split() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    words = random.choice([
        "Tin hoc 10 KNTT",
        "Lap trinh Python co ban",
        "Chu de F Tin 10",
        "Giai thuat va lap trinh",
        "Tri tue nhan tao 2026",
    ])
    code = f"s = '{words}'\nds = s.split()\nprint(len(ds))"
    out = _run_code_get_stdout(code)
    gt = f"Phương thức s.split() tách xâu '{words}' theo dấu cách thành danh sách gồm {out} từ nên len(ds) in ra {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là bao nhiêu?",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B25_SA_STR_SPLIT", "b25_str_split", "Bài 25", "SHORT_ANSWER", q, out, True, verified_explanation=gt)


# ==============================================================================
# NHÓM 4: HÀM, THAM SỐ, PHẠM VI BIẾN & GỠ LỖI (BÀI 26, 27, 28, 29, 30, 31, 32)
# ==============================================================================

def _bp_b26_sa_func_call() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    a_val = random.randint(3, 7)
    b_val = random.randint(2, 5)
    code = (
        f"def tinh_bieu_thuc(x, y):\n"
        f"    return x * 2 + y\n"
        f"kq = tinh_bieu_thuc({a_val}, {b_val})\n"
        f"print(kq)"
    )
    out = _run_code_get_stdout(code)
    gt = f"Lời gọi hàm tinh_bieu_thuc({a_val}, {b_val}) gán x = {a_val}, y = {b_val}. Biểu thức return x * 2 + y tính {a_val} * 2 + {b_val} = {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là bao nhiêu?",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B26_SA_FUNC_CALL", "b26_func_call", "Bài 26", "SHORT_ANSWER", q, out, True, verified_explanation=gt)


def _bp_b26_mcq_return_val() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    a = random.randint(3, 8)
    b = random.randint(2, 6)
    code = f"def tinh(x, y):\n    return x * y - 2\n\nkq = tinh({a}, {b})\nprint(kq)"
    out = _run_code_get_stdout(code)
    val = int(out)
    opts, ans = _shuffle_mcq_options(out, _make_numeric_distractors(val))
    gt = f"Hàm tinh({a}, {b}) thực hiện phép tính return {a} * {b} - 2 = {a * b - 2} = {out} nên lệnh print(kq) in ra {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là bao nhiêu?",
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B26_MCQ_RETURN_VAL", "b26_return_val", "Bài 26", "MCQ", q, out, True, verified_explanation=gt)


def _bp_b26_tf_func_def() -> dict:
    lead_tmpl = random.choice(STEM_TF_LEADINS)
    a_val = random.randint(4, 9)
    b_val = random.randint(2, 6)
    code = (
        f"def tinh_chu_vi(dai, rong):\n"
        f"    return 2 * (dai + rong)\n"
        f"kq = tinh_chu_vi({a_val}, {b_val})\n"
        f"print(kq)"
    )
    out = _run_code_get_stdout(code)
    gt_tf = {
        "a": "Từ khóa def trong Python dùng để bắt đầu khai báo và định nghĩa một hàm mới.",
        "b": "Hàm tinh_chu_vi nhận hai tham số hình thức là dai và rong.",
        "c": f"Lời gọi hàm tinh_chu_vi({a_val}, {b_val}) tính 2 * ({a_val} + {b_val}) = {out} và gán vào biến kq.",
        "d": "Lệnh return dùng để trả về giá trị kết quả của hàm, nếu không có return hàm sẽ trả về None.",
    }
    q = {
        "cau_hoi_chung": lead_tmpl.format(code=code),
        "a": {
            "menh_de": "Từ khóa def dùng để khai báo định nghĩa hàm trong Python.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["a"],
        },
        "b": {
            "menh_de": "Hàm tinh_chu_vi chỉ có một tham số đầu vào duy nhất.",
            "dap_an": "Sai",
            "giai_thich": gt_tf["b"],
        },
        "c": {
            "menh_de": f"Kết quả in ra màn hình là {out}.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["c"],
        },
        "d": {
            "menh_de": "Nếu hàm không có lệnh return thì kết quả trả về của lời gọi hàm là số 0.",
            "dap_an": "Sai",
            "giai_thich": gt_tf["d"],
        },
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B26_TF_FUNC_DEF", "b26_func_def", "Bài 26", "TRUE_FALSE", q, out, True, verified_tf_explanations=gt_tf)


def _bp_b27_mcq_param_arg() -> dict:
    opts, ans = _shuffle_mcq_options(
        "Tham số là biến khai báo ở định nghĩa hàm; đối số là giá trị truyền vào khi gọi hàm",
        [
            "Tham số và đối số hoàn toàn đồng nghĩa và có thể thay thế cho nhau ở mọi vị trí",
            "Đối số là biến khai báo ở định nghĩa hàm; tham số là giá trị truyền vào khi gọi hàm",
            "Tham số chỉ dùng cho hàm có kiểu trả về số thực, đối số chỉ dùng cho kiểu xâu",
        ],
    )
    lead = random.choice([
        "Trong ngôn ngữ lập trình Python, phát biểu nào sau đây phân biệt chính xác giữa 'tham số' và 'đối số'?",
        "Khi làm việc với hàm trong Python, sự khác biệt giữa tham số (parameter) và đối số (argument) là gì?",
        "Khái niệm tham số và đối số của hàm trong Python được định nghĩa đúng như thế nào?",
    ])
    gt = "Tham số (parameter) là các biến được khai báo trong ngoặc đơn sau tên hàm khi định nghĩa; đối số (argument) là các giá trị thực tế truyền vào hàm khi gọi."
    q = {
        "cau_hoi": lead,
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B27_MCQ_PARAM_ARG", "b27_param_arg", "Bài 27", "MCQ", q, verified_explanation=gt)


def _bp_b27_mcq_default_param() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    val = random.randint(3, 7)
    code = f"def chao(n, lap=3):\n    return n * lap\n\nkq = chao({val})\nprint(kq)"
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, _make_numeric_distractors(int(out)))
    gt = f"Lời gọi hàm chao({val}) không truyền tham số thứ hai nên 'lap' nhận giá trị mặc định là 3. Kết quả {val} * 3 = {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là bao nhiêu?",
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B27_MCQ_DEFAULT_PARAM", "b27_def_param", "Bài 27", "MCQ", q, out, True, verified_explanation=gt)


def _bp_b27_tf_param_arg() -> dict:
    lead_tmpl = random.choice(STEM_TF_LEADINS)
    base = random.randint(3, 7)
    code = f"def tinh(x, he_so=2):\n    return x * he_so + 1\n\nkq = tinh({base})\nprint(kq)"
    out = _run_code_get_stdout(code)
    gt_tf = {
        "a": "x là tham số vị trí bắt buộc, he_so là tham số có giá trị mặc định bằng 2.",
        "b": f"Khi gọi tinh({base}), đối số {base} được truyền cho x, he_so nhận giá trị ngầm định 2.",
        "c": f"Kết quả tính toán {base} * 2 + 1 = {out} nên in ra màn hình là {out}.",
        "d": "Trong định nghĩa hàm Python, tham số có giá trị mặc định bắt buộc phải đặt sau các tham số không có giá trị mặc định.",
    }
    q = {
        "cau_hoi_chung": lead_tmpl.format(code=code),
        "a": {
            "menh_de": "Trong hàm tinh, tham số 'he_so' có giá trị mặc định bằng 2.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["a"],
        },
        "b": {
            "menh_de": f"Lời gọi hàm tinh({base}) bắt buộc phải truyền đủ 2 đối số nếu không sẽ báo lỗi.",
            "dap_an": "Sai",
            "giai_thich": gt_tf["b"],
        },
        "c": {
            "menh_de": f"Kết quả in ra màn hình là {out}.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["c"],
        },
        "d": {
            "menh_de": "Trong Python, có thể đặt tham số có giá trị mặc định đứng trước tham số không có giá trị mặc định.",
            "dap_an": "Sai",
            "giai_thich": gt_tf["d"],
        },
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B27_TF_PARAM_ARG", "b27_tf_param", "Bài 27", "TRUE_FALSE", q, out, True, verified_tf_explanations=gt_tf)


def _bp_b28_mcq_scope() -> dict:
    opts, ans = _shuffle_mcq_options(
        "Từ khóa global trước tên biến trong thân hàm",
        [
            "Từ khóa local trước tên biến trong thân hàm",
            "Từ khóa return trước tên biến toàn cục",
            "Từ khóa print trước tên biến trong thân hàm",
        ],
    )
    lead = random.choice([
        "Trong Python, để thay đổi giá trị của một biến toàn cục bên trong thân hàm def, ta cần khai báo bằng từ khóa nào?",
        "Muốn cập nhật giá trị biến toàn cục từ bên trong một hàm, lập trình viên sử dụng từ khóa nào?",
        "Từ khóa nào sau đây cho phép hàm Python ghi đè giá trị lên biến đã khai báo ở phạm vi toàn cục?",
    ])
    gt = "Khai báo global <ten_bien> bên trong hàm cho phép gán và cập nhật trực tiếp biến toàn cục bên ngoài hàm."
    q = {
        "cau_hoi": lead,
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B28_MCQ_SCOPE", "b28_mcq_scope", "Bài 28", "MCQ", q, verified_explanation=gt)


def _bp_b28_sa_scope_local_global() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    val_global = random.randint(10, 20)
    val_local = random.randint(2, 6)
    code = (
        f"n = {val_global}\n"
        f"def cap_nhat():\n"
        f"    n = {val_local}\n"
        f"    return n * 2\n"
        f"cap_nhat()\n"
        f"print(n)"
    )
    out = _run_code_get_stdout(code)
    gt = f"Biến n bên trong hàm cap_nhat là biến cục bộ (local). Biến n toàn cục ở ngoài hàm không bị thay đổi nên lệnh print(n) in ra {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là bao nhiêu?",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B28_SA_SCOPE", "b28_scope_sa", "Bài 28", "SHORT_ANSWER", q, out, True, verified_explanation=gt)


def _bp_b29_mcq_error_classify() -> dict:
    cases = [
        ("ZeroDivisionError", "a = 15\nb = 0\nprint(a / b)", "Chia một số cho 0 khi chương trình đang chạy gây ra ngoại lệ ZeroDivisionError."),
        ("IndexError", "ds = [4, 7, 9]\nprint(ds[5])", "Truy cập chỉ số 5 vượt quá phạm vi chỉ số hợp lệ 0..2 của danh sách gây ra ngoại lệ IndexError."),
        ("NameError", "m = 8\nprint(m + k)", "Biến k chưa từng được gán giá trị trước khi sử dụng nên gây ra ngoại lệ NameError."),
        ("TypeError", "s = 'TinHoc'\nprint(s + 10)", "Thực hiện phép cộng trực tiếp giữa xâu str và số nguyên int gây ra ngoại lệ TypeError."),
    ]
    err_name, buggy_code, gt = random.choice(cases)
    all_errs = ["ZeroDivisionError", "IndexError", "NameError", "TypeError", "SyntaxError"]
    dists = [e for e in all_errs if e != err_name][:3]
    opts, ans = _shuffle_mcq_options(err_name, dists)
    lead = random.choice([
        "Khi chạy đoạn chương trình Python sau, chương trình sẽ báo lỗi gì (loại ngoại lệ nào)?",
        "Quan sát đoạn mã Python dưới đây và cho biết ngoại lệ phát sinh khi chạy là gì?",
        "Đoạn mã sau xảy ra lỗi khi thực thi, đó là loại lỗi nào?",
    ])
    q = {
        "cau_hoi": f"{lead}\n{buggy_code}",
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton(f"B29_MCQ_{err_name.upper()}", f"b29_{err_name.lower()}", "Bài 29", "MCQ", q, verified_explanation=gt)


def _bp_b29_mcq_syntax_vs_logic() -> dict:
    opts, ans = _shuffle_mcq_options(
        "Lỗi logic (ngữ nghĩa)",
        ["Lỗi cú pháp (SyntaxError)", "Lỗi chia cho không (ZeroDivisionError)", "Lỗi tên biến (NameError)"],
    )
    lead = random.choice([
        "Một chương trình Python chạy hết không báo lỗi cú pháp hay ngoại lệ nhưng lại in ra kết quả tính toán sai so với yêu cầu bài toán. Đó là loại lỗi nào?",
        "Hiện tượng chương trình chạy thông suốt nhưng kết quả đầu ra sai lệch với yêu cầu thuật toán là dấu hiệu của loại lỗi gì?",
        "Khi mã nguồn viết đúng quy tắc ngôn ngữ nhưng thuật toán tính sai kết quả, lỗi này thuộc nhóm nào?",
    ])
    gt = "Chương trình chạy bình thường nhưng cho kết quả sai do thuật toán hoặc công thức viết chưa đúng thuộc nhóm lỗi logic (ngữ nghĩa)."
    q = {
        "cau_hoi": lead,
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B29_MCQ_LOGIC_ERR", "b29_logic_err", "Bài 29", "MCQ", q, verified_explanation=gt)


def _bp_b29_tf_error() -> dict:
    code = "a = 12\nb = 4\nkq = a // b\nprint(kq)"
    out = _run_code_get_stdout(code)
    gt_tf = {
        "a": "Các lệnh gán, phép chia nguyên và print đều đúng cú pháp Python với b = 4 khác 0.",
        "b": "Chia cho 0 phát sinh ngoại lệ ZeroDivisionError khi chạy, không phải lỗi cú pháp SyntaxError.",
        "c": f"Phép chia lấy nguyên 12 // 4 trả về {out} nên print(kq) in ra {out}.",
        "d": "Dùng tên biến chưa khai báo phát sinh ngoại lệ NameError, không phải IndexError.",
    }
    q = {
        "cau_hoi_chung": f"Cho đoạn chương trình Python đã kiểm thử và gỡ lỗi sau:\n{code}\nXét các phát biểu về lỗi và kiểm thử sau:",
        "a": {
            "menh_de": "Đoạn chương trình trên viết đúng cú pháp và không phát sinh ngoại lệ khi chạy.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["a"],
        },
        "b": {
            "menh_de": "Nếu thay b = 0 thì chương trình sẽ báo lỗi cú pháp SyntaxError ngay khi thực thi.",
            "dap_an": "Sai",
            "giai_thich": gt_tf["b"],
        },
        "c": {
            "menh_de": f"Kết quả in ra màn hình là {out}.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["c"],
        },
        "d": {
            "menh_de": "Nếu gọi biến chưa khai báo c trong print(c) thì chương trình báo ngoại lệ IndexError.",
            "dap_an": "Sai",
            "giai_thich": gt_tf["d"],
        },
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B29_TF_ERROR", "b29_tf_error", "Bài 29", "TRUE_FALSE", q, out, True, verified_tf_explanations=gt_tf)


def _bp_b29_tf_syntax_vs_runtime() -> dict:
    lead_tmpl = random.choice(STEM_TF_LEADINS)
    a = random.choice([20, 24, 30, 36])
    b = random.choice([3, 4, 6])
    code = f"x = {a}\ny = {b}\nprint(x // y)"
    out = _run_code_get_stdout(code)
    gt_tf = {
        "a": f"Đoạn mã gán số nguyên và thực hiện chia nguyên x // y hợp lệ, không có lỗi cú pháp.",
        "b": "Khi y = 0, phép chia thực thi gây ra ngoại lệ ZeroDivisionError (thuộc nhóm lỗi runtime/ngoại lệ, không phải SyntaxError).",
        "c": f"Kết quả phép chia nguyên {a} // {b} là {out}.",
        "d": "Lỗi cú pháp (SyntaxError) được phát hiện ngay trong giai đoạn biên dịch/dịch trước khi chương trình được chạy thực sự.",
    }
    q = {
        "cau_hoi_chung": lead_tmpl.format(code=code),
        "a": {
            "menh_de": "Đoạn mã trên hoàn toàn hợp lệ về mặt cú pháp và chạy bình thường.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["a"],
        },
        "b": {
            "menh_de": "Nếu thay y = 0, chương trình phát sinh ngoại lệ ZeroDivisionError khi thực thi.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["b"],
        },
        "c": {
            "menh_de": f"Kết quả in ra màn hình là {out}.",
            "dap_an": "Đúng",
            "giai_thich": gt_tf["c"],
        },
        "d": {
            "menh_de": "Lỗi cú pháp SyntaxError chỉ xuất hiện sau khi chương trình đã chạy xong dòng lệnh cuối cùng.",
            "dap_an": "Sai",
            "giai_thich": gt_tf["d"],
        },
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B29_TF_SYNTAX_RUNTIME", "b29_tf_syntax_rt", "Bài 29", "TRUE_FALSE", q, out, True, verified_tf_explanations=gt_tf)


def _bp_b30_mcq_debug_test() -> dict:
    opts, ans = _shuffle_mcq_options(
        "Chạy thử chương trình với nhiều bộ dữ liệu kiểm thử",
        [
            "Xóa toàn bộ câu lệnh print có trong mã nguồn",
            "Đổi tên tệp mã nguồn sang phần mở rộng .txt",
            "Tắt trình thông dịch để bỏ qua các thông báo lỗi",
        ],
    )
    lead = random.choice([
        "Trong quá trình kiểm thử và gỡ lỗi chương trình Python, thao tác nào giúp phát hiện hiệu quả lỗi logic ở các trường hợp biên?",
        "Phương pháp khoa học nhất để xác nhận chương trình Python hoạt động chính xác trong mọi tình huống là gì?",
        "Để đảm bảo chương trình không mắc lỗi logic tiềm ẩn, người lập trình cần thực hiện biện pháp nào?",
    ])
    gt = "Việc chuẩn bị nhiều bộ dữ liệu kiểm thử (gồm dữ liệu thường và dữ liệu biên) giúp phát hiện sớm sai sót logic trong chương trình."
    q = {
        "cau_hoi": lead,
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B30_MCQ_DEBUG_TEST", "b30_debug_test", "Bài 30", "MCQ", q, verified_explanation=gt)


def _bp_b30_mcq_trace_bug() -> dict:
    opts, ans = _shuffle_mcq_options(
        "Chèn thêm các lệnh print() để in giá trị trung gian của biến",
        [
            "Xóa hết các dòng lệnh if và while trong chương trình",
            "Tăng tốc độ xung nhịp CPU của máy tính để bỏ qua lỗi",
            "Thay đổi kiểu dữ liệu của biến sang kiểu xâu str mà không cần lý do",
        ],
    )
    lead = random.choice([
        "Khi thực hiện truy vết (tracing) thủ công để tìm vị trí phát sinh lỗi logic trong chương trình Python, kỹ thuật nào sau đây đơn giản và hiệu quả nhất?",
        "Để theo dõi sự biến đổi giá trị của các biến qua từng bước thực thi trong quá trình gỡ lỗi, ta nên làm gì?",
        "Kỹ thuật gỡ lỗi cơ bản bằng cách quan sát luồng dữ liệu trung gian trong Python là gì?",
    ])
    gt = "Chèn các câu lệnh print() tại các điểm then chốt để in giá trị biến trung gian giúp người lập trình dễ dàng đối chiếu với tính toán trên giấy để tìm lỗi."
    q = {
        "cau_hoi": lead,
        **opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B30_MCQ_TRACE_BUG", "b30_trace_bug", "Bài 30", "MCQ", q, verified_explanation=gt)


def _bp_b30_sa_trace_fixed() -> dict:
    lead = random.choice([
        "Trong quá trình kiểm thử và gỡ lỗi chương trình, học sinh chạy đoạn mã sau:",
        "Khi thực hiện kiểm thử một đoạn mã Python để phát hiện lỗi, chương trình sau được thực thi:",
    ])
    a = random.randint(4, 10)
    b = random.randint(3, 8)
    code = f"a = {a}\nb = {b}\nchu_vi = 2 * (a + b)\nprint(chu_vi)"
    out = _run_code_get_stdout(code)
    gt = f"Công thức chu_vi = 2 * ({a} + {b}) = 2 * {a + b} = {out} đã đúng logic nên kiểm thử in ra {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là bao nhiêu?",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B30_SA_TRACE_FIXED", "b30_trace_fixed", "Bài 30", "SHORT_ANSWER", q, out, True, verified_explanation=gt)


def _bp_b30_sa_trace_correction() -> dict:
    lead = random.choice([
        "Trong quá trình kiểm thử và sửa lỗi logic, đoạn mã Python sau được thực thi:",
        "Sau khi gỡ lỗi và kiểm thử lại chương trình, đoạn mã sau được chạy:",
    ])
    a = random.randint(4, 9)
    b = random.randint(2, 5)
    code = f"# Đã sửa thuật toán hoán đổi\nx = {a}\ny = {b}\nx, y = y, x\nprint(x * 10 + y)"
    out = _run_code_get_stdout(code)
    gt = f"Sau lệnh hoán đổi x, y = y, x: x nhận giá trị {b} và y nhận giá trị {a}. Biểu thức x * 10 + y tính {b} * 10 + {a} = {out}."
    q = {
        "cau_hoi": f"{lead}\n{code}\nKết quả in ra màn hình là bao nhiêu?",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("B30_SA_TRACE_CORR", "b30_trace_corr", "Bài 30", "SHORT_ANSWER", q, out, True, verified_explanation=gt)


# ==============================================================================
# NHÓM 5: BÀI TẬP TỰ LUẬN VIẾT MÃ LẬP TRÌNH (ESSAY_CODE) - XOAY VÒNG ĐA DẠNG
# ==============================================================================

def _bp_ec_temp_filter(bai_hoc: str = "Bài 22") -> dict:
    temps = random.sample([26, 28, 31, 33, 35, 29, 32], 5)
    threshold = 30
    code = (
        f"nhiet_do = {temps}\n"
        f"dem = 0\n"
        f"for t in nhiet_do:\n"
        f"    if t > {threshold}:\n"
        f"        dem += 1\n"
        f"print(dem)"
    )
    out = _run_code_get_stdout(code)
    gt = (
        f"Giải thích thuật toán:\n"
        f"1. Khởi tạo danh sách nhiệt độ nhiet_do = {temps} và biến đếm dem = 0.\n"
        f"2. Sử dụng vòng lặp for duyệt từng giá trị t trong danh sách nhiet_do.\n"
        f"3. Dùng câu lệnh if kiểm tra điều kiện t > {threshold}, nếu đúng thì tăng dem lên 1.\n"
        f"4. Sau khi kết thúc vòng lặp, in giá trị dem ra màn hình ({out}).\n\n"
        f"Tiêu chí chấm điểm:\n"
        f"- Khởi tạo đúng danh sách nhiệt độ và biến đếm ban đầu bằng 0 (0.3đ)\n"
        f"- Sử dụng đúng vòng lặp for và câu lệnh if kiểm tra điều kiện > {threshold} (0.4đ)\n"
        f"- In ra đúng số lượng ngày thỏa mãn ({out} ngày) (0.3đ)"
    )
    q = {
        "tinh_huong": f"Nhiệt độ đo được trong 5 ngày liên tiếp tại một trạm quan trắc là danh sách nhiet_do = {temps} (độ C).",
        "yeu_cau_hoc_sinh": f"Viết chương trình Python đếm và in ra số ngày có nhiệt độ vượt ngưỡng {threshold} độ C.",
        "dap_an_mau": code,
        "giai_thich": gt,
        "tieu_chi_cham_diem": [
            "Khởi tạo đúng danh sách nhiệt độ và biến đếm ban đầu bằng 0 (0.3đ)",
            f"Sử dụng đúng vòng lặp for và câu lệnh if kiểm tra điều kiện > {threshold} (0.4đ)",
            f"In ra đúng số lượng ngày thỏa mãn ({out} ngày) (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_TEMP_FILTER", "ec_temp_filter", bai_hoc, "ESSAY_CODE", q, out, True, verified_explanation=gt)


def _bp_ec_avg_score(bai_hoc: str = "Bài 22") -> dict:
    scores = random.sample([6, 7, 8, 9, 10, 8, 7], 5)
    code = (
        f"diem = {scores}\n"
        f"tong = 0\n"
        f"for d in diem:\n"
        f"    tong += d\n"
        f"tb = round(tong / len(diem), 2)\n"
        f"print(tb)"
    )
    out = _run_code_get_stdout(code)
    gt = (
        f"Giải thích thuật toán:\n"
        f"1. Khởi tạo danh sách điểm diem = {scores} và biến tích lũy tong = 0.\n"
        f"2. Sử dụng vòng lặp for duyệt từng điểm d trong danh sách để cộng dồn vào tong.\n"
        f"3. Tính điểm trung bình bằng tong / len(diem) và dùng hàm round(..., 2) làm tròn 2 chữ số thập phân.\n"
        f"4. In kết quả điểm trung bình ra màn hình ({out}).\n\n"
        f"Tiêu chí chấm điểm:\n"
        f"- Khởi tạo đúng danh sách điểm và biến tổng ban đầu (0.3đ)\n"
        f"- Duyệt các phần tử và tính chính xác tổng điểm của danh sách (0.4đ)\n"
        f"- Chia cho độ dài len(diem) và in kết quả đúng ({out}) (0.3đ)"
    )
    q = {
        "tinh_huong": f"Kết quả kiểm tra môn Tin học của một học sinh được lưu trong danh sách diem = {scores}.",
        "yeu_cau_hoc_sinh": "Viết chương trình Python tính và in ra điểm trung bình của học sinh đó (làm tròn 2 chữ số thập phân).",
        "dap_an_mau": code,
        "giai_thich": gt,
        "tieu_chi_cham_diem": [
            "Khởi tạo đúng danh sách điểm và biến tổng ban đầu (0.3đ)",
            "Duyệt các phần tử và tính chính xác tổng điểm của danh sách (0.4đ)",
            f"Chia cho độ dài len(diem) và in kết quả đúng ({out}) (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_AVG_SCORE", "ec_avg_score", bai_hoc, "ESSAY_CODE", q, out, True, verified_explanation=gt)


def _bp_ec_max_value(bai_hoc: str = "Bài 22") -> dict:
    nums = random.sample([15, 42, 8, 91, 56, 73], 5)
    code = (
        f"A = {nums}\n"
        f"max_val = A[0]\n"
        f"for x in A:\n"
        f"    if x > max_val:\n"
        f"        max_val = x\n"
        f"print(max_val)"
    )
    out = _run_code_get_stdout(code)
    gt = (
        f"Giải thích thuật toán:\n"
        f"1. Khởi tạo danh sách A = {nums} và gán max_val bằng phần tử đầu tiên A[0].\n"
        f"2. Duyệt qua từng phần tử x trong danh sách A bằng vòng lặp for.\n"
        f"3. Dùng lệnh if so sánh: nếu x > max_val thì cập nhật max_val = x.\n"
        f"4. Sau khi duyệt hết danh sách, in giá trị max_val ra màn hình ({out}).\n\n"
        f"Tiêu chí chấm điểm:\n"
        f"- Khởi tạo đúng danh sách A và biến lưu giá trị lớn nhất ban đầu (0.3đ)\n"
        f"- Duyệt từng phần tử và cập nhật giá trị lớn nhất chính xác qua lệnh if (0.4đ)\n"
        f"- In ra giá trị lớn nhất đúng ({out}) (0.3đ)"
    )
    q = {
        "tinh_huong": f"Cho danh sách các số nguyên A = {nums}.",
        "yeu_cau_hoc_sinh": "Viết chương trình Python tìm và in ra giá trị lớn nhất trong danh sách A mà không sử dụng hàm max() có sẵn.",
        "dap_an_mau": code,
        "giai_thich": gt,
        "tieu_chi_cham_diem": [
            "Khởi tạo đúng danh sách A và biến lưu giá trị lớn nhất ban đầu (0.3đ)",
            "Duyệt từng phần tử và cập nhật giá trị lớn nhất chính xác qua lệnh if (0.4đ)",
            f"In ra giá trị lớn nhất đúng ({out}) (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_MAX_VALUE", "ec_max_value", bai_hoc, "ESSAY_CODE", q, out, True, verified_explanation=gt)


def _bp_ec_func_password(bai_hoc: str = "Bài 26") -> dict:
    pwd = random.choice(["Admin2026", "TinHoc10", "PythonKNTT", "Pass1234"])
    code = (
        f"def kiem_tra_mat_khau(s):\n"
        f"    return len(s) >= 8\n"
        f"mk = '{pwd}'\n"
        f"print(kiem_tra_mat_khau(mk))"
    )
    out = _run_code_get_stdout(code)
    gt = (
        f"Giải thích thuật toán:\n"
        f"1. Định nghĩa hàm kiem_tra_mat_khau(s) bằng từ khóa def với tham số hình thức s.\n"
        f"2. Sử dụng biểu thức điều kiện len(s) >= 8 để trả về kết quả True hoặc False qua câu lệnh return.\n"
        f"3. Khởi tạo xâu mk = '{pwd}', gọi hàm kiem_tra_mat_khau(mk) và in kết quả ra màn hình ({out}).\n\n"
        f"Tiêu chí chấm điểm:\n"
        f"- Định nghĩa đúng hàm bằng từ khóa def kèm tham số hình thức (0.3đ)\n"
        f"- Kiểm tra độ dài xâu và trả về kết quả qua lệnh return (0.4đ)\n"
        f"- Gọi hàm và in kết quả chính xác ra màn hình ({out}) (0.3đ)"
    )
    q = {
        "tinh_huong": f"Một hệ thống yêu cầu kiểm tra tính an toàn của mật khẩu người dùng mk = '{pwd}'.",
        "yeu_cau_hoc_sinh": f"Viết hàm kiem_tra_mat_khau(s) trả về True nếu độ dài xâu s >= 8 kí tự, ngược lại trả về False; sau đó gọi hàm kiểm tra với xâu mk = '{pwd}' và in kết quả ra màn hình.",
        "dap_an_mau": code,
        "giai_thich": gt,
        "tieu_chi_cham_diem": [
            "Định nghĩa đúng hàm bằng từ khóa def kèm tham số hình thức (0.3đ)",
            "Kiểm tra độ dài xâu và trả về kết quả qua lệnh return (0.4đ)",
            f"Gọi hàm và in kết quả chính xác ra màn hình ({out}) (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_FUNC_PASSWORD", "ec_func_password", bai_hoc, "ESSAY_CODE", q, out, True, verified_explanation=gt)


def _bp_ec_func_prime_count(bai_hoc: str = "Bài 26") -> dict:
    n_limit = random.choice([15, 20, 25, 30])
    code = (
        f"def la_so_nguyen_to(n):\n"
        f"    if n < 2:\n"
        f"        return False\n"
        f"    for i in range(2, int(n**0.5) + 1):\n"
        f"        if n % i == 0:\n"
        f"            return False\n"
        f"    return True\n"
        f"dem = 0\n"
        f"for x in range(1, {n_limit} + 1):\n"
        f"    if la_so_nguyen_to(x):\n"
        f"        dem += 1\n"
        f"print(dem)"
    )
    out = _run_code_get_stdout(code)
    gt = (
        f"Giải thích thuật toán:\n"
        f"1. Định nghĩa hàm la_so_nguyen_to(n): nếu n < 2 trả về False; duyệt các số i từ 2 đến căn bậc hai của n, nếu n chia hết cho i thì trả về False; ngược lại trả về True.\n"
        f"2. Khởi tạo biến đếm dem = 0; duyệt x từ 1 đến {n_limit} qua vòng lặp for.\n"
        f"3. Nếu la_so_nguyen_to(x) là True thì tăng dem lên 1.\n"
        f"4. In ra số lượng các số nguyên tố ({out}).\n\n"
        f"Tiêu chí chấm điểm:\n"
        f"- Định nghĩa đúng cấu trúc hàm kiểm tra số nguyên tố (0.4đ)\n"
        f"- Duyệt vòng lặp đếm đúng số nguyên tố từ 1 đến {n_limit} (0.3đ)\n"
        f"- In ra kết quả chính xác ({out}) (0.3đ)"
    )
    q = {
        "tinh_huong": f"Yêu cầu thống kê số lượng các số nguyên tố trong phạm vi từ 1 đến {n_limit}.",
        "yeu_cau_hoc_sinh": f"Viết hàm la_so_nguyen_to(n) trả về True nếu n là số nguyên tố, ngược lại trả về False; sau đó đếm và in ra số lượng số nguyên tố trong đoạn từ 1 đến {n_limit}.",
        "dap_an_mau": code,
        "giai_thich": gt,
        "tieu_chi_cham_diem": [
            "Định nghĩa đúng cấu trúc hàm kiểm tra số nguyên tố (0.4đ)",
            f"Duyệt vòng lặp đếm đúng số nguyên tố từ 1 đến {n_limit} (0.3đ)",
            f"In ra kết quả chính xác ({out}) (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_FUNC_PRIME", "ec_func_prime", bai_hoc, "ESSAY_CODE", q, out, True, verified_explanation=gt)


def _bp_ec_func_rect_area(bai_hoc: str = "Bài 26") -> dict:
    a = random.randint(4, 9)
    b = random.randint(3, 7)
    code = (
        f"def tinh_hcn(dai, rong):\n"
        f"    chu_vi = 2 * (dai + rong)\n"
        f"    dien_tich = dai * rong\n"
        f"    return chu_vi, dien_tich\n"
        f"cv, dt = tinh_hcn({a}, {b})\n"
        f"print(cv, dt)"
    )
    out = _run_code_get_stdout(code)
    gt = (
        f"Giải thích thuật toán:\n"
        f"1. Định nghĩa hàm tinh_hcn(dai, rong) nhận 2 tham số hình thức dai và rong.\n"
        f"2. Tính chu vi = 2 * (dai + rong), diện tích = dai * rong và trả về cặp (chu_vi, dien_tich) qua return.\n"
        f"3. Gọi hàm tinh_hcn({a}, {b}) với các giá trị dai = {a}, rong = {b} đã cho và in kết quả ra màn hình ({out}).\n\n"
        f"Tiêu chí chấm điểm:\n"
        f"- Định nghĩa đúng cấu trúc hàm với 2 tham số hình thức dai, rong (0.3đ)\n"
        f"- Tính đúng công thức chu vi và diện tích, trả về qua return (0.4đ)\n"
        f"- Gọi hàm tinh_hcn({a}, {b}) và in ra hai giá trị chính xác ({out}) (0.3đ)"
    )
    q = {
        "tinh_huong": f"Một mảnh vườn hình chữ nhật có chiều dài dai = {a} mét và chiều rộng rong = {b} mét.",
        "yeu_cau_hoc_sinh": f"Viết hàm tinh_hcn(dai, rong) tính chu vi và diện tích hình chữ nhật rồi trả về hai giá trị; sau đó gọi hàm tinh_hcn({a}, {b}) với các giá trị dai = {a}, rong = {b} đã cho và in kết quả ra màn hình.",
        "dap_an_mau": code,
        "giai_thich": gt,
        "tieu_chi_cham_diem": [
            "Định nghĩa đúng cấu trúc hàm với 2 tham số hình thức dai, rong (0.3đ)",
            "Tính đúng công thức chu vi và diện tích, trả về qua return (0.4đ)",
            f"Gọi hàm tinh_hcn({a}, {b}) và in ra hai giá trị chính xác ({out}) (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_FUNC_RECT", "ec_func_rect", bai_hoc, "ESSAY_CODE", q, out, True, verified_explanation=gt)


def _bp_ec_min_and_count_div5(bai_hoc: str = "Bài 31") -> dict:
    nums = random.sample([10, 15, 7, 25, 33, 40, 12, 5], 6)
    code = (
        f"ds = {nums}\n"
        f"dem = 0\n"
        f"min_val = ds[0]\n"
        f"for x in ds:\n"
        f"    if x % 5 == 0:\n"
        f"        dem += 1\n"
        f"    if x < min_val:\n"
        f"        min_val = x\n"
        f"print(dem, min_val)"
    )
    out = _run_code_get_stdout(code)
    gt = (
        f"Giải thích thuật toán:\n"
        f"1. Khởi tạo danh sách ds = {nums}, biến đếm dem = 0 và min_val = ds[0].\n"
        f"2. Duyệt từng phần tử x trong ds: nếu x % 5 == 0 thì tăng dem lên 1; nếu x < min_val thì cập nhật min_val = x.\n"
        f"3. In ra hai giá trị đếm và giá trị nhỏ nhất ({out}).\n\n"
        f"Tiêu chí chấm điểm:\n"
        f"- Khởi tạo đúng danh sách ds và các biến lưu trữ ban đầu (0.3đ)\n"
        f"- Duyệt vòng lặp, kiểm tra đúng điều kiện chia hết cho 5 và cập nhật min (0.4đ)\n"
        f"- In ra kết quả chính xác theo yêu cầu ({out}) (0.3đ)"
    )
    q = {
        "tinh_huong": f"Cho một danh sách các số nguyên ds = {nums}.",
        "yeu_cau_hoc_sinh": "Viết chương trình Python duyệt danh sách ds để đếm số phần tử chia hết cho 5 và tìm giá trị nhỏ nhất trong danh sách; sau đó in hai kết quả ra màn hình.",
        "dap_an_mau": code,
        "giai_thich": gt,
        "tieu_chi_cham_diem": [
            "Khởi tạo đúng danh sách ds và các biến lưu trữ ban đầu (0.3đ)",
            "Duyệt vòng lặp, kiểm tra đúng điều kiện chia hết cho 5 và cập nhật min (0.4đ)",
            f"In ra kết quả chính xác theo yêu cầu ({out}) (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_MIN_DIV5", "ec_min_div5", bai_hoc, "ESSAY_CODE", q, out, True, verified_explanation=gt)


def _bp_ec_str_count_digits(bai_hoc: str = "Bài 31") -> dict:
    code_str = random.choice(["HS2026_K10A1", "PY9876_VN", "CNTT10_2025", "DANANG2026"])
    code = (
        f"s = '{code_str}'\n"
        f"dem = 0\n"
        f"for ch in s:\n"
        f"    if ch.isdigit():\n"
        f"        dem += 1\n"
        f"print(dem)"
    )
    out = _run_code_get_stdout(code)
    gt = (
        f"Giải thích thuật toán:\n"
        f"1. Khởi tạo xâu s = '{code_str}' và biến đếm dem = 0.\n"
        f"2. Duyệt từng kí tự ch trong xâu s bằng vòng lặp for.\n"
        f"3. Dùng phương thức ch.isdigit() kiểm tra xem kí tự có phải là chữ số hay không, nếu đúng thì tăng dem lên 1.\n"
        f"4. In ra tổng số chữ số có trong xâu ({out}).\n\n"
        f"Tiêu chí chấm điểm:\n"
        f"- Khởi tạo xâu s và biến đếm ban đầu (0.3đ)\n"
        f"- Duyệt từng kí tự và kiểm tra đúng kí tự chữ số bằng isdigit() (0.4đ)\n"
        f"- In ra số lượng chữ số chính xác ({out}) (0.3đ)"
    )
    q = {
        "tinh_huong": f"Một chuỗi mã định danh học sinh được lưu trong xâu s = '{code_str}'.",
        "yeu_cau_hoc_sinh": f"Viết chương trình Python đếm và in ra số lượng kí tự là chữ số xuất hiện trong xâu s = '{code_str}'.",
        "dap_an_mau": code,
        "giai_thich": gt,
        "tieu_chi_cham_diem": [
            "Khởi tạo xâu s và biến đếm ban đầu (0.3đ)",
            "Duyệt từng kí tự và kiểm tra đúng kí tự chữ số bằng isdigit() (0.4đ)",
            f"In ra số lượng chữ số chính xác ({out}) (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_STR_DIGITS", "ec_str_digits", bai_hoc, "ESSAY_CODE", q, out, True, verified_explanation=gt)


def _bp_ec_while_sum_limit(bai_hoc: str = "Bài 21") -> dict:
    target = random.choice([50, 70, 100, 120])
    code = (
        f"S = 0\n"
        f"k = 1\n"
        f"while S <= {target}:\n"
        f"    S += k\n"
        f"    k += 1\n"
        f"print(k - 1, S)"
    )
    out = _run_code_get_stdout(code)
    gt = (
        f"Giải thích thuật toán:\n"
        f"1. Khởi tạo tổng S = 0 và số nguyên dương k = 1.\n"
        f"2. Sử dụng vòng lặp while với điều kiện S <= {target}: mỗi bước cộng dồn S += k và tăng k += 1.\n"
        f"3. Vòng lặp dừng lại ngay khi S vượt quá {target}. Lúc này số nguyên cuối cùng vừa cộng vào là k - 1.\n"
        f"4. In ra giá trị k - 1 và tổng S ({out}).\n\n"
        f"Tiêu chí chấm điểm:\n"
        f"- Khởi tạo đúng biến tổng S = 0 và biến đếm k = 1 (0.3đ)\n"
        f"- Xây dựng đúng vòng lặp while kiểm tra điều kiện S <= {target} và tăng k (0.4đ)\n"
        f"- In ra đúng giá trị k - 1 và tổng S ({out}) (0.3đ)"
    )
    q = {
        "tinh_huong": f"Cần tìm số nguyên dương k nhỏ nhất sao cho tổng 1 + 2 + ... + k vượt ngưỡng {target}.",
        "yeu_cau_hoc_sinh": f"Viết chương trình Python dùng vòng lặp while để tìm và in ra giá trị k đó cùng với tổng tích lũy đạt được khi vượt ngưỡng {target}.",
        "dap_an_mau": code,
        "giai_thich": gt,
        "tieu_chi_cham_diem": [
            "Khởi tạo đúng biến tổng S = 0 và biến đếm k = 1 (0.3đ)",
            f"Xây dựng đúng vòng lặp while kiểm tra điều kiện S <= {target} và tăng k (0.4đ)",
            f"In ra đúng giá trị k - 1 và tổng S ({out}) (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_WHILE_LIMIT", "ec_while_limit", bai_hoc, "ESSAY_CODE", q, out, True, verified_explanation=gt)


def _bp_ec_safe_div_debug(bai_hoc: str = "Bài 29") -> dict:
    nums = random.sample([12, 18, 24, 30, 36], 4)
    code = (
        f"ds = {nums}\n"
        f"so_chia = 2\n"
        f"if so_chia != 0:\n"
        f"    kq = sum(ds) / so_chia\n"
        f"    print(kq)\n"
        f"else:\n"
        f"    print('Khong chia duoc cho 0')"
    )
    out = _run_code_get_stdout(code)
    gt = (
        f"Giải thích thuật toán:\n"
        f"1. Khởi tạo danh sách ds = {nums} và biến so_chia = 2.\n"
        f"2. Sử dụng cấu trúc rẽ nhánh if so_chia != 0 để phòng ngừa ngoại lệ ZeroDivisionError trước khi thực hiện phép tính.\n"
        f"3. Nếu so_chia != 0: tính kết quả kq = sum(ds) / so_chia và in kq ra màn hình ({out}). Ngược lại in thông báo lỗi.\n\n"
        f"Tiêu chí chấm điểm:\n"
        f"- Khởi tạo đúng danh sách ds và kiểm tra điều kiện khác 0 tránh ZeroDivisionError (0.4đ)\n"
        f"- Tính chính xác kết quả phép chia khi hợp lệ (0.3đ)\n"
        f"- In kết quả kiểm thử chính xác ({out}), chạy không lỗi (0.3đ)"
    )
    q = {
        "tinh_huong": f"Để kiểm thử và phòng tránh ngoại lệ ZeroDivisionError khi chia tổng danh sách ds = {nums} cho số chia = 2.",
        "yeu_cau_hoc_sinh": "Viết chương trình Python kiểm tra điều kiện số chia khác 0 trước khi thực hiện phép chia và in kết quả kiểm thử ra màn hình.",
        "dap_an_mau": code,
        "giai_thich": gt,
        "tieu_chi_cham_diem": [
            "Khởi tạo đúng danh sách ds và kiểm tra điều kiện khác 0 tránh ZeroDivisionError (0.4đ)",
            "Tính chính xác kết quả phép chia khi hợp lệ (0.3đ)",
            f"In kết quả kiểm thử chính xác ({out}), chạy không lỗi (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_SAFE_DIV_DEBUG", "ec_safe_div_debug", bai_hoc, "ESSAY_CODE", q, out, True, verified_explanation=gt)


def _bp_ec_electricity_bill(bai_hoc: str = "Bài 19") -> dict:
    kwh = random.choice([60, 75, 90, 110, 130])
    code = (
        f"so_kwh = {kwh}\n"
        f"if so_kwh <= 50:\n"
        f"    tien = so_kwh * 1700\n"
        f"else:\n"
        f"    tien = 50 * 1700 + (so_kwh - 50) * 2000\n"
        f"print(tien)"
    )
    out = _run_code_get_stdout(code)
    gt = (
        f"Giải thích thuật toán:\n"
        f"1. Khởi tạo biến so_kwh = {kwh}.\n"
        f"2. Sử dụng cấu trúc rẽ nhánh if-else phân loại bậc thang điện sinh hoạt:\n"
        f"   - Nếu so_kwh <= 50: số tiền tính là so_kwh * 1700.\n"
        f"   - Ngược lại: 50 kWh đầu tính 50 * 1700, các kWh vượt tính (so_kwh - 50) * 2000.\n"
        f"3. In ra số tiền điện phải trả ({out} đồng).\n\n"
        f"Tiêu chí chấm điểm:\n"
        f"- Khởi tạo đúng biến so_kwh ban đầu (0.2đ)\n"
        f"- Xây dựng đúng điều kiện rẽ nhánh if-else phân loại bậc thang (0.4đ)\n"
        f"- Tính chính xác số tiền theo từng mức và in ra màn hình ({out} đồng) (0.4đ)"
    )
    q = {
        "tinh_huong": f"Một hộ gia đình tiêu thụ hết so_kwh = {kwh} kWh điện sinh hoạt trong tháng. Giá điện tính theo bậc thang: 50 kWh đầu giá 1700 đồng/kWh; các kWh từ 51 trở đi giá 2000 đồng/kWh.",
        "yeu_cau_hoc_sinh": "Viết chương trình Python sử dụng cấu trúc rẽ nhánh if-else để tính và in ra số tiền điện phải trả của hộ gia đình đó.",
        "dap_an_mau": code,
        "giai_thich": gt,
        "tieu_chi_cham_diem": [
            "Khởi tạo đúng biến so_kwh ban đầu (0.2đ)",
            "Xây dựng đúng điều kiện rẽ nhánh if-else phân loại bậc thang (0.4đ)",
            f"Tính chính xác số tiền theo từng mức và in ra màn hình ({out} đồng) (0.4đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_ELECTRICITY_BILL", "ec_elec_bill", bai_hoc, "ESSAY_CODE", q, out, True, verified_explanation=gt)


def _bp_ec_count_char_frequency(bai_hoc: str = "Bài 24") -> dict:
    names = random.choice([
        ("Nguyen Van An", "a"),
        ("Tran Thi Mai", "i"),
        ("Le Hoang Nam", "a"),
        ("Pham Quoc Bao", "o"),
    ])
    text, target_ch = names
    code = (
        f"s = '{text}'\n"
        f"dem = 0\n"
        f"for ch in s.lower():\n"
        f"    if ch == '{target_ch}':\n"
        f"        dem += 1\n"
        f"print(dem)"
    )
    out = _run_code_get_stdout(code)
    gt = (
        f"Giải thích thuật toán:\n"
        f"1. Khởi tạo xâu s = '{text}' và biến đếm dem = 0.\n"
        f"2. Chuyển xâu về chữ thường s.lower() và duyệt từng kí tự ch bằng vòng lặp for.\n"
        f"3. Dùng câu lệnh if so sánh ch == '{target_ch}', nếu đúng tăng dem lên 1.\n"
        f"4. In ra số lần xuất hiện của kí tự '{target_ch}' trong xâu ({out}).\n\n"
        f"Tiêu chí chấm điểm:\n"
        f"- Khởi tạo xâu s và biến đếm ban đầu (0.3đ)\n"
        f"- Duyệt từng kí tự qua vòng lặp for và so sánh chuẩn xác với kí tự '{target_ch}' (0.4đ)\n"
        f"- In ra số lần xuất hiện chính xác ({out}) (0.3đ)"
    )
    q = {
        "tinh_huong": f"Cho một xâu họ tên học sinh s = '{text}'.",
        "yeu_cau_hoc_sinh": f"Viết chương trình Python đếm số lần xuất hiện của kí tự '{target_ch}' (không phân biệt chữ hoa, chữ thường) trong xâu s và in kết quả ra màn hình.",
        "dap_an_mau": code,
        "giai_thich": gt,
        "tieu_chi_cham_diem": [
            "Khởi tạo xâu s và biến đếm ban đầu (0.3đ)",
            f"Duyệt từng kí tự qua vòng lặp for và so sánh chuẩn xác với kí tự '{target_ch}' (0.4đ)",
            f"In ra số lần xuất hiện chính xác ({out}) (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_COUNT_CHAR", "ec_count_char", bai_hoc, "ESSAY_CODE", q, out, True, verified_explanation=gt)


def _bp_ec_even_odd_split(bai_hoc: str = "Bài 23") -> dict:
    nums = random.sample([4, 7, 12, 15, 18, 23, 26], 6)
    code = (
        f"ds = {nums}\n"
        f"chan = []\n"
        f"for x in ds:\n"
        f"    if x % 2 == 0:\n"
        f"        chan.append(x)\n"
        f"print(len(chan), sum(chan))"
    )
    out = _run_code_get_stdout(code)
    gt = (
        f"Giải thích thuật toán:\n"
        f"1. Khởi tạo danh sách ds = {nums} và danh sách rỗng chan = [].\n"
        f"2. Duyệt từng phần tử x trong ds qua vòng lặp for.\n"
        f"3. Dùng câu lệnh if x % 2 == 0 kiểm tra số chẵn, nếu thỏa mãn thì thêm vào danh sách chan bằng chan.append(x).\n"
        f"4. In ra số lượng phần tử len(chan) và tổng các số chẵn sum(chan) ({out}).\n\n"
        f"Tiêu chí chấm điểm:\n"
        f"- Khởi tạo đúng danh sách ban đầu ds và danh sách rỗng chan = [] (0.3đ)\n"
        f"- Duyệt danh sách và dùng append() thêm các số chẵn thỏa mãn x % 2 == 0 (0.4đ)\n"
        f"- In ra số lượng và tổng các số chẵn chính xác ({out}) (0.3đ)"
    )
    q = {
        "tinh_huong": f"Một danh sách các số nguyên được cho trước là ds = {nums}.",
        "yeu_cau_hoc_sinh": "Viết chương trình Python duyệt danh sách ds, thêm các số chẵn vào một danh sách mới tên là chan, sau đó in ra số lượng và tổng của các số chẵn đó.",
        "dap_an_mau": code,
        "giai_thich": gt,
        "tieu_chi_cham_diem": [
            "Khởi tạo đúng danh sách ban đầu ds và danh sách rỗng chan = [] (0.3đ)",
            "Duyệt danh sách và dùng append() thêm các số chẵn thỏa mãn x % 2 == 0 (0.4đ)",
            f"In ra số lượng và tổng các số chẵn chính xác ({out}) (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_EVEN_ODD_SPLIT", "ec_even_odd", bai_hoc, "ESSAY_CODE", q, out, True, verified_explanation=gt)


def _bp_b21_tf_wrap() -> dict:
    return _bp_b21_tf_while()


# ==============================================================================
# BẢNG ĐĂNG KÝ BLUEPRINT MỞ RỘNG (155 BLUEPRINTS PHỦ ĐỦ 17 BÀI × 4 DẠNG)
# ==============================================================================

def _build_registry() -> dict[tuple[int, str], list[Callable[[], dict]]]:
    """Ánh xạ đầy đủ mọi cặp (so_bai, loai_cau_hoi) sang danh sách hàm sinh khung tham số hóa gốc (không gán chéo bài học)."""
    reg: dict[tuple[int, str], list[Callable[[], dict]]] = {
        # Bài 16
        (16, "MCQ"): [_bp_b16_mcq_script_mode, _bp_b16_mcq_high_level, _bp_b16_mcq_print_expr],

        # Bài 17
        (17, "MCQ"): [_bp_b17_mcq_valid_var, _bp_b17_mcq_assign_valid],
        (17, "SHORT_ANSWER"): [_bp_b17_sa_div_mod, _bp_b17_sa_swap_update],

        # Bài 18
        (18, "MCQ"): [_bp_b18_mcq_type_cast, _bp_b18_mcq_int_print],
        (18, "TRUE_FALSE"): [_bp_b18_tf_io, _bp_b18_tf_input_cast],
        (18, "SHORT_ANSWER"): [_bp_b18_sa_cast_calc],

        # Bài 19
        (19, "MCQ"): [_bp_b19_mcq_if_elif, _bp_b19_mcq_logic_expr],
        (19, "TRUE_FALSE"): [_bp_b19_tf_branch],
        (19, "SHORT_ANSWER"): [_bp_b19_sa_branch, _bp_b19_sa_elif_grade],
        (19, "ESSAY_CODE"): [_bp_ec_electricity_bill],

        # Bài 20
        (20, "MCQ"): [_bp_b20_mcq_for_sum, _bp_b20_mcq_for_count_mult3],
        (20, "TRUE_FALSE"): [_bp_b20_tf_for_range],
        (20, "SHORT_ANSWER"): [_bp_b20_sa_for_odd_sum, _bp_b20_sa_for_if_sum],

        # Bài 21
        (21, "MCQ"): [_bp_b21_mcq_while_condition, _bp_b21_mcq_while_steps],
        (21, "TRUE_FALSE"): [_bp_b21_tf_while, _bp_b21_tf_while_condition],
        (21, "SHORT_ANSWER"): [_bp_b21_sa_while_acc],
        (21, "ESSAY_CODE"): [_bp_ec_while_sum_limit],

        # Bài 22
        (22, "MCQ"): [_bp_b22_mcq_list_index, _bp_b22_mcq_list_modify],
        (22, "TRUE_FALSE"): [_bp_b22_tf_list_indexing_slice, _bp_b22_tf_list_filter],
        (22, "ESSAY_CODE"): [_bp_ec_avg_score, _bp_ec_temp_filter, _bp_ec_max_value],

        # Bài 23
        (23, "MCQ"): [_bp_b23_mcq_list_append, _bp_b23_mcq_list_slice],
        (23, "SHORT_ANSWER"): [_bp_b23_sa_list_ops, _bp_b23_sa_list_methods],
        (23, "ESSAY_CODE"): [_bp_ec_even_odd_split],

        # Bài 24
        (24, "MCQ"): [_bp_b24_mcq_str_len, _bp_b24_mcq_str_index],
        (24, "TRUE_FALSE"): [_bp_b24_tf_str, _bp_b24_tf_str_immutable],
        (24, "ESSAY_CODE"): [_bp_ec_count_char_frequency],

        # Bài 25
        (25, "MCQ"): [_bp_b25_mcq_str_find],
        (25, "SHORT_ANSWER"): [_bp_b25_sa_str_find_count, _bp_b25_sa_str_split],

        # Bài 26
        (26, "MCQ"): [_bp_b26_mcq_return_val],
        (26, "TRUE_FALSE"): [_bp_b26_tf_func_def],
        (26, "SHORT_ANSWER"): [_bp_b26_sa_func_call],
        (26, "ESSAY_CODE"): [_bp_ec_func_rect_area, _bp_ec_func_password, _bp_ec_func_prime_count],

        # Bài 27
        (27, "MCQ"): [_bp_b27_mcq_param_arg, _bp_b27_mcq_default_param],
        (27, "TRUE_FALSE"): [_bp_b27_tf_param_arg],

        # Bài 28
        (28, "MCQ"): [_bp_b28_mcq_scope],
        (28, "SHORT_ANSWER"): [_bp_b28_sa_scope_local_global],

        # Bài 29
        (29, "MCQ"): [_bp_b29_mcq_error_classify, _bp_b29_mcq_syntax_vs_logic],
        (29, "TRUE_FALSE"): [_bp_b29_tf_error, _bp_b29_tf_syntax_vs_runtime],
        (29, "ESSAY_CODE"): [_bp_ec_safe_div_debug],

        # Bài 30
        (30, "MCQ"): [_bp_b30_mcq_trace_bug, _bp_b30_mcq_debug_test],
        (30, "SHORT_ANSWER"): [_bp_b30_sa_trace_correction, _bp_b30_sa_trace_fixed],

        # Bài 31
        (31, "ESSAY_CODE"): [_bp_ec_min_and_count_div5, _bp_ec_str_count_digits],
    }

    # Tích hợp toàn bộ blueprint mở rộng từ core/symbolic_blueprints_ext.py
    try:
        from core.symbolic_blueprints_ext import EXT_REGISTRY_ENTRIES
        for key, fns in EXT_REGISTRY_ENTRIES.items():
            if key in reg:
                reg[key].extend(fns)
            else:
                reg[key] = list(fns)
    except Exception as e:
        print(f"   ⚠️ Lỗi khi nạp symbolic_blueprints_ext: {e}", flush=True)

    return reg


def list_blueprints() -> list[dict]:
    """Trả về danh sách siêu dữ liệu của toàn bộ các blueprint độc nhất trong engine."""
    reg = _build_registry()
    unique_bps = {}
    for (lesson, loai), fns in reg.items():
        for fn in fns:
            try:
                bp = fn()
                bp_id = bp.get("blueprint_id")
                if bp_id and bp_id not in unique_bps:
                    unique_bps[bp_id] = {
                        "blueprint_id": bp_id,
                        "bai_hoc": bp.get("bai_hoc"),
                        "loai_cau_hoi": bp.get("loai_cau_hoi"),
                        "motif_tag": bp.get("motif_tag"),
                    }
            except Exception:
                pass
    return list(unique_bps.values())


# ==============================================================================
# BỘ SINH KHUNG CÂU HỎI & ĐÁP ÁN (NEURO-SYMBOLIC VERIFIED SKELETON)
# ==============================================================================

def build_verified_skeleton(
    bai_hoc: str,
    loai_cau_hoi: str,
    muc_do: str = "TH",
    used_blueprint_ids: set[str] | None = None,
    recent_blueprint_ids: set[str] | list[str] | None = None,
    chu_de_chi_tiet: str = "",
) -> dict[str, Any]:
    """
    Sinh khung câu hỏi & đáp án đã kiểm chứng toán học/Sandbox 100% theo kiến trúc Neuro-Symbolic.
    Ưu tiên bốc thăm không hoàn lại theo blueprint_id trong cùng một đề (used_blueprint_ids),
    đồng thời chống lặp xuyên đề bằng cách ưu tiên bốc các blueprint KHÔNG nằm trong recent_blueprint_ids.
    Tuyệt đối không gán nhãn bài học giả; giữ nguyên bài học gốc của blueprint đã bốc.
    """
    lesson_num = _normalize_lesson_num(bai_hoc)
    norm_lesson = f"Bài {lesson_num}"
    loai = str(loai_cau_hoi or "MCQ").strip().upper()
    used = used_blueprint_ids if isinstance(used_blueprint_ids, set) else set()
    recent = set(recent_blueprint_ids) if isinstance(recent_blueprint_ids, (set, list)) else set()

    registry = _build_registry()

    candidates = list(registry.get((lesson_num, loai), []))
    if not candidates:
        fallback_by_type: dict[str, list[Callable[[], dict]]] = {
            "MCQ": [_bp_b19_mcq_if_elif, _bp_b20_mcq_for_sum, _bp_b22_mcq_list_index, _bp_b24_mcq_str_index, _bp_b26_mcq_return_val],
            "TRUE_FALSE": [_bp_b18_tf_input_cast, _bp_b19_tf_branch, _bp_b20_tf_for_range, _bp_b21_tf_while_condition, _bp_b22_tf_list_indexing_slice, _bp_b24_tf_str_immutable, _bp_b26_tf_func_def, _bp_b29_tf_syntax_vs_runtime],
            "SHORT_ANSWER": [_bp_b17_sa_div_mod, _bp_b19_sa_elif_grade, _bp_b20_sa_for_if_sum, _bp_b21_sa_while_acc, _bp_b23_sa_list_methods, _bp_b26_sa_func_call, _bp_b30_sa_trace_correction],
            "ESSAY_CODE": [
                _bp_ec_temp_filter,
                _bp_ec_avg_score,
                _bp_ec_max_value,
                _bp_ec_min_and_count_div5,
                _bp_ec_str_count_digits,
                _bp_ec_electricity_bill,
                _bp_ec_count_char_frequency,
                _bp_ec_even_odd_split,
            ],
        }
        candidates = fallback_by_type.get(loai, [_bp_b19_mcq_if_elif])

    random.shuffle(candidates)

    fresh_packs: list[dict[str, Any]] = []
    fallback_packs: list[dict[str, Any]] = []
    any_packs: list[dict[str, Any]] = []

    for fn in candidates:
        try:
            pack = fn()
            bp_id = pack["blueprint_id"]
            any_packs.append(pack)
            if bp_id not in used:
                fallback_packs.append(pack)
                if bp_id not in recent:
                    fresh_packs.append(pack)
        except Exception as e:
            print(f"   ⚠️ Lỗi khi sinh blueprint {fn}: {e}", flush=True)

    if fresh_packs:
        chosen_pack = random.choice(fresh_packs)
    elif fallback_packs:
        chosen_pack = random.choice(fallback_packs)
    else:
        # Cặp (lesson_num, loai) đã hết blueprint chưa dùng trong đề này:
        # Tìm trên toàn bộ các bài học khác trong registry có blueprint của loại này chưa dùng
        global_fresh = []
        global_fallback = []
        for (l_other, t_other), fns in registry.items():
            if t_other == loai and l_other != lesson_num:
                for fn in fns:
                    try:
                        p = fn()
                        bid = p["blueprint_id"]
                        if bid not in used:
                            if bid not in recent:
                                global_fresh.append(p)
                            else:
                                global_fallback.append(p)
                    except Exception:
                        pass
        if global_fresh:
            chosen_pack = random.choice(global_fresh)
        elif global_fallback:
            chosen_pack = random.choice(global_fallback)
        elif any_packs:
            chosen_pack = random.choice(any_packs)
        else:
            chosen_pack = candidates[0]()

    return chosen_pack
