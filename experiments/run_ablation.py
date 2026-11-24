import os
import sys
import json
import time
import argparse
import requests
from datetime import datetime
from typing import Any

os.environ["ANONYMIZED_TELEMETRY"] = "False"

# Đảm bảo import được từ thư mục gốc dự án D:\AI_Agent_NCKH
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from core.retriever import retrieve_evidence_package, _get_vector_db, estimate_tokens
from core.validator import validate_question
from core.generator import (
    call_ollama_json,
    _parse_llm_json,
    _build_json_schema_hint,
    _build_prompt,
    MAX_RETRIES,
)
from experiments.logger import log_generation_event

EXP_DIR = os.path.join(BASE_DIR, "experiments")
XLSX_OUT = os.path.join(EXP_DIR, "ablation_results.xlsx")
CHART_OUT = os.path.join(EXP_DIR, "ablation_charts.png")
RAW_JSON_OUT = os.path.join(EXP_DIR, "ablation_raw_results.json")

# ==============================================================================
# BỘ 12 TÁC VỤ CHUẨN CHỦ ĐỀ F (BÀI 17, 19, 20, 22, 26; ĐỦ 4 DẠNG CÂU HỎI)
# ==============================================================================
BENCHMARK_TASKS_12 = [
    {"id": "T01", "bai_hoc": "Bài 17", "loai_cau_hoi": "MCQ", "muc_do": "NB", "chu_de_chi_tiet": "Biến, quy tắc đặt tên biến và lệnh gán trong Python"},
    {"id": "T02", "bai_hoc": "Bài 19", "loai_cau_hoi": "MCQ", "muc_do": "TH", "chu_de_chi_tiet": "Biểu thức lôgic và câu lệnh rẽ nhánh if-else"},
    {"id": "T03", "bai_hoc": "Bài 22", "loai_cau_hoi": "MCQ", "muc_do": "TH", "chu_de_chi_tiet": "Khởi tạo danh sách list, chỉ số và phương thức append"},
    {"id": "T04", "bai_hoc": "Bài 26", "loai_cau_hoi": "MCQ", "muc_do": "NB", "chu_de_chi_tiet": "Hàm thiết kế sẵn và định nghĩa hàm bằng từ khoá def"},
    {"id": "T05", "bai_hoc": "Bài 19", "loai_cau_hoi": "TRUE_FALSE", "muc_do": "TH", "chu_de_chi_tiet": "Đọc hiểu đoạn mã câu lệnh rẽ nhánh if-else"},
    {"id": "T06", "bai_hoc": "Bài 20", "loai_cau_hoi": "TRUE_FALSE", "muc_do": "TH", "chu_de_chi_tiet": "Đọc hiểu vòng lặp for kết hợp hàm range"},
    {"id": "T07", "bai_hoc": "Bài 22", "loai_cau_hoi": "TRUE_FALSE", "muc_do": "VD", "chu_de_chi_tiet": "Duyệt danh sách list và xử lý phần tử"},
    {"id": "T08", "bai_hoc": "Bài 26", "loai_cau_hoi": "TRUE_FALSE", "muc_do": "VD", "chu_de_chi_tiet": "Đọc hiểu hàm tự định nghĩa def và return"},
    {"id": "T09", "bai_hoc": "Bài 17", "loai_cau_hoi": "SHORT_ANSWER", "muc_do": "TH", "chu_de_chi_tiet": "Tính giá trị biểu thức số học và lệnh gán"},
    {"id": "T10", "bai_hoc": "Bài 20", "loai_cau_hoi": "SHORT_ANSWER", "muc_do": "VD", "chu_de_chi_tiet": "Tính tổng bằng vòng lặp for và range"},
    {"id": "T11", "bai_hoc": "Bài 22", "loai_cau_hoi": "ESSAY_CODE", "muc_do": "VD", "chu_de_chi_tiet": "Viết chương trình xử lý danh sách số cụ thể"},
    {"id": "T12", "bai_hoc": "Bài 26", "loai_cau_hoi": "ESSAY_CODE", "muc_do": "VD", "chu_de_chi_tiet": "Viết hàm def tính toán trên số hoặc danh sách cụ thể"},
]

