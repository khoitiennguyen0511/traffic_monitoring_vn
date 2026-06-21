# PHỤ LỤC: HƯỚNG DẪN CÀI ĐẶT VÀ VẬN HÀNH HỆ THỐNG
*(Tài liệu đính kèm Báo cáo Đồ án Tốt nghiệp)*

---

Tài liệu này cung cấp hướng dẫn kỹ thuật chi tiết nhằm thiết lập môi trường, cấu hình truyền thông và khởi chạy toàn bộ hệ thống giám sát giao thông thông minh từ đầu cuối (End-to-End). Hướng dẫn được phân chia rõ ràng giữa các tác vụ thực hiện trên máy tính cá nhân (Central Server) và máy tính nhúng tại biên (Raspberry Pi 4 - Edge Agent).

> [IMPORTANT]
> **YÊU CẦU MẠNG NỘI BỘ (WI-FI LAN):** 
> Toàn bộ các thiết bị bao gồm: **Máy tính trung tâm (Laptop Windows)**, **Thiết bị biên (Raspberry Pi 4)** và **Bộ điều khiển ESP32** bắt buộc phải kết nối chung vào một điểm phát Wi-Fi (Mạng cục bộ - LAN). Nếu kết nối khác mạng, các thiết bị sẽ không thể truyền nhận gói tin MQTT và dữ liệu ảnh HTTP POST cho nhau. Có thể sử dụng tính năng điểm phát sóng cá nhân (Hotspot) trên điện thoại di động để đảm bảo độ ổn định và định tuyến thông suốt.

---

## THỰC HIỆN TẢI MÃ NGUỒN (GIT CLONE)

Trước khi tiến hành cài đặt các thành phần trên bất kỳ thiết bị nào, thực hiện nhân bản (clone) mã nguồn dự án:

