from torchvision import models



# ── Pretrained backbone registry ─────────────────────────────────────────────
# Muốn thêm backbone mới → thêm 1 dòng ở đây
# Key = tên dùng trong params.yaml
# Value = (constructor, weights, fc_attr)
#   - constructor : hàm tạo model từ torchvision
#   - weights     : pretrained weights string
#   - fc_attr     : tên attribute của layer cuối cần thay
# Pretrained dùng chung cho model và embedding

PRETRAINED_BACKBONES = {
    "ResNet18": (
        models.resnet18,
        "IMAGENET1K_V1",
        "fc",
    ),
    "ResNet34": (
        models.resnet34,
        "IMAGENET1K_V1",
        "fc"
    ),
    "ResNet50": (
        models.resnet50,
        "IMAGENET1K_V1",
        "fc",
    ),
    "MobileNetV3Small": (
        models.mobilenet_v3_small,
        "IMAGENET1K_V1",
        "classifier",           # MobileNet dùng "classifier" thay vì "fc"
    ),
    "EfficientNetB0": (
        models.efficientnet_b0,
        "IMAGENET1K_V1",
        "classifier",
    ),

    "VGG16": (
        models.vgg16,
        "IMAGENET1K_V1",
        "classifier"
    ),
}