QUICK_TASK_IDS = {"T02", "T06", "T09", "T12"}

CONFIG_NAMES = [
    "Config_1_LLM_Only",
    "Config_2_Naive_RAG",
    "Config_3_RAG_Glossary",
    "Config_4_Full_Agentic_RAG",
]


# ==============================================================================
# CÁC HÀM CHẠY TỪNG CẤU HÌNH (TUẦN TỰ, KHÔNG ĐỔI MODEL GIỮA CHỪNG)
# ==============================================================================

def _run_config_1_llm_only(task: dict, eval_ev: dict) -> dict:
    """Config 1: Chỉ gọi LLM thuần (không RAG, không Glossary, không 1-shot, không tự sửa)."""
    t0 = time.time()
    loai = task["loai_cau_hoi"]
    schema = _build_json_schema_hint(loai)
    prompt = (
        f"Hãy soạn 1 câu hỏi Tin học 10 (Python) cho {task['bai_hoc']} ({task['chu_de_chi_tiet']}), "
        f"dạng {loai}, mức độ {task['muc_do']}.\n"
        f"Chỉ xuất duy nhất 1 khối JSON hợp lệ theo mẫu:\n{schema}"
    )
    try:
        raw = call_ollama_json(prompt, temperature=0.15)
        q_json = _parse_llm_json(raw)
    except Exception as e:
        print(f"      ⚠️ Lỗi LLM Config 1: {e}", flush=True)
        q_json = {}

    val = validate_question(q_json, loai, eval_ev)
    return {
        "question_json": q_json,
        "validation": val,
        "retry_count": 0,
        "latency_sec": round(time.time() - t0, 2),
        "prompt_tokens": estimate_tokens(prompt),
    }


def _run_config_2_naive_rag(task: dict, naive_ctx: str, eval_ev: dict) -> dict:
    """Config 2: Naive RAG (top-3 similarity search không khóa bài học, không Glossary, không 1-shot, không tự sửa)."""
    t0 = time.time()
    loai = task["loai_cau_hoi"]
    schema = _build_json_schema_hint(loai)
    prompt = (
        f"Dựa vào tài liệu sau:\n{naive_ctx}\n\n"
        f"Soạn 1 câu hỏi Tin học 10 cho {task['bai_hoc']} ({task['chu_de_chi_tiet']}), "
        f"dạng {loai}, mức độ {task['muc_do']}.\n"
        f"Xuất duy nhất 1 khối JSON hợp lệ theo mẫu (kèm trich_dan_sgk):\n{schema}"
    )
    try:
        raw = call_ollama_json(prompt, temperature=0.15)
        q_json = _parse_llm_json(raw)
    except Exception as e:
        print(f"      ⚠️ Lỗi LLM Config 2: {e}", flush=True)
        q_json = {}

    val = validate_question(q_json, loai, eval_ev)
    return {
        "question_json": q_json,
        "validation": val,
        "retry_count": 0,
        "latency_sec": round(time.time() - t0, 2),
        "prompt_tokens": estimate_tokens(prompt),
    }


def _run_config_3_rag_glossary(task: dict, eval_ev: dict) -> dict:
    """Config 3: Strict RAG theo bài học + Grounded Glossary + 1-shot Template (chạy 1 lượt, KHÔNG tự sửa)."""
    t0 = time.time()
    loai = task["loai_cau_hoi"]
    dummy_state: Any = {
        "bai_hoc": eval_ev["bai_hoc"],
        "loai_cau_hoi": loai,
        "muc_do": task["muc_do"],
        "evidence_package": eval_ev,
        "feedback": "",
        "retry_count": 0,
    }
    prompt, prompt_tokens = _build_prompt(dummy_state)
    try:
        raw = call_ollama_json(prompt, temperature=0.15)
        q_json = _parse_llm_json(raw)
    except Exception as e:
        print(f"      ⚠️ Lỗi LLM Config 3: {e}", flush=True)
        q_json = {}

    val = validate_question(q_json, loai, eval_ev)
    return {
        "question_json": q_json,
        "validation": val,
        "retry_count": 0,
        "latency_sec": round(time.time() - t0, 2),
        "prompt_tokens": prompt_tokens,
    }


