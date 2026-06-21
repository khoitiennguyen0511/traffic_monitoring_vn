import sqlite3
import os
from pathlib import Path

DB_PATH = Path(os.path.dirname(__file__)).parent / "data/traffic.db"

def get_db_connection() -> sqlite3.Connection:
    """Kết nối SQLite và cấu hình chế độ ghi trước nhật ký (WAL) cùng đồng bộ NORMAL."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    return conn

def init_db() -> None:
    """Khởi tạo bảng cơ sở dữ liệu nếu chưa tồn tại."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS violations (
            id TEXT PRIMARY KEY,
            timestamp TEXT,
            plate_text TEXT,
            confidence REAL,
            image_path TEXT
        )
    """)
    conn.commit()
    conn.close()

def insert_violation(v_id: str, timestamp: str, plate_text: str, confidence: float, image_path: str) -> None:
    """Ghi nhận phương tiện vi phạm vào cơ sở dữ liệu SQLite."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO violations (id, timestamp, plate_text, confidence, image_path) VALUES (?, ?, ?, ?, ?)",
        (v_id, timestamp, plate_text, confidence, image_path)
    )
    conn.commit()
    conn.close()

def get_latest_violations(limit: int = 50) -> list:
    """Lấy danh sách các phương tiện vi phạm mới nhất."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, timestamp, plate_text, confidence, image_path FROM violations ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    
    # Chuyển đổi từ Row object sang list of dicts
    return [dict(row) for row in rows]
