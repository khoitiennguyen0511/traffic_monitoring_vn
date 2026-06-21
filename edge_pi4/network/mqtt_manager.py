"""
network/mqtt_manager.py — MQTTManager
======================================
MQTT client không bao giờ block luồng gọi nó.

Thiết kế:
  - Kết nối và reconnect chạy trong thread riêng với exponential backoff.
  - Publish thông qua internal queue → luồng gọi không chờ network.
  - Subscribe callbacks chạy trong thread của paho (loop_start mode).
  - Khi mất kết nối, tự động đăng ký lại tất cả subscriptions.
  - stop() dừng sạch toàn bộ threads nội bộ.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
from typing import Callable

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class MQTTManager:
    """
    Non-blocking MQTT manager với auto-reconnect.

    Parameters
    ----------
    broker : str
        Hostname hoặc IP của MQTT Broker.
    port : int
        Cổng broker (thường là 1883).
    client_id : str
        ID định danh client trên broker.
    keepalive : int
        Khoảng thời gian keepalive (giây).
    """

    _RECONNECT_BASE: float = 2.0   # Giây chờ lần reconnect đầu tiên
    _RECONNECT_MAX:  float = 60.0  # Giới hạn trên backoff

    def __init__(
        self,
        broker: str,
        port: int,
        client_id: str = "edge_pi4",
        keepalive: int = 60,
    ) -> None:
        self._broker = broker
        self._port = port
        self._keepalive = keepalive

        # Đăng ký subscription: topic → callback(topic, payload_str)
        self._subscriptions: dict[str, Callable[[str, str], None]] = {}

        # Hàng đợi publish nội bộ: (topic, payload_str, qos, retain)
        self._pub_queue: queue.Queue[tuple[str, str, int, bool]] = queue.Queue(maxsize=128)

        # Trạng thái kết nối
        self._connected = threading.Event()
        self._stop_event = threading.Event()

        # Khởi tạo paho client
        self._client = mqtt.Client(client_id=client_id)
        self._client.on_connect    = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message    = self._on_message

        # Khởi động 2 threads nội bộ
        self._connect_thread = threading.Thread(
            target=self._connect_loop, daemon=True, name="MQTT-Connect"
        )
        self._publish_thread = threading.Thread(
            target=self._publish_loop, daemon=True, name="MQTT-Publish"
        )
        self._connect_thread.start()
        self._publish_thread.start()

    # ──────────────────────────────────────────────────────────────────────────
    # Paho callbacks (chạy trong paho internal thread)
    # ──────────────────────────────────────────────────────────────────────────

    def _on_connect(self, client, userdata, flags, rc: int) -> None:
        if rc == 0:
            logger.info("[MQTT] Kết nối thành công → %s:%d", self._broker, self._port)
            self._connected.set()
            # Re-subscribe tất cả topics sau khi reconnect
            for topic in self._subscriptions:
                client.subscribe(topic)
                logger.debug("[MQTT] Re-subscribed: %s", topic)
        else:
            logger.warning("[MQTT] Kết nối thất bại rc=%d", rc)

    def _on_disconnect(self, client, userdata, rc: int) -> None:
        self._connected.clear()
        if rc != 0:
            logger.warning("[MQTT] Mất kết nối bất ngờ rc=%d. Đang reconnect...", rc)

    def _on_message(self, client, userdata, msg: mqtt.MQTTMessage) -> None:
        topic = msg.topic
        if topic in self._subscriptions:
            try:
                payload = msg.payload.decode("utf-8", errors="replace").strip()
                self._subscriptions[topic](topic, payload)
            except Exception as exc:
                logger.error("[MQTT] Lỗi callback topic=%s: %s", topic, exc)

    # ──────────────────────────────────────────────────────────────────────────
    # Internal threads
    # ──────────────────────────────────────────────────────────────────────────

    def _connect_loop(self) -> None:
        """Thread quản lý kết nối với exponential backoff."""
        delay = self._RECONNECT_BASE

        while not self._stop_event.is_set():
            if self._client.is_connected():
                # Đã kết nối — chờ và kiểm tra lại sau 5 giây
                self._stop_event.wait(5.0)
                continue

            try:
                logger.info(
                    "[MQTT] Đang kết nối tới %s:%d ...", self._broker, self._port
                )
                self._client.connect(self._broker, self._port, self._keepalive)
                self._client.loop_start()
                delay = self._RECONNECT_BASE   # Reset backoff khi thành công
                self._stop_event.wait(5.0)
            except Exception as exc:
                logger.error(
                    "[MQTT] Lỗi kết nối: %s. Thử lại sau %.1fs.", exc, delay
                )
                self._stop_event.wait(delay)
                delay = min(delay * 2, self._RECONNECT_MAX)

        # Dọn dẹp khi stop
        try:
            self._client.loop_stop()
            self._client.disconnect()
        except Exception:
            pass
        logger.info("[MQTT] Connect thread đã dừng.")

    def _publish_loop(self) -> None:
        """Thread gửi tin nhắn từ queue ra broker."""
        while not self._stop_event.is_set():
            try:
                topic, payload, qos, retain = self._pub_queue.get(timeout=1.0)
                if self._connected.is_set():
                    self._client.publish(topic, payload, qos=qos, retain=retain)
                else:
                    logger.debug("[MQTT] Không có kết nối, bỏ qua publish topic=%s", topic)
                self._pub_queue.task_done()
            except queue.Empty:
                continue
            except Exception as exc:
                logger.error("[MQTT] Lỗi publish: %s", exc)
        logger.info("[MQTT] Publish thread đã dừng.")

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def subscribe(self, topic: str, callback: Callable[[str, str], None]) -> None:
        """
        Đăng ký lắng nghe một topic.

        Parameters
        ----------
        topic : str
            Topic MQTT.
        callback : Callable[[str, str], None]
            Hàm được gọi khi nhận tin: callback(topic, payload_str).
        """
        self._subscriptions[topic] = callback
        if self._connected.is_set():
            self._client.subscribe(topic)

    def publish(
        self,
        topic: str,
        payload: str | dict | list,
        qos: int = 0,
        retain: bool = False,
    ) -> None:
        """
        Đưa tin nhắn vào hàng đợi để gửi (non-blocking).
        Nếu queue đầy (backpressure), tin nhắn bị bỏ qua và log cảnh báo.

        Parameters
        ----------
        payload : str | dict | list
            Nếu là dict/list, tự động serialize sang JSON.
        """
        if not isinstance(payload, str):
            payload = json.dumps(payload, ensure_ascii=False)
        try:
            self._pub_queue.put_nowait((topic, payload, qos, retain))
        except queue.Full:
            logger.warning(
                "[MQTT] Publish queue đầy, bỏ qua tin nhắn topic=%s", topic
            )

    def stop(self) -> None:
        """Dừng tất cả các threads nội bộ một cách sạch sẽ."""
        self._stop_event.set()
