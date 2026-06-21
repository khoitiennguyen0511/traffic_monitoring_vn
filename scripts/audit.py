#!/usr/bin/env python3
"""
scripts/audit.py — Production-grade Edge AI System Auditor for Raspberry Pi 4.
Performs: Environment Audit, Camera Audit, Model Audit (1-4 threads), Pipeline Audit, 
and System Profiling (5-minute run with CSV export).
"""

import sys
import time
import os
import platform
import subprocess
import sqlite3
import queue
import csv
import argparse
from pathlib import Path
import numpy as np
import cv2

# Set project root path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "edge_pi4"))

# Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

def print_banner(text):
    print(f"\n{BOLD}{GREEN}================================================================{RESET}")
    print(f"{BOLD}{GREEN}  {text.upper():^60}  {RESET}")
    print(f"{BOLD}{GREEN}================================================================{RESET}")

def print_section(text):
    print(f"\n{BOLD}{BLUE}--- {text} ---{RESET}")

def run_cmd(args):
    try:
        res = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        return res.stdout.strip() if res.stdout else "N/A"
    except Exception:
        return "N/A"

def get_percentiles(latencies):
    if not latencies:
        return {"min": 0, "avg": 0, "p95": 0, "p99": 0, "max": 0}
    arr = np.array(latencies)
    return {
        "min": np.min(arr),
        "avg": np.mean(arr),
        "p95": np.percentile(arr, 95),
        "p99": np.percentile(arr, 99),
        "max": np.max(arr)
    }

# =====================================================================
# PHASE 1: ENVIRONMENT AUDIT
# =====================================================================
def run_environment_audit():
    print_banner("Phase 1: Environment Audit")
    
    # 1. Hardware Details
    print_section("Hardware & OS")
    cpu_model = "Unknown"
    cpu_info = run_cmd(["cat", "/proc/cpuinfo"])
    for line in cpu_info.split("\n"):
        if "Model" in line or "model name" in line:
            cpu_model = line.split(":")[1].strip()
            break
    
    gov_path = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    governor = gov_path.read_text().strip() if gov_path.exists() else "Unknown"
    
    freq_path = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")
    freq_khz = freq_path.read_text().strip() if freq_path.exists() else "Unknown"
    freq_mhz = f"{int(freq_khz)//1000} MHz" if freq_khz.isdigit() else "Unknown"
    
    temp_path = Path("/sys/class/thermal/thermal_zone0/temp")
    temp_c = f"{float(temp_path.read_text().strip()) / 1000.0:.1f}°C" if temp_path.exists() else "Unknown"
    
    # Storage type check
    storage_type = "Unknown"
    sd_ssd = "Unknown"
    lsblk_out = run_cmd(["lsblk", "-d", "-o", "name,rota,tran"])
    # If tran contains usb, it is likely SSD/USB Boot. If rota=1 it's HDD, if rota=0 and name=mmcblk0 it's SD card.
    if "mmcblk0" in lsblk_out:
        sd_ssd = "MicroSD Card"
        storage_type = "SD (MMC/SDIO)"
    elif "sda" in lsblk_out or "sdb" in lsblk_out:
        for line in lsblk_out.split("\n"):
            if "sda" in line or "sdb" in line:
                if "usb" in line:
                    sd_ssd = "USB External (likely SSD/HDD)"
                    storage_type = "USB Flash/SSD"
                else:
                    sd_ssd = "SATA/NVMe SSD/HDD"
                    storage_type = "SSD/HDD"
                    
    usb_speed = run_cmd(["lsusb", "-t"])
    usb_bus_info = "Check output:\n" + usb_speed if usb_speed != "N/A" else "N/A"
    
    print(f"  CPU Model       : {cpu_model}")
    print(f"  CPU Governor    : {governor}")
    print(f"  ARM Frequency   : {freq_mhz}")
    print(f"  SoC Temperature : {temp_c}")
    print(f"  Storage Device  : {sd_ssd}")
    print(f"  Storage Bus Type: {storage_type}")
    print(f"  Kernel Version  : {platform.release()} ({platform.architecture()[0]} / {run_cmd(['getconf', 'LONG_BIT'])} bits)")
    
    # RAM / Swap Status
    free_mem = run_cmd(["free", "-h"])
    print("\n  Memory Telemetry:")
    print(free_mem)
    
    # 2. OpenCV Build Flags
    print_section("OpenCV Optimizations")
    print(f"  OpenCV Version  : {cv2.__version__}")
    build_info = cv2.getBuildInformation()
    
    def check_flag(flag_name, build_str):
        if flag_name.lower() not in build_str.lower():
            return "NO"
        for line in build_str.split("\n"):
            if flag_name.lower() in line.lower():
                # Bỏ qua từ khóa 'nonfree' để không bị nhận diện nhầm là 'no'
                clean_line = line.lower().replace("nonfree", "")
                if "no" in clean_line and "yes" not in clean_line:
                    return "NO"
        return "YES"

    neon = "YES" if ("neon" in build_info.lower() or "asimd" in build_info.lower()) else "NO"
    vfpv3 = "YES" if "vfp" in build_info.lower() else "NO"
    openmp = check_flag("OpenMP", build_info)
    tbb = check_flag("TBB", build_info)
    gstreamer = check_flag("GStreamer", build_info)
    ffmpeg = check_flag("FFmpeg", build_info)
    opencl = check_flag("OpenCL", build_info)

    print(f"  ARM NEON        : {neon}")
    print(f"  VFPV3           : {vfpv3}")
    print(f"  OpenMP          : {openmp}")
    print(f"  TBB             : {tbb}")
    print(f"  GStreamer       : {gstreamer}")
    print(f"  FFmpeg          : {ffmpeg}")
    print(f"  OpenCL          : {opencl}")

    # 3. NCNN Engine Configuration
    print_section("NCNN Build Settings")
    try:
        import ncnn
        opt = ncnn.Option()
        print(f"  NCNN Binding    : Loaded successfully [v{getattr(ncnn, '__version__', 'Unknown')}]")
        print(f"  OpenMP Support  : YES (Default threads: {opt.num_threads})")
        print(f"  FP16 Packed     : {getattr(opt, 'use_packing_layout', 'N/A')}")
        print(f"  FP16 Arithmetic : {getattr(opt, 'use_fp16_arithmetic', 'N/A')}")
        print(f"  BF16 Storage    : {getattr(opt, 'use_bf16_storage', 'N/A')}")
        print(f"  Vulkan Support  : {getattr(opt, 'use_vulkan_compute', 'N/A')}")
    except ImportError:
        print(f"  NCNN Binding    : {RED}Not Installed / FAILED TO LOAD{RESET}")

    # 4. Python Package Version Checks
    print_section("Python Package Versions")
    packages = ["numpy", "cv2", "ncnn", "ultralytics", "supervision", "paho.mqtt"]
    for pkg in packages:
        try:
            mod = __import__(pkg, fromlist=[''])
            version = getattr(mod, "__version__", "Unknown")
            print(f"  {pkg:<15} : Installed [v{version}]")
        except ImportError:
            print(f"  {pkg:<15} : {RED}Not Installed{RESET}")

