import streamlit as st
import sys
import time
from pathlib import Path
from datetime import datetime

# Thêm project root vào path để import
base_dir = Path(__file__).parent.parent
if str(base_dir) not in sys.path:
    sys.path.append(str(base_dir))

from server.core.database import get_latest_violations

st.set_page_config(page_title="Màn Hình Cảnh Sát - GSGT", layout="wide")

# --- SIDEBAR ---
st.sidebar.title("Cấu hình hiển thị")
auto_refresh = st.sidebar.checkbox("Bật tự động làm mới (3s)", value=True)
limit_cards = st.sidebar.slider("Số lượng thẻ hiển thị tối đa", min_value=4, max_value=100, value=20, step=4)
min_confidence = st.sidebar.slider("Ngưỡng tin cậy OCR (%)", min_value=0, max_value=100, value=0, step=5)

st.title("Bảng Điều Khiển Phương Tiện Lấn Làn")
st.markdown("Giám sát các phương tiện lấn làn theo chiều thời gian thực.")

def load_data(limit=500):
    try:
        return get_latest_violations(limit=limit)
    except Exception as e:
        st.error(f"Lỗi truy vấn cơ sở dữ liệu: {e}")
        return []

# Tải dữ liệu với limit lớn, sau đó lọc theo Sidebar
all_violations = load_data(limit=1000)

# Lọc theo độ tin cậy
filtered_violations = [v for v in all_violations if v['confidence'] * 100 >= min_confidence]

# Cắt theo giới hạn hiển thị
display_violations = filtered_violations[:limit_cards]

# --- KPI METRICS ---
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Tổng vi phạm (gần đây)", len(all_violations))
with col2:
    st.metric("Đạt chuẩn tin cậy OCR", len(filtered_violations))
with col3:
    st.metric("Cập nhật lần cuối", datetime.now().strftime("%H:%M:%S"))

st.markdown("---")

# --- MAIN CONTENT ---
if not display_violations:
    st.info("Hiện tại chưa có phương tiện nào vi phạm thỏa mãn điều kiện lọc.")
else:
    # Hiển thị dải Card trên 4 Cột
    cols = st.columns(4)
    for idx, v in enumerate(display_violations):
        with cols[idx % 4]:
            with st.container(border=True):
                st.markdown(f"### {v['plate_text']}")
                st.caption(f"**Lúc:** {v['timestamp']}")
                st.caption(f"**Độ tin cậy OCR:** {v['confidence']*100:.1f}%")
                
                img_path = Path(v['image_path'])
                if img_path.exists():
                    st.image(str(img_path), use_container_width=True)
                else:
                    st.error("Không tìm thấy tệp đính kèm")

# --- AUTO REFRESH LOGIC ---
if auto_refresh:
    time.sleep(3)
    st.rerun()
