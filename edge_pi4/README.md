# YOLOv11 Inference on Raspberry Pi using Python, ncnn & OpenCV
## ARM NEON + OpenMP + Telemetry Suite Optimized

High-performance YOLOv11 Nano (YOLO11n) inference pipeline for Raspberry Pi 4 using Python, ncnn, and OpenCV, optimized for edge deployment with:

* **Mosquitto MQTT Broker hosted directly on Raspberry Pi**
* **OpenMP multi-core CPU parallelism** (configured to run on 3 threads for optimal load-balancing on Cortex-A72)
* **ARM NEON vectorization** (SIMD optimization enabled in OpenCV via pip binary)
* **FP16 optimized inference support**
* **Comprehensive validation, benchmarking, and profiling scripts**

This repository contains custom scripts to automate environment validation, run model comparison benchmarks, profile system hardware components, log live telemetry (temperature, CPU speed, memory), and generate automated reports.

---

## Project Structure
```
traffic_monitoring_vn/
├── edge_pi4/
│   ├── core/
│   │   ├── detection.py
│   │   ├── pipeline.py
│   │   └── tracking.py
│   ├── network/
│   │   ├── http_client.py
│   │   └── mqtt_manager.py
│   ├── agent_ncnn.py       # Optimized multi-threaded NCNN Python Agent
│   ├── agent_pt.py         # Standard PyTorch Fallback Agent
│   └── requirements.txt
├── scripts/
│   ├── check_env_pi.py     # Environment scanner & health checker
│   ├── compare_models.py   # Benchmark comparing PyTorch vs NCNN
│   ├── audit.py            # Comprehensive system and pipeline auditor
│   ├── plot_charts.py      # Telemetry & performance chart plotter
│   └── run_automated_tests.sh # Automated validation & profiling runner
└── shared/
    └── models/             # Pre-trained vehicle detection NCNN weights
```

---

## System Dependencies
First, update your package list and install the required build tools, library dependencies, and **Mosquitto MQTT Broker** on the Raspberry Pi:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y build-essential cmake git libopencv-dev libomp-dev python3-pip python3-venv libvulkan-dev vulkan-tools protobuf-compiler libprotobuf-dev mosquitto mosquitto-clients
```

### Configure Mosquitto Broker on Raspberry Pi
Since Mosquitto 2.0+, anonymous connection is disabled and only binds to local interface by default. To allow ESP32 and other devices to connect:
1. Open the Mosquitto configuration file on Raspberry Pi:
   ```bash
   sudo nano /etc/mosquitto/mosquitto.conf
   ```
2. Add the following lines at the end of the file:
   ```conf
   listener 1883
   allow_anonymous true
   ```
3. Save the file (`Ctrl + O`, `Enter`, `Ctrl + X`) and restart the Mosquitto service:
   ```bash
   sudo systemctl restart mosquitto
   ```

---

## Project Setup

### 1. Clone Repository & Setup Environment
Clone this project onto the Raspberry Pi, navigate to the project directory, and create a Python virtual environment:
```bash
git clone https://github.com/khoitiennguyen0511/traffic_monitoring_vn.git
cd ~/traffic_monitoring_vn
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Python Dependencies (OpenCV via pip)
Install the required packages for the Edge Agent, including OpenCV via pip:
```bash
pip install --upgrade pip
pip install -r edge_pi4/requirements.txt
```

