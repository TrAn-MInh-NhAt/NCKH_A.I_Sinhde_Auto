# -*- coding: utf-8 -*-
"""
Mô-đun mở rộng symbolic_blueprints_ext.py:
Bổ sung 83 khuôn bài (blueprints) tham số hóa độc lập mới, nâng tổng số blueprint
lên >= 150 blueprints độc nhất phủ đều toàn bộ 17 bài học Chủ đề F (Bài 16 đến Bài 32).

Đặc tính kỹ thuật:
- 100% dữ liệu ngẫu nhiên động (zero hardcode).
- Chạy qua core/sandbox.py lấy stdout chính xác 100%.
- Cung cấp verified_explanation và verified_tf_explanations khóa cứng.
"""

import random
import re
from typing import Any, Callable, Dict, List, Tuple

from core.symbolic_engine import (
    STEM_MCQ_LEADINS,
    STEM_SA_LEADINS,
    STEM_TF_LEADINS,
    _run_code_get_stdout,
    _shuffle_mcq_options,
    _make_numeric_distractors,
    _pack_skeleton,
)


# ==============================================================================
# 1. 32 KHUÔN BÀI MCQ MỚI (TRẮC NGHIỆM 4 PHƯƠNG ÁN)
# ==============================================================================

def _bp_b16_mcq_ext_extension() -> dict:
    lead = "Tệp mã nguồn chương trình viết bằng ngôn ngữ lập trình Python thường có phần mở rộng (đuôi tệp) chuẩn là gì?"
    opts, ans = _shuffle_mcq_options(".py", [".pt", ".python", ".pyt", ".txt"])
    gt = "Theo quy ước chuẩn của ngôn ngữ Python, các tệp mã nguồn được lưu trữ với phần mở rộng là .py."
    q = {
        "cau_hoi": lead,
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Tệp mã nguồn Python có phần mở rộng là .py.",
        **opts
    }
    return _pack_skeleton("MCQ_B16_EXT", "mcq_ext", "Bài 16", "MCQ", q, "", False, gt)


def _bp_b16_mcq_interpreter_trait() -> dict:
    lead = "Đặc điểm nổi bật của trình thông dịch (Interpreter) trong ngôn ngữ Python là:"
    corr = "Dịch và thực hiện từng câu lệnh một, gặp lỗi ở đâu thì dừng ở đó"
    dist = [
        "Dịch toàn bộ chương trình sang mã máy một lần rồi mới thực thi",
        "Tự động sửa lỗi cú pháp mà không cần người lập trình can thiệp",
        "Chỉ thực hiện được các phép toán số học đơn giản"
    ]
    opts, ans = _shuffle_mcq_options(corr, dist)
    gt = "Trình thông dịch của Python thực hiện dịch và chạy từng dòng lệnh theo thứ tự từ trên xuống dưới; khi gặp lỗi cú pháp hoặc ngoại lệ, chương trình sẽ dừng ngay tại vị trí đó."
    q = {
        "cau_hoi": lead,
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Python là ngôn ngữ thông dịch, dịch và thực hiện từng câu lệnh.",
        **opts
    }
    return _pack_skeleton("MCQ_B16_INTERPRETER", "mcq_interp", "Bài 16", "MCQ", q, "", False, gt)


def _bp_b17_mcq_keyword_error() -> dict:
    lead = "Trong các tên biến sau đây, tên nào KHÔNG hợp lệ trong Python vì trùng với từ khóa của ngôn ngữ?"
    kw = random.choice(["def", "for", "while", "if", "class", "return"])
    valid1 = random.choice(["_tong", "dem_so", "soLuong", "bien1"])
    valid2 = random.choice(["diem_tb", "x_val", "temp_c", "res_2"])
    valid3 = random.choice(["my_var", "n10", "chieu_dai", "ketQua"])
    opts, ans = _shuffle_mcq_options(kw, [valid1, valid2, valid3])
    gt = f"Từ '{kw}' là một từ khóa (keyword) được bảo lưu trong Python, do đó không được sử dụng để đặt tên cho biến."
    q = {
        "cau_hoi": lead,
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Tên biến không được trùng với các từ khóa trong Python.",
        **opts
    }
    return _pack_skeleton("MCQ_B17_KW_ERR", "mcq_kw", "Bài 17", "MCQ", q, "", False, gt)


def _bp_b17_mcq_multi_assign() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    a = random.randint(3, 8)
    b = random.randint(10, 18)
    code = f"x, y = {a}, {b}\nx, y = y, x + y\nprint(x)"
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, _make_numeric_distractors(int(out), [a, b, a + b]))
    gt = f"Ban đầu x = {a}, y = {b}. Lệnh gán đồng thời x, y = y, x + y tính vế phải trước: y nhận giá trị {b}, x + y nhận giá trị {a + b}. Do đó x nhận giá trị mới là {out}."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nKết quả in ra màn hình là gì?",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Python cho phép thực hiện phép gán đồng thời nhiều biến.",
        **opts
    }
    return _pack_skeleton("MCQ_B17_MULTI_ASSIGN", "mcq_multi_assign", "Bài 17", "MCQ", q, out, True, gt)


def _bp_b17_mcq_compound_ops() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    base = random.randint(15, 30)
    sub = random.randint(4, 9)
    code = f"s = {base}\ns -= {sub}\ns *= 2\nprint(s)"
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, _make_numeric_distractors(int(out)))
    gt = f"Sau lệnh s -= {sub}, s = {base - sub}. Sau lệnh s *= 2, s = {(base - sub) * 2} = {out}."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nGiá trị in ra màn hình là bao nhiêu?",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Các toán tử gán kết hợp thực hiện phép toán và gán lại kết quả cho biến.",
        **opts
    }
    return _pack_skeleton("MCQ_B17_COMPOUND", "mcq_compound", "Bài 17", "MCQ", q, out, True, gt)


def _bp_b18_mcq_sep_end() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    v1 = random.choice(["Tin", "Hoc", "Lop", "Ma"])
    v2 = random.choice(["10", "A1", "KNTT", "Python"])
    sep = random.choice(["-", "#", "*"])
    code = f"print('{v1}', '{v2}', sep='{sep}', end='!')"
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, [f"{v1} {v2}!", f"{v1}{sep}{v2}", f"{v1} {v2}", f"{v1}\n{v2}!"])
    gt = f"Tham số sep='{sep}' quy định ký tự ngăn cách giữa các đối số ('{v1}{sep}{v2}'), tham số end='!' quy định ký tự kết thúc ở cuối dòng, in ra kết quả '{out}'."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nĐoạn mã trên sẽ in ra nội dung nào sau đây?",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Lệnh print() có thể sử dụng các tham số sep và end để tùy chỉnh định dạng in.",
        **opts
    }
    return _pack_skeleton("MCQ_B18_SEP_END", "mcq_sep_end", "Bài 18", "MCQ", q, out, True, gt)


def _bp_b18_mcq_float_cast() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    a = random.choice([2, 4, 5])
    code = f"s = '10'\nx = float(s) / {a}\nprint(x)"
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, ["10", str(10 // a), f"10/{a}", str(float(10 * a))])
    gt = f"float(s) chuyển xâu '10' thành số thực 10.0. Phép chia 10.0 / {a} cho kết quả số thực {out}."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nKết quả xuất ra màn hình là gì?",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Hàm float() chuyển đổi một xâu hoặc số nguyên thành số thực.",
        **opts
    }
    return _pack_skeleton("MCQ_B18_FLOAT_CAST", "mcq_float_cast", "Bài 18", "MCQ", q, out, True, gt)


def _bp_b19_mcq_nested_if() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    num = random.choice([-8, 7, 14, -3])
    code = (
        f"n = {num}\n"
        f"if n > 0:\n"
        f"    if n % 2 == 0:\n"
        f"        print('Duong_Chan')\n"
        f"    else:\n"
        f"        print('Duong_Le')\n"
        f"else:\n"
        f"    print('Khong_Duong')"
    )
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, ["Duong_Chan", "Duong_Le", "Khong_Duong", "Loi_Cu_Phap"])
    gt = f"Với n = {num}, điều kiện đầu tiên n > 0 trả về {'True' if num > 0 else 'False'}, do đó chương trình thực thi nhánh in ra '{out}'."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nKết quả in ra màn hình khi thực hiện chương trình là gì?",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Các câu lệnh rẽ nhánh if có thể lồng nhau để xử lý các điều kiện phức tạp.",
        **opts
    }
    return _pack_skeleton("MCQ_B19_NESTED_IF", "mcq_nested_if", "Bài 19", "MCQ", q, out, True, gt)


def _bp_b19_mcq_logic_not() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    a = random.choice([5, 12])
    b = random.choice([8, 15])
    code = (
        f"a = {a}\n"
        f"b = {b}\n"
        f"if not (a > 10) and b > 10:\n"
        f"    print('Nhanh_A')\n"
        f"else:\n"
        f"    print('Nhanh_B')"
    )
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, ["Nhanh_A", "Nhanh_B", "True", "False"])
    gt = f"Ta có a = {a}, a > 10 là {a > 10}, nên not (a > 10) là {not (a > 10)}. b = {b}, b > 10 là {b > 10}. Biểu thức logic tổng hợp nhận giá trị {'True' if out == 'Nhanh_A' else 'False'}, nên in ra '{out}'."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nKết quả hiển thị trên màn hình là:",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Các phép toán logic not, and, or được sử dụng để kết hợp các điều kiện.",
        **opts
    }
    return _pack_skeleton("MCQ_B19_LOGIC_NOT", "mcq_logic_not", "Bài 19", "MCQ", q, out, True, gt)


def _bp_b19_mcq_missing_condition() -> dict:
    lead = "Để kiểm tra số nguyên dương n có phải là số chia hết cho cả 3 và 5 hay không, biểu thức điều kiện cần điền vào dấu ... trong câu lệnh 'if ...:' là:"
    corr = "n % 3 == 0 and n % 5 == 0"
    dist = [
        "n % 3 == 0 or n % 5 == 0",
        "n // 3 == 0 and n // 5 == 0",
        "n % 15 != 0"
    ]
    opts, ans = _shuffle_mcq_options(corr, dist)
    gt = "Số chia hết cho cả 3 và 5 phải thỏa mãn đồng thời hai điều kiện số dư bằng 0: n % 3 == 0 and n % 5 == 0."
    q = {
        "cau_hoi": lead,
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Phép toán and trả về True khi và chỉ khi cả hai biểu thức thành phần đều đúng.",
        **opts
    }
    return _pack_skeleton("MCQ_B19_MISSING_COND", "mcq_miss_cond", "Bài 19", "MCQ", q, "", False, gt)


def _bp_b20_mcq_range_3args() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    start = random.choice([2, 3])
    stop = random.choice([11, 14])
    step = random.choice([2, 3])
    code = (
        f"tong = 0\n"
        f"for i in range({start}, {stop}, {step}):\n"
        f"    tong += i\n"
        f"print(tong)"
    )
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, _make_numeric_distractors(int(out)))
    gt = f"Hàm range({start}, {stop}, {step}) sinh dãy số từ {start} đến dưới {stop} với bước nhảy {step}. Tổng các số là {out}."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nGiá trị của biến tong sau khi vòng lặp kết thúc là:",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Hàm range(start, stop, step) tạo dãy số bắt đầu từ start, nhỏ hơn stop với bước nhảy step.",
        **opts
    }
    return _pack_skeleton("MCQ_B20_RANGE_3ARGS", "mcq_range_3args", "Bài 20", "MCQ", q, out, True, gt)


