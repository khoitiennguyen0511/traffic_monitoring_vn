#!/usr/bin/env python3
"""
agent_ncnn.py — Edge Agent (NCNN Optimized)
============================================
Pipeline giám sát giao thông tối ưu cho Raspberry Pi 4.

Kiến trúc đa luồng:
  ┌─────────────────────────────────────────────────────────────┐
  │  Thread [CaptureThread]  → Always-fresh frame               │
  │    Camera/Video ──────→ shared _frame (lock-protected)      │
  │                                                             │
  │  Thread [MQTT-Connect]   → paho auto-reconnect loop         │
  │  Thread [MQTT-Publish]   → non-blocking publish queue       │
  │  Thread [HTTP-Worker]    → upload ảnh vi phạm bất đồng bộ  │
  │                                                             │
  │  Main Thread             → Inference + Tracking + Render    │
  │    get_latest_frame()                                       │
  │    → NCNN detect (4 cores ARM)                              │
  │    → ByteTrack update                                       │
  │    → ViolationDetector check                                │
  │    → cv2.imshow / headless mode                             │
  └─────────────────────────────────────────────────────────────┘

So với thiết kế cũ (single-thread sequential):
  - Camera không bị stall trong khi NCNN inference (~80-120ms).
  - Không còn frame tích lũy lag trong buffer OpenCV.
  - MQTT publish không block main thread.
  - Graceful shutdown qua Ctrl+C / SIGINT.

Chạy:
    cd edge_pi4
    source .venv/bin/activate
    python3 agent_ncnn.py
"""

from __future__ import annotations

import logging
import random
import signal
import sys
import threading
import time
from pathlib import Path

import cv2

# Đảm bảo mã hóa UTF-8 trên Windows để không lỗi print kí tự tiếng Việt
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
import numpy as np
import supervision as sv
import yaml

# ── Đường dẫn gốc project ────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent          # traffic_monitoring_vn/
EDGE_DIR = Path(__file__).parent                  # edge_pi4/
sys.path.insert(0, str(BASE_DIR))

# ── Local imports ─────────────────────────────────────────────────────────────
from core.detection import VehicleDetector
from core.tracking import TrafficFlowAnalyzer, ViolationDetector
from core.pipeline import CaptureThread
from network.http_client import APIClient
from network.mqtt_manager import MQTTManager

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)-12s] %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("agent_ncnn")

