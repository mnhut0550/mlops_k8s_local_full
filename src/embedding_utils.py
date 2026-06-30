"""
embedding_utils.py
=================
"""

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from PIL import Image
from .models.models import PRETRAINED_BACKBONES as EMBEDDING_BACKBONES




SUPPORTED_MODELS = list(EMBEDDING_BACKBONES.keys())


# ============================================================
# INTERNAL DATASET
# ============================================================

class _PathDataset(Dataset):
    def __init__(self, paths: list, transform):
        self.paths = paths
        self.transform = transform

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        img = Image.open(self.paths[idx]).convert("RGB")
        return self.transform(img)


# ============================================================
# BUILD BACKBONE
# ============================================================

def build_embedding_backbone(model_name: str, device: str) -> torch.nn.Module:
    """
    Khởi tạo backbone pretrained, bỏ head, trả về feature extractor.
    """
    if model_name not in EMBEDDING_BACKBONES:
        raise ValueError(
            f"embedding_model '{model_name}' không hợp lệ.\n"
            f"Chọn một trong: {SUPPORTED_MODELS}"
        )

    constructor, weights, fc_attr = EMBEDDING_BACKBONES[model_name]
    backbone = constructor(weights=weights)

    # Bỏ classification head → chỉ giữ feature extractor
    setattr(backbone, fc_attr, torch.nn.Identity())

    backbone.eval().to(device)
    return backbone


# ============================================================
# EXTRACT EMBEDDINGS
# ============================================================

def extract_embeddings(paths: list, model_name: str, img_size: int,
                       batch_size: int, device: str) -> torch.Tensor:
    """
    Extract L2-normalized embedding từ list ảnh.

    Returns:
        Tensor shape (N, D), L2-normalized, trên CPU.
    """
    backbone  = build_embedding_backbone(model_name, device)
    transform = transforms.Compose([
        transforms.Resize((img_size, img_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                             std=[0.229, 0.224, 0.225]),
    ])

    dataset    = _PathDataset(paths, transform)
    dataloader = DataLoader(dataset, batch_size=batch_size,
                            shuffle=False, num_workers=0)

    all_embs = []
    with torch.no_grad():
        for batch in dataloader:
            batch = batch.to(device)
            emb   = backbone(batch)
            emb   = F.normalize(emb, dim=1)
            all_embs.append(emb.cpu())

    return torch.cat(all_embs, dim=0)   # (N, D)