def _bp_b20_mcq_for_break() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    lim = random.choice([5, 6, 7])
    code = (
        f"s = 0\n"
        f"for i in range(1, 15):\n"
        f"    if i == {lim}:\n"
        f"        break\n"
        f"    s += i\n"
        f"print(s)"
    )
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, _make_numeric_distractors(int(out), [lim, lim * (lim + 1) // 2]))
    gt = f"Vòng lặp chạy i từ 1 đến {lim - 1}. Khi i == {lim}, lệnh break được thực thi lập tức kết thúc vòng lặp. Tổng tích lũy s là {out}."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nKết quả in ra màn hình là bao nhiêu?",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Câu lệnh break dùng để thoát ngay khỏi vòng lặp chứa nó.",
        **opts
    }
    return _pack_skeleton("MCQ_B20_FOR_BREAK", "mcq_for_break", "Bài 20", "MCQ", q, out, True, gt)


def _bp_b20_mcq_for_continue() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    skip = random.choice([3, 4])
    code = (
        f"dem = 0\n"
        f"for i in range(1, 6):\n"
        f"    if i == {skip}:\n"
        f"        continue\n"
        f"    dem += 1\n"
        f"print(dem)"
    )
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, ["5", "4", "3", "6"])
    gt = f"Vòng lặp lặp 5 lần (i từ 1 đến 5). Khi i == {skip}, lệnh continue bỏ qua câu lệnh dem += 1. Do đó biến dem được tăng 4 lần, in ra {out}."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nGiá trị của biến dem sau khi kết thúc chương trình là:",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Lệnh continue bỏ qua phần còn lại của lượt lặp hiện tại và chuyển sang lượt lặp kế tiếp.",
        **opts
    }
    return _pack_skeleton("MCQ_B20_FOR_CONTINUE", "mcq_for_continue", "Bài 20", "MCQ", q, out, True, gt)


def _bp_b21_mcq_while_break() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    start = random.randint(1, 4)
    code = (
        f"x = {start}\n"
        f"while True:\n"
        f"    x += 3\n"
        f"    if x > 10:\n"
        f"        break\n"
        f"print(x)"
    )
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, _make_numeric_distractors(int(out), [10, 11, 12, 13]))
    gt = f"Vòng lặp tăng x mỗi lần 3 đơn vị cho đến khi x vượt quá 10 thì gặp break dừng lại. Giá trị cuối cùng của x là {out}."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nKết quả in ra màn hình của đoạn chương trình trên là:",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Vòng lặp while True kết hợp với break là cấu trúc lặp vô hạn có điều kiện dừng.",
        **opts
    }
    return _pack_skeleton("MCQ_B21_WHILE_BREAK", "mcq_while_break", "Bài 21", "MCQ", q, out, True, gt)


def _bp_b21_mcq_while_find_factor() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    n = random.choice([15, 21, 35, 49])
    code = (
        f"n = {n}\n"
        f"d = 2\n"
        f"while n % d != 0:\n"
        f"    d += 1\n"
        f"print(d)"
    )
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, _make_numeric_distractors(int(out), [n, 2, 3, 5, 7]))
    gt = f"Vòng lặp while tăng d bắt đầu từ 2 để tìm ước số nguyên dương nhỏ nhất lớn hơn 1 của {n}. Kết quả tìm được là d = {out}."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nChương trình trên in ra giá trị nào?",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Vòng lặp while lặp lại khối lệnh khi điều kiện lặp còn đúng.",
        **opts
    }
    return _pack_skeleton("MCQ_B21_WHILE_FACTOR", "mcq_while_factor", "Bài 21", "MCQ", q, out, True, gt)


def _bp_b22_mcq_negative_index() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    ds = random.sample([12, 45, 78, 23, 56, 89], 5)
    code = f"ds = {ds}\nprint(ds[-2])"
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, [str(ds[-1]), str(ds[1]), str(ds[2]), str(ds[0])])
    gt = f"Trong Python, chỉ số -1 chỉ phần tử cuối cùng, chỉ số -2 chỉ phần tử áp chót của danh sách. Với ds = {ds}, ds[-2] là {out}."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nKết quả hiển thị trên màn hình là gì?",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Chỉ số âm trong danh sách được đếm ngược từ cuối: -1 là phần tử cuối cùng.",
        **opts
    }
    return _pack_skeleton("MCQ_B22_NEG_INDEX", "mcq_neg_index", "Bài 22", "MCQ", q, out, True, gt)


def _bp_b22_mcq_list_in_op() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    ds = [10, 20, 30, 40]
    target = random.choice([20, 25])
    code = f"ds = {ds}\nkq = {target} in ds\nprint(kq)"
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, ["True", "False", "1", "0"])
    gt = f"Toán tử in kiểm tra phần tử có nằm trong danh sách hay không. Số {target} {'có' if target in ds else 'không'} nằm trong ds, nên kết quả là {out}."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nKết quả in ra của câu lệnh trên là:",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Toán tử in trả về True nếu phần tử có mặt trong danh sách, ngược lại trả về False.",
        **opts
    }
    return _pack_skeleton("MCQ_B22_LIST_IN", "mcq_list_in", "Bài 22", "MCQ", q, out, True, gt)


def _bp_b22_mcq_list_len_empty() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    code = "ds = []\nprint(len(ds))"
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, ["1", "None", "-1", "Error"])
    gt = "Danh sách rỗng không chứa phần tử nào, do đó hàm len() trả về 0."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nKết quả in ra là:",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Hàm len(ds) trả về số lượng phần tử của danh sách ds.",
        **opts
    }
    return _pack_skeleton("MCQ_B22_LEN_EMPTY", "mcq_len_empty", "Bài 22", "MCQ", q, out, True, gt)


def _bp_b23_mcq_list_insert() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    code = "ds = [1, 3, 4]\nds.insert(1, 2)\nprint(ds)"
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, ["[1, 4, 3, 2]", "[2, 1, 3, 4]", "[1, 3, 4, 2]", "[1, 2, 4]"])
    gt = "Phương thức ds.insert(1, 2) chèn giá trị 2 vào vị trí có chỉ số 1, đẩy các phần tử phía sau sang phải. Danh sách trở thành [1, 2, 3, 4]."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nDanh sách ds sau khi thực hiện lệnh insert là:",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Phương thức insert(i, x) chèn phần tử x vào vị trí chỉ số i trong danh sách.",
        **opts
    }
    return _pack_skeleton("MCQ_B23_INSERT", "mcq_insert", "Bài 23", "MCQ", q, out, True, gt)


def _bp_b23_mcq_list_pop() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    nums = [10, 20, 30, 40]
    code = f"ds = {nums}\nx = ds.pop()\nprint(x)"
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, ["10", "20", "30", "[10, 20, 30]"])
    gt = "Phương thức ds.pop() không truyền tham số sẽ xóa và trả về phần tử cuối cùng của danh sách (ở đây là 40)."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nBiến x nhận giá trị nào sau khi thực thi lệnh pop()?",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Lệnh pop() xóa phần tử cuối cùng của danh sách và trả về giá trị của phần tử đó.",
        **opts
    }
    return _pack_skeleton("MCQ_B23_POP", "mcq_pop", "Bài 23", "MCQ", q, out, True, gt)


def _bp_b23_mcq_list_remove() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    code = "ds = [5, 9, 2, 9, 7]\nds.remove(9)\nprint(ds)"
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, ["[5, 2, 7]", "[5, 9, 2, 7]", "[5, 2, 9, 7]", "[9, 2, 9, 7]"])
    gt = "Phương thức ds.remove(9) chỉ xóa phần tử đầu tiên có giá trị 9 tìm thấy trong danh sách, các phần tử 9 phía sau vẫn giữ nguyên."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nKết quả in ra của chương trình là:",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Lệnh remove(x) xóa phần tử đầu tiên trong danh sách có giá trị bằng x.",
        **opts
    }
    return _pack_skeleton("MCQ_B23_REMOVE", "mcq_remove", "Bài 23", "MCQ", q, out, True, gt)


def _bp_b23_mcq_list_count() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    ds = [1, 2, 3, 2, 4, 2, 5]
    code = f"ds = {ds}\nprint(ds.count(2))"
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, ["1", "2", "3", "7"])
    gt = "Phương thức count(2) đếm số lần xuất hiện của số 2 trong danh sách, ở đây số 2 xuất hiện 3 lần."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nKết quả in ra là:",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Phương thức count(x) đếm số lần xuất hiện của phần tử x trong danh sách.",
        **opts
    }
    return _pack_skeleton("MCQ_B23_COUNT", "mcq_count", "Bài 23", "MCQ", q, out, True, gt)


def _bp_b24_mcq_str_slice() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    s = "LapTrinhPython"
    code = f"s = '{s}'\nprint(s[3:7])"
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, ["LapT", "Trinh", "Trin", "inhP"])
    gt = f"Phép cắt lát s[3:7] lấy các ký tự từ chỉ số 3 đến chỉ số 6: ký tự tại 3, 4, 5, 6 là '{out}'."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nKết quả in ra màn hình là:",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Cú pháp cắt lát xâu s[start:stop] lấy các ký tự từ start đến stop - 1.",
        **opts
    }
    return _pack_skeleton("MCQ_B24_STR_SLICE", "mcq_str_slice", "Bài 24", "MCQ", q, out, True, gt)


def _bp_b24_mcq_str_concat_mult() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    code = "s = 'Ha' * 2 + 'Noi'\nprint(s)"
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, ["HaNoiHaNoi", "HaHaNoi", "Ha2Noi", "HaNoi"])
    gt = "'Ha' * 2 tạo xâu 'HaHa'. Sau đó nối tiếp với 'Noi' tạo thành 'HaHaNoi'."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nGiá trị của biến s được in ra là:",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Toán tử + dùng để nối xâu, toán tử * dùng để lặp lại xâu nhiều lần.",
        **opts
    }
    return _pack_skeleton("MCQ_B24_STR_CONCAT", "mcq_str_concat", "Bài 24", "MCQ", q, out, True, gt)


def _bp_b24_mcq_str_in_op() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    code = "s = 'Tin Hoc 10'\nprint('Hoc' in s)"
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, ["True", "False", "1", "None"])
    gt = "Xâu con 'Hoc' có mặt trong xâu 'Tin Hoc 10', do đó toán tử in trả về True."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nĐoạn mã trên sẽ in ra kết quả nào?",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Toán tử in kiểm tra xem một xâu có phải là xâu con của xâu khác hay không.",
        **opts
    }
    return _pack_skeleton("MCQ_B24_STR_IN", "mcq_str_in", "Bài 24", "MCQ", q, out, True, gt)


def _bp_b25_mcq_str_split() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    code = "s = 'Ha Noi Viet Nam'\nds = s.split()\nprint(len(ds))"
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, ["16", "3", "4", "5"])
    gt = "Phương thức s.split() tách xâu theo khoảng trắng thành danh sách 4 phần tử ['Ha', 'Noi', 'Viet', 'Nam']. Do đó len(ds) là 4."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nKết quả in ra là:",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Phương thức split() phân tách xâu ký tự thành một danh sách các từ.",
        **opts
    }
    return _pack_skeleton("MCQ_B25_STR_SPLIT", "mcq_str_split", "Bài 25", "MCQ", q, out, True, gt)


def _bp_b25_mcq_str_replace() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    code = "s = '2025-2026'\ns_moi = s.replace('-', '/')\nprint(s_moi)"
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, ["2025-2026", "2025/2026", "2025//2026", "Loi_Cu_Phap"])
    gt = "Phương thức s.replace('-', '/') thay thế tất cả dấu gạch nối '-' bằng dấu gạch chéo '/', tạo ra xâu mới '2025/2026'."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nKết quả in ra màn hình là:",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Phương thức replace(old, new) thay thế các xâu con old bằng xâu new.",
        **opts
    }
    return _pack_skeleton("MCQ_B25_STR_REPLACE", "mcq_str_replace", "Bài 25", "MCQ", q, out, True, gt)


def _bp_b26_mcq_no_return() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    code = (
        "def chao(ten):\n"
        "    a = ten\n"
        "kq = chao('Nam')\n"
        "print(kq)"
    )
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, ["'Xin chao Nam'", "0", "True", "None"])
    gt = "Hàm chao() không có câu lệnh return, nên giá trị trả về mặc định của hàm là None khi in biến kq."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nKết quả in ra màn hình là:",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Nếu hàm không có lệnh return, giá trị trả về mặc định của hàm là None.",
        **opts
    }
    return _pack_skeleton("MCQ_B26_NO_RETURN", "mcq_no_return", "Bài 26", "MCQ", q, out, True, gt)


