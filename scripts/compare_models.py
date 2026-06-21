#!/usr/bin/env python3
"""
scripts/compare_models.py
==========================
Script đo đạc và so sánh hiệu năng suy luận (Inference Latency & Load Time) 
giữa mô hình PyTorch (.pt) và NCNN cho cả hai cấu hình kích thước: 320x320 và 480x480.
Chạy trực tiếp trên CPU để đưa ra đánh giá chuẩn xác nhất.
"""

import os
import sys
import time
from pathlib import Path
import numpy as np
import cv2

# Đảm bảo mã hóa UTF-8 trên Windows để không lỗi print kí tự tiếng Việt
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass


# Đường dẫn gốc dự án
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "edge_pi4"))

from core.detection import VehicleDetector

def benchmark_model(model_name: str, model_path: str, target_size: int, is_ncnn: bool, num_threads: int = 3, runs: int = 50):
    print(f"\n[BENCHMARK] Đang chạy đánh giá mô hình: {model_name}...")
    print(f"  - Đường dẫn: {model_path}")
    print(f"  - Cỡ ảnh: {target_size}x{target_size} | NCNN: {is_ncnn} | Threads: {num_threads}")

    # 1. Đo thời gian nạp mô hình (Load Time)
    t0 = time.perf_counter()
    detector = VehicleDetector(model_path, target_size=target_size, num_threads=num_threads)
    detector.load()
    load_time_ms = (time.perf_counter() - t0) * 1000.0
    print(f"  - Thời gian nạp: {load_time_ms:.2f} ms")

    # Nạp 1 khung hình thực tế từ video vehicle_counting.mp4 để benchmark chính xác (có chứa xe cộ để chạy NMS/bám vết)
    video_path = str(BASE_DIR / "vehicle_counting.mp4")
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        # Fallback tạo frame ảnh giả lập 960x540 nếu file video bị lỗi/thiếu
        frame = np.random.randint(0, 255, (540, 960, 3), dtype=np.uint8)
    else:
        frame = cv2.resize(frame, (960, 540))

    # 2. Warmup (Khởi động mô hình để tránh trễ lần đầu)
    print("  - Đang khởi động mô hình (Warmup 10 runs)...")
    for _ in range(10):
        detector.detect(frame)

    # 3. Chạy đo đạc chính thức
    print(f"  - Đang thực thi {runs} lần suy luận chính thức...")
    latencies = []
    for i in range(runs):
        t_start = time.perf_counter()
        detector.detect(frame)
        latencies.append((time.perf_counter() - t_start) * 1000.0)

    # Tính toán các chỉ số thống kê
    avg_latency = np.mean(latencies)
    min_latency = np.min(latencies)
    max_latency = np.max(latencies)
    p95_latency = np.percentile(latencies, 95)
    fps = 1000.0 / avg_latency if avg_latency > 0 else 0.0

    # Lấy dung lượng file mô hình
    model_size_mb = 0.0
    p = Path(model_path)
    if is_ncnn:
        if p.is_dir():
            # Ưu tiên các file đã tối ưu (model-opt.*) nếu tồn tại, ngược lại lấy model.ncnn.*
            has_opt = (p / "model-opt.bin").exists() and (p / "model-opt.param").exists()
            bin_name = "model-opt.bin" if has_opt else "model.ncnn.bin"
            param_name = "model-opt.param" if has_opt else "model.ncnn.param"
            for name in [bin_name, param_name]:
                f = p / name
                if f.exists():
                    model_size_mb += f.stat().st_size
        else:
            model_size_mb = p.stat().st_size
    else:
        if p.exists():
            model_size_mb = p.stat().st_size
    model_size_mb /= (1024 * 1024) # bytes to MB

    print(f"  => Kết quả: Avg={avg_latency:.1f}ms | P95={p95_latency:.1f}ms | FPS={fps:.1f} | Size={model_size_mb:.2f}MB")
    return {
        "name": model_name,
        "load_time_ms": load_time_ms,
        "avg_ms": avg_latency,
        "p95_ms": p95_latency,
        "fps": fps,
        "size_mb": model_size_mb
    }

