#!/usr/bin/env python3
"""
check_env_pi.py — Script kiểm tra môi trường Edge AI trên Raspberry Pi 4.
=======================================================================
Tự động quét và đánh giá cấu hình phần mềm, phần cứng, mạng và mô hình.
"""

import os
import sys
import socket
import subprocess
from pathlib import Path

# Đảm bảo mã hóa UTF-8 trên Windows để không lỗi print kí tự tiếng Việt
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Định nghĩa mã màu ANSI cho console log sinh động
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"
CONFIG_FILE = "shared/configs/settings.yaml"

def print_section(title: str):
    print(f"\n{BOLD}{BLUE}=== {title} ==={RESET}")

def print_ok(msg: str):
    print(f"  {GREEN}✓ {msg}{RESET}")

def print_warn(msg: str):
    print(f"  {YELLOW}⚠ {msg}{RESET}")

def print_err(msg: str):
    print(f"  {RED}✗ {msg}{RESET}")

def check_python_and_venv():
    print_section("1. KIỂM TRA PYTHON & VIRTUAL ENVIRONMENT")
    print(f"  Python Interpreter: {sys.executable}")
    print(f"  Python Version: {sys.version.split()[0]}")
    
    # Kiểm tra venv
    in_venv = sys.prefix != sys.base_prefix or 'VIRTUAL_ENV' in os.environ
    if in_venv:
        print_ok("Đang chạy trong môi trường ảo (.venv) thành công.")
    else:
        print_warn("Bạn KHÔNG chạy trong môi trường ảo! Khuyến nghị kích hoạt .venv trước khi chạy code.")

def check_python_libraries():
    print_section("2. KIỂM TRA CÁC THƯ VIỆN PYTHON CẦN THIẾT")
    libs = [
        ("cv2", "OpenCV"),
        ("ncnn", "Tencent NCNN Python Binding"),
        ("supervision", "Roboflow Supervision"),
        ("ultralytics", "Ultralytics YOLO Framework"),
        ("paho.mqtt", "MQTT Client Library"),
        ("requests", "HTTP Requests"),
        ("yaml", "PyYAML Config Parser")
    ]
    
    for lib_name, description in libs:
        try:
            mod = __import__(lib_name, fromlist=[''])
            version = getattr(mod, "__version__", "Không rõ phiên bản")
            print_ok(f"{lib_name:<15} ({description:<30}): Đã cài đặt [v{version}]")
        except ImportError:
            print_err(f"{lib_name:<15} ({description:<30}): CHƯA CÀI ĐẶT!")

def check_opencv_build_info():
    print_section("3. KIỂM TRA BẢN BUILD OPENCV (ARM OPTIMIZATIONS)")
    try:
        import cv2
        build_info = cv2.getBuildInformation()
        
        # Kiểm tra NEON
        if "NEON" in build_info:
            if "YES" in build_info.split("NEON")[1].split("\n")[0]:
                print_ok("OpenCV hỗ trợ tăng tốc ARM NEON: CÓ")
            else:
                print_warn("OpenCV có NEON trong build flag nhưng đang tắt (NO).")
        else:
            print_err("Không tìm thấy thông tin ARM NEON trong bản build OpenCV.")
            
        # Kiểm tra OpenMP / TBB
        has_openmp = "OpenMP" in build_info and "YES" in build_info.split("OpenMP")[1].split("\n")[0]
        has_tbb = "TBB" in build_info and "YES" in build_info.split("TBB")[1].split("\n")[0]
        
        if has_openmp or has_tbb:
            print_ok(f"OpenCV hỗ trợ đa luồng song song (OpenMP: {has_openmp}, TBB: {has_tbb}): CÓ")
        else:
            print_warn("OpenCV chạy đơn luồng (không có OpenMP/TBB)! Có thể gây bottleneck khi render GUI.")
            
    except Exception as e:
        print_err(f"Không thể đọc thông tin OpenCV build: {e}")