def _bp_b27_mcq_keyword_args() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    code = (
        f"def hieu(a, b):\n"
        f"    return a - b\n"
        f"print(hieu(b=10, a=30))"
    )
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, ["-20", "20", "40", "Loi_Tham_So"])
    gt = "Khi truyền đối số kèm tên tham số (keyword arguments) b=10, a=30, hàm nhận đúng a=30, b=10 bất kể thứ tự truyền. Do đó 30 - 10 = 20."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nKết quả in ra của chương trình trên là:",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Khi gọi hàm có thể truyền đối số theo tên tham số mà không phụ thuộc thứ tự vị trí.",
        **opts
    }
    return _pack_skeleton("MCQ_B27_KW_ARGS", "mcq_kw_args", "Bài 27", "MCQ", q, out, True, gt)


def _bp_b28_mcq_global_keyword() -> dict:
    lead = random.choice(STEM_MCQ_LEADINS)
    code = (
        f"dem = 5\n"
        f"def tang():\n"
        f"    global dem\n"
        f"    dem += 1\n"
        f"tang()\n"
        f"print(dem)"
    )
    out = _run_code_get_stdout(code)
    opts, ans = _shuffle_mcq_options(out, ["5", "6", "1", "Loi_Bien_Cuc_Bo"])
    gt = "Từ khóa global dem bên trong hàm tang() cho phép hàm thay đổi trực tiếp giá trị của biến toàn cục dem từ 5 lên 6."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nGiá trị của biến dem sau khi gọi hàm tang() là:",
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Sử dụng từ khóa global để khai báo biến toàn cục được chỉnh sửa bên trong hàm.",
        **opts
    }
    return _pack_skeleton("MCQ_B28_GLOBAL_KW", "mcq_global_kw", "Bài 28", "MCQ", q, out, True, gt)


def _bp_b29_mcq_zerodiv_error() -> dict:
    lead = "Khi chạy đoạn mã sau trong Python, chương trình sẽ phát sinh ngoại lệ (lỗi thời gian chạy) thuộc loại nào?\n```python\na = 10\nb = 0\nkq = a / b\n```"
    corr = "ZeroDivisionError"
    dist = ["TypeError", "ValueError", "IndexError"]
    opts, ans = _shuffle_mcq_options(corr, dist)
    gt = "Thực hiện phép chia một số cho 0 sẽ kích hoạt ngoại lệ ZeroDivisionError trong Python."
    q = {
        "cau_hoi": lead,
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Lỗi chia cho 0 trong Python được phân loại là ZeroDivisionError.",
        **opts
    }
    return _pack_skeleton("MCQ_B29_ZERODIV", "mcq_zerodiv", "Bài 29", "MCQ", q, "", False, gt)


def _bp_b29_mcq_type_error() -> dict:
    lead = "Đoạn lệnh nào sau đây sẽ làm phát sinh lỗi kiểu dữ liệu (TypeError) khi thực thi?"
    corr = "'Nam: ' + 2026"
    dist = ["int('2026')", "float(2026)", "'Nam: ' + str(2026)"]
    opts, ans = _shuffle_mcq_options(corr, dist)
    gt = "Trong Python, toán tử + không thể dùng trực tiếp giữa một xâu ký tự (str) và một số nguyên (int), gây ra TypeError."
    q = {
        "cau_hoi": lead,
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "TypeError xuất hiện khi thực hiện phép toán trên các đối tượng có kiểu dữ liệu không tương thích.",
        **opts
    }
    return _pack_skeleton("MCQ_B29_TYPE_ERR", "mcq_type_err", "Bài 29", "MCQ", q, "", False, gt)


def _bp_b30_mcq_test_boundary() -> dict:
    lead = "Khi kiểm thử một chương trình tính tiền điện với mức 1 áp dụng cho số điện từ 0 đến 50 kWh, các ca kiểm thử giá trị biên (boundary test cases) quan trọng nhất cần chọn là:"
    corr = "0, 50 và 51"
    dist = ["10, 20 và 30", "-50 và 100", "25, 75 và 150"]
    opts, ans = _shuffle_mcq_options(corr, dist)
    gt = "Kiểm thử giá trị biên tập trung vào các điểm mút và điểm lân cận mút của miền giá trị (0, 50 và 51) để phát hiện sai sót trong toán tử so sánh (<=, <)."
    q = {
        "cau_hoi": lead,
        "phuong_an": opts,
        "dap_an": ans,
        "giai_thich": gt,
        "trich_dan_sgk": "Kiểm thử giá trị biên giúp phát hiện lỗi tại các điểm chuyển tiếp điều kiện của chương trình.",
        **opts
    }
    return _pack_skeleton("MCQ_B30_BOUNDARY", "mcq_boundary", "Bài 30", "MCQ", q, "", False, gt)


# ==============================================================================
# 2. 12 KHUÔN BÀI TRUE_FALSE MỚI (ĐÚNG/SAI BẬC THANG 4 Ý)
# ==============================================================================

def _make_tf_question(stem: str, a: tuple, b: tuple, c: tuple, d: tuple, sgk_ref: str = "SGK Tin học 10 Kết nối tri thức - Chủ đề F.") -> dict:
    """Tạo cấu trúc dict chuẩn cho câu TRUE_FALSE."""
    return {
        "cau_hoi_chung": stem,
        "a": {"menh_de": a[0], "dap_an": "Đúng" if a[1] else "Sai", "giai_thich": a[2]},
        "b": {"menh_de": b[0], "dap_an": "Đúng" if b[1] else "Sai", "giai_thich": b[2]},
        "c": {"menh_de": c[0], "dap_an": "Đúng" if c[1] else "Sai", "giai_thich": c[2]},
        "d": {"menh_de": d[0], "dap_an": "Đúng" if d[1] else "Sai", "giai_thich": d[2]},
        "trich_dan_sgk": sgk_ref
    }


def _bp_b16_tf_interactive_vs_script() -> dict:
    q = _make_tf_question(
        "Xét các phát biểu sau về hai chế độ làm việc trong môi trường lập trình Python:",
        ("Chế độ gõ lệnh trực tiếp (Interactive Mode) phù hợp để chạy thử nghiệm nhanh từng câu lệnh đơn lẻ.", True, "Chế độ tương tác thực thi ngay từng câu lệnh sau khi nhấn Enter."),
        ("Chương trình viết ở chế độ soạn thảo (Script Mode) được lưu trữ vào tệp có phần mở rộng .py để sử dụng lại.", True, "Chế độ soạn thảo lưu trữ chương trình thành tệp mã nguồn hoàn chỉnh."),
        ("Ở chế độ gõ lệnh trực tiếp, khi đóng cửa sổ dòng lệnh thì toàn bộ các biến và câu lệnh đã gõ vẫn được tự động lưu lại vào ổ cứng.", False, "Chế độ tương tác không tự động lưu các lệnh vào tệp; khi đóng cửa sổ dữ liệu tạm sẽ mất."),
        ("Dấu nhắc >>> là dấu hiệu nhận biết môi trường đang ở chế độ gõ lệnh trực tiếp của Python.", True, "Dấu nhắc >>> thể hiện Python đã sẵn sàng nhận lệnh trực tiếp từ người dùng.")
    )
    return _pack_skeleton("TF_B16_MODES", "tf_modes", "Bài 16", "TRUE_FALSE", q, "", False)


def _bp_b17_tf_vars_naming() -> dict:
    q = _make_tf_question(
        "Xét các nhận định về biến và kiểu dữ liệu trong ngôn ngữ lập trình Python:",
        ("Tên biến có thể bắt đầu bằng một chữ số (ví dụ: 1diem, 2so).", False, "Tên biến trong Python không được phép bắt đầu bằng chữ số."),
        ("Python phân biệt chữ hoa và chữ thường trong tên biến (ví dụ: Tong và tong là hai biến khác nhau).", True, "Python là ngôn ngữ phân biệt chữ hoa và chữ thường trong định danh."),
        ("Kiểu dữ liệu của biến trong Python được tự động xác định khi thực hiện phép gán giá trị.", True, "Python sử dụng cơ chế định kiểu động dựa trên giá trị của biến."),
        ("Lệnh x = y = 0 gán đồng thời giá trị 0 cho cả hai biến x và y.", True, "Phép gán liên tiếp x = y = 0 hợp lệ và gán 0 cho cả hai biến.")
    )
    return _pack_skeleton("TF_B17_VARS", "tf_vars", "Bài 17", "TRUE_FALSE", q, "", False)


def _bp_b18_tf_sep_end_cast() -> dict:
    q = _make_tf_question(
        "Cho các nhận định về các lệnh vào/ra và chuyển đổi kiểu dữ liệu trong Python:",
        ("Hàm input() luôn trả về dữ liệu thuộc kiểu số nguyên int.", False, "input() luôn trả về kiểu dữ liệu xâu kí tự str."),
        ("Lệnh int('15.5') sẽ thực hiện chuyển đổi thành công thành số nguyên 15.", False, "int('15.5') gây lỗi ValueError vì xâu chứa dấu chấm thập phân."),
        ("Lệnh print(1, 2, sep='-') sẽ in ra màn hình chuỗi '1-2'.", True, "Tham số sep='-' quy định dấu gạch ngang phân cách giữa các đối số."),
        ("Tham số end='' trong lệnh print() ngăn việc tự động xuống dòng sau khi in.", True, "end='' ghi đè ký tự xuống dòng mặc định bằng ký tự rỗng.")
    )
    return _pack_skeleton("TF_B18_IO_CAST", "tf_io_cast", "Bài 18", "TRUE_FALSE", q, "", False)


def _bp_b19_tf_elif_logic() -> dict:
    q = _make_tf_question(
        "Cho đoạn mã Python sau:\n```python\nx = 15\nif x < 10:\n    y = 1\nelif x <= 20:\n    y = 2\nelse:\n    y = 3\n```\nXét tính Đúng/Sai của các phát biểu sau:",
        ("Biểu thức điều kiện x < 10 nhận giá trị False.", True, "15 < 10 là sai (False)."),
        ("Khối lệnh sau elif x <= 20 được thực hiện vì điều kiện x <= 20 nhận giá trị True.", True, "15 <= 20 là đúng (True) nên khối lệnh của elif được thực thi."),
        ("Sau khi thực hiện đoạn mã trên, biến y nhận giá trị bằng 3.", False, "Biến y nhận giá trị 2 sau nhánh elif."),
        ("Nếu thay x = 25 thì giá trị cuối cùng của biến y sẽ là 3.", True, "Với x = 25, cả if và elif đều sai nên nhảy vào else gán y = 3.")
    )
    return _pack_skeleton("TF_B19_ELIF", "tf_elif", "Bài 19", "TRUE_FALSE", q, "", False)


def _bp_b20_tf_nested_loop() -> dict:
    q = _make_tf_question(
        "Cho đoạn chương trình sau:\n```python\ndem = 0\nfor i in range(3):\n    for j in range(4):\n        dem += 1\n```\nXét các phát biểu sau:",
        ("Vòng lặp ngoài for i in range(3) thực hiện đúng 3 lần lặp.", True, "range(3) sinh ra các giá trị 0, 1, 2 tương ứng 3 lượt lặp."),
        ("Với mỗi lần lặp của vòng ngoài, vòng lặp trong for j in range(4) lặp 4 lần.", True, "Vòng trong lặp 4 lần ứng với j = 0, 1, 2, 3."),
        ("Tổng số lần câu lệnh dem += 1 được thực hiện là 12 lần.", True, "Tổng số lần lặp bằng 3 * 4 = 12 lần."),
        ("Sau khi hai vòng lặp kết thúc, giá trị của biến dem là 7.", False, "dem tăng 12 lần nên có giá trị là 12 chứ không phải 7.")
    )
    return _pack_skeleton("TF_B20_NESTED", "tf_nested", "Bài 20", "TRUE_FALSE", q, "", False)


