"""
core/pipeline.py — CaptureThread
=================================
Luồng camera chuyên dụng (always-fresh frame strategy).

Nguyên lý:
  - Chạy vòng lặp cap.read() ở tốc độ tối đa trong thread riêng biệt.
  - Luôn giữ lại frame **mới nhất**, bỏ qua frame cũ chưa được xử lý.
  - Main/Inference thread gọi get_latest_frame() để lấy frame tươi nhất
    mà không bao giờ bị block.
  - Khi nguồn video bị mất (RTSP disconnect, USB cam bị rút), tự động
    reconnect với exponential backoff.

Lợi ích so với thiết kế cũ (single-thread):
  - Trong khi NCNN đang inference ~80-120ms, camera không bị stall.
  - Không còn hiện tượng frame tích lũy lag trong buffer của OpenCV.
  - Khi inference xong, lấy ngay frame hiện tại của camera, không
    phải frame đã bị delay 100-200ms.
"""

from __future__ import annotations

import logging
import sys
import threading
import time

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class CaptureThread(threading.Thread):
    """
    Thread chụp ảnh camera liên tục, luôn cung cấp frame mới nhất.

    Parameters
    ----------
    source : int | str
        Số camera (0, 1, ...), đường dẫn file video, hoặc URL RTSP.
    W, H : int
        Kích thước đầu ra sau khi resize (pixels).
    """

    _MAX_RECONNECT_DELAY: float = 30.0   # Giới hạn trên của backoff (giây)
    _RECONNECT_DELAY_BASE: float = 1.0   # Thời gian chờ đầu tiên khi reconnect

    def __init__(self, source: int | str, W: int, H: int) -> None:
        super().__init__(daemon=True, name="CaptureThread")
        self._source = source
        self._W = W
        self._H = H

        # Shared state — bảo vệ bằng lock
        self._lock = threading.Lock()
        self._frame: np.ndarray | None = None
        self._frame_count: int = 0

        # Synchronization signals
        self._stop_event = threading.Event()
        self._first_frame_event = threading.Event()  # Báo hiệu frame đầu tiên đã sẵn sàng

    # ──────────────────────────────────────────────────────────────────────────
    # Thread entry point
    # ──────────────────────────────────────────────────────────────────────────

    def run(self) -> None:
        reconnect_delay = self._RECONNECT_DELAY_BASE

        while not self._stop_event.is_set():
            # Nhận dạng nguồn camera cục bộ để áp dụng V4L2 backend trên Linux
            is_local_cam = False
            if isinstance(self._source, int):
                is_local_cam = True
            elif isinstance(self._source, str):
                if self._source.isdigit():
                    self._source = int(self._source)
                    is_local_cam = True
                elif self._source.startswith("/dev/video"):
                    try:
                        index = int(self._source[10:])
                        self._source = index
                        is_local_cam = True
                    except ValueError:
                        pass

            if is_local_cam and sys.platform.startswith("linux"):
                logger.info(
                    "[Capture] Khởi tạo camera nguồn %s với backend V4L2 và độ phân giải %dx%d...",
                    self._source, self._W, self._H
                )
                cap = cv2.VideoCapture(self._source, cv2.CAP_V4L2)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._W)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._H)
            else:
                cap = cv2.VideoCapture(self._source)

            if not cap.isOpened():
                logger.error(
                    "[Capture] Không thể mở nguồn: %s. Thử lại sau %.1fs.",
                    self._source, reconnect_delay
                )
                self._stop_event.wait(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, self._MAX_RECONNECT_DELAY)
                continue

            # Kết nối thành công — reset backoff
            reconnect_delay = self._RECONNECT_DELAY_BASE
            logger.info("[Capture] Đã mở nguồn: %s", self._source)

            self._read_loop(cap)
            cap.release()

            if not self._stop_event.is_set():
                logger.warning(
                    "[Capture] Nguồn bị ngắt. Reconnect sau %.1fs.", reconnect_delay
                )
                self._stop_event.wait(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, self._MAX_RECONNECT_DELAY)

        logger.info("[Capture] Thread đã dừng.")

    def _read_loop(self, cap: cv2.VideoCapture) -> None:
        """
        Vòng lặp đọc frame từ camera đã kết nối.

        - Với file video cục bộ: tự động tính FPS gốc và pacing để
          không đọc nhanh hơn thực tế (tránh main loop render cùng
          1 frame hàng trăm lần/giây).
        - Với RTSP / USB camera: không pacing (camera tự giới hạn FPS).
        """
        need_resize = True

        # ── FPS pacing cho file video ──────────────────────────────────────
        src = str(self._source)
        is_usb_cam = isinstance(self._source, int) or src.isdigit()
        is_video_file = not is_usb_cam and not any(src.startswith(p) for p in ("rtsp://", "rtmp://", "/dev/"))
        if is_video_file:
            video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            frame_interval = 1.0 / video_fps
            logger.info("[Capture] Video FPS=%.1f → pacing interval=%.1fms",
                        video_fps, frame_interval * 1000)
        else:
            frame_interval = 0.0

        last_cap_time = time.perf_counter()

        while not self._stop_event.is_set():
            # Pacing: chờ đủ thời gian giữa hai frame
            if frame_interval > 0:
                elapsed = time.perf_counter() - last_cap_time
                wait = frame_interval - elapsed
                if wait > 0:
                    time.sleep(wait)
            last_cap_time = time.perf_counter()

            ret, frame = cap.read()

            if not ret:
                # Hết file video → loop lại từ đầu
                if is_video_file:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    last_cap_time = time.perf_counter()
                    continue
                # RTSP / camera thật → báo mất kết nối
                return

            # Resize một lần duy nhất tại capture thread
            if need_resize or frame.shape[1] != self._W or frame.shape[0] != self._H:
                frame = cv2.resize(frame, (self._W, self._H), interpolation=cv2.INTER_LINEAR)
                need_resize = False

            # Always-fresh: ghi đè frame cũ
            with self._lock:
                self._frame = frame
                self._frame_count += 1

            if not self._first_frame_event.is_set():
                self._first_frame_event.set()

    # ──────────────────────────────────────────────────────────────────────────
    # Public API (gọi từ main/inference thread)
    # ──────────────────────────────────────────────────────────────────────────

    def get_latest_frame(self) -> tuple[np.ndarray | None, int]:
        """
        Trả về bản sao của frame mới nhất và chỉ số frame.
        Non-blocking — trả về (None, 0) nếu chưa có frame nào.
        """
        with self._lock:
            if self._frame is None:
                return None, 0
            return self._frame.copy(), self._frame_count

    def wait_ready(self, timeout: float = 15.0) -> bool:
        """
        Block cho đến khi frame đầu tiên sẵn sàng hoặc hết timeout.

        Returns
        -------
        bool
            True nếu frame đã sẵn sàng, False nếu timeout.
        """
        return self._first_frame_event.wait(timeout)

    def stop(self) -> None:
        """Ra hiệu cho thread dừng. Gọi join() sau đó để đợi thread kết thúc."""
        self._stop_event.set()

    @property
    def frame_count(self) -> int:
        """Tổng số frame đã capture (thread-safe)."""
        with self._lock:
            return self._frame_count