> [!TIP]
> **Tối ưu hóa dung lượng (Khuyên dùng cho Pi):**
> Gói `ultralytics` sẽ tự động tải các thư viện cực kỳ nặng như PyTorch (`torch`), `torchvision` (chiếm >1.5 GB ổ cứng và cài đặt rất lâu). 
> Nếu bạn **chỉ muốn chạy Edge Agent NCNN tối ưu (`agent_ncnn.py`)**, hãy mở tệp [edge_pi4/requirements.txt](file:///d:/traffic_monitoring_vn/edge_pi4/requirements.txt) và comment dòng `ultralytics==8.3.207` (thêm dấu `#` ở đầu dòng) trước khi cài đặt. Các script NCNN vẫn sẽ hoạt động bình thường mà không cần PyTorch.


### 3. Compile NCNN from Repository (Vulkan + OpenMP Enabled)
To build the high-performance NCNN C++ SDK from the official source repository:
```bash
cd ~
git clone https://github.com/Tencent/ncnn.git
cd ncnn
git submodule update --init
mkdir build && cd build

cmake -DCMAKE_BUILD_TYPE=Release \
      -DNCNN_VULKAN=ON \
      -DNCNN_SYSTEM_GLSLANG=OFF \
      -DNCNN_DISABLE_RTTI=OFF \
      -DNCNN_OPENMP=ON \
      -DNCNN_BUILD_TOOLS=ON \
      -DNCNN_INSTALL_SDK=ON \
      -DNCNN_BUILD_BENCHMARK=OFF \
      -DNCNN_BUILD_TESTS=OFF \
      -DNCNN_BUILD_EXAMPLES=OFF ..

make -j4
sudo make install

# Copy compiled headers and libraries to /usr/local for system-wide access
sudo mkdir -p /usr/local/lib/ncnn 
sudo cp -r install/include/ncnn /usr/local/include/
sudo cp install/lib/libncnn.a /usr/local/lib/ncnn/
sudo ldconfig
```

Verify that NCNN headers and static library are in place:
```bash
ls /usr/local/include/ncnn/net.h && ls /usr/local/lib/ncnn/libncnn.a
```

Finally, install the `ncnn` python package inside your virtual environment:
```bash
# Activate your venv if not already done
source ~/traffic_monitoring_vn/.venv/bin/activate
pip install ncnn
```

---

## Environment Verification
Verify that your Python packages, libraries (OpenCV NEON/OpenMP build flags), hardware settings (CPU frequency governor), and model weights are ready:
```bash
python3 scripts/check_env_pi.py
```

---

## Model Performance Benchmarking
Run direct benchmarking to compare the model load times, inference latencies, and theoretical FPS between PyTorch (`.pt`) and NCNN (Original vs Optimized) at 320x320 and 480x480 resolution:
```bash
python3 scripts/compare_models.py
```
*The benchmark report will be written to `shared/configs/model_comparison_results.md`.*

---

## Automated Validation & Telemetry Suite
Run the comprehensive test script to validate and profile the entire Edge AI system under load:
```bash
bash scripts/run_automated_tests.sh
```

---

## [OPTIONAL] Model Optimization (FP16) & Quantization (INT8)
*Note: If you cloned this repository directly, you can use the pre-optimized FP16 model weights (`model-opt.param` and `model-opt.bin`) already included in the `shared/models/vehicle_custom_best_320_ncnn_model/` folder. Running this section is optional and is only required if you want to optimize or quantize your own custom-trained YOLO model.*


### 1. Model Optimization
```bash
cd ~/ncnn/build/tools
./ncnnoptimize \
  ~/traffic_monitoring_vn/shared/models/vehicle_best_ncnn_model/model.ncnn.param \
  ~/traffic_monitoring_vn/shared/models/vehicle_best_ncnn_model/model.ncnn.bin \
  ~/traffic_monitoring_vn/shared/models/vehicle_best_ncnn_model/model-opt.param \
  ~/traffic_monitoring_vn/shared/models/vehicle_best_ncnn_model/model-opt.bin 0
```

### 2. Generate INT8 Calibration Table
Create a `calib_list.txt` containing absolute paths to about 100-500 test images, then run:
```bash
./quantize/ncnn2table \
  ~/traffic_monitoring_vn/shared/models/vehicle_best_ncnn_model/model-opt.param \
  ~/traffic_monitoring_vn/shared/models/vehicle_best_ncnn_model/model-opt.bin \
  calib_list.txt \
  ~/traffic_monitoring_vn/shared/models/vehicle_best_ncnn_model/model.table \
  mean=0 norm=0.0039216 shape=320,320,3 pixel=BGR thread=4 method=aciq
```

### 3. Convert to INT8 Model
```bash
./quantize/ncnn2int8 \
  ~/traffic_monitoring_vn/shared/models/vehicle_best_ncnn_model/model-opt.param \
  ~/traffic_monitoring_vn/shared/models/vehicle_best_ncnn_model/model-opt.bin \
  ~/traffic_monitoring_vn/shared/models/vehicle_best_ncnn_model/model-int8.param \
  ~/traffic_monitoring_vn/shared/models/vehicle_best_ncnn_model/model-int8.bin \
  ~/traffic_monitoring_vn/shared/models/vehicle_best_ncnn_model/model.table
```

---

## Running the Edge Agent
Once configured, run the main NCNN Edge Agent.

### 1. Configure Server Connections
Edit `shared/configs/settings.yaml` to fill in the correct MQTT Broker and FastAPI Server IP addresses.
*(Example network mapping matching your settings)*:
```yaml
mqtt:
  broker: "172.20.10.5"   # Raspberry Pi IP (running Mosquitto Broker)
  port: 1883
edge:
  server_host: "172.20.10.2" # Laptop IP (running FastAPI Server)
  server_port: 8000
  camera_source: "vehicle_counting.mp4" # Or camera index like 0
```

### 2. Launch the Agent
* **GUI Mode (Displays Video Frame):**
  ```bash
  python3 edge_pi4/agent_ncnn.py
  ```
* **Headless Mode (Recommended for SSH / Console-only runs):**
  ```bash
  python3 edge_pi4/agent_ncnn.py --headless
  ```
* **PyTorch Fallback Mode (If NCNN is not used):**
  ```bash
  python3 edge_pi4/agent_pt.py
  ```