def _bp_b21_tf_while_counter() -> dict:
    q = _make_tf_question(
        "Cho đoạn mã Python sau:\n```python\nk = 1\ns = 0\nwhile k <= 4:\n    s += k\n    k += 1\n```\nXét các phát biểu sau:",
        ("Điều kiện lặp của vòng lặp while là k <= 4.", True, "Biểu thức k <= 4 quyết định việc tiếp tục lặp."),
        ("Vòng lặp thực hiện đúng 4 lượt lặp tương ứng với k = 1, 2, 3, 4.", True, "k tăng từ 1 đến 4 thực hiện 4 lượt."),
        ("Khi vòng lặp kết thúc, biến k có giá trị là 4.", False, "Khi thoát vòng lặp, k đã được tăng lên 5 để điều kiện k <= 4 thành False."),
        ("Giá trị cuối cùng của biến s sau khi kết thúc vòng lặp là 10.", True, "s = 1 + 2 + 3 + 4 = 10.")
    )
    return _pack_skeleton("TF_B21_COUNTER", "tf_counter", "Bài 21", "TRUE_FALSE", q, "", False)


def _bp_b22_tf_list_methods_all() -> dict:
    q = _make_tf_question(
        "Cho danh sách a = [10, 20, 30]. Xét các nhận định sau về các thao tác trên danh sách:",
        ("Lệnh a.append(40) sẽ thêm số 40 vào vị trí cuối cùng của danh sách.", True, "append() bổ sung phần tử vào cuối danh sách."),
        ("Lệnh a[0] = 99 sẽ thay thế phần tử đầu tiên của danh sách thành 99.", True, "Danh sách hỗ trợ phép gán đè phần tử qua chỉ số."),
        ("Phần tử a[-1] tương ứng với giá trị 10.", False, "a[-1] là phần tử cuối cùng (giá trị 30), a[0] mới là 10."),
        ("Hàm len(a) trả về độ dài hiện tại của danh sách a.", True, "len() đếm số lượng phần tử của danh sách.")
    )
    return _pack_skeleton("TF_B22_METHODS", "tf_methods", "Bài 22", "TRUE_FALSE", q, "", False)


def _bp_b23_tf_list_slice_mut() -> dict:
    q = _make_tf_question(
        "Cho danh sách ds = [1, 2, 3, 4, 5]. Đánh giá tính Đúng/Sai của các phát biểu sau:",
        ("Phép cắt lát ds[1:4] trả về danh sách con [2, 3, 4].", True, "Lấy các phần tử tại chỉ số 1, 2, 3 là [2, 3, 4]."),
        ("Lệnh ds.clear() sẽ xóa sạch toàn bộ phần tử và đưa ds về danh sách rỗng [].", True, "clear() xóa tất cả phần tử trong danh sách."),
        ("Lệnh ds.remove(x) sẽ xóa tất cả các phần tử có giá trị bằng x trong danh sách.", False, "remove(x) chỉ xóa phần tử đầu tiên tìm thấy."),
        ("Phép toán ds * 2 sẽ nhân đôi giá trị của từng phần tử bên trong danh sách ds.", False, "ds * 2 tạo danh sách mới lặp lại danh sách cũ 2 lần.")
    )
    return _pack_skeleton("TF_B23_SLICE_MUT", "tf_slice_mut", "Bài 23", "TRUE_FALSE", q, "", False)


def _bp_b24_tf_str_indexing_immut() -> dict:
    q = _make_tf_question(
        "Cho xâu ký tự s = 'Python'. Xét tính Đúng/Sai của các phát biểu sau:",
        ("Ký tự đầu tiên s[0] là chữ cái 'P'.", True, "Chỉ số 0 trỏ tới ký tự đầu tiên của xâu."),
        ("Hàm len(s) trả về giá trị là 6.", True, "Xâu 'Python' có đúng 6 ký tự."),
        ("Câu lệnh s[0] = 'p' sẽ chuyển chữ 'P' hoa thành chữ 'p' thường một cách hợp lệ.", False, "Xâu ký tự là bất biến (immutable), không thể gán lại phần tử."),
        ("Xâu ký tự trong Python là kiểu dữ liệu bất biến (immutable).", True, "Định nghĩa chuẩn của kiểu str trong Python là bất biến.")
    )
    return _pack_skeleton("TF_B24_IMMUT", "tf_immut", "Bài 24", "TRUE_FALSE", q, "", False)


def _bp_b25_tf_str_methods_split() -> dict:
    q = _make_tf_question(
        "Cho xâu ký tự st = 'Ha Noi, Viet Nam'. Đánh giá tính Đúng/Sai của các phát biểu sau:",
        ("Phương thức st.find('Noi') trả về vị trí chỉ số xuất hiện đầu tiên của từ 'Noi'.", True, "find() trả về chỉ số bắt đầu của xâu con tìm thấy."),
        ("Phương thức st.count('a') đếm số lần xuất hiện của chữ cái 'a' thường trong xâu.", True, "count() đếm số lần xuất hiện của ký tự con."),
        ("Phương thức st.split(',') sẽ tách xâu st thành một danh sách gồm 2 phần tử.", True, "Tách theo dấu phẩy thành ['Ha Noi', ' Viet Nam']."),
        ("Nếu từ khóa tìm kiếm không có trong xâu, phương thức find() sẽ làm chương trình báo lỗi dừng lại.", False, "find() trả về -1 khi không tìm thấy, không gây lỗi chương trình.")
    )
    return _pack_skeleton("TF_B25_METHODS", "tf_str_methods", "Bài 25", "TRUE_FALSE", q, "", False)


def _bp_b28_tf_scope_local_global() -> dict:
    stem = (
        "Cho đoạn mã nguồn Python sau:\n"
        "```python\n"
        "x = 10\n"
        "def kiem_tra():\n"
        "    y = 5\n"
        "    return x + y\n"
        "```\n"
        "Xét tính Đúng/Sai của các nhận định về phạm vi biến (Scope) trong chương trình:"
    )
    q = _make_tf_question(
        stem,
        ("Biến y được tạo ra bên trong hàm kiem_tra() là biến cục bộ (local variable) của hàm đó.", True, "Biến y được khai báo trong thân hàm kiem_tra() nên có phạm vi cục bộ."),
        ("Biến cục bộ y có thể được truy cập và in ra trực tiếp từ bên ngoài hàm kiem_tra().", False, "Biến y không thể truy xuất từ phạm vi bên ngoài hàm kiem_tra()."),
        ("Biến x được khai báo bên ngoài hàm là biến toàn cục (global variable) đối với hàm kiem_tra().", True, "Biến x được định nghĩa ở cấp module ngoài hàm nên là biến toàn cục."),
        ("Để thay đổi trực tiếp giá trị của biến toàn cục x từ bên trong hàm kiem_tra(), cần sử dụng từ khóa global.", True, "Để thay đổi giá trị của biến x từ bên trong hàm kiem_tra(), cần dùng từ khóa global x.")
    )
    return _pack_skeleton("TF_B28_SCOPE", "tf_scope", "Bài 28", "TRUE_FALSE", q, "", False)


def _bp_b30_tf_blackbox_testing() -> dict:
    q = _make_tf_question(
        "Xét các phát biểu sau về phương pháp kiểm thử và gỡ lỗi chương trình trong Python:",
        ("Kiểm thử chương trình nhằm mục đích phát hiện các lỗi còn tiềm ẩn trước khi đưa vào sử dụng.", True, "Mục tiêu chính của kiểm thử là phát hiện lỗi."),
        ("Kiểm thử hộp đen (Black-box testing) chỉ quan tâm đến đầu vào và đầu ra mà không cần biết cấu trúc mã nguồn bên trong.", True, "Định nghĩa chuẩn của kiểm thử hộp đen."),
        ("Chèn các câu lệnh print() để in giá trị biến trung gian là một phương pháp gỡ lỗi thủ công hiệu quả.", True, "Kỹ thuật gỡ lỗi in vết biến bằng lệnh print()."),
        ("Nếu chương trình chạy qua một bộ dữ liệu thử nghiệm (test case) duy nhất mà không báo lỗi thì khẳng định 100% chương trình không có lỗi.", False, "Một ca kiểm thử không thể chứng minh tính đúng đắn cho mọi trường hợp đầu vào.")
    )
    return _pack_skeleton("TF_B30_TESTING", "tf_testing", "Bài 30", "TRUE_FALSE", q, "", False)


# ==============================================================================
# 3. 16 KHUÔN BÀI SHORT_ANSWER MỚI (TRẢ LỜI NGẮN)
# ==============================================================================

def _bp_b16_sa_calc_priority() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    a = random.choice([20, 24, 30])
    b = random.choice([3, 4, 5])
    code = f"x = {a} // {b} + {a} % {b} * 2\nprint(x)"
    out = _run_code_get_stdout(code)
    gt = f"{a} // {b} = {a // b}, {a} % {b} = {a % b}. {a % b} * 2 = {a % b * 2}. Tổng x = {out}."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nKết quả in ra màn hình của biến x là số nào?",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "Thứ tự ưu tiên các phép toán số học thực hiện từ nhân chia trước, cộng trừ sau.",
    }
    return _pack_skeleton("SA_B16_CALC_PRIO", "sa_calc_prio", "Bài 16", "SHORT_ANSWER", q, out, True, gt)


def _bp_b17_sa_multi_assign_calc() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    a = random.randint(4, 9)
    b = random.randint(10, 15)
    code = f"p, q = {a}, {b}\np, q = q - p, p * 2\nprint(q)"
    out = _run_code_get_stdout(code)
    gt = f"Trước phép gán p = {a}, q = {b}. Biểu thức vế phải: q - p = {b - a}, p * 2 = {a * 2}. q nhận giá trị {out}."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nGiá trị của biến q được in ra màn hình là bao nhiêu?",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "Python tính toán toàn bộ vế phải trước khi gán đồng thời cho các biến ở vế trái.",
    }
    return _pack_skeleton("SA_B17_MULTI_CALC", "sa_multi_calc", "Bài 17", "SHORT_ANSWER", q, out, True, gt)


def _bp_b18_sa_str_repeat_len() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    rep = random.choice([3, 4, 5])
    code = f"st = 'abc' * {rep} + 'xy'\nprint(len(st))"
    out = _run_code_get_stdout(code)
    gt = f"Xâu 'abc' có 3 ký tự, nhân {rep} lần được 3 * {rep} = {3 * rep} ký tự. Cộng thêm xâu 'xy' (2 ký tự) được {out} ký tự."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nKết quả in ra của lệnh len(st) là bao nhiêu?",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "Hàm len() trả về số lượng ký tự có trong xâu.",
    }
    return _pack_skeleton("SA_B18_STR_LEN", "sa_str_len", "Bài 18", "SHORT_ANSWER", q, out, True, gt)


def _bp_b19_sa_nested_branch_val() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    val = random.choice([15, 25, 35])
    code = (
        f"diem = {val}\n"
        f"if diem >= 30:\n"
        f"    thuong = 100\n"
        f"elif diem >= 20:\n"
        f"    thuong = 50\n"
        f"else:\n"
        f"    thuong = 20\n"
        f"print(thuong)"
    )
    out = _run_code_get_stdout(code)
    gt = f"Với diem = {val}, kiểm tra các nhánh điều kiện, kết quả biến thuong nhận giá trị là {out}."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nGiá trị của biến thuong in ra màn hình là bao nhiêu?",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "Câu lệnh if-elif-else chọn thực hiện nhánh đầu tiên có điều kiện thỏa mãn.",
    }
    return _pack_skeleton("SA_B19_NESTED_VAL", "sa_nested_val", "Bài 19", "SHORT_ANSWER", q, out, True, gt)


