# PHỤ LỤC: HƯỚNG DẪN CÀI ĐẶT VÀ VẬN HÀNH HỆ THỐNG
*(Đính kèm Báo cáo Đồ án Tốt nghiệp)*

---

Tài liệu này cung cấp hướng dẫn kỹ thuật chi tiết nhằm thiết lập môi trường, cấu hình truyền thông và khởi chạy toàn bộ hệ thống giám sát giao thông thông minh từ đầu cuối (End-to-End). Hướng dẫn được phân chia rõ ràng giữa các tác vụ thực hiện trên máy tính cá nhân (Central Server) và máy tính nhúng tại biên (Raspberry Pi 4 - Edge Agent).

---

## THỰC HIỆN TẢI MÃ NGUỒN (GIT CLONE)

Trước khi tiến hành cài đặt các thành phần, thực hiện tải mã nguồn dự án về cả Máy tính trung tâm (Laptop) và Thiết bị biên (Raspberry Pi 4):
```bash
git clone https://github.com/khoitiennguyen0511/traffic_monitoring_vn.git
cd traffic_monitoring_vn
```

---

## A. KHỞI TẠO HẠ TẦNG MẠNG & MQTT BROKER TRÊN RASPBERRY PI 4

Trước khi cấu hình các thiết bị khác, cần thiết lập kênh truyền thông chung và xác định các địa chỉ IP trong mạng nội bộ.

### A.1. Xác định địa chỉ IP của Raspberry Pi
Mở Terminal trên Raspberry Pi 4 và chạy lệnh:
```bash
hostname -I
```
Ghi lại địa chỉ IP hiển thị (ví dụ: `172.20.10.5`). Địa chỉ này sẽ được dùng làm địa chỉ MQTT Broker cho toàn hệ thống.

### A.2. Cài đặt và cấu hình Mosquitto MQTT Broker
Trên Raspberry Pi 4, tiến hành cài đặt:
1. Cài đặt phần mềm Mosquitto và client:
   ```bash
   sudo apt update
   sudo apt install -y mosquitto mosquitto-clients
   ```
2. Cho phép các thiết bị ngoại vi (như ESP32 và Laptop) kết nối không cần bảo mật (Anonymous) và lắng nghe cổng mạng bằng cách chỉnh sửa cấu hình:
   ```bash
   sudo nano /etc/mosquitto/mosquitto.conf
   ```
   Thêm vào cuối tệp cấu hình:
   ```conf
   listener 1883
   allow_anonymous true
   ```
3. Khởi động lại dịch vụ để áp dụng cấu hình:
   ```bash
   sudo systemctl restart mosquitto
   ```

---

## B. THIẾT LẬP TRÊN MÁY TÍNH TRUNG TÂM (LAPTOP - WINDOWS)

### B.1. Xác định địa chỉ IP của Laptop Windows
Mở **cmd** hoặc **PowerShell** trên Windows và chạy lệnh:
```cmd
ipconfig
```
Xác định địa chỉ **IPv4 Address** của card mạng đang kết nối chung mạng với Raspberry Pi (ví dụ: `172.20.10.2`). Địa chỉ này sẽ được sử dụng để Raspberry Pi gửi ảnh xe vi phạm về máy chủ.

### B.2. Cấu hình Môi trường ảo Python và Thư viện
1. Mở cửa sổ **PowerShell** tại thư mục gốc dự án (`traffic_monitoring_vn`):
   ```powershell
   # Khởi tạo môi trường ảo Python
   python -m venv .venv

   # Kích hoạt môi trường ảo
   .\.venv\Scripts\Activate
   ```
2. Cài đặt các gói thư viện phụ thuộc cho Server và Dashboard:
   ```powershell
   pip install --upgrade pip
   pip install -r server/requirements.txt
   pip install streamlit
   ```

### B.3. Khởi chạy Phân hệ Máy chủ & Dashboard
Mở **hai Terminal riêng biệt** trên Windows, kích hoạt môi trường ảo `.venv` và khởi chạy các dịch vụ:
*   **Dịch vụ API Server (FastAPI):**
    ```powershell
    .\.venv\Scripts\Activate
    python server/main.py
    ```
    *Dịch vụ sẽ tự động tải mô hình định vị biển số và mô hình CRNN OCR vào RAM, sẵn sàng nhận ảnh vi phạm tại cổng 8000.*
*   **Giao diện Quản trị (Streamlit Dashboard):**
    ```powershell
    .\.venv\Scripts\Activate
    streamlit run server/dashboard.py
    ```
    *Giao diện giám sát thời gian thực tự động mở trên trình duyệt tại địa chỉ http://localhost:8501.*

---

## C. THIẾT LẬP VÀ NẠP CHƯƠNG TRÌNH CHO ESP32