# ── Global shutdown signal ────────────────────────────────────────────────────
_shutdown = threading.Event()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_settings(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _build_regions(region_cfg: dict, W: int, H: int) -> dict:
    """Chuyển đổi tọa độ tỷ lệ (0.0-1.0) thành pixel."""
    return {
        str(name): [[int(p[0] * W), int(p[1] * H)] for p in points]
        for name, points in region_cfg.items()
    }


def _default_regions(W: int, H: int) -> dict:
    """Vùng mặc định nếu settings.yaml không có 'regions'."""
    def r(x1f, y1f, x2f, y2f):
        return [
            [int(x1f * W), int(y1f * H)], [int(x2f * W), int(y1f * H)],
            [int(x2f * W), int(y2f * H)], [int(x1f * W), int(y2f * H)],
        ]
    return {
        "1": r(0.01, 0.28, 0.22, 0.90),
        "2": r(0.30, 0.01, 0.78, 0.22),
        "3": r(0.80, 0.22, 0.99, 0.85),
        "4": r(0.23, 0.88, 0.72, 0.99),
    }


def _handle_violation(
    k: int,
    tracked: sv.Detections,
    frame: np.ndarray,
    W: int,
    H: int,
    plates_files: list[Path],
    active_plates: dict,
    http_client: APIClient,
) -> None:
    """Xử lý một xe vi phạm: cắt ảnh, ghép biển số, gửi lên server."""
    tid = tracked.tracker_id[k]
    x1, y1, x2, y2 = map(int, tracked.xyxy[k])
    logger.warning("  ⚠  Xe #%d đè vạch cấm vượt đèn đỏ!", tid)

    # Clip tọa độ
    tx1, ty1 = max(0, x1), max(0, y1)
    tx2, ty2 = min(W, x2), min(H, y2)
    v_img = frame[ty1:ty2, tx1:tx2].copy()
    vh, vw = v_img.shape[:2]

    if vh <= 10 or vw <= 10:
        return

    upload_img = v_img   # Ảnh mặc định nếu không có biển số mô phỏng

    if plates_files:
        rand_plate = random.choice(plates_files)
        r_orig = cv2.imread(str(rand_plate))
        if r_orig is not None:
            orig_h, orig_w = r_orig.shape[:2]

            # Bản chất lượng cao để OCR đọc được (≥400px wide)
            tgt_w   = max(400, vw)
            tgt_vh  = int(vh * tgt_w / vw)
            v_big   = cv2.resize(v_img, (tgt_w, tgt_vh))
            rh_big  = int(tgt_w * orig_h / orig_w)
            r_big   = cv2.resize(r_orig, (tgt_w, rh_big))
            upload_img = np.vstack((v_big, r_big))

            # Bản nhỏ để overlay lên frame hiển thị
            disp_w = max(55, int(vw * 0.7))
            rh_sm  = int(disp_w * orig_h / orig_w)
            r_sm   = cv2.resize(r_orig, (disp_w, rh_sm))
            active_plates[tid] = {"img": r_sm, "frames": 60, "text": None}

    # Gửi ảnh lên FastAPI server (background thread, không block)
    http_client.send_violation_async(upload_img, plate_info=active_plates.get(tid))


# ─────────────────────────────────────────────────────────────────────────────
# Render helpers
# ─────────────────────────────────────────────────────────────────────────────

def _render_hud(
    frame: np.ndarray,
    avg_fps: float,
    avg_dt_ms: float,
    lane2_is_red: bool,
) -> None:
    """Vẽ HUD thông tin hiệu năng và trạng thái đèn (font lớn dễ đọc)."""
    light_txt = "DEN DO" if lane2_is_red else "DEN XANH"
    light_col = (0, 0, 255) if lane2_is_red else (0, 200, 0)
    text = f"NCNN | FPS:{avg_fps:5.1f} | {avg_dt_ms:5.1f}ms | {light_txt}"
    # Shadow đen → nổi bật trên mọi nền
    cv2.putText(frame, text, (16, 48), cv2.FONT_HERSHEY_SIMPLEX, 1.3, (0, 0, 0),     6, cv2.LINE_AA)
    cv2.putText(frame, text, (16, 48), cv2.FONT_HERSHEY_SIMPLEX, 1.3, light_col,    2, cv2.LINE_AA)


def _render_zones(
    frame: np.ndarray,
    tracker: TrafficFlowAnalyzer,
    tracked: sv.Detections,
    flow_counts: list,
    regions: dict,
    detector: VehicleDetector,
) -> None:
    """Vẽ các vùng polygon và thống kê lưu lượng — giống code cũ (PolygonZoneAnnotator)."""
    for zi, zone in enumerate(tracker.zones):
        inside_mask = zone.trigger(tracked)
        occ = int(np.sum(inside_mask))

        # Màu zone: xanh khi có xe, đỏ khi rỗng
        sv_color = sv.Color.GREEN if occ > 0 else sv.Color(r=255, g=0, b=0)
        text_color = (0, 255, 0) if occ > 0 else (0, 0, 255)

        # Vẽ vùng polygon bằng supervision (có fill màu nền bán trong suốt)
        zone_ann = sv.PolygonZoneAnnotator(zone=zone, color=sv_color, thickness=4)
        zone_ann.annotate(scene=frame)

        # Tính tâm vùng để vẽ text
        poly = np.array(regions[tracker.zone_names[zi]], dtype=np.float32)
        cx, cy = poly.mean(axis=0).astype(int)
        name = tracker.zone_names[zi]

        if name == "4":
            y_occ  = cy - 25
            y_flow = cy + 25
        else:
            y_occ  = cy + 30
            y_flow = cy + 90

        # Nhãn vùng và số xe — giống code cũ
        cv2.putText(frame, f"Region {name}  Occ:{occ}", (cx - 120, y_occ),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, text_color, 4, cv2.LINE_AA)

        # Tóm tắt lưu lượng theo loại xe
        summary = " | ".join(
            f"{detector.class_names_dict.get(cid, '?')}:{cnt}"
            for cid, cnt in flow_counts[zi].items() if cnt > 0
        )
        if summary:
            cv2.putText(frame, summary, (cx - 170, y_flow),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, text_color, 4, cv2.LINE_AA)


def _render_plates(
    frame: np.ndarray,
    tracked: sv.Detections,
    active_plates: dict,
    W: int,
    H: int,
) -> None:
    """Overlay biển số mô phỏng lên xe đang bị theo dõi vi phạm."""
    if len(tracked) == 0 or tracked.tracker_id is None:
        return
    for k, tid in enumerate(tracked.tracker_id):
        if tid not in active_plates:
            continue
        entry = active_plates[tid]
        r_img = entry["img"]
        ocr_text = entry.get("text")
        rh, rw = r_img.shape[:2]

        x1, y1, x2, y2 = map(int, tracked.xyxy[k])
        cx_box = x1 + (x2 - x1) // 2
        px1 = max(0, cx_box - rw // 2)
        px2 = min(W, px1 + rw)
        px1 = max(0, px2 - rw)
        py2 = min(H, y2)
        py1 = max(0, py2 - rh)

        if (px2 - px1) == rw and (py2 - py1) == rh:
            frame[py1:py2, px1:px2] = r_img
        if ocr_text:
            cv2.putText(
                frame, ocr_text,
                (px1, max(0, py1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2, cv2.LINE_AA,
            )


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    global _shutdown

    # ── Graceful shutdown qua Ctrl+C ─────────────────────────────────────────
    def _sigint_handler(sig, frame):
        logger.info("[Shutdown] Nhận SIGINT. Đang dừng pipeline...")
        _shutdown.set()

    signal.signal(signal.SIGINT, _sigint_handler)

    # ── Parse Command Line Arguments ─────────────────────────────────────────
    import argparse
    parser = argparse.ArgumentParser(description="Edge Agent — NCNN Optimized")
    parser.add_argument("--source", type=str, default=None, help="Camera source (e.g. 0, 1, video, rtsp://...)")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode without opening GUI windows")
    parser.add_argument("--config", type=str, default="shared/configs/settings.yaml", help="Path to config file (relative to root)")
    parser.add_argument("--model", type=str, default=None, help="Path to NCNN model folder (overrides config)")
    parser.add_argument("--size", type=int, default=None, help="Input size for model inference (overrides config)")
    args = parser.parse_args()

    # ── 1. Load cấu hình ─────────────────────────────────────────────────────
    settings_path = BASE_DIR / args.config
    cfg      = _load_settings(settings_path)
    edge_cfg = cfg.get("edge", {})
    mqtt_cfg = cfg.get("mqtt", {})
    srv_cfg  = cfg.get("server", {})

    W = int(edge_cfg.get("display_width", 1280))
    H = int(edge_cfg.get("display_height", 720))

    # Xử lý nguồn camera từ tham số dòng lệnh hoặc config
    sim_video = edge_cfg.get("simulation_video", "vehicle_counting.mp4")
    if args.source is not None:
        if args.source.isdigit():
            cam_src = int(args.source)
        elif args.source.lower() == "video":
            cam_src = str(BASE_DIR / sim_video)
        else:
            cam_src = args.source
    else:
        simulation_mode = bool(edge_cfg.get("simulation_mode", True))
        cam_src = edge_cfg.get("camera_source", 0)
        if simulation_mode and cam_src == 0:
            cam_src = str(BASE_DIR / sim_video)
        elif isinstance(cam_src, str) and cam_src.isdigit():
            cam_src = int(cam_src)

    headless = args.headless or not bool(edge_cfg.get("display_gui", True))

    # Resolve model_path
    if args.model is not None:
        model_path = str(BASE_DIR / args.model)
    else:
        model_path = str(BASE_DIR / edge_cfg.get("model_path", "shared/models/vehicle_best_ncnn_model"))

    # Resolve target_size
    if args.size is not None:
        target_size = args.size
    else:
        target_size = int(edge_cfg.get("target_size", 320))

    num_threads  = int(edge_cfg.get("num_threads", 4))
    conf_thresh  = float(edge_cfg.get("confidence_threshold", 0.25))
    skip_factor   = int(edge_cfg.get("skip_factor", 2))
    cooldown_sec  = float(edge_cfg.get("violation_cooldown_sec", 5.0))
    mqtt_ivl      = int(edge_cfg.get("mqtt_publish_interval_frames", 30))
    bench_ivl     = int(edge_cfg.get("benchmark_interval_frames", 60))
    display_scale = float(edge_cfg.get("display_scale", 0.75))
    fullscreen    = bool(edge_cfg.get("fullscreen", False))

    # Server host ưu tiên từ edge_cfg.server_host
    server_host = edge_cfg.get("server_host") or srv_cfg.get("host", "127.0.0.1")
    if server_host in ("0.0.0.0", ""):
        server_host = "127.0.0.1"
    server_port = int(srv_cfg.get("port", 8000))
    backend_url = f"http://{server_host}:{server_port}"

    # Vùng đếm xe
    region_cfg = edge_cfg.get("regions")
    regions = _build_regions(region_cfg, W, H) if region_cfg else _default_regions(W, H)

    # Vạch cấm
    vl = edge_cfg.get("violation_line", {})
    line_x1 = int(vl.get("x1_frac", 0.48) * W)
    line_x2 = int(vl.get("x2_frac", 0.70) * W)
    line_y  = int(vl.get("y_frac",  0.90) * H)

    plates_dir   = BASE_DIR / edge_cfg.get("plates_dir", "plates")
    plates_files = list(plates_dir.glob("*.png")) + list(plates_dir.glob("*.jpg"))

    logger.info("═" * 60)
    logger.info("  Edge Agent — NCNN Optimized")
    logger.info("  Source  : %s", cam_src)
    logger.info("  Model   : %s  (size=%d)", model_path, target_size)
    logger.info("  Server  : %s", backend_url)
    logger.info("  MQTT    : %s:%d", mqtt_cfg.get("broker"), mqtt_cfg.get("port", 1883))
    logger.info("  Display : %dx%d | skip=%d | cooldown=%.1fs",
                W, H, skip_factor, cooldown_sec)
    logger.info("═" * 60)

    # ── 2. Khởi tạo mô hình ──────────────────────────────────────────────────
    logger.info("[Init] Đang tải mô hình NCNN...")
    detector = VehicleDetector(model_path, target_size=target_size, num_threads=num_threads)
    detector.load()  # Eager load → loại bỏ latency spike ở frame đầu tiên
    logger.info("[Init] Mô hình NCNN đã tải xong.")

    # ── 3. Tracker + ViolationDetector ───────────────────────────────────────
    tracker    = TrafficFlowAnalyzer(regions)
    violator   = ViolationDetector(line_x1, line_x2, line_y, cooldown_sec)

    # ── 4. MQTT Manager ───────────────────────────────────────────────────────
    lane2_is_red: bool = True

    mqtt_mgr = MQTTManager(
        broker=mqtt_cfg.get("broker", "127.0.0.1"),
        port=int(mqtt_cfg.get("port", 1883)),
        client_id="edge_ncnn",
    )
    topic_vehicle = mqtt_cfg.get("topic_vehicle_count",
                                  "he_thong_giam_sat_luu_luong/vehicle_count")
    topic_light   = mqtt_cfg.get("topic_light_state",
                                  "he_thong_giam_sat_luu_luong/light_state")

    def _on_light(topic: str, payload: str) -> None:
        nonlocal lane2_is_red
        if payload in ("1_GREEN", "1_YELLOW"):
            lane2_is_red = True
        else:
            lane2_is_red = False
        logger.info("[MQTT] Trạng thái đèn: %-12s → lane2_red=%s", payload, lane2_is_red)

    mqtt_mgr.subscribe(topic_light, _on_light)

    # ── 5. HTTP Client ────────────────────────────────────────────────────────
    http_client = APIClient(backend_url)

    # ── 6. CaptureThread ─────────────────────────────────────────────────────
    capture = CaptureThread(source=cam_src, W=W, H=H)
    capture.start()
    logger.info("[Init] Chờ frame đầu tiên từ camera...")
    if not capture.wait_ready(timeout=15.0):
        logger.error("[Init] Timeout chờ camera! Kiểm tra lại nguồn: %s", cam_src)
        capture.stop()
        capture.join(timeout=3.0)
        return
    logger.info("[Init] Camera sẵn sàng. Bắt đầu vòng lặp inference.")

    # ── 7. Annotators (kích thước lớn để dễ đọc trên màn hình nhỏ) ─────────────
    trace_ann = sv.TraceAnnotator(thickness=3, trace_length=40)
    box_ann   = sv.BoxAnnotator(thickness=3)
    label_ann = sv.LabelAnnotator(
        text_thickness=2, text_scale=0.70, text_color=sv.Color.BLACK
    )

    # ── 7.5 Khởi tạo cửa sổ OpenCV MỘT LẦN ─────────────────────────────────────
    if not headless:
        # namedWindow/resizeWindow KHÔNG được gọi mỗi frame — sẽ gây double-frame!
        win_name = "Edge Pi4 — NCNN Optimized"
        disp_w   = int(W * display_scale)
        disp_h   = int(H * display_scale)
        try:
            cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
            if fullscreen:
                cv2.setWindowProperty(win_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            else:
                cv2.resizeWindow(win_name, disp_w, disp_h)
        except cv2.error:
            pass   # Headless

    # ── 8. State vòng lặp ─────────────────────────────────────────────────────
    active_plates: dict[int, dict] = {}
    frame_times: list[float] = []
    frame_count: int = 0
    last_render_frame: int = 0          # Chỉ render frame mới, bỏ qua frame trùng
    avg_dt: float = 0.05

    tracked_dets = sv.Detections.empty()
    flow_counts  = [{} for _ in tracker.zones]

    csv_path = BASE_DIR / "shared/configs/benchmark_ncnn.csv"

    logger.info("═══ NCNN PIPELINE ĐANG CHẠY — nhấn Q để thoát ═══")

    # ── 9. Main inference loop ────────────────────────────────────────────────
    while not _shutdown.is_set():
        frame, frame_idx = capture.get_latest_frame()
        if frame is None:
            time.sleep(0.005)
            continue

        # Bỏ qua nếu chưa có frame mới — tránh render cùng 1 frame nhiều lần
        if frame_idx == last_render_frame:
            time.sleep(0.001)
            continue
        last_render_frame = frame_idx

        frame_count += 1
        t0 = time.perf_counter()

        # ── Inference (mỗi skip_factor frame) ────────────────────────────────
        if frame_count % skip_factor == 0 or frame_count == 1:
            detections           = detector.detect(frame)
            tracked_dets, flow_counts = tracker.update(detections, frame)

        # ── Phát hiện vi phạm ─────────────────────────────────────────────────
        if len(tracked_dets) > 0:
            new_viol = violator.check(tracked_dets, lane2_is_red)
            for k in new_viol:
                _handle_violation(
                    k, tracked_dets, frame, W, H,
                    plates_files, active_plates, http_client,
                )

        # Giảm bộ đếm hiển thị biển số
        for tid in list(active_plates):
            active_plates[tid]["frames"] -= 1
            if active_plates[tid]["frames"] <= 0:
                del active_plates[tid]

        # ── MQTT publish (Occupancy-based for real-time adaptive traffic light) ──
        if frame_count % mqtt_ivl == 0:
            mqtt_data = {}
            for zi, name in enumerate(tracker.zone_names):
                rc = {"motorbike": 0, "car": 0, "bus": 0, "truck": 0}
                if len(tracked_dets) > 0:
                    inside_mask = tracker.zones[zi].trigger(tracked_dets)
                    for k, is_inside in enumerate(inside_mask):
                        if is_inside:
                            cid = tracked_dets.class_id[k]
                            cn = detector.class_names_dict.get(cid, "")
                            if cn in rc:
                                rc[cn] += 1
                mqtt_data[f"region_{name}"] = rc
            mqtt_mgr.publish(topic_vehicle, mqtt_data)
            logger.debug("[MQTT] Đã publish %d vùng (Occupancy).", len(mqtt_data))

        # ── FPS tracking ──────────────────────────────────────────────────────
        dt = time.perf_counter() - t0
        frame_times.append(dt)
        if len(frame_times) > 60:
            frame_times.pop(0)
        avg_dt  = sum(frame_times) / len(frame_times)
        avg_fps = 1.0 / avg_dt if avg_dt > 0 else 0.0

        # ── Benchmark CSV ─────────────────────────────────────────────────────
        if frame_count % bench_ivl == 0:
            hdr = not csv_path.exists()
            with open(csv_path, "a", encoding="utf-8") as f:
                if hdr:
                    f.write("frame,fps,latency_ms\n")
                f.write(f"{frame_count},{avg_fps:.2f},{avg_dt*1000:.2f}\n")

        # ── Render & GUI (Chỉ chạy khi không chạy ở chế độ headless) ──────────
        if not headless:
            out = frame.copy()

            # Vẽ xe + trace
            if len(tracked_dets) > 0 and tracked_dets.tracker_id is not None:
                labels = [
                    f"#{tid} {detector.class_names_dict.get(cid, '?')}"
                    for cid, tid in zip(tracked_dets.class_id, tracked_dets.tracker_id)
                ]
                out = trace_ann.annotate(scene=out, detections=tracked_dets)
                out = box_ann.annotate(scene=out, detections=tracked_dets)
                out = label_ann.annotate(scene=out, detections=tracked_dets, labels=labels)

            # Vạch cấm (giống code cũ — đổi màu theo đèn)
            line_color = (0, 0, 255) if lane2_is_red else (0, 255, 0)
            cv2.line(out, (line_x1, line_y), (line_x2, line_y), line_color, 5)

            # Vùng polygon
            _render_zones(out, tracker, tracked_dets, flow_counts, regions, detector)

            # Biển số overlay
            _render_plates(out, tracked_dets, active_plates, W, H)

            # HUD
            _render_hud(out, avg_fps, avg_dt * 1000, lane2_is_red)

            # ── imshow (mỗi frame mới — FPS được kẹp bởi CaptureThread pacing) ────────
            try:
                win_name = "Edge Pi4 — NCNN Optimized"
                if display_scale != 1.0:
                    disp_w = int(W * display_scale)
                    disp_h = int(H * display_scale)
                    display_out = cv2.resize(out, (disp_w, disp_h), interpolation=cv2.INTER_LINEAR)
                else:
                    display_out = out

                cv2.imshow(win_name, display_out)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == 27:   # Q hoặc ESC
                    _shutdown.set()
            except cv2.error:
                pass
        else:
            # Nghỉ ngắn ở luồng chính khi chạy headless để tránh chiếm dụng CPU quá mức
            time.sleep(0.001)

    # ── Cleanup ───────────────────────────────────────────────────────────────
    logger.info("[Shutdown] Dừng các threads...")
    capture.stop()
    capture.join(timeout=3.0)
    mqtt_mgr.stop()
    if not headless:
        cv2.destroyAllWindows()
    logger.info("═══ NCNN PIPELINE ĐÃ DỪNG ═══")


if __name__ == "__main__":
    main()
