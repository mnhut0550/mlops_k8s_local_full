from .pretrained import PRETRAINED_BACKBONES
from . import custom as CUSTOMIZE_MODEL
from .utils import _replace_head

import torch.nn as nn
import inspect




# ── Public API ────────────────────────────────────────────────────────────────
def build_model(name: str, num_classes: int, freeze_backbone: bool) -> nn.Module:
    """
    Factory function — train.py chỉ cần gọi hàm này.

    Args:
        name            : tên model khớp với params.yaml
        num_classes     : số class cần classify
        freeze_backbone : True = chỉ train layer cuối (nhanh hơn)

    Returns:
        nn.Module sẵn sàng train
    """
    custom_model_list = {
            name: cls
            for name, cls in inspect.getmembers(CUSTOMIZE_MODEL, inspect.isclass)
        }
    
    model = custom_model_list.get(name)
    
    if model is not None:
        return model(num_classes= num_classes)

    # Pretrained backbones
    if name not in PRETRAINED_BACKBONES:
        available = list(custom_model_list.keys()) + list(PRETRAINED_BACKBONES.keys())

        raise ValueError(
            f"Unknown model: '{name}'.\n"
            f"Available models: {available}\n"
            f"To register a custom model, add it to PRETRAINED_BACKBONES in src/models/custom.py"
        )

    constructor, weights, fc_attr = PRETRAINED_BACKBONES[name]

    # Khởi tạo với pretrained weights
    model = constructor(weights=weights)

    # Freeze toàn bộ backbone nếu cần
    if freeze_backbone:
        for param in model.parameters():
            param.requires_grad = False

    # Thay layer cuối
    _replace_head(model, fc_attr, num_classes)

    # Layer cuối luôn được train dù freeze_backbone=True
    head = getattr(model, fc_attr)
    for param in head.parameters():
        param.requires_grad = True

    total_params    = sum(p.numel() for p in model.parameters())
    trainable_params= sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  {name}: {trainable_params:,} trainable / {total_params:,} total params")

    return model