# BẢNG SO SÁNH HIỆU NĂNG MÔ HÌNH (PT vs NCNN)
| Tên Mô Hình | Cỡ Ảnh | Size (MB) | Tải Model (ms) | Trễ Tr.Bình (ms) | Trễ P95 (ms) | FPS Lý Thuyết |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| PyTorch 320x320 (vehicle_custom_best_320.pt) | 320x320 | 5.17 | 3595.2 | 17.9 | 19.9 | 55.9 |
| NCNN Original 320x320 (Non-opt) | 320x320 | 4.99 | 42.9 | 21.2 | 26.9 | 47.1 |
| NCNN FP16 320x320 (Optimized) | 320x320 | 4.99 | 36.3 | 20.7 | 23.1 | 48.4 |
| PyTorch 320x320 Toy (vehicle_custom_best_320_(toy).pt) | 320x320 | 5.17 | 44.0 | 19.1 | 23.0 | 52.2 |
| NCNN FP16 320x320 Toy (Optimized) | 320x320 | 4.99 | 38.6 | 19.4 | 23.6 | 51.5 |
| PyTorch 480x480 (vehicle_custom_best.pt) | 480x480 | 5.18 | 49.0 | 27.3 | 33.4 | 36.7 |
| NCNN Original 480x480 (Non-opt) | 480x480 | 5.02 | 39.8 | 44.1 | 53.7 | 22.7 |
| NCNN FP16 480x480 (Optimized) | 480x480 | 5.02 | 38.0 | 37.0 | 45.6 | 27.0 |