import logging
import sys

def get_logger(name: str) -> logging.Logger:
    """
    Khởi tạo và cấu hình logger chuẩn cho các module.
    """
    logger = logging.getLogger(name)
    
    # Tránh việc add handler nhiều lần nếu gọi get_logger lại cho cùng 1 name
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Định dạng dòng log
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        
        # In log ra terminal
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        
    return logger
