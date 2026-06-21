import sys
from pathlib import Path

# Bổ sung root vào đường dẫn để import được module server và shared
base_dir = Path(__file__).parent.parent
sys.path.append(str(base_dir))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yaml

from server.api.routers import violation_router
from server.core.ocr_engine import OCREngine

def load_settings(path="shared/configs/settings.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

app = FastAPI(title="Traffic Monitoring Central Server", version="1.0.0")

# 1. Cấu hình CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Khởi tạo Mô hình OCR vào bộ nhớ Server BootUP
settings_path = base_dir / "shared/configs/settings.yaml"
settings = load_settings(settings_path)

det_model_path = str(base_dir / "shared/models/license_best.pt")
rec_model_path = str(base_dir / "shared/models/ocr_crnn.pt")

print("Khởi động mô hình License Plate OCR...")
app.state.ocr_engine = OCREngine(det_model_path, rec_model_path)

# 3. Nhúng Routers
app.include_router(violation_router, prefix=settings['server']['api_prefix'])

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Máy chủ Giám sát Giao thông đã hoạt động"}

if __name__ == "__main__":
    import uvicorn
    # Sử dụng reload=False nếu load model AI khổng lồ để tránh tràn RAM
    uvicorn.run("main:app", host=settings['server']['host'], port=settings['server']['port'], reload=False)
