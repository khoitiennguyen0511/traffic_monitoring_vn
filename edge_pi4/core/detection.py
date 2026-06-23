import numpy as np
import supervision as sv
import cv2
from pathlib import Path

class VehicleDetector:
    def __init__(self, model_path: str, target_size: int = 320, num_threads: int = 4):
        self.model_path = model_path
        self.target_size = target_size
        self.num_threads = num_threads
        
        # Tự động phát hiện nếu là mô hình NCNN
        is_ncnn = False
        path_obj = Path(model_path)
        if path_obj.is_dir() and (model_path.endswith("_ncnn_model") or (path_obj / "model.ncnn.param").exists()):
            is_ncnn = True
        elif model_path.endswith(".param") or model_path.endswith(".bin"):
            is_ncnn = True
            
        self.is_ncnn = is_ncnn
        
        if self.is_ncnn:
            # Xác định đường dẫn tệp tin param và bin
            if path_obj.is_dir():
                if (path_obj / "model-opt.param").exists():
                    self.param_path = str(path_obj / "model-opt.param")
                    self.bin_path = str(path_obj / "model-opt.bin")
                else:
                    self.param_path = str(path_obj / "model.ncnn.param")
                    self.bin_path = str(path_obj / "model.ncnn.bin")
            else:
                if model_path.endswith(".param"):
                    self.param_path = model_path
                    self.bin_path = model_path.replace(".param", ".bin")
                else:
                    self.bin_path = model_path
                    self.param_path = model_path.replace(".bin", ".param")
            
            self.net = None
            
            # Định nghĩa nhãn lớp mặc định cho mô hình YOLOv11 tùy chỉnh
            self.class_names_dict = {
                0: "motorbike",
                1: "car",
                2: "bus",
                3: "truck",
                4: "bicycle"
            }
        else:
            from ultralytics import YOLO
            self.model = YOLO(model_path)
            self.class_names_dict = self.model.names
            
        # Danh sách các lớp xe cần giám sát lưu thông
        selected_class_names = ["motorbike", "car", "bus", "truck"]
        self.selected_class_ids = []
        for class_name in selected_class_names:
            for k, v in self.class_names_dict.items():
                if v == class_name:
                    self.selected_class_ids.append(k)
 
    def load(self):
        if self.is_ncnn:
            if self.net is not None:
                return
            import ncnn
            print(f"[NCNN] Đang tải mô hình NCNN từ: {self.param_path}")
            print(f"[NCNN] Và: {self.bin_path}")
            
            self.net = ncnn.Net()
            
            # Cấu hình tối ưu hiệu năng chạy CPU trên Raspberry Pi 4
            self.net.opt.use_vulkan_compute = False      # Tắt Vulkan
            self.net.opt.use_bf16_storage = False        # Tắt BF16 storage để tránh NCNN C++ xuất tensor dạng 16-bit
            self.net.opt.use_packing_layout = False      # Tắt packing layout vì Python-NCNN không xuất đúng dạng packed sang NumPy
            self.net.opt.num_threads = self.num_threads   # Tận dụng số luồng mong muốn
            self.net.opt.use_fp16_arithmetic = False     # Tắt FP16 arithmetic để ép buộc tính toán FP32 tiêu chuẩn, tránh lệch byte khi sang NumPy
            
            self.net.load_param(self.param_path)
            self.net.load_model(self.bin_path)
            print("[NCNN] Đã tải mô hình NCNN lên CPU thành công!")

    def detect(self, frame: np.ndarray):
        self.load()
        if self.is_ncnn:
            import ncnn
            # Đảm bảo mảng numpy đầu vào luôn liên tục trong RAM để C++ đọc chính xác
            frame = np.ascontiguousarray(frame)
            img_h, img_w = frame.shape[:2]
            
            # 1. Tiền xử lý (Letterbox resize giữ tỷ lệ) bằng Native NCNN APIs (Faster & memory-safe)
            target_size = self.target_size
            w = img_w
            h = img_h
            scale = 1.0
            if w > h:
                scale = target_size / w
                w = target_size
                h = int(h * scale)
            else:
                scale = target_size / h
                h = target_size
                w = int(w * scale)
                
            # Tạo NCNN Mat và thực hiện chuyển đổi BGR sang RGB + Resize đồng thời ở tầng C++
            mat_resized = ncnn.Mat.from_pixels_resize(
                frame, 
                ncnn.Mat.PixelType.PIXEL_BGR2RGB, 
                img_w, img_h, 
                w, h
            )
            
            # Thêm viền xám đối xứng (Padding)
            wpad = target_size - w
            hpad = target_size - h
            top = hpad // 2
            bottom = hpad - top
            left = wpad // 2
            right = wpad - left
            
            mat_in = ncnn.Mat()
            ncnn.copy_make_border(
                mat_resized,
                mat_in,
                top, bottom, left, right,
                ncnn.BorderType.BORDER_CONSTANT,
                114.0
            )
            
            # Chuẩn hóa về [0.0, 1.0] bằng hàm native cực nhanh
            mat_in.substract_mean_normalize([], [1.0/255.0, 1.0/255.0, 1.0/255.0])
            
            # 2. Chạy suy luận (Inference)
            with self.net.create_extractor() as ex:
                ex.input("in0", mat_in)
                ret, out0 = ex.extract("out0")
                if ret != 0:
                    print(f"[NCNN ERROR] Suy luận thất bại, mã lỗi: {ret}")
                    return sv.Detections.empty()
                # Clone Mat đầu ra để C++ sở hữu độc lập bộ nhớ, tránh phụ thuộc vào vòng đời của Extractor
                out0_cloned = out0.clone()
                out0_np = np.array(out0_cloned).copy()
            
            # 3. Hậu xử lý (Postprocessing)
            class_scores = out0_np[4:, :]
            
            # Chuyển vị và ép buộc mảng liên tục (C-contiguous) để tránh lỗi bộ nhớ đệm strided SIMD trên ARM RPi 4
            class_scores_t = np.ascontiguousarray(class_scores.T)
            max_class_scores = np.max(class_scores_t, axis=1)
            class_ids = np.argmax(class_scores_t, axis=1)
            
            conf_threshold = 0.25
            nms_threshold = 0.45
            
            # Lọc sơ bộ theo ngưỡng tin cậy
            conf_mask = max_class_scores >= conf_threshold
            valid_indices = np.where(conf_mask)[0]
            
            if len(valid_indices) == 0:
                return sv.Detections.empty()
                
            cxs = out0_np[0, valid_indices]
            cys = out0_np[1, valid_indices]
            ws = out0_np[2, valid_indices]
            hs = out0_np[3, valid_indices]
            probs = max_class_scores[valid_indices]
            labels = class_ids[valid_indices]
            
            # Chuyển đổi tọa độ tâm YOLO (cx, cy, w, h) sang dạng góc (x1, y1, x2, y2) trên ảnh 480x480
            x1s = cxs - ws * 0.5
            y1s = cys - hs * 0.5
            x2s = x1s + ws
            y2s = y1s + hs
            
            # Khôi phục tỷ lệ về độ phân giải gốc của camera (ví dụ: 1080p)
            x1s_scaled = (x1s - left) / scale
            y1s_scaled = (y1s - top) / scale
            x2s_scaled = (x2s - left) / scale
            y2s_scaled = (y2s - top) / scale
            
            # Giới hạn tọa độ trong biên ảnh gốc
            x1s_scaled = np.clip(x1s_scaled, 0, img_w - 1)
            y1s_scaled = np.clip(y1s_scaled, 0, img_h - 1)
            x2s_scaled = np.clip(x2s_scaled, 0, img_w - 1)
            y2s_scaled = np.clip(y2s_scaled, 0, img_h - 1)
            
            xyxy = np.stack([x1s_scaled, y1s_scaled, x2s_scaled, y2s_scaled], axis=1)
            
            # Mô phỏng Class-aware NMS của Ultralytics YOLO bằng kỹ thuật Offset
            max_coord = 4096.0
            offsets = labels * max_coord
            
            x_offset = x1s_scaled + offsets
            y_offset = y1s_scaled + offsets
            w_box = x2s_scaled - x1s_scaled
            h_box = y2s_scaled - y1s_scaled
            
            # Sử dụng cv2.dnn.NMSBoxes (OpenCV C++ core) trên tọa độ đã offset
            bboxes = np.stack([x_offset, y_offset, w_box, h_box], axis=1).tolist()
            indices = cv2.dnn.NMSBoxes(bboxes, probs.tolist(), conf_threshold, nms_threshold)
            
            if len(indices) > 0:
                indices = np.array(indices).flatten()
                xyxy = xyxy[indices]
                probs = probs[indices]
                labels = labels[indices]
                
                # Chỉ giữ lại các nhãn xe mong muốn
                selected_mask = np.isin(labels, self.selected_class_ids)
                if not np.any(selected_mask):
                    return sv.Detections.empty()
                
                xyxy = xyxy[selected_mask]
                probs = probs[selected_mask]
                labels = labels[selected_mask]
                
                # Trả về kết quả đóng gói dưới dạng supervision.Detections
                detections = sv.Detections(
                    xyxy=xyxy.astype(np.float32),
                    confidence=probs.astype(np.float32),
                    class_id=labels.astype(np.int32)
                )
                return detections
            else:
                return sv.Detections.empty()
        else:
            # Chạy qua PyTorch (YOLO gốc)
            results = self.model(frame, imgsz=self.target_size, verbose=False)[0]
            detections = sv.Detections.from_ultralytics(results)
            detections = detections[np.isin(detections.class_id, self.selected_class_ids)]
            return detections