### C.1. Cấu hình kết nối mạng nội bộ và MQTT
Trên máy tính trung tâm (Laptop), mở mã nguồn dự án:
1. Mở tệp [credentials.h](file:///d:/traffic_monitoring_vn/esp32/include/credentials.h) và cập nhật thông tin mạng Wi-Fi nội bộ:
   ```cpp
   #define WIFI_SSID "Tên_WiFi_Của_Bạn"
   #define WIFI_PASSWORD "Mật_Khẩu_WiFi"
   ```
2. Mở tệp [mqtt_config.h](file:///d:/traffic_monitoring_vn/esp32/include/mqtt_config.h) và điền địa chỉ IP của Raspberry Pi (MQTT Broker lấy ở bước A.1):
   ```cpp
   #define MQTT_BROKER_HOST "172.20.10.5" // Thay bằng IP thực tế của Raspberry Pi
   ```

### C.2. Biên dịch và nạp code cho ESP32
1. Kết nối bo mạch ESP32 với máy tính trung tâm thông qua cáp USB.
2. Sử dụng Terminal PlatformIO tại thư mục `esp32` để biên dịch, nạp code và theo dõi logs:
   ```powershell
   cd esp32
   pio run -t upload
   pio device monitor
   ```

---

## D. THIẾT LẬP VÀ VẬN HÀNH EDGE AGENT TRÊN RASPBERRY PI 4

### D.1. Thiết lập Môi trường ảo Python & Cài đặt Thư viện
1. Cài đặt các gói biên dịch và thư viện hệ thống cơ bản:
   ```bash
   sudo apt install -y build-essential cmake git libopencv-dev libomp-dev python3-pip python3-venv libvulkan-dev vulkan-tools protobuf-compiler libprotobuf-dev
   ```
2. Tạo và kích hoạt môi trường ảo trong thư mục dự án trên Pi:
   ```bash
   cd ~/traffic_monitoring_vn
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   ```
3. **Cấu hình loại bỏ thư viện nặng (Tối ưu hóa dung lượng):**
   Mở tệp `edge_pi4/requirements.txt` và thêm dấu `#` vào đầu dòng `ultralytics==8.3.207` (comment dòng này) để tránh việc pip tự động tải gói PyTorch nặng hơn 1.5 GB về thẻ nhớ của Pi. Tiến hành cài đặt:
   ```bash
   pip install -r edge_pi4/requirements.txt
   ```

### D.2. Biên dịch NCNN từ mã nguồn
Thực hiện biên dịch và cài đặt thư viện Tencent NCNN C++ SDK và Python binding từ source:
```bash
cd ~
git clone https://github.com/Tencent/ncnn.git
cd ncnn
git submodule update --init
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release -DNCNN_VULKAN=ON -DNCNN_SYSTEM_GLSLANG=OFF -DNCNN_DISABLE_RTTI=OFF -DNCNN_OPENMP=ON -DNCNN_BUILD_TOOLS=ON -DNCNN_INSTALL_SDK=ON -DNCNN_BUILD_BENCHMARK=OFF -DNCNN_BUILD_TESTS=OFF -DNCNN_BUILD_EXAMPLES=OFF ..
make -j4
sudo make install

# Link thư viện tĩnh đã build vào hệ thống /usr/local
sudo mkdir -p /usr/local/lib/ncnn 
sudo cp -r install/include/ncnn /usr/local/include/
sudo cp install/lib/libncnn.a /usr/local/lib/ncnn/
sudo ldconfig

# Cài đặt python binding trong môi trường ảo
source ~/traffic_monitoring_vn/.venv/bin/activate
pip install ncnn
```

### D.3. Cấu hình liên kết mạng và chạy Edge Agent
1. Cấu hình liên kết mạng tại tệp `shared/configs/settings.yaml` trên Pi:
   ```yaml
   mqtt:
     broker: "172.20.10.5"   # Địa chỉ IP của Raspberry Pi (đã lấy ở bước A.1)
     port: 1883
   edge:
     server_host: "172.20.10.2" # Địa chỉ IP của Laptop Windows (đã lấy ở bước B.1)
     server_port: 8000
   ```
2. Khởi chạy Edge Agent NCNN:
   *   **Chế độ GUI (Có màn hình hiển thị):**
       ```bash
       python3 edge_pi4/agent_ncnn.py
       ```
   *   **Chế độ Headless (Qua giao diện dòng lệnh SSH):**
       ```bash
       python3 edge_pi4/agent_ncnn.py --headless
       ```

---

## E. CHẠY THỰC NGHIỆM THU THẬP SỐ LIỆU ĐO ĐẠC (PHỤC VỤ CHƯƠNG 5)

Để tự động đo đạc hiệu năng vi xử lý, so sánh độ trễ suy luận của các mô hình và vẽ các biểu đồ báo cáo phục vụ trực tiếp cho Chương 5 của đồ án tốt nghiệp:
1. Truy cập Terminal của Raspberry Pi, kích hoạt môi trường ảo:
   ```bash
   cd ~/traffic_monitoring_vn
   source .venv/bin/activate
   ```
2. Thực thi script Stress Test tự động kéo dài 60 giây:
   ```bash
   bash scripts/run_automated_tests.sh
   ```
3. Sau khi kết thúc, truy cập thư mục kết quả sinh ra dạng `results_summary_[TIMESTAMP]/` để lấy toàn bộ các tệp phục vụ báo cáo:
   *   `plots/hinh5_2_fps_comparison.png` (Biểu đồ FPS lý thuyết).
   *   `plots/hinh5_4_cpu_temperature.png` (Biểu đồ nhiệt độ stress test).
   *   `plots/hinh5_5_ram_usage.png` (Biểu đồ RAM tiêu thụ).
   *   `BÁO_CÁO_THỰC_NGHIỆM_TỔNG_HỢP.md` (Số liệu trung bình thực tế).