def main():
    import shutil

    # Thư mục chứa các mô hình
    models_dir = BASE_DIR / "shared/models"
    
    # Tạo danh sách tạm lưu các thư mục gốc để dọn dẹp sau
    temp_dirs = []

    # Hàm tạo thư mục mô hình gốc chưa tối ưu từ file .bak nếu có
    def prepare_original_ncnn(model_dir_name):
        src_dir = models_dir / model_dir_name
        dest_dir = models_dir / (model_dir_name + "_original")
        
        param_bak = src_dir / "model.ncnn.param.bak"
        bin_bak = src_dir / "model.ncnn.bin.bak"
        
        if param_bak.exists() and bin_bak.exists():
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(param_bak, dest_dir / "model.ncnn.param")
            shutil.copy2(bin_bak, dest_dir / "model.ncnn.bin")
            temp_dirs.append(dest_dir)
            return str(dest_dir)
        return None

    # Chuẩn bị mô hình gốc chưa tối ưu
    ncnn_320_original_path = prepare_original_ncnn("vehicle_custom_best_320_ncnn_model")
    ncnn_480_original_path = prepare_original_ncnn("vehicle_custom_best_ncnn_model")

    # Danh sách các mô hình cần đánh giá
    models_to_test = [
        {
            "name": "PyTorch 320x320 (vehicle_custom_best_320.pt)",
            "path": str(models_dir / "vehicle_custom_best_320.pt"),
            "size": 320,
            "is_ncnn": False
        }
    ]

    # Nếu có NCNN 320 gốc chưa tối ưu
    if ncnn_320_original_path:
        models_to_test.append({
            "name": "NCNN Original 320x320 (Non-opt)",
            "path": ncnn_320_original_path,
            "size": 320,
            "is_ncnn": True
        })

    # NCNN 320 tối ưu (luôn có)
    models_to_test.append({
        "name": "NCNN FP16 320x320 (Optimized)",
        "path": str(models_dir / "vehicle_custom_best_320_ncnn_model"),
        "size": 320,
        "is_ncnn": True
    })

    # PyTorch 480
    models_to_test.append({
        "name": "PyTorch 480x480 (vehicle_custom_best.pt)",
        "path": str(models_dir / "vehicle_custom_best.pt"),
        "size": 480,
        "is_ncnn": False
    })

    # Nếu có NCNN 480 gốc chưa tối ưu
    if ncnn_480_original_path:
        models_to_test.append({
            "name": "NCNN Original 480x480 (Non-opt)",
            "path": ncnn_480_original_path,
            "size": 480,
            "is_ncnn": True
        })

    # NCNN 480 tối ưu (luôn có)
    models_to_test.append({
        "name": "NCNN FP16 480x480 (Optimized)",
        "path": str(models_dir / "vehicle_custom_best_ncnn_model"),
        "size": 480,
        "is_ncnn": True
    })

    results = []
    for m in models_to_test:
        # Kiểm tra file/thư mục tồn tại trước khi benchmark
        p_path = Path(m["path"])
        if not p_path.exists():
            print(f"\n[WARN] Không tìm thấy đường dẫn mô hình: {m['path']}. Bỏ qua test.")
            continue
            
        try:
            res = benchmark_model(
                model_name=m["name"],
                model_path=m["path"],
                target_size=m["size"],
                is_ncnn=m["is_ncnn"],
                num_threads=3, # Thiết lập 3 threads tối ưu cho Pi 4
                runs=30 # Giảm xuống 30 lần để benchmark nhanh gọn
            )
            results.append(res)
        except Exception as e:
            print(f"[ERROR] Thất bại khi chạy benchmark {m['name']}: {e}")

    # Dọn dẹp các thư mục tạm
    for d in temp_dirs:
        try:
            shutil.rmtree(d)
        except Exception as e:
            print(f"[WARN] Lỗi khi dọn dẹp thư mục tạm {d}: {e}")

    # Vẽ bảng so sánh Markdown
    if not results:
        print("Không có kết quả nào được tạo ra.")
        return

    table_lines = []
    table_lines.append("# BẢNG SO SÁNH HIỆU NĂNG MÔ HÌNH (PT vs NCNN)")
    table_lines.append("| Tên Mô Hình | Cỡ Ảnh | Size (MB) | Tải Model (ms) | Trễ Tr.Bình (ms) | Trễ P95 (ms) | FPS Lý Thuyết |")
    table_lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
    
    for r in results:
        sz = "320x320" if "320" in r["name"] else "480x480"
        table_lines.append(
            f"| {r['name']} | {sz} | {r['size_mb']:.2f} | {r['load_time_ms']:.1f} | {r['avg_ms']:.1f} | {r['p95_ms']:.1f} | {r['fps']:.1f} |"
        )

    report_content = "\n".join(table_lines)
    print("\n" + "="*70)
    print("                 KẾT QUẢ SO SÁNH HIỆU NĂNG MÔ HÌNH")
    print("="*70)
    print(report_content)
    print("="*70 + "\n")

    # Lưu kết quả so sánh ra file cấu hình dùng chung
    out_file = BASE_DIR / "shared/configs/model_comparison_results.md"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(report_content)
    print(f"[INFO] Kết quả lưu tại: {out_file}")

    # Xuất thêm tệp JSON kết quả để dùng làm đầu vào động cho biểu đồ
    import json
    json_file = BASE_DIR / "results/model_comparison_results.json"
    json_file.parent.mkdir(parents=True, exist_ok=True)
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    print(f"[INFO] Kết quả JSON lưu tại: {json_file}")

if __name__ == "__main__":
    main()