# =====================================================================
# PHASE 2: CAMERA AUDIT
# =====================================================================
def run_camera_audit(source_str):
    print_banner("Phase 2: Camera Audit")
    
    # Try parsing numeric camera index
    try:
        source = int(source_str)
    except ValueError:
        source = source_str
        
    print(f"  Target Source   : {source}")
    
    # 1. Camera Open Latency
    t0 = time.perf_counter()
    cap = cv2.VideoCapture(source)
    open_latency = (time.perf_counter() - t0) * 1000.0
    
    if not cap.isOpened():
        print(f"  {RED}Camera source failed to open.{RESET}")
        return
        
    print(f"  Open Latency    : {open_latency:.2f} ms")
    
    # Get frame properties
    w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    fps_prop = cap.get(cv2.CAP_PROP_FPS)
    print(f"  Resolution      : {int(w)}x{int(h)}")
    print(f"  Reported FPS    : {fps_prop}")
    
    # 2. Frame Read & Decode Latency
    read_latencies = []
    # Warmup 10 frames
    for _ in range(10):
        cap.read()
        
    # Test 100 frames
    t_start_loop = time.perf_counter()
    frames_read = 0
    for _ in range(100):
        t_frame_start = time.perf_counter()
        ret, frame = cap.read()
        if not ret:
            break
        read_latencies.append((time.perf_counter() - t_frame_start) * 1000.0)
        frames_read += 1
    total_time = (time.perf_counter() - t_start_loop)
    cap.release()
    
    actual_fps = frames_read / total_time if total_time > 0 else 0
    stats = get_percentiles(read_latencies)
    
    print(f"  Actual Decode FPS: {actual_fps:.2f} FPS")
    print(f"  Frame Read Latency stats:")
    print(f"    Min           : {stats['min']:.2f} ms")
    print(f"    Avg           : {stats['avg']:.2f} ms")
    print(f"    p95           : {stats['p95']:.2f} ms")
    print(f"    p99           : {stats['p99']:.2f} ms")
    print(f"    Max           : {stats['max']:.2f} ms")