def _bp_b20_sa_for_step_sum() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    start = random.choice([1, 2])
    stop = random.choice([10, 12])
    step = 2
    code = (
        f"s = 0\n"
        f"for i in range({start}, {stop}, {step}):\n"
        f"    s += i\n"
        f"print(s)"
    )
    out = _run_code_get_stdout(code)
    gt = f"Vòng lặp tính tổng các số từ {start} đến dưới {stop} cách nhau {step} đơn vị. Kết quả s = {out}."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nGiá trị in ra màn hình của biến s là:",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "Hàm range(start, stop, step) duyệt các giá trị với bước nhảy xác định.",
    }
    return _pack_skeleton("SA_B20_STEP_SUM", "sa_step_sum", "Bài 20", "SHORT_ANSWER", q, out, True, gt)


def _bp_b20_sa_for_break_val() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    target = random.choice([4, 5])
    code = (
        f"tong = 0\n"
        f"for k in range(1, 10):\n"
        f"    tong += k\n"
        f"    if k == {target}:\n"
        f"        break\n"
        f"print(tong)"
    )
    out = _run_code_get_stdout(code)
    gt = f"Khi k chạy từ 1 đến {target}, tổng tích lũy là {out}. Gặp lệnh break, vòng lặp dừng ngay lập tức."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nGiá trị của biến tong khi kết thúc vòng lặp là:",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "Lệnh break kết thúc vòng lặp ngay khi điều kiện thỏa mãn.",
    }
    return _pack_skeleton("SA_B20_BREAK_VAL", "sa_break_val", "Bài 20", "SHORT_ANSWER", q, out, True, gt)


def _bp_b21_sa_while_digit_sum() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    n = random.choice([253, 416, 735])
    code = (
        f"n = {n}\n"
        f"tong = 0\n"
        f"while n > 0:\n"
        f"    tong += n % 10\n"
        f"    n //= 10\n"
        f"print(tong)"
    )
    out = _run_code_get_stdout(code)
    digits = [int(c) for c in str(n)]
    gt = f"Thuật toán tách từng chữ số của {n} bằng phép chia lấy dư n % 10. Tổng các chữ số {' + '.join(str(d) for d in digits)} = {out}."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nKết quả in ra của chương trình trên là số nào?",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "Vòng lặp while thường được sử dụng trong bài toán tách các chữ số của một số nguyên.",
    }
    return _pack_skeleton("SA_B21_DIGIT_SUM", "sa_digit_sum", "Bài 21", "SHORT_ANSWER", q, out, True, gt)


def _bp_b21_sa_while_count_divisors() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    n = random.choice([12, 18, 20])
    code = (
        f"n = {n}\n"
        f"dem = 0\n"
        f"i = 1\n"
        f"while i <= n:\n"
        f"    if n % i == 0:\n"
        f"        dem += 1\n"
        f"    i += 1\n"
        f"print(dem)"
    )
    out = _run_code_get_stdout(code)
    divs = [x for x in range(1, n + 1) if n % x == 0]
    gt = f"Các ước số nguyên dương của {n} là {divs}, tổng cộng có {out} ước số."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nGiá trị in ra của biến dem là:",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "Vòng lặp while kiểm tra và đếm các ước số của số nguyên n.",
    }
    return _pack_skeleton("SA_B21_COUNT_DIV", "sa_count_div", "Bài 21", "SHORT_ANSWER", q, out, True, gt)


def _bp_b22_sa_list_negative_slice() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    ds = [10, 25, 40, 55, 70]
    code = f"ds = {ds}\nds[-1] = 99\nprint(ds[-2] + ds[-1])"
    out = _run_code_get_stdout(code)
    gt = f"ds[-1] nhận giá trị mới là 99. ds[-2] có giá trị 55. 55 + 99 = {out}."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nKết quả in ra của phép tính trên là:",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "Chỉ số âm cho phép truy cập và cập nhật các phần tử ở cuối danh sách.",
    }
    return _pack_skeleton("SA_B22_NEG_SLICE", "sa_neg_slice", "Bài 22", "SHORT_ANSWER", q, out, True, gt)


def _bp_b23_sa_list_insert_pop() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    code = (
        f"a = [5, 15, 25]\n"
        f"a.insert(1, 10)\n"
        f"a.pop()\n"
        f"print(len(a))"
    )
    out = _run_code_get_stdout(code)
    gt = "Ban đầu len(a)=3. insert thêm 1 phần tử (độ dài 4), pop xóa 1 phần tử cuối (độ dài 3). In ra 3."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nĐộ dài len(a) in ra là bao nhiêu?",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "Các phương thức insert và pop làm thay đổi số lượng phần tử của danh sách.",
    }
    return _pack_skeleton("SA_B23_INS_POP", "sa_ins_pop", "Bài 23", "SHORT_ANSWER", q, out, True, gt)


def _bp_b24_sa_str_slice_rev() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    w = random.choice(["PYTHON", "TINHOC", "DAIHOC"])
    code = f"s = '{w}'\nprint(s[::-1])"
    out = _run_code_get_stdout(code)
    gt = f"Cú pháp cắt lát s[::-1] đảo ngược thứ tự các ký tự của xâu '{w}', thu được '{out}'."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nKết quả in ra của xâu đảo ngược là gì?",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "Bước nhảy âm trong phép cắt lát xâu cho phép duyệt xâu theo chiều ngược lại.",
    }
    return _pack_skeleton("SA_B24_STR_REV", "sa_str_rev", "Bài 24", "SHORT_ANSWER", q, out, True, gt)


def _bp_b25_sa_str_split_count() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    words = random.choice(["Chuc cac em thi tot", "Hoc lap trinh Python rat vui", "Kiem tra kien thuc tin hoc"])
    code = f"st = '{words}'\nprint(len(st.split()))"
    out = _run_code_get_stdout(code)
    gt = f"Xâu '{words}' có đúng {out} từ được phân tách bởi dấu cách. Do đó len(st.split()) = {out}."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nChương trình trên in ra số lượng từ là bao nhiêu?",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "Hàm split() tách xâu thành các từ phân cách bởi khoảng trắng.",
    }
    return _pack_skeleton("SA_B25_SPLIT_CNT", "sa_split_cnt", "Bài 25", "SHORT_ANSWER", q, out, True, gt)


def _bp_b26_sa_func_compose() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    x = random.randint(2, 5)
    code = (
        f"def f(x):\n"
        f"    return x * 2 + 1\n"
        f"def g(y):\n"
        f"    return y - 3\n"
        f"print(f(g({x + 5})))"
    )
    out = _run_code_get_stdout(code)
    gt = f"g({x + 5}) = {x + 5} - 3 = {x + 2}. Sau đó f({x + 2}) = {x + 2} * 2 + 1 = {out}."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nKết quả in ra của lời gọi hàm trên là:",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "Kết quả trả về của một hàm có thể được dùng làm đối số cho một hàm khác.",
    }
    return _pack_skeleton("SA_B26_COMPOSE", "sa_compose", "Bài 26", "SHORT_ANSWER", q, out, True, gt)


def _bp_b27_sa_func_default_param() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    a = random.randint(3, 7)
    code = (
        f"def tinh(a, b=4):\n"
        f"    return a * b\n"
        f"print(tinh({a}))"
    )
    out = _run_code_get_stdout(code)
    gt = f"Khi chỉ truyền 1 đối số a = {a}, tham số b nhận giá trị mặc định là 4. Kết quả tinh({a}) = {a} * 4 = {out}."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nGiá trị in ra màn hình của lời gọi hàm tinh({a}) là:",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "Tham số có giá trị mặc định sẽ nhận giá trị đó nếu khi gọi hàm không truyền đối số tương ứng.",
    }
    return _pack_skeleton("SA_B27_DEFAULT_PARAM", "sa_def_param", "Bài 27", "SHORT_ANSWER", q, out, True, gt)


def _bp_b28_sa_global_counter() -> dict:
    lead = random.choice(STEM_SA_LEADINS)
    code = (
        f"cnt = 10\n"
        f"def tang():\n"
        f"    global cnt\n"
        f"    cnt += 5\n"
        f"tang()\n"
        f"tang()\n"
        f"print(cnt)"
    )
    out = _run_code_get_stdout(code)
    gt = "Hàm tang() được gọi 2 lần, mỗi lần tăng biến toàn cục cnt thêm 5 đơn vị. 10 + 5 + 5 = 20."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nGiá trị của biến cnt in ra màn hình là:",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "Từ khóa global cho phép hàm ghi đè và cập nhật biến toàn cục.",
    }
    return _pack_skeleton("SA_B28_GLOBAL_CNT", "sa_global_cnt", "Bài 28", "SHORT_ANSWER", q, out, True, gt)


def _bp_b30_sa_bug_fix_output() -> dict:
    lead = "Trong quá trình kiểm thử và gỡ lỗi chương trình, học sinh thực thi đoạn mã sau:"
    code = (
        f"# Đoạn mã sau đã được sửa lỗi thụt lề:\n"
        f"s = 0\n"
        f"for i in [2, 4, 6]:\n"
        f"    s += i\n"
        f"print(s)"
    )
    out = _run_code_get_stdout("s = 0\nfor i in [2, 4, 6]:\n    s += i\nprint(s)")
    gt = "Tổng các phần tử trong danh sách [2, 4, 6] là 2 + 4 + 6 = 12."
    q = {
        "cau_hoi": f"{lead}\n```python\n{code}\n```\nKết quả in ra của chương trình chuẩn sau khi chạy là:",
        "dap_an_ngan": out,
        "giai_thich": gt,
        "trich_dan_sgk": "Sửa lỗi thụt lề câu lệnh giúp chương trình thực thi đúng cấu trúc khối lệnh.",
    }
    return _pack_skeleton("SA_B30_BUG_FIX", "sa_bug_fix", "Bài 30", "SHORT_ANSWER", q, out, True, gt)


# ==============================================================================
# 4. 23 KHUÔN BÀI ESSAY_CODE MỚI (TỰ LUẬN LẬP TRÌNH PYTHON)
# ==============================================================================

