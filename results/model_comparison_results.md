# BẢNG SO SÁNH HIỆU NĂNG MÔ HÌNH (PT vs NCNN)
| Tên Mô Hình | Cỡ Ảnh | Size (MB) | Tải Model (ms) | Trễ Tr.Bình (ms) | Trễ P95 (ms) | FPS Lý Thuyết |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| PyTorch 320x320 (vehicle_custom_best_320.pt) | 320x320 | 5.17 | 7697.6 | 222.2 | 302.7 | 4.5 |
| NCNN Original 320x320 (Non-opt) | 320x320 | 4.99 | 110.5 | 95.3 | 103.5 | 10.5 |
| NCNN FP16 320x320 (Optimized) | 320x320 | 4.99 | 82.7 | 95.0 | 99.9 | 10.5 |
| PyTorch 480x480 (vehicle_custom_best.pt) | 480x480 | 5.18 | 190.1 | 299.2 | 306.4 | 3.3 |
| NCNN Original 480x480 (Non-opt) | 480x480 | 5.02 | 92.1 | 197.2 | 204.4 | 5.1 |
| NCNN FP16 480x480 (Optimized) | 480x480 | 5.02 | 75.8 | 197.9 | 206.4 | 5.1 |