### 1. Trên Máy tính trung tâm (Laptop Windows):
Mở Git Bash hoặc cửa sổ Command Prompt/PowerShell tại thư mục lưu trữ dự án (ví dụ: ổ `D:\`) và thực thi:
```bash
git clone https://github.com/khoitiennguyen0511/traffic_monitoring_vn.git
cd traffic_monitoring_vn
```

### 2. Trên Thiết bị biên (Raspberry Pi 4):
Mở terminal của Raspberry Pi 4 (hoặc qua kết nối SSH) và chạy lệnh tại thư mục người dùng (`home`):
```bash
cd ~
git clone https://github.com/khoitiennguyen0511/traffic_monitoring_vn.git
cd traffic_monitoring_vn
```

---

## A. KHỞI TẠO HẠ TẦNG MẠNG & MQTT BROKER TRÊN RASPBERRY PI 4

Để cấu hình kết nối cho ESP32 và Server, ta cần thiết lập MQTT Broker đóng vai trò máy chủ trung gian truyền tin trước và lấy thông tin địa chỉ IP của Raspberry Pi.

### A.1. Xác định địa chỉ IP của Raspberry Pi
Mở Terminal trên Raspberry Pi 4 và chạy lệnh:
```bash
hostname -I
```
Lệnh sẽ trả về danh sách các địa chỉ IP. Hãy xác định địa chỉ IPv4 nội bộ đang hoạt động (thường bắt đầu bằng `192.168.x.x` hoặc `172.20.x.x`, ví dụ: `172.20.10.5`). 
*Địa chỉ này sẽ được ghi nhớ để điền vào cấu hình MQTT Broker cho toàn hệ thống.*

### A.2. Cài đặt và cấu hình Mosquitto MQTT Broker
Mosquitto từ phiên bản 2.0 trở đi mặc định chặn các kết nối từ bên ngoài mạng nội bộ và yêu cầu xác thực. Ta cần cấu hình cho phép các thiết bị ngoại vi kết nối ẩn danh (không mật khẩu):
1. Tiến hành cài đặt dịch vụ Mosquitto cục bộ trên Pi:
   ```bash
   sudo apt update
   sudo apt install -y mosquitto mosquitto-clients
   ```
2. Mở tệp cấu hình Mosquitto bằng trình soạn thảo văn bản `nano`:
   ```bash
   sudo nano /etc/mosquitto/mosquitto.conf
   ```
3. Di chuyển xuống cuối tệp cấu hình và thêm chính xác 2 dòng sau:
   ```conf
   listener 1883
   allow_anonymous true
   ```
4. Lưu tệp cấu hình bằng cách nhấn tổ hợp phím `Ctrl + O`, nhấn `Enter` để xác nhận, và nhấn `Ctrl + X` để thoát.
5. Khởi động lại dịch vụ Mosquitto để áp dụng các thay đổi:
   ```bash
   sudo systemctl restart mosquitto
   ```
6. Kiểm tra trạng thái hoạt động của dịch vụ để đảm bảo hoạt động bình thường (`active (running)`):
   ```bash
   sudo systemctl status mosquitto
   ```

---

## B. THIẾT LẬP TRÊN MÁY TÍNH TRUNG TÂM (LAPTOP - WINDOWS)

Máy tính trung tâm đóng vai trò lưu trữ cơ sở dữ liệu vi phạm, chạy API Server nhận diện biển số xe (OCR), giao diện Web Streamlit Dashboard điều hành và nạp chương trình firmware cho ESP32.

### B.1. Xác định địa chỉ IP của Laptop Windows
Mở cửa sổ Command Prompt (`cmd`) hoặc PowerShell trên Laptop Windows và thực thi:
```cmd
ipconfig
```
Tìm kiếm cạc mạng không dây (Wireless LAN adapter Wi-Fi) và ghi lại địa chỉ **IPv4 Address** (ví dụ: `172.20.10.2`). 
*Địa chỉ này sẽ được điền vào cấu hình trên Raspberry Pi để nó đẩy hình ảnh vi phạm và siêu dữ liệu thông qua giao thức HTTP POST.*

### B.2. Cấu hình Môi trường ảo Python và Cài đặt Thư viện
Mở cửa sổ **PowerShell** tại thư mục gốc dự án (`D:\traffic_monitoring_vn`):
1. Khởi tạo môi trường ảo Python cô lập để tránh xung đột thư viện hệ thống:
   ```powershell
   python -m venv .venv
   ```
2. Kích hoạt môi trường ảo:
   ```powershell
   .\.venv\Scripts\Activate
   ```
3. Nâng cấp bộ quản lý gói `pip` và tiến hành cài đặt toàn bộ thư viện cần thiết:
   ```powershell
   pip install --upgrade pip
   pip install -r server/requirements.txt
   pip install streamlit
   ```

### B.3. Khởi chạy Phân hệ Máy chủ & Dashboard
Mở **hai cửa sổ Terminal/PowerShell riêng biệt** trên Windows, kích hoạt môi trường ảo `.venv` trên cả hai và khởi chạy các dịch vụ:
*   **Terminal 1 (FastAPI Backend Server):**
    ```powershell
    .\.venv\Scripts\Activate
    python server/main.py
    ```
    *Hệ thống sẽ tải toàn bộ mô hình định vị biển số (`license_best.pt`) và mô hình nhận dạng ký tự CRNN (`ocr_crnn.pt`) vào RAM. Máy chủ bắt đầu lắng nghe tại cổng `8000`. Tài liệu API Swagger có thể truy cập tại địa chỉ http://127.0.0.1:8000/docs.*
*   **Terminal 2 (Streamlit Front-end Dashboard):**
    ```powershell
    .\.venv\Scripts\Activate
    streamlit run server/dashboard.py
    ```
    *Giao diện bảng điều khiển giao thông sẽ tự động khởi động tại trình duyệt web với địa chỉ http://localhost:8501.*

---

## C. THIẾT LẬP VÀ NẠP CHƯƠNG TRÌNH CHO ESP32

Mạch ESP32 đóng vai trò điều khiển đèn giao thông vật lý, chuyển đổi chu kỳ đèn và đồng bộ trạng thái màu đèn với Edge Agent biên thông qua MQTT.

### C.1. Cấu hình kết nối mạng nội bộ và MQTT
Trên máy tính trung tâm (Laptop Windows), truy cập thư mục `esp32/include/`:
1. Mở tệp [credentials.h](file:///d:/traffic_monitoring_vn/esp32/include/credentials.h) và điền chính xác thông tin mạng Wi-Fi chung:
   ```cpp
   #define WIFI_SSID "SSID_WiFi_Nội_Bộ"
   #define WIFI_PASSWORD "Mật_Khẩu_WiFi"
   ```
2. Mở tệp [mqtt_config.h](file:///d:/traffic_monitoring_vn/esp32/include/mqtt_config.h) và cập nhật địa chỉ IP của Raspberry Pi (Retrieved ở mục A.1) nơi chạy MQTT Broker:
   ```cpp
   #define MQTT_BROKER_HOST "172.20.10.5" // Địa chỉ IP thực tế của Raspberry Pi
   ```

### C.2. Biên dịch và nạp code cho ESP32
1. Kết nối bo mạch ESP32 với máy tính trung tâm (Laptop Windows) thông qua cáp truyền dữ liệu micro-USB.
2. **Khắc phục lỗi driver phần cứng (Nếu có):** Nếu PlatformIO báo lỗi không tìm thấy cổng COM kết nối, cần tải và cài đặt driver USB-to-UART tương ứng với chíp nạp trên kit ESP32 (phổ biến nhất là driver Silicon Labs **CP210x** hoặc **CH340**).
3. Mở Terminal tại thư mục `esp32` và tiến hành nạp code:
   ```powershell
   cd esp32
   # Nạp chương trình firmware xuống ESP32
   pio run -t upload
   # Mở màn hình monitor theo dõi logs trực tiếp từ cổng Serial
   pio device monitor
   ```

---

## D. THIẾT LẬP VÀ VẬN HÀNH EDGE AGENT TRÊN RASPBERRY PI 4

Thiết bị Raspberry Pi 4 chịu trách nhiệm thu luồng ảnh camera, chạy thuật toán phát hiện (YOLOv11) và theo dõi xe (ByteTrack) tối ưu qua NCNN.

### D.1. Thiết lập Môi trường ảo Python & Cài đặt Thư viện
1. Cài đặt các gói biên dịch bắt buộc và thư viện xử lý đồ họa hệ thống:
   ```bash
   sudo apt install -y build-essential cmake git libopencv-dev libomp-dev python3-pip python3-venv libvulkan-dev vulkan-tools protobuf-compiler libprotobuf-dev
   ```
2. Điều hướng vào thư mục dự án trên Pi và khởi tạo môi trường ảo Python:
   ```bash
   cd ~/traffic_monitoring_vn
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   ```
3. **Cấu hình loại bỏ thư viện nặng (Tối ưu hóa dung lượng cho Pi):**
   Gói thư viện `ultralytics` mặc định sẽ tự động tải các gói PyTorch rất lớn (`torch`, `torchvision` > 1.5 GB), chiếm dụng thẻ nhớ và mất nhiều thời gian cài đặt. 
   Trường hợp chỉ vận hành Edge Agent tối ưu hóa bằng NCNN (`agent_ncnn.py`), hãy mở tệp `edge_pi4/requirements.txt` bằng trình nano:
   ```bash
   nano edge_pi4/requirements.txt
   ```
   Thêm dấu `#` vào đầu dòng `ultralytics==8.3.207` để vô hiệu hóa nó, sau đó tiến hành cài đặt:
   ```bash
   pip install -r edge_pi4/requirements.txt
   ```

### D.2. Biên dịch thư viện Tencent NCNN từ mã nguồn
Để kích hoạt tính năng gia tốc phần cứng OpenMP đa luồng và GPU Vulkan trên Raspberry Pi 4, ta bắt buộc phải biên dịch NCNN từ repo chính thức:
1. Thực hiện tải mã nguồn NCNN và các submodule liên quan:
   ```bash
   cd ~
   git clone https://github.com/Tencent/ncnn.git
   cd ncnn
   git submodule update --init
   ```
2. Khởi tạo thư mục build và biên dịch phát hành (Release Mode):
   ```bash
   mkdir build && cd build
   cmake -DCMAKE_BUILD_TYPE=Release -DNCNN_VULKAN=ON -DNCNN_SYSTEM_GLSLANG=OFF -DNCNN_DISABLE_RTTI=OFF -DNCNN_OPENMP=ON -DNCNN_BUILD_TOOLS=ON -DNCNN_INSTALL_SDK=ON -DNCNN_BUILD_BENCHMARK=OFF -DNCNN_BUILD_TESTS=OFF -DNCNN_BUILD_EXAMPLES=OFF ..
   make -j4
   sudo make install
   ```
3. Thiết lập các tệp thư viện tĩnh và header toàn cục để môi trường Python liên kết được:
   ```bash
   sudo mkdir -p /usr/local/lib/ncnn 
   sudo cp -r install/include/ncnn /usr/local/include/
   sudo cp install/lib/libncnn.a /usr/local/lib/ncnn/
   sudo ldconfig
   ```
4. Kích hoạt môi trường ảo dự án và cài đặt bộ liên kết Python (Python bindings) của NCNN:
   ```bash
   source ~/traffic_monitoring_vn/.venv/bin/activate
   pip install ncnn
   ```

### D.3. Cấu hình liên kết mạng và chạy Edge Agent
1. Trên Raspberry Pi, mở tệp `shared/configs/settings.yaml` để cấu hình IP kết nối:
   ```yaml
   mqtt:
     broker: "172.20.10.5"   # Địa chỉ IP của chính Raspberry Pi (retrieved ở bước A.1)
     port: 1883
   edge:
     server_host: "172.20.10.2" # Địa chỉ IP của Laptop Windows (retrieved ở bước B.1)
     server_port: 8000
   ```
2. Khởi chạy tiến trình Edge Agent:
   *   **Chế độ GUI (Nếu Pi kết nối màn hình ngoài hoặc VNC):**
       ```bash
       python3 edge_pi4/agent_ncnn.py
       ```
   *   **Chế độ Headless (Nếu chạy dòng lệnh qua SSH, không cần mở cửa sổ đồ họa):**
       ```bash
       python3 edge_pi4/agent_ncnn.py --headless
       ```

---

## E. THỰC NGHIỆM ĐÁNH GIÁ HIỆU NĂNG VÀ THU THẬP SỐ LIỆU ĐO ĐẠC

Quy trình thực nghiệm đo đạc hiệu suất phần cứng (nhiệt độ CPU, xung nhịp vi xử lý, dung lượng RAM tiêu thụ) và so sánh tốc độ suy luận (FPS) giữa các framework phục vụ cho nội dung phân tích thực nghiệm được tiến hành theo các bước sau:

1. Kích hoạt môi trường chạy thực nghiệm trên thiết bị biên Raspberry Pi 4:
   ```bash
   cd ~/traffic_monitoring_vn
   source .venv/bin/activate
   ```
2. Thực hiện khởi chạy kịch bản kiểm thử tải giới hạn (Stress Test) tích hợp thu thập dữ liệu tự động trong thời gian 60 giây:
   ```bash
   bash scripts/run_automated_tests.sh
   ```
3. Thu thập kết quả thực nghiệm tự động xuất bản tại thư mục kết quả `results_summary_[TIMESTAMP]/` bao gồm:
   * **Đồ thị trực quan hóa dữ liệu (thư mục con `plots/`):**
     - `plots/hinh5_2_fps_comparison.png`: Biểu đồ so sánh tốc độ xử lý (FPS) giữa PyTorch và NCNN.
     - `plots/hinh5_4_cpu_temperature.png`: Biểu đồ giám sát biến thiên nhiệt độ CPU trong quá trình kiểm thử tải.
     - `plots/hinh5_5_ram_usage.png`: Biểu đồ giám sát dung lượng RAM tiêu hao của hệ thống.
   * **Số liệu phân tích tổng hợp:**
     - Tệp `BÁO_CÁO_THỰC_NGHIỆM_TỔNG_HỢP.md` cung cấp các giá trị đo trung bình và cực đại của các tham số viễn đo.