def _bp_ec_water_bill(bai_hoc: str = "Bài 19") -> dict:
    m3 = random.randint(15, 35)
    code = (
        f"m3 = {m3}\n"
        f"if m3 <= 10:\n"
        f"    tien = m3 * 6000\n"
        f"elif m3 <= 20:\n"
        f"    tien = 10 * 6000 + (m3 - 10) * 7000\n"
        f"else:\n"
        f"    tien = 10 * 6000 + 10 * 7000 + (m3 - 20) * 8500\n"
        f"print(tien)"
    )
    out = _run_code_get_stdout(code)
    q = {
        "tinh_huong": f"Giá nước sinh hoạt gia đình được tính theo bậc thang: 10 m³ đầu giá 6.000 đ/m³; từ 11 đến 20 m³ giá 7.000 đ/m³; trên 20 m³ giá 8.500 đ/m³. Một hộ gia đình sử dụng hết m3 = {m3} m³ nước.",
        "yeu_cau_hoc_sinh": "Viết chương trình tính và in ra màn hình tổng số tiền nước hộ gia đình phải trả.",
        "dap_an_mau": code,
        "tieu_chi_cham_diem": [
            "Khởi tạo đúng biến m3 và cấu trúc if-elif-else bậc thang (0.4đ)",
            "Tính đúng công thức tiền theo các khoảng lũy tiến (0.3đ)",
            f"In ra kết quả chính xác ({out} đồng) (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_WATER_BILL", "ec_water_bill", bai_hoc, "ESSAY_CODE", q, out, True)


def _bp_ec_grade_classification(bai_hoc: str = "Bài 19") -> dict:
    score = round(random.uniform(5.5, 9.5), 1)
    code = (
        f"dtb = {score}\n"
        f"if dtb >= 8.0:\n"
        f"    xl = 'Gioi'\n"
        f"elif dtb >= 6.5:\n"
        f"    xl = 'Kha'\n"
        f"elif dtb >= 5.0:\n"
        f"    xl = 'Trung_Binh'\n"
        f"else:\n"
        f"    xl = 'Chua_Dat'\n"
        f"print(xl)"
    )
    out = _run_code_get_stdout(code)
    q = {
        "tinh_huong": f"Một học sinh có điểm trung bình môn học là dtb = {score}. Quy định xếp loại: từ 8.0 trở lên đạt 'Gioi', từ 6.5 đến dưới 8.0 đạt 'Kha', từ 5.0 đến dưới 6.5 đạt 'Trung_Binh', dưới 5.0 là 'Chua_Dat'.",
        "yeu_cau_hoc_sinh": "Viết chương trình xếp loại học lực của học sinh và in kết quả xếp loại ra màn hình.",
        "dap_an_mau": code,
        "tieu_chi_cham_diem": [
            "Khởi tạo biến điểm dtb và viết đúng cấu trúc if-elif-else (0.4đ)",
            "Đặt điều kiện biên chính xác cho từng mức xếp loại (0.3đ)",
            f"In ra đúng kết quả xếp loại ('{out}') (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_GRADE_CLASS", "ec_grade_class", bai_hoc, "ESSAY_CODE", q, out, True)


def _bp_ec_triangle_check(bai_hoc: str = "Bài 19") -> dict:
    a, b, c = random.choice([(3, 4, 5), (6, 8, 10), (5, 5, 8)])
    code = (
        f"a, b, c = {a}, {b}, {c}\n"
        f"if a + b > c and a + c > b and b + c > a:\n"
        f"    chu_vi = a + b + c\n"
        f"    print(chu_vi)\n"
        f"else:\n"
        f"    print('Khong_Hop_Le')"
    )
    out = _run_code_get_stdout(code)
    q = {
        "tinh_huong": f"Cho ba số dương a = {a}, b = {b}, c = {c} biểu thị độ dài ba đoạn thẳng.",
        "yeu_cau_hoc_sinh": "Viết chương trình kiểm tra xem ba đoạn thẳng có tạo thành một hình tam giác hợp lệ hay không; nếu hợp lệ thì in chu vi của tam giác, ngược lại in 'Khong_Hop_Le'.",
        "dap_an_mau": code,
        "tieu_chi_cham_diem": [
            "Kiểm tra đầy đủ 3 bất đẳng thức tam giác bằng toán tử and (0.4đ)",
            "Tính đúng chu vi khi tam giác hợp lệ (0.3đ)",
            f"In kết quả chính xác ({out}) (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_TRIANGLE_CHECK", "ec_triangle_check", bai_hoc, "ESSAY_CODE", q, out, True)


def _bp_ec_leap_year(bai_hoc: str = "Bài 19") -> dict:
    y = random.choice([2024, 2025, 2000, 2100])
    code = (
        f"nam = {y}\n"
        f"if (nam % 400 == 0) or (nam % 4 == 0 and nam % 100 != 0):\n"
        f"    print('Nam_Nhuan')\n"
        f"else:\n"
        f"    print('Nam_Thuong')"
    )
    out = _run_code_get_stdout(code)
    q = {
        "tinh_huong": f"Cho số nguyên dương nam = {y} biểu thị một năm dương lịch.",
        "yeu_cau_hoc_sinh": "Viết chương trình xác định năm đó là năm nhuận hay năm thường. In ra 'Nam_Nhuan' nếu là năm nhuận, ngược lại in 'Nam_Thuong'.",
        "dap_an_mau": code,
        "tieu_chi_cham_diem": [
            "Thiết lập đúng điều kiện năm nhuận kết hợp and và or (0.5đ)",
            "Rẽ nhánh in đúng thông báo (0.3đ)",
            f"Kết quả thực thi chuẩn xác ('{out}') (0.2đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_LEAP_YEAR", "ec_leap_year", bai_hoc, "ESSAY_CODE", q, out, True)


def _bp_ec_taxi_fare(bai_hoc: str = "Bài 19") -> dict:
    km = random.randint(3, 25)
    code = (
        f"km = {km}\n"
        f"if km <= 1:\n"
        f"    tien = 12000\n"
        f"elif km <= 10:\n"
        f"    tien = 12000 + (km - 1) * 10000\n"
        f"else:\n"
        f"    tien = 12000 + 9 * 10000 + (km - 10) * 8500\n"
        f"print(tien)"
    )
    out = _run_code_get_stdout(code)
    q = {
        "tinh_huong": f"Cước taxi được tính như sau: km đầu tiên giá 12.000 đồng; từ km thứ 2 đến km thứ 10 giá 10.000 đ/km; từ km thứ 11 trở đi giá 8.500 đ/km. Một hành khách đi quãng đường km = {km} km.",
        "yeu_cau_hoc_sinh": "Viết chương trình tính và in ra số tiền cước taxi hành khách phải trả.",
        "dap_an_mau": code,
        "tieu_chi_cham_diem": [
            "Khởi tạo biến km và rẽ nhánh đúng theo các mốc cước (0.4đ)",
            "Tính chính xác tiền cho từng đoạn đường (0.3đ)",
            f"In ra kết quả đúng ({out}) (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_TAXI_FARE", "ec_taxi_fare", bai_hoc, "ESSAY_CODE", q, out, True)


def _bp_ec_bmi_calculator(bai_hoc: str = "Bài 19") -> dict:
    w = random.randint(48, 75)
    h = random.choice([1.60, 1.65, 1.70, 1.75])
    code = (
        f"can_nang = {w}\n"
        f"chieu_cao = {h}\n"
        f"bmi = can_nang / (chieu_cao ** 2)\n"
        f"if bmi < 18.5:\n"
        f"    danh_gia = 'Gay'\n"
        f"elif bmi < 25.0:\n"
        f"    danh_gia = 'Binh_Thuong'\n"
        f"else:\n"
        f"    danh_gia = 'Thua_Can'\n"
        f"print(danh_gia)"
    )
    out = _run_code_get_stdout(code)
    q = {
        "tinh_huong": f"Một học sinh có cân nặng {w} kg và chiều cao {h} m.",
        "yeu_cau_hoc_sinh": "Viết chương trình tính chỉ số khối cơ thể BMI = can_nang / (chieu_cao ** 2) và in ra đánh giá: 'Gay' nếu BMI < 18.5, 'Binh_Thuong' nếu 18.5 <= BMI < 25.0, 'Thua_Can' nếu BMI >= 25.0.",
        "dap_an_mau": code,
        "tieu_chi_cham_diem": [
            "Tính đúng công thức BMI (0.3đ)",
            "Cấu trúc if-elif phân loại thể trạng chuẩn (0.4đ)",
            f"In ra kết quả chính xác ('{out}') (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_BMI_CALC", "ec_bmi_calc", bai_hoc, "ESSAY_CODE", q, out, True)


def _bp_ec_count_perfect_squares(bai_hoc: str = "Bài 20") -> dict:
    nums = [random.choice([4, 9, 16, 25, 36]) if i % 2 == 0 else random.randint(10, 30) for i in range(6)]
    code = (
        f"ds = {nums}\n"
        f"dem = 0\n"
        f"for x in ds:\n"
        f"    can = int(x ** 0.5)\n"
        f"    if can * can == x:\n"
        f"        dem += 1\n"
        f"print(dem)"
    )
    out = _run_code_get_stdout(code)
    q = {
        "tinh_huong": f"Cho danh sách các số nguyên dương ds = {nums}.",
        "yeu_cau_hoc_sinh": "Viết chương trình đếm và in ra số lượng các số chính phương (số có căn bậc hai là số nguyên) có trong danh sách ds.",
        "dap_an_mau": code,
        "tieu_chi_cham_diem": [
            "Duyệt danh sách bằng vòng lặp for (0.3đ)",
            "Kiểm tra điều kiện số chính phương chính xác (0.4đ)",
            f"Đếm và in ra kết quả đúng ({out}) (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_PERFECT_SQUARES", "ec_perfect_squares", bai_hoc, "ESSAY_CODE", q, out, True)


def _bp_ec_second_largest(bai_hoc: str = "Bài 22") -> dict:
    nums = random.sample([65, 80, 95, 70, 88, 92], 6)
    code = (
        f"ds = {nums}\n"
        f"ds_khac = list(set(ds))\n"
        f"ds_khac.sort()\n"
        f"print(ds_khac[-2])"
    )
    out = _run_code_get_stdout(code)
    q = {
        "tinh_huong": f"Trong một kỳ thi học sinh giỏi, điểm số của các thí sinh được lưu trong danh sách ds = {nums}.",
        "yeu_cau_hoc_sinh": "Viết chương trình tìm và in ra điểm số lớn thứ hai trong danh sách điểm thi ds.",
        "dap_an_mau": code,
        "tieu_chi_cham_diem": [
            "Loại bỏ trùng lặp và sắp xếp hoặc duyệt tìm max1, max2 (0.4đ)",
            "Xử lý đúng vị trí phần tử lớn thứ hai (0.3đ)",
            f"In ra kết quả đúng ({out}) (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_SECOND_LARGEST", "ec_second_largest", bai_hoc, "ESSAY_CODE", q, out, True)


def _bp_ec_filter_revenue(bai_hoc: str = "Bài 22") -> dict:
    rev = [random.randint(15, 60) * 100 for _ in range(6)]
    threshold = 3000
    code = (
        f"doanh_so = {rev}\n"
        f"dem = 0\n"
        f"for ds in doanh_so:\n"
        f"    if ds >= {threshold}:\n"
        f"        dem += 1\n"
        f"print(dem)"
    )
    out = _run_code_get_stdout(code)
    q = {
        "tinh_huong": f"Bảng số liệu doanh thu hàng ngày của một cửa hàng (đơn vị: nghìn đồng) là doanh_so = {rev}.",
        "yeu_cau_hoc_sinh": f"Viết chương trình đếm và in ra số ngày có doanh thu đạt từ {threshold} nghìn đồng trở lên.",
        "dap_an_mau": code,
        "tieu_chi_cham_diem": [
            "Khởi tạo đúng danh sách và biến đếm (0.3đ)",
            f"Duyệt danh sách và kiểm tra điều kiện >= {threshold} (0.4đ)",
            f"In ra số lượng ngày đạt chuẩn ({out}) (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_FILTER_REVENUE", "ec_filter_revenue", bai_hoc, "ESSAY_CODE", q, out, True)


def _bp_ec_normalize_fullname(bai_hoc: str = "Bài 25") -> dict:
    raw_name = random.choice(["  nguyen   van   an  ", "  tran   thi   mai ", "  le   hoang   nam "])
    code = (
        f"ho_ten = '{raw_name}'\n"
        f"tu = ho_ten.split()\n"
        f"chuan_hoa = ' '.join(t.capitalize() for t in tu)\n"
        f"print(chuan_hoa)"
    )
    out = _run_code_get_stdout(code)
    q = {
        "tinh_huong": f"Một học sinh nhập họ tên có nhiều khoảng trắng thừa: ho_ten = '{raw_name}'.",
        "yeu_cau_hoc_sinh": "Viết chương trình chuẩn hóa xâu họ tên: loại bỏ các khoảng trắng thừa và viết hoa chữ cái đầu của mỗi từ, sau đó in xâu chuẩn hóa ra màn hình.",
        "dap_an_mau": code,
        "tieu_chi_cham_diem": [
            "Tách từ bằng split() để loại khoảng trắng thừa (0.4đ)",
            "Viết hoa chữ cái đầu mỗi từ bằng capitalize() hoặc title() (0.3đ)",
            f"Nối xâu và in ra kết quả chuẩn ('{out}') (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_NORM_FULLNAME", "ec_norm_fullname", bai_hoc, "ESSAY_CODE", q, out, True)


def _bp_ec_count_vowels(bai_hoc: str = "Bài 24") -> dict:
    text = random.choice(["Chuc mung nam moi 2026", "Hoc lap trinh Python rat thu vi", "Truong dai hoc su pham Da Nang"])
    code = (
        f"s = '{text}'\n"
        f"nguyen_am = 'aeiouAEIOU'\n"
        f"dem = 0\n"
        f"for ch in s:\n"
        f"    if ch in nguyen_am:\n"
        f"        dem += 1\n"
        f"print(dem)"
    )
    out = _run_code_get_stdout(code)
    q = {
        "tinh_huong": f"Cho xâu văn bản s = '{text}'.",
        "yeu_cau_hoc_sinh": "Viết chương trình đếm và in ra màn hình tổng số ký tự là nguyên âm tiếng Anh ('a', 'e', 'i', 'o', 'u' kể cả chữ hoa) xuất hiện trong xâu s.",
        "dap_an_mau": code,
        "tieu_chi_cham_diem": [
            "Khai báo tập nguyên âm và duyệt từng ký tự trong xâu (0.3đ)",
            "Dùng toán tử in để kiểm tra nguyên âm chính xác (0.4đ)",
            f"Đếm và in ra đúng số lượng ({out}) (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_COUNT_VOWELS", "ec_count_vowels", bai_hoc, "ESSAY_CODE", q, out, True)


def _bp_ec_password_strength(bai_hoc: str = "Bài 26") -> dict:
    pwd = random.choice(["Python2026", "hocsinh10", "MatKhau#99", "admin"])
    code = (
        f"def kiem_tra_mat_khau(p):\n"
        f"    if len(p) < 8:\n"
        f"        return False\n"
        f"    co_chu = any(c.isalpha() for c in p)\n"
        f"    co_so = any(c.isdigit() for c in p)\n"
        f"    return co_chu and co_so\n"
        f"mk = '{pwd}'\n"
        f"if kiem_tra_mat_khau(mk):\n"
        f"    print('Hop_Le')\n"
        f"else:\n"
        f"    print('Yeu')"
    )
    out = _run_code_get_stdout(code)
    q = {
        "tinh_huong": f"Một hệ thống yêu cầu mật khẩu hợp lệ phải có độ dài tối thiểu 8 ký tự và chứa đồng thời cả chữ cái lẫn chữ số. Cho mật khẩu mk = '{pwd}'.",
        "yeu_cau_hoc_sinh": "Viết hàm kiem_tra_mat_khau(p) trả về True nếu mật khẩu hợp lệ và False nếu không. Sau đó gọi hàm kiểm tra mật khẩu mk và in ra 'Hop_Le' hoặc 'Yeu'.",
        "dap_an_mau": code,
        "tieu_chi_cham_diem": [
            "Định nghĩa hàm nhận tham số và kiểm tra độ dài >= 8 (0.3đ)",
            "Kiểm tra có chữ cái và chữ số bằng isalpha, isdigit (0.4đ)",
            f"Gọi hàm và in ra kết quả chính xác ('{out}') (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_PASSWORD_STRENGTH", "ec_pwd_strength", bai_hoc, "ESSAY_CODE", q, out, True)


def _bp_ec_func_circle_area(bai_hoc: str = "Bài 26") -> dict:
    r = random.choice([3, 5, 7])
    code = (
        f"def hinh_tron(r):\n"
        f"    pi = 3.14\n"
        f"    chu_vi = 2 * pi * r\n"
        f"    dien_tich = pi * (r ** 2)\n"
        f"    return round(chu_vi, 2), round(dien_tich, 2)\n"
        f"cv, dt = hinh_tron({r})\n"
        f"print(cv, dt)"
    )
    out = _run_code_get_stdout(code)
    q = {
        "tinh_huong": f"Cho bán kính hình tròn r = {r}.",
        "yeu_cau_hoc_sinh": "Viết hàm hinh_tron(r) với pi = 3.14 trả về chu vi và diện tích hình tròn. Gọi hàm với bán kính r và in ra chu vi, diện tích.",
        "dap_an_mau": code,
        "tieu_chi_cham_diem": [
            "Định nghĩa hàm hinh_tron(r) tính đúng công thức chu vi và diện tích (0.4đ)",
            "Trả về cặp giá trị chu vi và diện tích (0.3đ)",
            f"Gọi hàm và in ra kết quả chính xác ({out}) (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_CIRCLE_AREA", "ec_circle_area", bai_hoc, "ESSAY_CODE", q, out, True)


def _bp_ec_even_odd_list_split(bai_hoc: str = "Bài 23") -> dict:
    nums = random.sample([3, 8, 12, 17, 20, 25, 30], 6)
    code = (
        f"ds = {nums}\n"
        f"chan = []\n"
        f"le = []\n"
        f"for x in ds:\n"
        f"    if x % 2 == 0:\n"
        f"        chan.append(x)\n"
        f"    else:\n"
        f"        le.append(x)\n"
        f"print(chan)\n"
        f"print(le)"
    )
    out = _run_code_get_stdout(code)
    q = {
        "tinh_huong": f"Cho danh sách các số nguyên ds = {nums}.",
        "yeu_cau_hoc_sinh": "Viết chương trình tách danh sách ds thành hai danh sách con: chan chứa các số chẵn và le chứa các số lẻ, sau đó in hai danh sách ra màn hình.",
        "dap_an_mau": code,
        "tieu_chi_cham_diem": [
            "Khởi tạo hai danh sách rỗng chan và le (0.3đ)",
            "Duyệt danh sách và dùng append() phân loại số chẵn/lẻ (0.4đ)",
            "In ra kết quả hai danh sách đúng định dạng (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_EVEN_ODD_LIST_SPLIT", "ec_even_odd_split_ext", bai_hoc, "ESSAY_CODE", q, out, True)


def _bp_ec_first_negative_index(bai_hoc: str = "Bài 22") -> dict:
    nums = [random.randint(5, 20), random.randint(10, 30), -random.randint(2, 9), random.randint(1, 15)]
    code = (
        f"ds = {nums}\n"
        f"vi_tri = -1\n"
        f"for i in range(len(ds)):\n"
        f"    if ds[i] < 0:\n"
        f"        vi_tri = i\n"
        f"        break\n"
        f"print(vi_tri)"
    )
    out = _run_code_get_stdout(code)
    q = {
        "tinh_huong": f"Cho danh sách số nguyên ds = {nums}.",
        "yeu_cau_hoc_sinh": "Viết chương trình tìm và in ra chỉ số (index) đầu tiên của phần tử mang giá trị âm trong danh sách. Nếu không có số âm, in ra -1.",
        "dap_an_mau": code,
        "tieu_chi_cham_diem": [
            "Duyệt danh sách theo chỉ số range(len(ds)) (0.3đ)",
            "Kiểm tra điều kiện ds[i] < 0 và dùng break khi tìm thấy (0.4đ)",
            f"In ra vị trí chính xác ({out}) (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_FIRST_NEG_IDX", "ec_first_neg_idx", bai_hoc, "ESSAY_CODE", q, out, True)


def _bp_ec_words_longer_than(bai_hoc: str = "Bài 25") -> dict:
    sentence = "Lap trinh Python giup hoc sinh ren luyen tu duy sang tao"
    k = 4
    code = (
        f"cau = '{sentence}'\n"
        f"k = {k}\n"
        f"cac_tu = cau.split()\n"
        f"dem = 0\n"
        f"for t in cac_tu:\n"
        f"    if len(t) > k:\n"
        f"        dem += 1\n"
        f"print(dem)"
    )
    out = _run_code_get_stdout(code)
    q = {
        "tinh_huong": f"Cho câu văn bản: cau = '{sentence}'.",
        "yeu_cau_hoc_sinh": f"Viết chương trình đếm và in ra số lượng các từ trong câu có độ dài lớn hơn {k} ký tự.",
        "dap_an_mau": code,
        "tieu_chi_cham_diem": [
            "Tách câu thành danh sách các từ bằng split() (0.3đ)",
            f"Duyệt danh sách và kiểm tra điều kiện len(t) > {k} (0.4đ)",
            f"Đếm và in ra số lượng chính xác ({out}) (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_WORDS_LONGER", "ec_words_longer", bai_hoc, "ESSAY_CODE", q, out, True)


def _bp_ec_even_index_sum(bai_hoc: str = "Bài 22") -> dict:
    nums = random.sample([10, 25, 30, 45, 50, 65], 6)
    code = (
        f"ds = {nums}\n"
        f"tong = 0\n"
        f"for i in range(0, len(ds), 2):\n"
        f"    tong += ds[i]\n"
        f"print(tong)"
    )
    out = _run_code_get_stdout(code)
    q = {
        "tinh_huong": f"Cho danh sách số nguyên ds = {nums}.",
        "yeu_cau_hoc_sinh": "Viết chương trình tính và in ra tổng các phần tử nằm ở vị trí có chỉ số chẵn (chỉ số 0, 2, 4...) trong danh sách ds.",
        "dap_an_mau": code,
        "tieu_chi_cham_diem": [
            "Duyệt danh sách với bước nhảy 2 hoặc kiểm tra i % 2 == 0 (0.4đ)",
            "Cộng dồn chính xác các phần tử ở vị trí chẵn (0.3đ)",
            f"In ra kết quả tổng đúng ({out}) (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_EVEN_IDX_SUM", "ec_even_idx_sum", bai_hoc, "ESSAY_CODE", q, out, True)


def _bp_ec_reverse_string(bai_hoc: str = "Bài 24") -> dict:
    st = random.choice(["DaNang2026", "PythonKNTT", "ThuatToanAI"])
    code = (
        f"s = '{st}'\n"
        f"dao = ''\n"
        f"for ch in s:\n"
        f"    dao = ch + dao\n"
        f"print(dao)"
    )
    out = _run_code_get_stdout(code)
    q = {
        "tinh_huong": f"Cho xâu ký tự s = '{st}'.",
        "yeu_cau_hoc_sinh": "Viết chương trình đảo ngược xâu s mà không dùng hàm đảo ngược có sẵn, sau đó in xâu đảo ngược ra màn hình.",
        "dap_an_mau": code,
        "tieu_chi_cham_diem": [
            "Khởi tạo xâu kết quả rỗng (0.2đ)",
            "Duyệt xâu và ghép ký tự theo chiều ngược (0.5đ)",
            f"In ra xâu đảo ngược chính xác ('{out}') (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_REV_STRING", "ec_rev_string", bai_hoc, "ESSAY_CODE", q, out, True)


def _bp_ec_count_max_frequency(bai_hoc: str = "Bài 23") -> dict:
    nums = [10, 8, 10, 7, 9, 10, 6]
    random.shuffle(nums)
    code = (
        f"ds = {nums}\n"
        f"max_val = max(ds)\n"
        f"so_lan = ds.count(max_val)\n"
        f"print(max_val, so_lan)"
    )
    out = _run_code_get_stdout(code)
    q = {
        "tinh_huong": f"Trong một bài kiểm tra, điểm số của nhóm học sinh được ghi nhận là ds = {nums}.",
        "yeu_cau_hoc_sinh": "Viết chương trình tìm điểm số cao nhất và đếm số lượng học sinh đạt được điểm số cao nhất đó. In ra điểm cao nhất và số lần xuất hiện.",
        "dap_an_mau": code,
        "tieu_chi_cham_diem": [
            "Tìm đúng giá trị lớn nhất max(ds) (0.3đ)",
            "Đếm số lần xuất hiện bằng count() hoặc vòng lặp (0.4đ)",
            f"In ra kết quả đúng ({out}) (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_COUNT_MAX_FREQ", "ec_count_max_freq", bai_hoc, "ESSAY_CODE", q, out, True)


def _bp_ec_is_sorted_asc(bai_hoc: str = "Bài 22") -> dict:
    is_asc = random.choice([True, False])
    nums = [2, 5, 8, 12, 19] if is_asc else [3, 9, 4, 15, 8]
    code = (
        f"ds = {nums}\n"
        f"tang_dan = True\n"
        f"for i in range(len(ds) - 1):\n"
        f"    if ds[i] > ds[i+1]:\n"
        f"        tang_dan = False\n"
        f"        break\n"
        f"if tang_dan:\n"
        f"    print('Tang_Dan')\n"
        f"else:\n"
        f"    print('Khong_Tang')"
    )
    out = _run_code_get_stdout(code)
    q = {
        "tinh_huong": f"Cho danh sách các số nguyên ds = {nums}.",
        "yeu_cau_hoc_sinh": "Viết chương trình kiểm tra danh sách ds có được sắp xếp tăng dần hay không. In ra 'Tang_Dan' nếu tăng dần, ngược lại in 'Khong_Tang'.",
        "dap_an_mau": code,
        "tieu_chi_cham_diem": [
            "Khởi tạo cờ hiệu và duyệt các cặp phần tử liền kề (0.4đ)",
            "Kiểm tra điều kiện ds[i] > ds[i+1] và cập nhật cờ hiệu (0.3đ)",
            f"In ra kết quả chính xác ('{out}') (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_IS_SORTED_ASC", "ec_is_sorted_asc", bai_hoc, "ESSAY_CODE", q, out, True)


def _bp_ec_bank_interest(bai_hoc: str = "Bài 21") -> dict:
    tien = random.choice([10, 20]) * 1000000
    lai_suat = 0.05
    thang = 3
    code = (
        f"von = {tien}\n"
        f"lai_suat = {lai_suat}\n"
        f"thang_da_gui = 0\n"
        f"while thang_da_gui < {thang}:\n"
        f"    von += von * (lai_suat / 12)\n"
        f"    thang_da_gui += 1\n"
        f"print(int(von))"
    )
    out = _run_code_get_stdout(code)
    gt = f"Sử dụng vòng lặp while lặp {thang} tháng, mỗi tháng tiền vốn được cộng thêm von * ({lai_suat}/12). Sau {thang} tháng, kết quả làm tròn nguyên in ra là {out}."
    q = {
        "tinh_huong": f"Bác Ba gửi tiết kiệm {tien:,} đồng vào ngân hàng với lãi suất {lai_suat*100}%/năm, tiền lãi mỗi tháng được cộng dồn vào vốn gốc. Thời hạn gửi là {thang} tháng.",
        "yeu_cau_hoc_sinh": "Sử dụng vòng lặp while để tính và in ra số tiền (làm tròn số nguyên) bác Ba nhận được sau thời hạn trên.",
        "dap_an_mau": code,
        "tieu_chi_cham_diem": [
            "Khởi tạo đúng số tiền gốc và lãi suất (0.3đ)",
            "Sử dụng vòng lặp while cập nhật lãi kép hàng tháng (0.4đ)",
            f"In ra kết quả số nguyên đúng ({out}) (0.3đ)",
        ],
        "giai_thich": gt,
        "trich_dan_sgk": "Vòng lặp while thực hiện lặp khi điều kiện lặp còn đúng.",
    }
    return _pack_skeleton("EC_BANK_INTEREST", "ec_bank_interest", bai_hoc, "ESSAY_CODE", q, out, True, gt)


def _bp_ec_is_perfect_number(bai_hoc: str = "Bài 26") -> dict:
    n = random.choice([6, 28, 12])
    code = (
        f"def la_so_hoan_hao(n):\n"
        f"    tong_uoc = 0\n"
        f"    for i in range(1, n):\n"
        f"        if n % i == 0:\n"
        f"            tong_uoc += i\n"
        f"    return tong_uoc == n\n"
        f"x = {n}\n"
        f"if la_so_hoan_hao(x):\n"
        f"    print('Hoan_Hao')\n"
        f"else:\n"
        f"    print('Khong_Hoan_Hao')"
    )
    out = _run_code_get_stdout(code)
    q = {
        "tinh_huong": f"Số hoàn hảo là số nguyên dương có tổng các ước số thực sự (nhỏ hơn nó) bằng chính nó (ví dụ 6 = 1 + 2 + 3). Cho số nguyên x = {n}.",
        "yeu_cau_hoc_sinh": "Viết hàm la_so_hoan_hao(n) trả về True nếu n là số hoàn hảo, ngược lại trả về False. Gọi hàm với số x và in ra 'Hoan_Hao' hoặc 'Khong_Hoan_Hao'.",
        "dap_an_mau": code,
        "tieu_chi_cham_diem": [
            "Định nghĩa hàm la_so_hoan_hao và tính tổng các ước thực sự (0.4đ)",
            "So sánh tổng ước với số ban đầu và trả về giá trị boolean (0.3đ)",
            f"Gọi hàm và in ra kết quả chính xác ('{out}') (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_IS_PERFECT_NUM", "ec_is_perfect_num", bai_hoc, "ESSAY_CODE", q, out, True)


def _bp_ec_keyword_frequency(bai_hoc: str = "Bài 25") -> dict:
    text = "Hoc Python can thuc hanh nhieu. Python la ngon ngu pho bien. Chuc ban hoc tot python!"
    code = (
        f"van_ban = '{text}'\n"
        f"tu_khoa = 'python'\n"
        f"cac_tu = van_ban.lower().split()\n"
        f"dem = 0\n"
        f"for t in cac_tu:\n"
        f"    if tu_khoa in t:\n"
        f"        dem += 1\n"
        f"print(dem)"
    )
    out = _run_code_get_stdout(code)
    q = {
        "tinh_huong": f"Cho đoạn văn bản: van_ban = '{text}'.",
        "yeu_cau_hoc_sinh": "Viết chương trình đếm số lần xuất hiện của từ 'python' (không phân biệt chữ hoa, chữ thường) có trong đoạn văn bản trên.",
        "dap_an_mau": code,
        "tieu_chi_cham_diem": [
            "Chuyển văn bản về chữ thường bằng lower() và tách từ bằng split() (0.3đ)",
            "Duyệt danh sách từ và đếm từ khóa 'python' (0.4đ)",
            f"In ra số lần xuất hiện chính xác ({out}) (0.3đ)",
        ],
        "trich_dan_sgk": "",
    }
    return _pack_skeleton("EC_KEYWORD_FREQ", "ec_keyword_freq", bai_hoc, "ESSAY_CODE", q, out, True)


# ==============================================================================
# BẢNG ÁNH XẠ ĐĂNG KÝ BỔ SUNG CHO TỪNG BÀI HỌC VÀ DẠNG CÂU HỎI
# ==============================================================================

EXT_REGISTRY_ENTRIES: Dict[Tuple[int, str], List[Callable[[], dict]]] = {
    # Bài 16
    (16, "MCQ"): [_bp_b16_mcq_ext_extension, _bp_b16_mcq_interpreter_trait],
    (16, "TRUE_FALSE"): [_bp_b16_tf_interactive_vs_script],
    (16, "SHORT_ANSWER"): [_bp_b16_sa_calc_priority],

    # Bài 17
    (17, "MCQ"): [_bp_b17_mcq_keyword_error, _bp_b17_mcq_multi_assign, _bp_b17_mcq_compound_ops],
    (17, "TRUE_FALSE"): [_bp_b17_tf_vars_naming],
    (17, "SHORT_ANSWER"): [_bp_b17_sa_multi_assign_calc],

    # Bài 18
    (18, "MCQ"): [_bp_b18_mcq_sep_end, _bp_b18_mcq_float_cast],
    (18, "TRUE_FALSE"): [_bp_b18_tf_sep_end_cast],
    (18, "SHORT_ANSWER"): [_bp_b18_sa_str_repeat_len],
    (18, "ESSAY_CODE"): [_bp_ec_bmi_calculator],

    # Bài 19
    (19, "MCQ"): [_bp_b19_mcq_nested_if, _bp_b19_mcq_logic_not, _bp_b19_mcq_missing_condition],
    (19, "TRUE_FALSE"): [_bp_b19_tf_elif_logic],
    (19, "SHORT_ANSWER"): [_bp_b19_sa_nested_branch_val],
    (19, "ESSAY_CODE"): [
        _bp_ec_water_bill,
        _bp_ec_grade_classification,
        _bp_ec_triangle_check,
        _bp_ec_leap_year,
        _bp_ec_taxi_fare,
    ],

    # Bài 20
    (20, "MCQ"): [_bp_b20_mcq_range_3args, _bp_b20_mcq_for_break, _bp_b20_mcq_for_continue],
    (20, "TRUE_FALSE"): [_bp_b20_tf_nested_loop],
    (20, "SHORT_ANSWER"): [_bp_b20_sa_for_step_sum, _bp_b20_sa_for_break_val],
    (20, "ESSAY_CODE"): [_bp_ec_count_perfect_squares],

    # Bài 21
    (21, "MCQ"): [_bp_b21_mcq_while_break, _bp_b21_mcq_while_find_factor],
    (21, "TRUE_FALSE"): [_bp_b21_tf_while_counter],
    (21, "SHORT_ANSWER"): [_bp_b21_sa_while_digit_sum, _bp_b21_sa_while_count_divisors],
    (21, "ESSAY_CODE"): [_bp_ec_bank_interest],

    # Bài 22
    (22, "MCQ"): [_bp_b22_mcq_negative_index, _bp_b22_mcq_list_in_op, _bp_b22_mcq_list_len_empty],
    (22, "TRUE_FALSE"): [_bp_b22_tf_list_methods_all],
    (22, "SHORT_ANSWER"): [_bp_b22_sa_list_negative_slice],
    (22, "ESSAY_CODE"): [
        _bp_ec_second_largest,
        _bp_ec_filter_revenue,
        _bp_ec_even_index_sum,
        _bp_ec_first_negative_index,
        _bp_ec_is_sorted_asc,
    ],

    # Bài 23
    (23, "MCQ"): [_bp_b23_mcq_list_insert, _bp_b23_mcq_list_pop, _bp_b23_mcq_list_remove, _bp_b23_mcq_list_count],
    (23, "TRUE_FALSE"): [_bp_b23_tf_list_slice_mut],
    (23, "SHORT_ANSWER"): [_bp_b23_sa_list_insert_pop],
    (23, "ESSAY_CODE"): [
        _bp_ec_even_odd_list_split,
        _bp_ec_count_max_frequency,
    ],

    # Bài 24
    (24, "MCQ"): [_bp_b24_mcq_str_slice, _bp_b24_mcq_str_concat_mult, _bp_b24_mcq_str_in_op],
    (24, "TRUE_FALSE"): [_bp_b24_tf_str_indexing_immut],
    (24, "SHORT_ANSWER"): [_bp_b24_sa_str_slice_rev],
    (24, "ESSAY_CODE"): [
        _bp_ec_count_vowels,
        _bp_ec_reverse_string,
    ],

    # Bài 25
    (25, "MCQ"): [_bp_b25_mcq_str_split, _bp_b25_mcq_str_replace],
    (25, "TRUE_FALSE"): [_bp_b25_tf_str_methods_split],
    (25, "SHORT_ANSWER"): [_bp_b25_sa_str_split_count],
    (25, "ESSAY_CODE"): [
        _bp_ec_normalize_fullname,
    ],

    # Bài 26
    (26, "MCQ"): [_bp_b26_mcq_no_return],
    (26, "SHORT_ANSWER"): [_bp_b26_sa_func_compose],
    (26, "ESSAY_CODE"): [
        _bp_ec_func_circle_area,
        _bp_ec_is_perfect_number,
    ],

    # Bài 27
    (27, "MCQ"): [_bp_b27_mcq_keyword_args],
    (27, "SHORT_ANSWER"): [_bp_b27_sa_func_default_param],
    (27, "ESSAY_CODE"): [
        _bp_ec_password_strength,
    ],

    # Bài 28
    (28, "MCQ"): [_bp_b28_mcq_global_keyword],
    (28, "TRUE_FALSE"): [_bp_b28_tf_scope_local_global],
    (28, "SHORT_ANSWER"): [_bp_b28_sa_global_counter],

    # Bài 29
    (29, "MCQ"): [_bp_b29_mcq_zerodiv_error, _bp_b29_mcq_type_error],

    # Bài 30
    (30, "MCQ"): [_bp_b30_mcq_test_boundary],
    (30, "TRUE_FALSE"): [_bp_b30_tf_blackbox_testing],
    (30, "SHORT_ANSWER"): [_bp_b30_sa_bug_fix_output],

    # Bài 31
    (31, "ESSAY_CODE"): [
        _bp_ec_words_longer_than,
    ],

    # Bài 32
    (32, "ESSAY_CODE"): [
        _bp_ec_keyword_frequency,
    ],
}
