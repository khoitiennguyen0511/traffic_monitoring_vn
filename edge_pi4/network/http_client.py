import requests
import cv2
import numpy as np
import threading
import queue
import time

class APIClient:
    def __init__(self, backend_url: str):
        self.backend_url = backend_url
        # Hàng đợi chứa các tác vụ gửi ảnh vi phạm (image, plate_info)
        self.task_queue = queue.Queue()
        
        # Khởi động duy nhất 1 Worker Thread chạy ngầm suốt dòng đời của ứng dụng
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def _worker_loop(self):
        """Luồng phụ chạy ngầm tuần tự nhặt công việc từ hàng đợi để gửi đi"""
        while True:
            try:
                # Lấy công việc từ hàng đợi (hàm sẽ chặn cho tới khi có hàng)
                image, plate_info = self.task_queue.get()
                
                # Thực hiện gửi HTTP đồng bộ trên luồng phụ này
                self._send_task(image, plate_info)
                
                # Xác nhận đã xử lý xong công việc
                self.task_queue.task_done()
            except Exception as e:
                print(f"[EDGE WORKER ERROR] Lỗi hệ thống hàng đợi: {e}")
                time.sleep(1)

    def _send_task(self, image: np.ndarray, plate_info: dict = None):
        """
        Tác vụ ngầm gửi ảnh trên luồng phụ, tránh nghẽn camera chính của Pi
        """
        print("[EDGE HTTP] Bắt đầu đẩy ảnh vi phạm lên máy chủ...")
        _, img_encoded = cv2.imencode('.jpg', image)
        img_bytes = img_encoded.tobytes()
        
        files = {
            'file': ('violation.jpg', img_bytes, 'image/jpeg')
        }
        try:
            # Rút ngắn timeout kết nối từ 7s xuống 4s để giải phóng tài nguyên nhanh hơn
            response = requests.post(f"{self.backend_url}/api/v1/upload-violation", files=files, timeout=4)
            if response.status_code == 200:
                data = response.json()
                print(f"[EDGE HTTP] Thành công! Phản hồi máy chủ: {data}")
                if plate_info is not None and data.get("status") == "success":
                    plate_info["text"] = f"{data.get('plate_text')} ({data.get('confidence', 0):.2f})"
                return data
            else:
                print(f"[EDGE HTTP LỖI] Máy chủ phản hồi mã lỗi: {response.status_code}")
        except Exception as e:
            print(f"[EDGE HTTP LỖI] Kết nối Server thất bại: {e}")
        return None

    def send_violation_async(self, image: np.ndarray, plate_info: dict = None):
        """
        Đẩy tác vụ gửi ảnh vi phạm vào hàng đợi (không bao giờ block camera chính).
        Giới hạn kích thước queue tối đa 5 ảnh để tránh rò rỉ bộ nhớ RAM của Pi khi mất mạng.
        """
        if self.task_queue.qsize() < 5:
            self.task_queue.put((image, plate_info))
        else:
            print("[EDGE WARN] Hàng đợi gửi ảnh vi phạm đã đầy (mạng nghẽn hoặc server sập)! Bỏ qua ảnh để bảo vệ RAM.")

