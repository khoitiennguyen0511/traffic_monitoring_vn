# Intelligent Traffic Monitoring and Adaptive Control System (RASPBERRY PI 4 + YOLOv11 + NCNN + ESP32)

An end-to-end distributed Edge AI system designed to detect traffic lane-crossing violations during red lights and dynamically adapt traffic light cycles based on real-time vehicle density. 

The system leverages a high-performance Edge AI pipeline (YOLOv11 object detector and ByteTrack multi-object tracker) optimized using Tencent NCNN on a Raspberry Pi 4, communicates asynchronously via MQTT with an ESP32 microcontroller, offloads violation evidence to a Central Laptop Server (FastAPI) for license plate recognition (CRNN OCR), and visualizes real-time metrics on a Streamlit Web Dashboard.

---

## Repository Structure

```
.
├── edge_pi4/            # Raspberry Pi 4 Edge Agent (Python)
│   ├── core/            # Inference, tracking, and capture threads
│   │   ├── detection.py # YOLOv11 NCNN wrapper
│   │   ├── tracking.py  # Traffic flow analyzer & ByteTrack wrapper
│   │   └── pipeline.py  # Multi-threaded capture pipeline
│   ├── network/         # HTTP and MQTT async clients
│   │   ├── http_client.py
│   │   └── mqtt_manager.py
│   ├── cpp/             # Pure C++ NCNN implementation (Alternative)
│   ├── agent_ncnn.py    # Main NCNN Edge Agent runner
│   ├── agent_pt.py      # PyTorch fallback Edge Agent runner
│   └── requirements.txt # Python package requirements for Pi
├── esp32/               # ESP32 Traffic Light Controller (PlatformIO Project)
│   ├── include/         # Globals, MQTT configurations, and credentials
│   └── src/             # Firmware source code (main.cpp, logic, network)
├── server/              # Central Laptop Server (FastAPI & Streamlit)
│   ├── api/             # FastAPI routing and schema layers
│   ├── core/            # Database handlers & CRNN OCR engine
│   ├── main.py          # FastAPI application entrypoint
│   ├── dashboard.py     # Streamlit Web App entrypoint
│   └── requirements.txt # Python package requirements for Server
├── scripts/             # Telemetry, health check, and benchmarking scripts
│   ├── check_env_pi.py  # Diagnostics and environment check
│   ├── compare_models.py# Benchmark PyTorch vs NCNN
│   ├── audit.py         # Hardware profiling
│   └── run_automated_tests.sh # Stress test runner & report generator
├── shared/              # Shared assets across devices
│   ├── configs/         # Central configuration files (settings.yaml)
│   └── models/          # NCNN & PyTorch model weight files
└── README.md            # Main project documentation
```

---

## Installation & Run Guide

This distributed system is divided into two primary environments:
1. **Central Server (Laptop / Windows PC):** Hosts the FastAPI OCR engine, Streamlit Dashboard, SQLite database, and compiles/flashes the ESP32 firmware.
2. **Edge Node (Raspberry Pi 4):** Hosts the local Mosquitto MQTT Broker and runs the Edge AI pipeline.

### Step 0: Clone the Repository
Clone the project repository to both your Laptop (Windows) and Raspberry Pi 4 (Edge Node):
```bash
git clone https://github.com/khoitiennguyen0511/traffic_monitoring_vn.git
cd traffic_monitoring_vn
```

### 1. Central Server Setup (Laptop - Windows)

#### Step 1.1: Environment Setup
Open PowerShell in the cloned `traffic_monitoring_vn` directory:
1. Create a Python virtual environment:
   ```powershell
   python -m venv .venv
   ```
2. Activate the virtual environment:
   ```powershell
   .\.venv\Scripts\Activate
   ```
3. Install dependencies:
   ```powershell
   pip install --upgrade pip
   pip install -r server/requirements.txt
   pip install streamlit
   ```

#### Step 1.2: Retrieve Network IP Address
Run the following command in cmd/PowerShell:
```cmd
ipconfig
```
Identify the **IPv4 Address** of the active network adapter (e.g., `172.20.10.2`). This IP will be referenced by the Raspberry Pi and ESP32 to upload data.

#### Step 1.3: Start FastAPI Server & Web Dashboard
Open **two separate terminals** on your Windows Laptop, activate `.venv` on both, and run:
*   **Terminal 1 (FastAPI Backend Server):**
    ```powershell
    .\.venv\Scripts\Activate
    python server/main.py
    ```
    *Starts the FastAPI backend at `http://127.0.0.1:8000`. You can access the API Swagger docs at `http://127.0.0.1:8000/docs`.*

*   **Terminal 2 (Streamlit Front-end Dashboard):**
    ```powershell
    .\.venv\Scripts\Activate
    streamlit run server/dashboard.py
    ```
    *Starts the management web interface at `http://localhost:8501`.*

