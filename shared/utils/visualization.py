import cv2
import numpy as np
import supervision as sv

def render_hud(
    frame: np.ndarray,
    avg_fps: float,
    avg_dt_ms: float,
    lane2_is_red: bool,
    scale: float = 1.0,
    model_name: str = "AI Engine",
) -> None:
    """Vẽ thông tin hiệu năng hệ thống lên khung hình hiển thị."""
    light_txt = "DEN DO" if lane2_is_red else "DEN XANH"
    light_col = (0, 0, 255) if lane2_is_red else (0, 200, 0)
    text = f"{model_name} | FPS: {avg_fps:.1f} | Latency: {avg_dt_ms:.1f}ms | {light_txt}"
    
    font_scale = 1.3 * scale
    thickness_bg = int(6 * scale)
    thickness_fg = int(2 * scale)
    pos_y = int(48 * scale)
    pos_x = int(16 * scale)

    cv2.putText(frame, text, (pos_x, pos_y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), thickness_bg, cv2.LINE_AA)
    cv2.putText(frame, text, (pos_x, pos_y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, light_col, thickness_fg, cv2.LINE_AA)


def render_zones(
    frame: np.ndarray,
    tracker,
    tracked: sv.Detections,
    flow_counts: list,
    regions: dict,
    detector_class_names: dict,
    scale: float = 1.0,
) -> None:
    """Vẽ các vùng Polygon và thông số lưu lượng xe tương ứng."""
    scaled_regions = {}
    for r_name, points in regions.items():
        scaled_regions[r_name] = [[int(pt[0] * scale), int(pt[1] * scale)] for pt in points]

    for zi, zone in enumerate(tracker.zones):
        inside_mask = zone.trigger(tracked)
        occ = int(np.sum(inside_mask))

        sv_color = sv.Color.GREEN if occ > 0 else sv.Color(r=255, g=0, b=0)
        text_color = (0, 255, 0) if occ > 0 else (0, 0, 255)

        poly_points = np.array(scaled_regions[tracker.zone_names[zi]], dtype=np.int32)
        cv2.polylines(frame, [poly_points], isClosed=True, color=sv_color.as_bgr(), thickness=int(4 * scale))

        overlay = frame.copy()
        cv2.fillPoly(overlay, [poly_points], color=sv_color.as_bgr())
        cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)

        cx, cy = poly_points.mean(axis=0).astype(int)
        name = tracker.zone_names[zi]

        if name == "4":
            y_occ = cy - int(25 * scale)
            y_flow = cy + int(25 * scale)
        else:
            y_occ = cy + int(30 * scale)
            y_flow = cy + int(90 * scale)

        text_scale = 0.9 * scale
        text_thickness = int(3 * scale)

        cv2.putText(frame, f"Region {name} Occ:{occ}", (cx - int(120 * scale), y_occ),
                    cv2.FONT_HERSHEY_SIMPLEX, text_scale, text_color, text_thickness, cv2.LINE_AA)

        summary = " | ".join(
            f"{detector_class_names.get(cid, '?')}:{cnt}"
            for cid, cnt in flow_counts[zi].items() if cnt > 0
        )
        if summary:
            cv2.putText(frame, summary, (cx - int(170 * scale), y_flow),
                        cv2.FONT_HERSHEY_SIMPLEX, text_scale, text_color, text_thickness, cv2.LINE_AA)


def render_plates(
    frame: np.ndarray,
    tracked: sv.Detections,
    active_plates: dict,
    ocr_plates: dict | None = None,
    scale: float = 1.0,
) -> None:
    """Hiển thị biển số xe mô phỏng đè lên phần đuôi xe vi phạm trong GUI."""
    if len(tracked) == 0 or tracked.tracker_id is None:
        return
        
    scaled_xyxy = tracked.xyxy * scale if scale != 1.0 else tracked.xyxy
    disp_h, disp_w_limit = frame.shape[:2]

    for k, tid in enumerate(tracked.tracker_id):
        if tid not in active_plates:
            continue
        entry = active_plates[tid]
        r_img = entry["img"]
        
        # Lấy thông tin text OCR từ ocr_plates hoặc trực tiếp từ active_plates entry
        ocr_text = None
        if ocr_plates is not None:
            ocr_text = ocr_plates.get(tid, {}).get("text")
        else:
            ocr_text = entry.get("text")
        
        # Co giãn kích thước hiển thị của biển số theo tỷ lệ scale
        rh, rw = r_img.shape[:2]
        rh_scaled = int(rh * scale)
        rw_scaled = int(rw * scale)
        if rh_scaled <= 0 or rw_scaled <= 0:
            continue
        r_img_scaled = cv2.resize(r_img, (rw_scaled, rh_scaled))

        x1, y1, x2, y2 = map(int, scaled_xyxy[k])
        cx_box = x1 + (x2 - x1) // 2
        
        px1 = max(0, cx_box - rw_scaled // 2)
        px2 = min(disp_w_limit, px1 + rw_scaled)
        px1 = max(0, px2 - rw_scaled)
        py2 = min(disp_h, y2)
        py1 = max(0, py2 - rh_scaled)

        if (px2 - px1) == rw_scaled and (py2 - py1) == rh_scaled:
            frame[py1:py2, px1:px2] = r_img_scaled
            
        if ocr_text:
            cv2.putText(
                frame, ocr_text,
                (px1, max(0, py1 - int(6 * scale))),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5 * scale, (0, 255, 0), int(2 * scale), cv2.LINE_AA,
            )
