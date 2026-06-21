# BẢNG SO SÁNH HIỆU NĂNG MÔ HÌNH (PT vs NCNN)
| Tên Mô Hình | Cỡ Ảnh | Size (MB) | Tải Model (ms) | Trễ Tr.Bình (ms) | Trễ P95 (ms) | FPS Lý Thuyết |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| PyTorch 320x320 (vehicle_custom_best_320.pt) | 320x320 | 5.17 | 7443.2 | 38.2 | 77.1 | 26.2 |
| NCNN Original 320x320 (Non-opt) | 320x320 | 4.99 | 133.4 | 39.6 | 61.0 | 25.3 |
| NCNN FP16 320x320 (Optimized) | 320x320 | 4.99 | 100.1 | 32.6 | 55.4 | 30.7 |
| PyTorch 480x480 (vehicle_custom_best.pt) | 480x480 | 5.18 | 62.9 | 36.4 | 48.3 | 27.5 |
| NCNN Original 480x480 (Non-opt) | 480x480 | 5.02 | 76.4 | 72.8 | 109.9 | 13.7 |
| NCNN FP16 480x480 (Optimized) | 480x480 | 5.02 | 49.8 | 75.8 | 111.8 | 13.2 |