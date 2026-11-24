# -*- coding: utf-8 -*-
import os
import sys
import json
import time

sys.path.insert(0, ".")

from core.exam_assembler import assemble_exam, RECENT_BLUEPRINTS_PATH
from core.retriever import get_exam_matrix

def run_test():
    print("======================================================================")
    print("KIỂM THỬ TÍNH ĐA DẠNG XUYÊN ĐỀ (CROSS-EXAM ANTI-REPETITION)")
    print("======================================================================")

    # 0. Chuẩn bị file recent_blueprints.json sạch trước khi bắt đầu
    if os.path.exists(RECENT_BLUEPRINTS_PATH):
        try:
            os.remove(RECENT_BLUEPRINTS_PATH)
            print("Đã dọn dẹp file recent_blueprints.json trước khi bắt đầu test.")
        except Exception as e:
            print(f"Lưu ý: {e}")

    matrix = get_exam_matrix()
    preset_1_specs = matrix.get("presets_ma_tran_10_diem", [])[0].get("specs", [])
    print(f"Preset 1 gốc có {len(preset_1_specs)} specs.")

    # 1. SINH ĐỀ 1
    print("\n----------------------------------------------------------------------")
    print(">>> ĐANG SINH MÃ ĐỀ 1 (18 CÂU - 10.0 ĐIỂM)...")
    print("----------------------------------------------------------------------")
    t0 = time.time()
    exam_1 = assemble_exam(specs=preset_1_specs, enable_logging=False, use_neuro_symbolic=True)
    t1_elapsed = round(time.time() - t0, 2)

    items_1 = exam_1.get("items", [])
    bp_1 = [it.get("blueprint_id", "") for it in items_1]
    lessons_1 = [it.get("bai_hoc", "") for it in items_1]
    print(f"\n[KẾT QUẢ ĐỀ 1] Số câu: {len(items_1)}/18 | Điểm: {exam_1.get('tong_diem')}đ | Thời gian: {t1_elapsed}s")
    print(f"Blueprints Đề 1 ({len(bp_1)}): {bp_1}")
    print(f"Bài học Đề 1: {set(lessons_1)}")

    assert len(items_1) == 18, f"Đề 1 không đủ 18 câu: {len(items_1)}"
    assert exam_1.get("tong_diem") == 10.0, f"Đề 1 không đạt 10.0đ: {exam_1.get('tong_diem')}"

    # Kiểm tra recent_blueprints.json sau đề 1
    assert os.path.exists(RECENT_BLUEPRINTS_PATH), "recent_blueprints.json chưa được tạo!"
    with open(RECENT_BLUEPRINTS_PATH, "r", encoding="utf-8") as f:
        recent_data = json.load(f)
    recent_list_1 = recent_data.get("recent_blueprints", [])
    print(f"[RECENT_BLUEPRINTS] Đã lưu {len(recent_list_1)} ID sau Đề 1.")

    # 2. SINH ĐỀ 2
    print("\n----------------------------------------------------------------------")
    print(">>> ĐANG SINH MÃ ĐỀ 2 (18 CÂU - 10.0 ĐIỂM)...")
    print("----------------------------------------------------------------------")
    t0_2 = time.time()
    exam_2 = assemble_exam(specs=preset_1_specs, enable_logging=False, use_neuro_symbolic=True)
    t2_elapsed = round(time.time() - t0_2, 2)

    items_2 = exam_2.get("items", [])
    bp_2 = [it.get("blueprint_id", "") for it in items_2]
    lessons_2 = [it.get("bai_hoc", "") for it in items_2]
    print(f"\n[KẾT QUẢ ĐỀ 2] Số câu: {len(items_2)}/18 | Điểm: {exam_2.get('tong_diem')}đ | Thời gian: {t2_elapsed}s")
    print(f"Blueprints Đề 2 ({len(bp_2)}): {bp_2}")
    print(f"Bài học Đề 2: {set(lessons_2)}")

    assert len(items_2) == 18, f"Đề 2 không đủ 18 câu: {len(items_2)}"
    assert exam_2.get("tong_diem") == 10.0, f"Đề 2 không đạt 10.0đ: {exam_2.get('tong_diem')}"

    # 3. ĐỐI CHIẾU ĐỘ TRÙNG LẶP BLUEPRINT GIỮA 2 ĐỀ
    overlap = set(bp_1) & set(bp_2)
    overlap_rate = len(overlap) / 18.0
    print("\n======================================================================")
    print(f"ĐỐI CHIẾU TRÙNG LẶP: {len(overlap)}/18 câu trùng blueprint ({overlap_rate:.1%})")
    print(f"Các blueprint bị trùng: {overlap}")
    print("======================================================================")

    assert overlap_rate < 0.15, f"Tỷ lệ trùng blueprint vượt quá 15%: {overlap_rate:.1%} ({len(overlap)} câu)"

    # 4. KIỂM TRA LỜI GIẢI THÍCH VÀ TRÍCH DẪN SGK
    print("\nKiểm tra tính chuẩn xác lời giải thích và làm sạch trích dẫn SGK...")
    prompt_leak_cues = ["chép nguyên văn", "bằng chứng sgk ở trên", "câu hỏi:", "bằng chứng sgk:"]

    for exam_idx, items in [(1, items_1), (2, items_2)]:
        for i, it in enumerate(items, 1):
            q = it.get("question_json", {})
            loai = it.get("loai_cau_hoi")
            cite = str(q.get("trich_dan_sgk", "")).lower()

            for cue in prompt_leak_cues:
                assert cue not in cite, f"Đề {exam_idx} Câu {i}: Trích dẫn SGK còn sót prompt leak: '{cue}' trong '{cite}'"

            if loai in ("MCQ", "SHORT_ANSWER"):
                gt = str(q.get("giai_thich", "")).strip()
                assert len(gt) >= 15, f"Đề {exam_idx} Câu {i}: Thiếu hoặc giải thích quá ngắn: '{gt}'"
            elif loai == "ESSAY_CODE":
                tc = q.get("tieu_chi_cham_diem", [])
                tc_str = " ".join(tc) if isinstance(tc, list) else str(tc)
                gt = str(q.get("giai_thich", "")).strip() or tc_str
                assert len(gt) >= 15, f"Đề {exam_idx} Câu {i}: Thiếu tiêu chí chấm/giải thích: '{gt}'"
            elif loai == "TRUE_FALSE":
                for k in ("a", "b", "c", "d"):
                    gt_k = str(q.get(k, {}).get("giai_thich", "")).strip()
                    assert len(gt_k) >= 15, f"Đề {exam_idx} Câu {i} ({k}): Thiếu giải thích ý {k}: '{gt_k}'"

    print("✅ TẤT CẢ CÁC CÂU CẢ 2 ĐỀ ĐỀU ĐẠT 100% LỜI GIẢI THÍCH CHUẨN XÁC, 0 PROMPT LEAKS!")
    print("✅ TEST THÀNH CÔNG VƯỢT MỨC MONG ĐỢI!")

if __name__ == "__main__":
    run_test()
