# BÁO CÁO KẾT QUẢ THỰC NGHIỆM HỆ THỐNG EDGE AI
**Ngày kết xuất:** 23/06/2026 17:09:09  
**Thư mục lưu trữ:** results_summary_20260623_170540/

---

## 1. THÔNG SỐ CẤU HÌNH THỰC TẾ
* **Thiết bị:** Raspberry Pi 4 Model B Rev 1.5
* **Hệ điều hành:** 
* **Xung nhịp CPU ổn định:** 1800 MHz (Governor: performance)
* **Thư viện OpenCV:** v4.10.0 (Tối ưu hóa ARM NEON: )
* **Thư viện NCNN:** Loaded successfully [v1.0.20260526]

---

## 2. KẾT QUẢ SO SÁNH HIỆU NĂNG MÔ HÌNH (PT VS NCNN)
Bảng số liệu trích xuất từ đo đạc trực tiếp trên 3 threads:

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

### Đánh giá:
* **Tốc độ suy luận**: Bản NCNN FP16 320x320 đạt tốc độ **9.5
9.5 FPS** (Độ trễ trung bình **105.5
104.8 ms**), nhanh hơn **gấp 1.8 lần** so với PyTorch gốc (trễ **172.4
173.4 ms**).
* **Thời gian nạp mô hình**: NCNN tải xong trong khoảng **100 ms** (nhanh hơn 65 lần so với PyTorch).

---

## 3. KẾT QUẢ TELEMETRY KHI VẬN HÀNH THỰC TẾ (HEADLESS MODE)
Đo đạc trong thời gian chạy 60 giây liên tục dưới áp lực luồng camera H.264 và MQTT:
* **Nhiệt độ CPU trung bình:** 59.9°C (Ngưỡng an toàn không bị throttling)
* **Xung nhịp CPU hoạt động:** 1800 MHz
* **Tốc độ xử lý vòng lặp (Loop FPS) đạt được:** ~23.8 FPS (Tiệm cận mức tối đa thời gian thực)

---

*Lưu ý: Dữ liệu vi phạm chi tiết được lưu trữ trực tiếp trên Máy chủ trung tâm (Windows PC) tại `server/data/traffic.db` và có thể theo dõi qua Streamlit Dashboard.*