def _run_config_4_full_agentic(task: dict, eval_ev: dict) -> dict:
    """Config 4: Full Agentic RAG (Strict RAG + Glossary + 1-shot + Kiểm định 2 tầng + Sandbox + Tự sửa <= 3 lần)."""
    t0 = time.time()
    loai = task["loai_cau_hoi"]
    feedback = ""
    best_q: dict = {}
    best_val: dict = {}
    best_score = -1.0
    retries_used = 0
    last_tokens = 0

    for attempt in range(MAX_RETRIES + 1):
        temp = min(0.35, 0.15 + 0.08 * attempt)
        state_proxy: Any = {
            "bai_hoc": eval_ev["bai_hoc"],
            "loai_cau_hoi": loai,
            "muc_do": task["muc_do"],
            "evidence_package": eval_ev,
            "feedback": feedback,
            "retry_count": attempt,
        }
        prompt, last_tokens = _build_prompt(state_proxy)
        try:
            raw = call_ollama_json(prompt, temperature=temp)
            q_json = _parse_llm_json(raw)
        except Exception as e:
            print(f"      ⚠️ Lỗi LLM Config 4 lần {attempt + 1}: {e}", flush=True)
            q_json = {}

        val = validate_question(q_json, loai, eval_ev)
        score = float(val.get("diem_chat_luong", 0.0))

        if q_json and (score > best_score or not best_q):
            best_q = q_json
            best_val = val
            best_score = score

        if val.get("is_pass"):
            retries_used = attempt
            break
        retries_used = attempt + 1 if attempt < MAX_RETRIES else MAX_RETRIES
        feedback = val.get("feedback", "")

    latency = round(time.time() - t0, 2)
    final_val = best_val or validate_question({}, loai, eval_ev)

    # Tự động ghi nhận lượt sinh chuẩn vào experiments/system_logs.csv
    log_generation_event(
        bai_hoc=eval_ev["bai_hoc"],
        muc_do=task["muc_do"],
        loai_cau_hoi=loai,
        rule_pass=bool(final_val.get("tier1", {}).get("passed", False)),
        sandbox_verified=bool(final_val.get("sandbox_verified", False)),
        fuzzy_score=float(final_val.get("diem_chat_luong", 0.0)),
        retry_count=retries_used,
        latency_sec=latency,
        trang_thai_duyet="ABLATION_TEST",
    )

    return {
        "question_json": best_q,
        "validation": final_val,
        "retry_count": retries_used,
        "latency_sec": latency,
        "prompt_tokens": last_tokens,
    }


# ==============================================================================
# TỔNG HỢP THỐNG KÊ, XUẤT EXCEL (.XLSX) VÀ VẼ BIỂU ĐỒ (.PNG)
# ==============================================================================

def _compute_summary(rows: list[dict]) -> list[dict]:
    summary = []
    for cfg in CONFIG_NAMES:
        sub = [r for r in rows if r["Config"] == cfg]
        n = len(sub) or 1
        rule_rate = round(100.0 * sum(1 for r in sub if r["Rule_Pass"]) / n, 1)
        dat_rate = round(100.0 * sum(1 for r in sub if r["Xep_Loai"] == "ĐẠT") / n, 1)
        sb_rate = round(100.0 * sum(1 for r in sub if r["Sandbox_Verified"]) / n, 1)
        avg_fuzzy = round(sum(r["Fuzzy_Score"] for r in sub) / n, 3)
        avg_sgk = round(sum(r["SGK_Grounding"] for r in sub) / n, 3)
        avg_cog = round(sum(r["Cognitive_Score"] for r in sub) / n, 3)
        avg_dis = round(sum(r["Distractor_Score"] for r in sub) / n, 3)
        avg_retry = round(sum(r["Retry_Count"] for r in sub) / n, 2)
        avg_lat = round(sum(r["Latency_Sec"] for r in sub) / n, 2)
        summary.append({
            "Config": cfg,
            "So_Cau": len(sub),
            "Rule_Pass_Rate_%": rule_rate,
            "Dat_Rate_%": dat_rate,
            "Sandbox_Verified_%": sb_rate,
            "Avg_Fuzzy_Score": avg_fuzzy,
            "Avg_SGK_Grounding": avg_sgk,
            "Avg_Cognitive": avg_cog,
            "Avg_Distractor": avg_dis,
            "Avg_Retries": avg_retry,
            "Avg_Latency_Sec": avg_lat,
        })
    return summary