def check_cpp_ncnn_sdk():
    print_section("4. KIỂM TRA THƯ VIỆN NCNN C++ SDK (HỆ THỐNG)")
    paths = [
        ("/usr/local/include/ncnn/net.h", "File header NCNN (net.h)"),
        ("/usr/local/lib/ncnn/libncnn.a", "File thư viện tĩnh NCNN (libncnn.a)"),
    ]
    
    for path_str, desc in paths:
        path = Path(path_str)
        if path.exists():
            size_kb = path.stat().st_size / 1024
            print_ok(f"{desc:<35} tại {path_str} [Tồn tại, {size_kb:.1f} KB]")
        else:
            print_warn(f"{desc:<35} KHÔNG tìm thấy tại {path_str}. Điều này không ảnh hưởng nếu bạn chỉ chạy Python NCNN binding, nhưng sẽ gây lỗi nếu bạn biên dịch code C++.")

def check_model_files():
    print_section("5. KIỂM TRA TỆP MÔ HÌNH NCNN")
    base_dir = Path(__file__).parent.parent
    settings_path = base_dir / CONFIG_FILE
    model_path_str = "shared/models/vehicle_best_ncnn_model"
    
    if settings_path.exists():
        try:
            import yaml
            with open(settings_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
                model_path_str = cfg.get("edge", {}).get("model_path", model_path_str)
        except Exception:
            pass
            
    model_dir = base_dir / model_path_str
    print(f"  Đường dẫn kiểm tra: {model_path_str}")
    
    if not model_dir.exists():
        print_err(f"Thư mục chứa mô hình NCNN không tồn tại: {model_dir}")
        return
        
    files = ["model-opt.param", "model-opt.bin", "model.ncnn.param", "model.ncnn.bin"]
    found_any = False
    
    for file_name in files:
        fpath = model_dir / file_name
        if fpath.exists():
            found_any = True
            size_mb = fpath.stat().st_size / (1024 * 1024)
            if size_mb == 0:
                print_err(f"{file_name:<20} bị lỗi 0 Bytes! Hãy nạp lại mô hình.")
            else:
                print_ok(f"{file_name:<20}: Đang tồn tại [{size_mb:.2f} MB]")
        else:
            print(f"  - {file_name:<20}: Không tìm thấy (Bình thường nếu bạn chỉ dùng bản đã optimize hoặc bản gốc)")
            
    if not found_any:
        print_err(f"Không tìm thấy bất kỳ tệp mô hình NCNN nào trong thư mục {model_path_str} !")

def check_network_connections():
    print_section("6. KIỂM TRA KẾT NỐI MẠNG (PING / SOCKET)")
    
    # Đọc cấu hình để lấy IP
    base_dir = Path(__file__).parent.parent
    settings_path = base_dir / CONFIG_FILE
    server_host = "172.20.10.2"
    server_port = 8000
    mqtt_host = "172.20.10.5"
    mqtt_port = 1883
    
    if settings_path.exists():
        try:
            import yaml
            with open(settings_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
                edge_cfg = cfg.get("edge", {})
                mqtt_cfg = cfg.get("mqtt", {})
                srv_cfg = cfg.get("server", {})
                
                server_host = edge_cfg.get("server_host") or srv_cfg.get("host", "172.20.10.2")
                server_port = int(srv_cfg.get("port", 8000))
                mqtt_host = mqtt_cfg.get("broker", "172.20.10.5")
                mqtt_port = int(mqtt_cfg.get("port", 1883))
        except Exception:
            pass

    # Kiểm tra cổng FastAPI Server
    print(f"  Đang kiểm tra kết nối tới FastAPI Server ({server_host}:{server_port})...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3.0)
    try:
        s.connect((server_host, server_port))
        print_ok(f"Kết nối tới FastAPI Server thành công!")
    except Exception as e:
        print_err(f"Không thể kết nối tới FastAPI Server ({server_host}:{server_port}): {e}")
        print("    -> Vui lòng kiểm tra lại xem Server trên máy tính đã được bật chưa và hai thiết bị có chung mạng wifi không.")
    finally:
        s.close()
        
    # Kiểm tra cổng Mosquitto MQTT Broker
    print(f"  Đang kiểm tra kết nối tới MQTT Broker ({mqtt_host}:{mqtt_port})...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3.0)
    try:
        s.connect((mqtt_host, mqtt_port))
        print_ok(f"Kết nối tới MQTT Broker thành công!")
    except Exception as e:
        print_err(f"Không thể kết nối tới MQTT Broker ({mqtt_host}:{mqtt_port}): {e}")
        print("    -> Vui lòng kiểm tra lại dịch vụ Mosquitto Broker trên thiết bị đích.")
    finally:
        s.close()

def check_hardware_status():
    print_section("7. KIỂM TRA TRẠNG THÁI PHẦN CỨNG (RASPBERRY PI)")
    
    # 1. Đo nhiệt độ CPU
    temp_path = Path("/sys/class/thermal/thermal_zone0/temp")
    if temp_path.exists():
        try:
            with open(temp_path, "r") as f:
                temp_raw = float(f.read().strip())
                temp_c = temp_raw / 1000.0
                if temp_c >= 75.0:
                    print_err(f"Nhiệt độ CPU hiện tại: {temp_c:.1f}°C (Quá nóng! CPU có thể bị bóp hiệu năng)")
                elif temp_c >= 60.0:
                    print_warn(f"Nhiệt độ CPU hiện tại: {temp_c:.1f}°C (Khá ấm, nên bật quạt tản nhiệt)")
                else:
                    print_ok(f"Nhiệt độ CPU hiện tại: {temp_c:.1f}°C (Mát mẻ, an toàn)")
        except Exception as e:
            print_warn(f"Không thể đọc nhiệt độ CPU: {e}")
    else:
        print("  - Nhiệt độ CPU: Không được hỗ trợ trên OS này (Có thể không phải Linux/Pi)")

    # 2. Kiểm tra CPU Governor
    gov_path = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    if gov_path.exists():
        try:
            with open(gov_path, "r") as f:
                gov = f.read().strip()
                if gov == "performance":
                    print_ok(f"CPU Governor mode: {gov} (Tối ưu hiệu năng tối đa)")
                else:
                    print_warn(f"CPU Governor mode: {gov} (Đang ở chế độ tiết kiệm điện. Khuyên dùng lệnh chuyển sang 'performance')")
        except Exception as e:
            print_warn(f"Không thể đọc CPU Governor: {e}")
    else:
        print("  - CPU Governor: Không được hỗ trợ trên OS này")

def main():
    global CONFIG_FILE
    import argparse
    parser = argparse.ArgumentParser(description="Raspberry Pi 4 Environment Checker")
    parser.add_argument("--config", type=str, default="shared/configs/settings.yaml", help="Path to config file (relative to root)")
    args = parser.parse_args()
    
    CONFIG_FILE = args.config
    
    print(f"\n{BOLD}{GREEN}===================================================={RESET}")
    print(f"{BOLD}{GREEN}     HỆ THỐNG KIỂM TRA MÔI TRƯỜNG EDGE AI PI 4{RESET}")
    print(f"{BOLD}{GREEN}===================================================={RESET}")
    
    check_python_and_venv()
    check_python_libraries()
    check_opencv_build_info()
    check_cpp_ncnn_sdk()
    check_model_files()
    check_network_connections()
    check_hardware_status()
    
    print(f"\n{BOLD}{GREEN}===================================================={RESET}")
    print(f"{BOLD}{GREEN}                 HOÀN THÀNH QUÉT HỆ THỐNG{RESET}")
    print(f"{BOLD}{GREEN}===================================================={RESET}\n")

if __name__ == "__main__":
    main()