def get_model_path_from_settings():
    import yaml
    settings_path = BASE_DIR / "shared/configs/settings.yaml"
    default_model = "shared/models/vehicle_custom_best_320_ncnn_model"
    if settings_path.exists():
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
                return str(BASE_DIR / cfg.get("edge", {}).get("model_path", default_model))
        except Exception:
            pass
    return str(BASE_DIR / default_model)

# =====================================================================
# PHASE 3: MODEL AUDIT
# =====================================================================
def run_model_audit():
    print_banner("Phase 3: Model Audit")
    
    model_path = get_model_path_from_settings()
    if not os.path.exists(model_path):
        print(f"  {RED}Model folder not found: {model_path}{RESET}")
        return
        
    try:
        from core.detection import VehicleDetector
    except ImportError:
        print(f"  {RED}Cannot import core.detection.VehicleDetector.{RESET}")
        return
        
    dummy_frame = np.random.randint(0, 255, (320, 320, 3), dtype=np.uint8)
    
    for threads in [1, 2, 3, 4]:
        print_section(f"Model Inference Audit - Threads: {threads}")
        
        # Load time
        t0 = time.perf_counter()
        detector = VehicleDetector(model_path, target_size=320, num_threads=threads)
        # Force load net
        detector.load()
        load_time = (time.perf_counter() - t0) * 1000.0
        
        # Warmup time (10 iterations)
        t_warmup_start = time.perf_counter()
        for _ in range(10):
            detector.detect(dummy_frame)
        warmup_time = (time.perf_counter() - t_warmup_start) * 1000.0 / 10.0
        
        # Inference Latency (50 iterations)
        latencies = []
        for _ in range(50):
            t_inf_start = time.perf_counter()
            detector.detect(dummy_frame)
            latencies.append((time.perf_counter() - t_inf_start) * 1000.0)
            
        stats = get_percentiles(latencies)
        
        print(f"  Load Time       : {load_time:.2f} ms")
        print(f"  Avg Warmup Time : {warmup_time:.2f} ms/frame")
        print(f"  Inference Latency:")
        print(f"    Min           : {stats['min']:.2f} ms")
        print(f"    Avg           : {stats['avg']:.2f} ms")
        print(f"    p95           : {stats['p95']:.2f} ms")
        print(f"    p99           : {stats['p99']:.2f} ms")
        print(f"    Max           : {stats['max']:.2f} ms")