def export_excel(rows: list[dict], summary: list[dict]) -> None:
    os.makedirs(EXP_DIR, exist_ok=True)
    wb = openpyxl.Workbook()

    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    bold_font = Font(bold=True)

    def _style_sheet(ws):
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for col in ws.columns:
            max_len = max(len(str(c.value or "")) for c in col)
            ws.column_dimensions[get_column_letter(col[0].column)].width = min(46, max(13, max_len + 3))

    # Sheet 1: Bảng tổng hợp 4 cấu hình
    ws1 = wb.active
    ws1.title = "Tong_Hop_4_Cau_Hinh"
    s_cols = list(summary[0].keys())
    ws1.append(s_cols)
    for row in summary:
        ws1.append([row[c] for c in s_cols])
    for cell in ws1[ws1.max_row]:
        cell.font = bold_font
    _style_sheet(ws1)

    # Sheet 2: Chi tiết từng câu
    ws2 = wb.create_sheet("Chi_Tiet_Tung_Cau")
    d_cols = [
        "Task_ID", "Config", "Bai_Hoc", "Loai_Cau_Hoi", "Muc_Do",
        "Rule_Pass", "Sandbox_Verified", "Fuzzy_Score", "Xep_Loai",
        "SGK_Grounding", "Cognitive_Score", "Distractor_Score",
        "Retry_Count", "Prompt_Tokens", "Latency_Sec", "Ghi_Chu",
    ]
    ws2.append(d_cols)
    for r in rows:
        ws2.append([r.get(c, "") for c in d_cols])
    _style_sheet(ws2)

    # Sheet 3: So sánh theo 4 dạng câu hỏi
    ws3 = wb.create_sheet("Theo_Dang_Cau_Hoi")
    ws3.append(["Loai_Cau_Hoi"] + [f"{c}_AvgFuzzy" for c in CONFIG_NAMES] + [f"{c}_Dat%" for c in CONFIG_NAMES])
    for loai in ("MCQ", "TRUE_FALSE", "SHORT_ANSWER", "ESSAY_CODE"):
        line = [loai]
        for cfg in CONFIG_NAMES:
            sub = [r for r in rows if r["Loai_Cau_Hoi"] == loai and r["Config"] == cfg]
            line.append(round(sum(r["Fuzzy_Score"] for r in sub) / max(len(sub), 1), 3))
        for cfg in CONFIG_NAMES:
            sub = [r for r in rows if r["Loai_Cau_Hoi"] == loai and r["Config"] == cfg]
            line.append(round(100.0 * sum(1 for r in sub if r["Xep_Loai"] == "ĐẠT") / max(len(sub), 1), 1))
        ws3.append(line)
    _style_sheet(ws3)

    try:
        wb.save(XLSX_OUT)
        print(f"\n📊 Đã xuất bảng thực nghiệm Excel tại: {XLSX_OUT}", flush=True)
    except PermissionError:
        alt_xlsx = os.path.join(EXP_DIR, f"ablation_results_{datetime.now().strftime('%H%M%S')}.xlsx")
        wb.save(alt_xlsx)
        print(f"\n⚠️ ablation_results.xlsx đang bị mở bởi Excel -> đã lưu bản mới tại: {alt_xlsx}", flush=True)


