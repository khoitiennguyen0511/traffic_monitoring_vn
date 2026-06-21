import os
import torch
import torch.nn as nn
import timm
from PIL import Image
from torchvision import transforms
from ultralytics import YOLO

# Cấu hình OCR params theo notebook
PLATE_CHARS = "0123456789ABCDEFGHIKLMNPRSTUVXYZ"
BLANK_CHAR = "-"
CHARS = BLANK_CHAR + PLATE_CHARS
VOCAB_SIZE = len(CHARS)
CHAR_TO_IDX = {char: idx for idx, char in enumerate(CHARS)}
IDX_TO_CHAR = {idx: char for char, idx in CHAR_TO_IDX.items()}

class CRNN(nn.Module):
    def __init__(self, vocab_size, hidden_size=256, n_layers=3, dropout=0.2):
        super(CRNN, self).__init__()
        # Backbone ResNet34
        backbone = timm.create_model("resnet34", in_chans=1, pretrained=False)
        modules = list(backbone.children())[:-2]
        modules.append(nn.AdaptiveAvgPool2d((1, None)))
        self.backbone = nn.Sequential(*modules)

        self.mapSeq = nn.Sequential(
            nn.Linear(512, 512),
            nn.ReLU(),
            nn.Dropout(dropout)
        )
        self.gru = nn.GRU(
            512,
            hidden_size,
            n_layers,
            bidirectional=True,
            batch_first=True,
            dropout=dropout if n_layers > 1 else 0,
        )
        self.layer_norm = nn.LayerNorm(hidden_size * 2)
        self.out = nn.Sequential(
            nn.Linear(hidden_size * 2, vocab_size),
            nn.LogSoftmax(dim=2)
        )

    def forward(self, x):
        x = self.backbone(x)
        x = x.permute(0, 3, 1, 2)
        x = x.view(x.size(0), x.size(1), -1)  # Flatten the feature map
        x = self.mapSeq(x)
        x, _ = self.gru(x)
        x = self.layer_norm(x)
        x = self.out(x)
        x = x.permute(1, 0, 2)  # Based on CTC
        return x

def decode(encoded_sequences, idx_to_char, blank_idx=0):
    decoded_sequences = []
    for seq in encoded_sequences:
        decoded_label = []
        prev_token = None
        for token in seq:
            token_val = token.item()
            if token_val != blank_idx and token_val != prev_token:
                decoded_label.append(idx_to_char[token_val])
            prev_token = token_val
        decoded_sequences.append("".join(decoded_label))
    return decoded_sequences

class OCREngine:
    def __init__(self, det_model_path: str, rec_model_path: str):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[OCR] Khởi tạo mô hình trên thiết bị: {self.device}")
        
        # 1. Load YOLO (Phát hiện khung biển số)
        self.detector = YOLO(det_model_path)
        
        # 2. Load CRNN (Đọc chữ)
        self.recognizer = CRNN(
            vocab_size=VOCAB_SIZE,
            hidden_size=256,
            n_layers=3,
            dropout=0.2,
        ).to(self.device)
        self.recognizer.load_state_dict(torch.load(rec_model_path, map_location=self.device, weights_only=True))
        self.recognizer.eval()
        
        # 3. Transform
        self.rec_transforms = transforms.Compose([
            transforms.Resize((100, 420)),
            transforms.Grayscale(num_output_channels=1),
            transforms.ToTensor(),
            transforms.Normalize((0.5,), (0.5,)),
        ])

    def process_image(self, pil_image: Image.Image):
        """
        Nhận vào ảnh PIL. Trả về String chứa đoạn text trên biển, độ tin cậy và toạ độ.
        """
        # YOLO inference để khoanh vùng biển số trên xe
        results = self.detector(pil_image, verbose=False)[0]
        boxes = results.boxes.xyxy.cpu().numpy()
        confs = results.boxes.conf.cpu().numpy()
        
        if len(boxes) == 0:
            return None, None, None # Không tìm thấy biển số

        # Lấy biển có confidence cao nhất
        best_idx = confs.argmax()
        x1, y1, x2, y2 = map(int, boxes[best_idx])
        conf_det = confs[best_idx]
        
        # Cắt riêng tấm biển số
        cropped_image = pil_image.crop((x1, y1, x2, y2))
        
        # Tiền xử lý và đưa vào CRNN
        img_tensor = self.rec_transforms(cropped_image).unsqueeze(0).to(self.device)
        with torch.no_grad():
            outputs = self.recognizer(img_tensor)
            _, preds = outputs.max(2)
            preds = preds.transpose(1, 0).contiguous().view(-1)
            
        transcribed_text = decode([preds], IDX_TO_CHAR)[0]
        
        return transcribed_text, float(conf_det), (x1, y1, x2, y2)