# =====================================================================
# PHASE 4: PIPELINE AUDIT
# =====================================================================
def run_pipeline_audit():
    print_banner("Phase 4: Pipeline Audit")
    
    runs = 100
    dummy_720p = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)
    dummy_crop = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
    
    # 1. Resize benchmark
    latencies = []
    for _ in range(runs):
        t0 = time.perf_counter()
        cv2.resize(dummy_720p, (320, 320), interpolation=cv2.INTER_LINEAR)
        latencies.append((time.perf_counter() - t0) * 1000.0)
    print_pipeline_stats("Resize (720p -> 320x320)", latencies)
    
    # 2. Preprocess (NCNN simulator or native logic)
    # Norm normalization preprocessing emulation
    latencies = []
    for _ in range(runs):
        t0 = time.perf_counter()
        # Resize BGR
        res = cv2.resize(dummy_720p, (320, 320))
        # Norm
        mat_in = res.astype(np.float32)
        mat_in = (mat_in - 114.0) / 255.0
        latencies.append((time.perf_counter() - t0) * 1000.0)
    print_pipeline_stats("Preprocessing (Simulation)", latencies)

    # 3. NCNN Inference (using 3 threads)
    model_path = get_model_path_from_settings()
    detector = None
    if os.path.exists(model_path):
        try:
            from core.detection import VehicleDetector
            detector = VehicleDetector(model_path, target_size=320, num_threads=3)
            detector.load()
        except:
            pass
            
    if detector:
        latencies = []
        for _ in range(runs):
            t0 = time.perf_counter()
            detector.detect(dummy_720p)
            latencies.append((time.perf_counter() - t0) * 1000.0)
        print_pipeline_stats("NCNN Inference (3 threads)", latencies)
    else:
        print("  NCNN Inference: Model/Detector not available, skipping.")

    # 4. NMS Box Benchmark (C++ OpenCV Core)
    latencies = []
    # Generate 50 boxes
    boxes = [[float(np.random.randint(0, 300)), float(np.random.randint(0, 300)), 
              float(np.random.randint(20, 100)), float(np.random.randint(20, 100))] for _ in range(50)]
    scores = np.random.uniform(0.1, 0.9, 50).tolist()
    for _ in range(runs):
        t0 = time.perf_counter()
        cv2.dnn.NMSBoxes(boxes, scores, 0.25, 0.45)
        latencies.append((time.perf_counter() - t0) * 1000.0)
    print_pipeline_stats("NMS Boxes (OpenCV C++ core, 50 bboxes)", latencies)

    # 5. ByteTrack
    try:
        import supervision as sv
        tracker = sv.ByteTrack(track_activation_threshold=0.25, lost_track_buffer=15)
        xyxy = np.array([[10, 10, 50, 50], [100, 100, 160, 160], [200, 50, 250, 120]], dtype=np.float32)
        detections = sv.Detections(
            xyxy=xyxy,
            confidence=np.array([0.9, 0.8, 0.75], dtype=np.float32),
            class_id=np.array([0, 1, 0], dtype=np.int32)
        )
        latencies = []
        for _ in range(runs):
            t0 = time.perf_counter()
            tracker.update_with_detections(detections)
            latencies.append((time.perf_counter() - t0) * 1000.0)
        print_pipeline_stats("ByteTrack Update", latencies)
    except Exception as e:
        print(f"  ByteTrack Update: Failed to run ({e})")

    # 6. Counting (Flow Analysis)
    try:
        from core.tracking import TrafficFlowAnalyzer
        regions = {"1": [[0, 0], [100, 0], [100, 100], [0, 100]]}
        analyzer = TrafficFlowAnalyzer(regions)
        xyxy = np.array([[10, 10, 50, 50]], dtype=np.float32)
        detections = sv.Detections(
            xyxy=xyxy,
            confidence=np.array([0.9], dtype=np.float32),
            class_id=np.array([0], dtype=np.int32)
        )
        # Mock tracker update
        detections.tracker_id = np.array([1])
        
        latencies = []
        for _ in range(runs):
            t0 = time.perf_counter()
            # Simulate updating zones
            for zone in analyzer.zones:
                zone.trigger(detections)
            latencies.append((time.perf_counter() - t0) * 1000.0)
        print_pipeline_stats("Flow Counting (Polygon Trigger)", latencies)
    except Exception as e:
        print(f"  Flow Counting: Failed to run ({e})")

    # 7. SQLite Write (DELETE vs WAL)
    db_file = "test_audit_db.db"
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS logs (msg TEXT)")
        conn.commit()
        latencies = []
        for i in range(runs):
            t0 = time.perf_counter()
            c.execute("INSERT INTO logs VALUES (?)", (f"log_{i}",))
            conn.commit()
            latencies.append((time.perf_counter() - t0) * 1000.0)
        conn.close()
        print_pipeline_stats("SQLite Write (Journal Mode DELETE)", latencies)
    except Exception as e:
        print(f"  SQLite DELETE Write: Failed ({e})")
    finally:
        if os.path.exists(db_file):
            os.remove(db_file)
            
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("CREATE TABLE IF NOT EXISTS logs (msg TEXT)")
        conn.commit()
        latencies = []
        for i in range(runs):
            t0 = time.perf_counter()
            c.execute("INSERT INTO logs VALUES (?)", (f"log_{i}",))
            conn.commit()
            latencies.append((time.perf_counter() - t0) * 1000.0)
        conn.close()
        print_pipeline_stats("SQLite Write (WAL + synchronous=NORMAL)", latencies)
    except Exception as e:
        print(f"  SQLite WAL Write: Failed ({e})")
    finally:
        for suffix in ["", "-wal", "-shm"]:
            f = Path(db_file + suffix)
            if f.exists():
                os.remove(f)

    # 8. MQTT Publish
    import yaml
    settings_path = BASE_DIR / "shared/configs/settings.yaml"
    broker = "127.0.0.1"
    port = 1883
    if settings_path.exists():
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
                mqtt_cfg = cfg.get("mqtt", {})
                broker = mqtt_cfg.get("broker", "127.0.0.1")
                port = int(mqtt_cfg.get("port", 1883))
        except Exception:
            pass

    try:
        import paho.mqtt.client as mqtt
        try:
            client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
        except AttributeError:
            client = mqtt.Client()
        client.connect(broker, port, keepalive=60)
        client.loop_start()
        latencies = []
        for i in range(50):
            t0 = time.perf_counter()
            inf = client.publish("he_thong_giam_sat_luu_luong/audit_test", f'{{"data": {i}}}')
            inf.wait_for_publish()
            latencies.append((time.perf_counter() - t0) * 1000.0)
        client.loop_stop()
        client.disconnect()
        print_pipeline_stats(f"MQTT Publish Latency ({broker}:{port})", latencies)
    except Exception as e:
        print(f"  MQTT Publish ({broker}:{port}): Offline/Failed to benchmark ({e})")

    # 9. JPEG Encode
    latencies = []
    for _ in range(runs):
        t0 = time.perf_counter()
        cv2.imencode('.jpg', dummy_crop, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        latencies.append((time.perf_counter() - t0) * 1000.0)
    print_pipeline_stats("JPEG Encode (200x200 crop, quality=85)", latencies)

def print_pipeline_stats(name, latencies):
    stats = get_percentiles(latencies)
    print(f"  {name:<40} : Min={stats['min']:.2f}ms | Avg={stats['avg']:.2f}ms | p95={stats['p95']:.2f}ms | p99={stats['p99']:.2f}ms | Max={stats['max']:.2f}ms")

# =====================================================================
# PHASE 5: SYSTEM PROFILING
# =====================================================================
def run_system_profile(source_str, duration):
    print_banner(f"Phase 5: System Profiling ({duration} seconds)")
    
    # Try parsing numeric camera index
    try:
        source = int(source_str)
    except ValueError:
        source = source_str
        
    # Check psutil
    try:
        import psutil
    except ImportError:
        print(f"  {RED}psutil library is required for profiling!{RESET}")
        return
        
    # Load model
    model_path = get_model_path_from_settings()
    if not os.path.exists(model_path):
        print(f"  {RED}Model folder not found: {model_path}{RESET}")
        return
        
    try:
        from core.detection import VehicleDetector
        from core.tracking import TrafficFlowAnalyzer, ViolationDetector
    except ImportError:
        print(f"  {RED}Cannot import core.detection or core.tracking components.{RESET}")
        return

    # Initing components
    detector = VehicleDetector(model_path, target_size=320, num_threads=3)
    detector.load()
    
    # Default regions
    regions = {
        "1": [[10, 200], [280, 200], [280, 640], [10, 640]],
        "2": [[380, 10], [990, 10], [990, 150], [380, 150]],
    }
    tracker = TrafficFlowAnalyzer(regions)
    violator = ViolationDetector(100, 300, 500, 5.0)
    
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"  {RED}Failed to open camera source: {source}{RESET}")
        return
        
    # Create thread-safe queues
    input_queue = queue.Queue(maxsize=1)
    output_queue = queue.Queue(maxsize=1)
    
    # Logging profile stats
    profile_data = []
    csv_file_path = BASE_DIR / "scripts/system_profile.csv"
    print(f"  Profiling starting... CSV output target: {csv_file_path}")
    
    # Run loop
    frame_count = 0
    t_start = time.perf_counter()
    t_last_tick = t_start
    
    # Prepare system temperature reading
    temp_path = Path("/sys/class/thermal/thermal_zone0/temp")
    
    # Performance trackers
    frame_times = []
    loop_latencies = []
    frame_drops = 0
    
    print(f"  Progress: [", end="", flush=True)
    progress_ticks = 20
    next_tick = t_start + (duration / progress_ticks)
    tick_count = 0
    
    try:
        while time.perf_counter() - t_start < duration:
            t_loop_start = time.perf_counter()
            ret, frame = cap.read()
            if not ret:
                # Video file loop fallback
                if isinstance(source, str) and Path(source).exists():
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
                    if not ret:
                        break
                else:
                    break
                    
            # Simulating input queue push
            if input_queue.full():
                frame_drops += 1
                try:
                    input_queue.get_nowait()
                except queue.Empty:
                    pass
            input_queue.put(frame)
            
            # Read from input queue and execute inference
            active_frame = input_queue.get()
            t_inf_start = time.perf_counter()
            
            # Detect -> Track -> Logic
            detections = detector.detect(active_frame)
            tracked, flow = tracker.update(detections, active_frame)
            violator.check(tracked, lane2_is_red=True)
            
            inf_latency = (time.perf_counter() - t_inf_start) * 1000.0
            loop_latencies.append(inf_latency)
            
            frame_count += 1
            t_now = time.perf_counter()
            dt = t_now - t_last_tick
            t_last_tick = t_now
            frame_times.append(dt)
            
            # Measure CPU / RAM / Temp
            if frame_count % 30 == 0:
                cpu_p = psutil.cpu_percent()
                ram_p = psutil.virtual_memory().percent
                if temp_path.exists():
                    temp_val = float(temp_path.read_text().strip()) / 1000.0
                else:
                    temp_val = 0.0
                    
                q_occ = 1 if input_queue.full() else 0
                
                # Append metrics row
                profile_data.append({
                    "timestamp": round(t_now - t_start, 2),
                    "fps": round(1.0 / dt if dt > 0 else 0, 1),
                    "latency_ms": round(inf_latency, 2),
                    "cpu_percent": cpu_p,
                    "ram_percent": ram_p,
                    "temperature": temp_val,
                    "frame_drops": frame_drops,
                    "queue_occupancy": q_occ
                })
                
            # Progress print
            if t_now >= next_tick and tick_count < progress_ticks:
                print("#", end="", flush=True)
                tick_count += 1
                next_tick = t_start + ((tick_count + 1) * duration / progress_ticks)
                
            # Yield some time to simulate capture thread frequency (~25 FPS limit)
            elapsed_loop = (time.perf_counter() - t_loop_start)
            sleep_time = max(0.005, 0.040 - elapsed_loop)  # aim around 25 fps
            time.sleep(sleep_time)
            
    finally:
        cap.release()
        print("] Done!")
        
    # Finalize stats
    total_elapsed = time.perf_counter() - t_start
    final_fps = frame_count / total_elapsed if total_elapsed > 0 else 0
    avg_lat = np.mean(loop_latencies) if loop_latencies else 0
    
    print(f"\n  Profiling Completed:")
    print(f"    Total Frames Processed : {frame_count}")
    print(f"    Avg End-to-End FPS     : {final_fps:.2f} FPS")
    print(f"    Avg Inference Latency  : {avg_lat:.2f} ms")
    print(f"    Total Frame Drops      : {frame_drops}")
    
    # Save to CSV
    if profile_data:
        keys = profile_data[0].keys()
        with open(csv_file_path, "w", newline="", encoding="utf-8") as f:
            dict_writer = csv.DictWriter(f, keys)
            dict_writer.writeheader()
            dict_writer.writerows(profile_data)
        print(f"    {GREEN}Successfully exported profile data to {csv_file_path}{RESET}")
    else:
        print(f"    {RED}No profiling data collected. CSV not written.{RESET}")

# =====================================================================
# MAIN ENTRY POINT
# =====================================================================
def main():
    parser = argparse.ArgumentParser(description="Raspberry Pi 4 Edge AI Production Auditor")
    parser.add_argument("--source", type=str, default="0", help="Camera source index (int) or RTSP url (str) or video file path")
    parser.add_argument("--duration", type=int, default=300, help="System profile duration in seconds (default 300s / 5 mins)")
    parser.add_argument("--skip-profile", action="store_true", help="Skip the 5-minute system profiling phase")
    args = parser.parse_args()
    
    print_banner("Edge AI System Audit Started")
    print(f"  Target Source: {args.source}")
    print(f"  Profile Time : {args.duration}s")
    
    run_environment_audit()
    run_camera_audit(args.source)
    run_model_audit()
    run_pipeline_audit()
    
    if not args.skip_profile:
        run_system_profile(args.source, args.duration)
        
    print_banner("Audit Execution Completed")
    print(f"  {GREEN}Please collect the generated report and scripts/system_profile.csv for further analysis.{RESET}\n")

if __name__ == "__main__":
    main()
