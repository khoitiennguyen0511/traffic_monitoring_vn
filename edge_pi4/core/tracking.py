"""
core/tracking.py — TrafficFlowAnalyzer & ViolationDetector
===========================================================
Hai class riêng biệt với trách nhiệm rõ ràng:

TrafficFlowAnalyzer
  - Bọc ByteTrack và N vùng PolygonZone.
  - Đếm lưu lượng xe tích lũy theo từng vùng và loại xe.

ViolationDetector
  - Phát hiện xe đè vạch cấm khi đèn đỏ.
  - Cooldown-based: dùng timestamp thay vì set ID đơn giản,
    tránh gửi ảnh trùng lặp trong cùng một sự kiện vi phạm.
  - Tự dọn dẹp bộ nhớ (pruning) để tránh memory leak khi chạy dài.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict

import numpy as np
import supervision as sv

logger = logging.getLogger(__name__)


class TrafficFlowAnalyzer:
    """
    Theo dõi đa đối tượng và đếm lưu lượng xe theo N vùng polygon.

    Parameters
    ----------
    regions_dict : dict
        {"tên_vùng": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]], ...}
        Tọa độ pixel, chiều kim đồng hồ.
    """

    def __init__(self, regions_dict: dict) -> None:
        self.tracker = sv.ByteTrack(
            track_activation_threshold=0.25,
            lost_track_buffer=15,
            minimum_matching_threshold=0.7,
        )
        self.zones: list[sv.PolygonZone] = []
        self.zone_names: list[str] = []

        for name, coords in regions_dict.items():
            poly = np.array(coords, dtype=np.int32)
            self.zones.append(sv.PolygonZone(polygon=poly))
            self.zone_names.append(str(name))

        # Tập hợp track_id đã được đếm trong từng vùng (tránh đếm trùng)
        self._seen_ids: list[set[int]] = [set() for _ in self.zones]
        # Đếm tích lũy: flow_counts[zone_idx][class_id] = count
        self._flow_counts: list[defaultdict[int, int]] = [
            defaultdict(int) for _ in self.zones
        ]

    def update(
        self, detections: sv.Detections, frame: np.ndarray
    ) -> tuple[sv.Detections, list[defaultdict[int, int]]]:
        """
        Cập nhật tracker và đếm lưu lượng.

        Parameters
        ----------
        detections : sv.Detections
            Kết quả detection từ VehicleDetector.
        frame : np.ndarray
            Frame hiện tại (dùng bởi ByteTrack nội bộ).

        Returns
        -------
        tracked_detections : sv.Detections
            Detections đã được gán tracker_id.
        flow_counts : list[defaultdict]
            Đếm tích lũy theo vùng và class_id.
        """
        tracked = self.tracker.update_with_detections(detections)

        for zi, zone in enumerate(self.zones):
            inside_mask = zone.trigger(tracked)
            for k, is_inside in enumerate(inside_mask):
                if not is_inside:
                    continue
                tid = tracked.tracker_id[k]
                if tid is None or tid in self._seen_ids[zi]:
                    continue
                # Xe mới bước vào vùng → đếm
                self._seen_ids[zi].add(tid)
                
                # Dọn dẹp tránh memory leak khi chạy 24/7
                if len(self._seen_ids[zi]) > 10000:
                    self._seen_ids[zi].clear()
                    
                self._flow_counts[zi][tracked.class_id[k]] += 1
        return tracked, self._flow_counts


class ViolationDetector:
    """
    Phát hiện xe đè vạch cấm khi đèn đỏ.

    Thiết kế cooldown-based:
      - Mỗi track_id được phép vi phạm tối đa 1 lần / cooldown_sec giây.
      - Điều này cho phép cùng xe bị phạt lại nếu nó rời khỏi vạch
        và vượt lại sau thời gian cooldown (thực tế hiếm gặp nhưng đúng đắn).
      - Tự động dọn dẹp các entry cũ để tránh memory leak khi chạy 24/7.

    Parameters
    ----------
    line_x1, line_x2, line_y : int
        Tọa độ pixel của vạch cấm nằm ngang.
    cooldown_sec : float
        Thời gian chờ tối thiểu giữa hai lần phạt cùng một xe.
    """

    def __init__(
        self,
        line_x1: int,
        line_x2: int,
        line_y: int,
        cooldown_sec: float = 5.0,
    ) -> None:
        self.line_x1 = line_x1
        self.line_x2 = line_x2
        self.line_y = line_y
        self.cooldown_sec = cooldown_sec
        # track_id → thời điểm vi phạm gần nhất (time.monotonic)
        self._last_violation: dict[int, float] = {}

    def check(
        self,
        tracked: sv.Detections,
        lane2_is_red: bool,
    ) -> list[int]:
        """
        Kiểm tra và trả về danh sách **chỉ số** (index vào tracked)
        của những xe vừa bị phát hiện vi phạm mới.

        Parameters
        ----------
        tracked : sv.Detections
            Detections đã có tracker_id.
        lane2_is_red : bool
            True nếu làn 2 đang đèn đỏ.

        Returns
        -------
        list[int]
            Danh sách chỉ số k (0-based) vào tracked.xyxy của xe vi phạm.
            Rỗng nếu không có vi phạm hoặc đèn xanh.
        """
        if not lane2_is_red or len(tracked) == 0:
            return []

        now = time.monotonic()
        violating: list[int] = []

        for k in range(len(tracked)):
            tid = tracked.tracker_id[k]
            if tid is None:
                continue

            x1, y1, x2, y2 = map(int, tracked.xyxy[k])

            # Điều kiện chạm vạch: bounding box giao với vạch ngang
            touches_line = (
                y1 <= self.line_y <= y2   # Vạch nằm trong chiều cao bbox
                and x1 <= self.line_x2    # Bbox chưa sang phải hoàn toàn
                and x2 >= self.line_x1    # Bbox chưa sang trái hoàn toàn
            )
            if not touches_line:
                continue

            last = self._last_violation.get(tid, 0.0)
            if now - last >= self.cooldown_sec:
                self._last_violation[tid] = now
                violating.append(k)
                logger.warning(
                    "[ViolationDetector] Xe #%d đè vạch cấm! (cooldown=%.1fs)",
                    tid, self.cooldown_sec
                )

        # Dọn dẹp entry cũ hơn 4× cooldown để tránh memory leak
        if self._last_violation:
            cutoff = now - self.cooldown_sec * 4
            self._last_violation = {
                k: v for k, v in self._last_violation.items() if v > cutoff
            }

        return violating
