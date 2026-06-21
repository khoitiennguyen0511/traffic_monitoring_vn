from fastapi import APIRouter, UploadFile, File, Request
from fastapi.concurrency import run_in_threadpool
from PIL import Image
import io
import os
import uuid
import datetime
from pathlib import Path
from .schemas import ViolationResponse
from server.core.database import init_db, insert_violation

violation_router = APIRouter()

DATA_DIR = Path(os.path.dirname(__file__)).parent / "data"
VIOLATIONS_DIR = DATA_DIR / "violations"

# Khởi tạo thư mục và database SQLite WAL
VIOLATIONS_DIR.mkdir(parents=True, exist_ok=True)
init_db()

@violation_router.post("/upload-violation", response_model=ViolationResponse)
async def upload_violation(request: Request, file: UploadFile = File(...)):
    """
    Nhận vào 1 file ảnh chụp (có thể là full xe hoặc crop biển).
    Ảnh được xử lý trực tiếp trên RAM, Nếu nhận diện ra sẽ LƯU XUỐNG SQLite để Streamlit đọc được.
    """
    if not file.content_type.startswith("image/"):
        return ViolationResponse(status="error", message="Định dạng file không phải hình ảnh.")
        
    try:
        # 1. Đọc nội dung ảnh vào RAM
        img_bytes = await file.read()
        pil_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        
        # 2. Truy xuất OCREngine lưu sẵn trên biến state của ứng dụng
        ocr_engine = request.app.state.ocr_engine
        
        # 3. Yêu cầu bóc tách (chạy trên thread pool hệ thống để tránh chặn Event Loop)
        text, conf, box = await run_in_threadpool(ocr_engine.process_image, pil_image)
        
        # 4. Phản hồi
        if text:
            print(f"[OCR] Phân tích thành công: {text} - Độ tin cậy: {conf:.2f}")
            
            # Sinh mã lưu ảnh nháp
            v_id = str(uuid.uuid4())[:8]
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_path = VIOLATIONS_DIR / f"{v_id}.jpg"
            
            # Lưu ảnh
            pil_image.save(save_path, "JPEG")
            
            # Lưu siêu dữ liệu vào SQLite WAL bất đồng bộ
            await run_in_threadpool(insert_violation, v_id, timestamp, text, round(conf, 2), str(save_path))
            
            return ViolationResponse(status="success", plate_text=text, confidence=conf)
        else:
            print("[OCR] Không kiếm thấy biển số")
            return ViolationResponse(status="not_found", message="Không phát hiện biển số hợp lệ")
            
    except Exception as e:
        print(f"[OCR ERROR] {e}")
        return ViolationResponse(status="error", message=str(e))
