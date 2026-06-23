# BẢNG SO SÁNH HIỆU NĂNG MÔ HÌNH (PT vs NCNN)
| Tên Mô Hình | Cỡ Ảnh | Size (MB) | Tải Model (ms) | Trễ Tr.Bình (ms) | Trễ P95 (ms) | FPS Lý Thuyết |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| PyTorch 320x320 (vehicle_custom_best_320.pt) | 320x320 | 5.17 | 6772.2 | 172.4 | 177.3 | 5.8 |
| NCNN Original 320x320 (Non-opt) | 320x320 | 4.99 | 91.4 | 104.9 | 110.5 | 9.5 |
| NCNN FP16 320x320 (Optimized) | 320x320 | 4.99 | 59.6 | 105.5 | 110.6 | 9.5 |
| PyTorch 320x320 Toy (vehicle_custom_best_320_(toy).pt) | 320x320 | 5.17 | 190.0 | 173.4 | 177.6 | 5.8 |
| NCNN FP16 320x320 Toy (Optimized) | 320x320 | 4.99 | 68.7 | 104.8 | 109.2 | 9.5 |
| PyTorch 480x480 (vehicle_custom_best.pt) | 480x480 | 5.18 | 200.3 | 308.7 | 314.9 | 3.2 |
| NCNN Original 480x480 (Non-opt) | 480x480 | 5.02 | 69.7 | 228.7 | 234.1 | 4.4 |
| NCNN FP16 480x480 (Optimized) | 480x480 | 5.02 | 67.9 | 229.8 | 235.7 | 4.4 |