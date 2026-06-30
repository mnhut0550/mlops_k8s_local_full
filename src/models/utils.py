import torch.nn as nn


def _replace_head(model: nn.Module, fc_attr: str, num_classes: int):
    """Thay layer cuối của bất kỳ backbone nào để khớp num_classes."""
    head = getattr(model, fc_attr)

    # fc thường là Linear, classifier có thể là Sequential
    if isinstance(head, nn.Linear):
        in_features = head.in_features
        setattr(model, fc_attr, nn.Linear(in_features, num_classes))

    elif isinstance(head, nn.Sequential):
        
        # Lấy in_features của Linear layer cuối cùng trong Sequential
        last_linear = [m for m in head.modules() if isinstance(m, nn.Linear)][-1]
        in_features = last_linear.in_features

        # Giữ nguyên Sequential, chỉ thay Linear cuối
        children = list(head.children())
        children[-1] = nn.Linear(in_features, num_classes)
        setattr(model, fc_attr, nn.Sequential(*children))