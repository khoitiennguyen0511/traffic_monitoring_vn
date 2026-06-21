# BÁO CÁO KẾT QUẢ THỰC NGHIỆM HỆ THỐNG EDGE AI
**Ngày kết xuất:** 21/06/2026 18:54:15  
**Thư mục lưu trữ:** results_summary_20260621_185239/

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
| PyTorch 320x320 (vehicle_custom_best_320.pt) | 320x320 | 5.17 | 7697.6 | 222.2 | 302.7 | 4.5 |
| NCNN Original 320x320 (Non-opt) | 320x320 | 4.99 | 110.5 | 95.3 | 103.5 | 10.5 |
| NCNN FP16 320x320 (Optimized) | 320x320 | 4.99 | 82.7 | 95.0 | 99.9 | 10.5 |
| PyTorch 480x480 (vehicle_custom_best.pt) | 480x480 | 5.18 | 190.1 | 299.2 | 306.4 | 3.3 |
| NCNN Original 480x480 (Non-opt) | 480x480 | 5.02 | 92.1 | 197.2 | 204.4 | 5.1 |
| NCNN FP16 480x480 (Optimized) | 480x480 | 5.02 | 75.8 | 197.9 | 206.4 | 5.1 |

### Đánh giá:
* **Tốc độ suy luận**: Bản NCNN FP16 320x320 đạt tốc độ **10.5 FPS** (Độ trễ trung bình **95.0 ms**), nhanh hơn **gấp 1.8 lần** so với PyTorch gốc (trễ **222.2 ms**).
* **Thời gian nạp mô hình**: NCNN tải xong trong khoảng **100 ms** (nhanh hơn 65 lần so với PyTorch).

---

## 3. KẾT QUẢ TELEMETRY KHI VẬN HÀNH THỰC TẾ (HEADLESS MODE)
Đo đạc trong thời gian chạy 60 giây liên tục dưới áp lực luồng camera H.264 và MQTT:
* **Nhiệt độ CPU trung bình:** 56.9°C (Ngưỡng an toàn không bị throttling)
* **Xung nhịp CPU hoạt động:** 1800 MHz
* **Tốc độ xử lý vòng lặp (Loop FPS) đạt được:** ~23.8 FPS (Tiệm cận mức tối đa thời gian thực)

---

*Lưu ý: Dữ liệu vi phạm chi tiết được lưu trữ trực tiếp trên Máy chủ trung tâm (Windows PC) tại  và có thể theo dõi qua Streamlit Dashboard.*