def export_charts(rows: list[dict], summary: list[dict]) -> None:
    os.makedirs(EXP_DIR, exist_ok=True)
    short_labels = ["C1: LLM\nOnly", "C2: Naive\nRAG", "C3: RAG +\nGlossary", "C4: Full\nAgentic RAG"]
    x = np.arange(len(CONFIG_NAMES))

    rule_rates = [s["Rule_Pass_Rate_%"] for s in summary]
    dat_rates = [s["Dat_Rate_%"] for s in summary]
    avg_fuzzy = [s["Avg_Fuzzy_Score"] for s in summary]
    avg_sgk = [s["Avg_SGK_Grounding"] for s in summary]
    avg_lat = [s["Avg_Latency_Sec"] for s in summary]

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2), dpi=220)
    fig.suptitle(
        "Thực Nghiệm Đối Sánh 4 Cấu Hình Sinh Đề Tin Học 10 (Chủ đề F – Llama 3.2 3B)",
        fontsize=13,
        fontweight="bold",
        y=0.98,
    )

    # Panel 1: Tỉ lệ đạt Tầng 1 (Hard Gate) và ĐẠT chuẩn (>= 0.75)
    w = 0.35
    b1 = axes[0].bar(x - w / 2, rule_rates, w, label="Đạt Tầng 1 (Hard Gate %)", color="#4C78A8")
    b2 = axes[0].bar(x + w / 2, dat_rates, w, label="Đạt chuẩn Tầng 2 (>=0.75 %)", color="#54A24B")
    axes[0].set_title("Tỉ lệ Đạt Chuẩn Kiểm Định (%)")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(short_labels, fontsize=9)
    axes[0].set_ylim(0, 115)
    axes[0].set_ylabel("Phần trăm (%)")
    axes[0].legend(fontsize=8.5, loc="upper left")
    axes[0].grid(axis="y", linestyle="--", alpha=0.35)
    for bar in list(b1) + list(b2):
        h = bar.get_height()
        axes[0].text(bar.get_x() + bar.get_width() / 2, h + 2, f"{h:.0f}%", ha="center", va="bottom", fontsize=8)

    # Panel 2: Điểm trung bình Logic mờ & Bám nguồn SGK
    b3 = axes[1].bar(x - w / 2, avg_fuzzy, w, label="Điểm Logic mờ TB (0–1)", color="#F58518")
    b4 = axes[1].bar(x + w / 2, avg_sgk, w, label="Độ bám nguồn SGK TB (0–1)", color="#72B7B2")
    axes[1].axhline(0.75, color="red", linestyle="--", linewidth=1.1, label="Ngưỡng ĐẠT (0.75)")
    axes[1].set_title("Chất Lượng Câu Hỏi & Bám Nguồn SGK")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(short_labels, fontsize=9)
    axes[1].set_ylim(0, 1.15)
    axes[1].set_ylabel("Điểm (0.0 – 1.0)")
    axes[1].legend(fontsize=8.5, loc="upper left")
    axes[1].grid(axis="y", linestyle="--", alpha=0.35)
    for bar in list(b3) + list(b4):
        h = bar.get_height()
        axes[1].text(bar.get_x() + bar.get_width() / 2, h + 0.02, f"{h:.2f}", ha="center", va="bottom", fontsize=8)

    # Panel 3: Thời gian xử lý trung bình (Latency) theo cấu hình
    colors_lat = ["#9D755D", "#BAB0AC", "#B279A2", "#E45756"]
    b5 = axes[2].bar(x, avg_lat, width=0.5, color=colors_lat)
    axes[2].set_title("Độ Trễ Trung Bình / Câu (giây)")
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(short_labels, fontsize=9)
    axes[2].set_ylim(0, max(avg_lat + [5]) * 1.25)
    axes[2].set_ylabel("Giây (s)")
    axes[2].grid(axis="y", linestyle="--", alpha=0.35)
    for bar, s in zip(b5, summary):
        h = bar.get_height()
        axes[2].text(
            bar.get_x() + bar.get_width() / 2,
            h + max(avg_lat + [1]) * 0.03,
            f"{h:.1f}s\n({s['Avg_Retries']:.1f} retry)",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    plt.savefig(CHART_OUT, dpi=220)
    plt.close(fig)
    print(f"📈 Đã xuất biểu đồ đối sánh tại: {CHART_OUT}", flush=True)


def print_summary_table(summary: list[dict]) -> None:
    print("\n" + "=" * 114, flush=True)
    print("BẢNG KẾT QUẢ THỰC NGHIỆM ĐỐI SÁNH 4 CẤU HÌNH (ABLATION STUDY - CHỦ ĐỀ F TIN HỌC 10)", flush=True)
    print("=" * 114, flush=True)
    header = (
        f"{'Cấu hình':<26} | {'N':>2} | {'Rule Pass':>9} | {'ĐẠT>=0.75':>9} | "
        f"{'Sandbox':>7} | {'Fuzzy TB':>8} | {'SGK TB':>6} | {'Retries':>7} | {'Latency':>8}"
    )
    print(header, flush=True)
    print("-" * 114, flush=True)
    for s in summary:
        print(
            f"{s['Config']:<26} | {s['So_Cau']:>2} | {s['Rule_Pass_Rate_%']:>8.1f}% | "
            f"{s['Dat_Rate_%']:>8.1f}% | {s['Sandbox_Verified_%']:>6.1f}% | "
            f"{s['Avg_Fuzzy_Score']:>8.3f} | {s['Avg_SGK_Grounding']:>6.3f} | "
            f"{s['Avg_Retries']:>7.2f} | {s['Avg_Latency_Sec']:>7.2f}s",
            flush=True,
        )
    print("=" * 114, flush=True)


def run_ablation(quick: bool = False) -> None:
    tasks = [t for t in BENCHMARK_TASKS_12 if t["id"] in QUICK_TASK_IDS] if quick else BENCHMARK_TASKS_12
    mode_lbl = f"NHANH ({len(tasks)} câu x 4 cấu hình = {len(tasks)*4} lượt)" if quick else f"ĐẦY ĐỦ ({len(tasks)} câu x 4 cấu hình = {len(tasks)*4} lượt)"
    print(f"=== BẮT ĐẦU THỰC NGHIỆM ĐỐI SÁNH 4 CẤU HÌNH - CHẾ ĐỘ {mode_lbl} ===", flush=True)
    t_start = time.time()

    # PHA 1: Tiền truy xuất toàn bộ Evidence Package & Naive RAG trước (tránh tráo model nomic <-> llama3.2 trên 4GB VRAM)
    print("\n[PHA 1] Tiền truy xuất dữ liệu ChromaDB (nomic-embed-text) cho tất cả tác vụ...", flush=True)
    db = _get_vector_db()
    cached_eval_ev: dict[str, dict] = {}
    cached_naive_ctx: dict[str, str] = {}

    for task in tasks:
        tid = task["id"]
        cached_eval_ev[tid] = retrieve_evidence_package(
            bai_hoc=task["bai_hoc"],
            loai_cau_hoi=task["loai_cau_hoi"],
            chu_de_chi_tiet=task["chu_de_chi_tiet"],
            muc_do=task["muc_do"],
            max_context_tokens=950,
        )
        # Naive RAG: truy xuất top-3 toàn DB không khóa bài học
        naive_docs = db.similarity_search(f"{task['bai_hoc']} {task['chu_de_chi_tiet']}", k=3)
        cached_naive_ctx[tid] = "\n---\n".join(d.page_content[:420].strip() for d in naive_docs)
    print(f"   ✅ Đã chuẩn bị xong ngữ cảnh cho {len(tasks)} tác vụ trong {time.time() - t_start:.1f}s.", flush=True)

    # Giải phóng hoàn toàn nomic-embed-text khỏi VRAM trước khi nạp llama3.2_tinhoc10 (tránh nghẽn 4GB VRAM)
    try:
        requests.post("http://localhost:11434/api/embed", json={"model": "nomic-embed-text", "keep_alive": 0}, timeout=10)
        time.sleep(1.5)
        print("   🧹 Đã giải phóng VRAM của nomic-embed-text (keep_alive=0) trước khi chạy LLM.\n", flush=True)
    except Exception:
        pass

    # PHA 2: Chạy tuần tự 4 cấu hình trên từng tác vụ (chỉ giữ llama3.2_tinhoc10 trong VRAM)
    print("[PHA 2] Chạy tuần tự 4 cấu hình trên llama3.2_tinhoc10 (an toàn 4GB VRAM)...", flush=True)
    all_rows: list[dict] = []
    raw_dump: list[dict] = []

    for t_idx, task in enumerate(tasks, 1):
        tid = task["id"]
        ev = cached_eval_ev[tid]
        naive_ctx = cached_naive_ctx[tid]
        print(f"\n--- [{t_idx}/{len(tasks)}] {tid} | {task['bai_hoc']} | {task['loai_cau_hoi']} | {task['muc_do']} ---", flush=True)

        runners = [
            ("Config_1_LLM_Only", lambda: _run_config_1_llm_only(task, ev)),
            ("Config_2_Naive_RAG", lambda: _run_config_2_naive_rag(task, naive_ctx, ev)),
            ("Config_3_RAG_Glossary", lambda: _run_config_3_rag_glossary(task, ev)),
            ("Config_4_Full_Agentic_RAG", lambda: _run_config_4_full_agentic(task, ev)),
        ]

        for cfg_name, fn in runners:
            out = fn()
            val = out["validation"]
            t1_pass = bool(val.get("tier1", {}).get("passed", False))
            sb_ok = bool(val.get("sandbox_verified", False))
            fuzzy = float(val.get("diem_chat_luong", 0.0))
            xep_loai = val.get("xep_loai", "KHÔNG ĐẠT")
            t2_detail = (val.get("tier2") or {}).get("chi_tiet", {})
            sgk_s = float(t2_detail.get("bam_nguon_sgk", 0.0))
            cog_s = float(t2_detail.get("nhan_thuc_su_pham", 0.0))
            dis_s = float(t2_detail.get("chat_luong_nhieu", 0.0))
            note = "; ".join(val.get("tier1", {}).get("errors", []))[:180] if not t1_pass else xep_loai

            row = {
                "Task_ID": tid,
                "Config": cfg_name,
                "Bai_Hoc": task["bai_hoc"],
                "Loai_Cau_Hoi": task["loai_cau_hoi"],
                "Muc_Do": task["muc_do"],
                "Rule_Pass": t1_pass,
                "Sandbox_Verified": sb_ok,
                "Fuzzy_Score": fuzzy,
                "Xep_Loai": xep_loai,
                "SGK_Grounding": sgk_s,
                "Cognitive_Score": cog_s,
                "Distractor_Score": dis_s,
                "Retry_Count": out["retry_count"],
                "Prompt_Tokens": out["prompt_tokens"],
                "Latency_Sec": out["latency_sec"],
                "Ghi_Chu": note,
            }
            all_rows.append(row)
            raw_dump.append({**row, "question_json": out["question_json"]})

            print(
                f"   • {cfg_name:<26}: Rule={'PASS' if t1_pass else 'FAIL'} | "
                f"SB={'OK' if sb_ok else '--'} | Fuzzy={fuzzy:.3f} ({xep_loai:<9}) | "
                f"Retry={out['retry_count']} | {out['latency_sec']:>5.1f}s",
                flush=True,
            )

    summary = _compute_summary(all_rows)
    print_summary_table(summary)
    export_excel(all_rows, summary)
    export_charts(all_rows, summary)

    with open(RAW_JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(
            {"run_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "summary": summary, "details": raw_dump},
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"\n🎉 HOÀN TẤT TOÀN BỘ ABLATION STUDY trong {time.time() - t_start:.1f}s!", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Thực nghiệm đối sánh 4 cấu hình Agentic RAG Tin học 10")
    parser.add_argument("--quick", action="store_true", help="Chạy thử nghiệm nhanh 4 câu mẫu (đủ 4 dạng)")
    args = parser.parse_args()
    run_ablation(quick=args.quick)