#### Step 1.4: Upload Firmware to ESP32
1. Connect the ESP32 board to the laptop via a micro-USB cable.
2. Edit [credentials.h](file:///d:/traffic_monitoring_vn/esp32/include/credentials.h) to match your Wi-Fi credentials:
   ```cpp
   #define WIFI_SSID "Your_WiFi_SSID"
   #define WIFI_PASSWORD "Your_WiFi_Password"
   ```
3. Edit [mqtt_config.h](file:///d:/traffic_monitoring_vn/esp32/include/mqtt_config.h) to configure the target MQTT Broker IP address (this should point to the IP of the Raspberry Pi, e.g., `172.20.10.5`):
   ```cpp
   #define MQTT_BROKER_HOST "172.20.10.5"
   ```
4. Build and upload using PlatformIO inside the `esp32` directory:
   ```powershell
   cd esp32
   pio run -t upload
   pio device monitor
   ```

---

### 2. Edge Agent Setup (Raspberry Pi 4)

#### Step 2.1: Configure Mosquitto MQTT Broker
On the Raspberry Pi terminal, install and configure Mosquitto:
1. Install package and client tools:
   ```bash
   sudo apt update
   sudo apt install -y mosquitto mosquitto-clients
   ```
2. Enable external connections (allowing ESP32 to publish/subscribe) by editing the config:
   ```bash
   sudo nano /etc/mosquitto/mosquitto.conf
   ```
   Add the following listener configuration at the bottom:
   ```conf
   listener 1883
   allow_anonymous true
   ```
3. Restart the service to apply settings:
   ```bash
   sudo systemctl restart mosquitto
   ```
   *Retrieve your Pi's local IP address using `hostname -I` (e.g., `172.20.10.5`).*

#### Step 2.2: Setup Virtual Environment & Python Packages
1. Install essential compiler tools, OpenCV, OpenMP, and Vulkan packages:
   ```bash
   sudo apt install -y build-essential cmake git libopencv-dev libomp-dev python3-pip python3-venv libvulkan-dev vulkan-tools protobuf-compiler libprotobuf-dev
   ```
2. Setup the virtual environment:
   ```bash
   cd ~/traffic_monitoring_vn
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   ```
3. **Storage Optimization Tip:**
   The `ultralytics` package automatically installs massive PyTorch binaries (`torch` & `torchvision`), which take >1.5 GB of storage. 
   If you **only plan to run the NCNN optimized Edge Agent (`agent_ncnn.py`)**, open [edge_pi4/requirements.txt](file:///d:/traffic_monitoring_vn/edge_pi4/requirements.txt) and comment out `ultralytics==8.3.207` (add `#` at the beginning of the line). Then install requirements:
   ```bash
   pip install -r edge_pi4/requirements.txt
   ```

#### Step 2.3: Compile NCNN from Repository
To compile the high-performance Tencent NCNN library with Vulkan GPU and OpenMP CPU multi-threading support:
```bash
cd ~
git clone https://github.com/Tencent/ncnn.git
cd ncnn
git submodule update --init
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release -DNCNN_VULKAN=ON -DNCNN_SYSTEM_GLSLANG=OFF -DNCNN_DISABLE_RTTI=OFF -DNCNN_OPENMP=ON -DNCNN_BUILD_TOOLS=ON -DNCNN_INSTALL_SDK=ON -DNCNN_BUILD_BENCHMARK=OFF -DNCNN_BUILD_TESTS=OFF -DNCNN_BUILD_EXAMPLES=OFF ..
make -j4
sudo make install

# Deploy headers and static library globally
sudo mkdir -p /usr/local/lib/ncnn 
sudo cp -r install/include/ncnn /usr/local/include/
sudo cp install/lib/libncnn.a /usr/local/lib/ncnn/
sudo ldconfig

# Install ncnn python binding in virtual environment
source ~/traffic_monitoring_vn/.venv/bin/activate
pip install ncnn
```

#### Step 2.4: Configure settings.yaml
Edit `shared/configs/settings.yaml` on the Raspberry Pi to set up IP mappings:
```yaml
mqtt:
  broker: "172.20.10.5"   # Raspberry Pi IP
  port: 1883
edge:
  server_host: "172.20.10.2" # Laptop Windows IP
  server_port: 8000
```

#### Step 2.5: Run the Edge Agent
With the virtual environment activated, run the agent:
*   **GUI Mode (Displays Video Frame):**
    ```bash
    python3 edge_pi4/agent_ncnn.py
    ```
*   **Headless Mode (SSH / Console):**
    ```bash
    python3 edge_pi4/agent_ncnn.py --headless
    ```
*   **PyTorch Fallback Mode (If NCNN is not used):**
    ```bash
    python3 edge_pi4/agent_pt.py
    ```

---

### 3. Verification, Benchmarking & Optimization (Optional)

#### Step 3.1: Environment Verification
Verify that your Python packages, libraries (OpenCV NEON/OpenMP build flags), hardware settings (CPU frequency governor), and model weights are ready:
```bash
python3 scripts/check_env_pi.py
```

#### Step 3.2: Model Performance Benchmarking
Compare model load times, inference latencies, and theoretical FPS between PyTorch (`.pt`) and NCNN (Original vs Optimized) at 320x320 and 480x480 resolution:
```bash
python3 scripts/compare_models.py
```
*The benchmark report will be written to `shared/configs/model_comparison_results.md`.*

#### Step 3.3: Automated Validation & Telemetry Suite
Run the automated stress-test script to profile system resource usage (CPU temperature, CPU load, RAM usage) under load:
```bash
bash scripts/run_automated_tests.sh
```

#### Step 3.4: Model Optimization (FP16)
If you want to optimize your own custom-trained YOLO model to FP16 (pre-optimized FP16 model weights are already provided in the repository under `shared/models/`):

```bash
cd ~/ncnn/build/tools
./ncnnoptimize \
  ~/traffic_monitoring_vn/shared/models/vehicle_best_ncnn_model/model.ncnn.param \
  ~/traffic_monitoring_vn/shared/models/vehicle_best_ncnn_model/model.ncnn.bin \
  ~/traffic_monitoring_vn/shared/models/vehicle_best_ncnn_model/model-opt.param \
  ~/traffic_monitoring_vn/shared/models/vehicle_best_ncnn_model/model-opt.bin 0
```