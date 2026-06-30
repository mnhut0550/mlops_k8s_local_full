"""
cls_trainer.py
Classification training helpers: dataset, dataloader, optimizer, Optuna objective.
"""

import os

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from torchvision import datasets, transforms
from sklearn.metrics import f1_score

import mlflow
import mlflow.pytorch
import optuna

from models.models import build_model


# ============================================================
# TRANSFORM + DATASET
# ============================================================

def build_transform(img_size: int) -> transforms.Compose:
    return transforms.Compose([
        transforms.Grayscale(num_output_channels=3),
        transforms.Resize((img_size, img_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
    ])


class RawImageDataset(Dataset):
    """Custom dataset từ list paths, lấy label từ class folder (parent dirname)."""
    def __init__(self, paths: list, classes: list, transform):
        self.transform = transform
        cls2idx        = {c: i for i, c in enumerate(classes)}
        self.samples   = [
            (p, cls2idx[os.path.basename(os.path.dirname(p))])
            for p in paths
            if os.path.basename(os.path.dirname(p)) in cls2idx
        ]
        self.classes = classes

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        img = datasets.folder.default_loader(path)
        return self.transform(img), label


def build_cls_loaders(splits: dict, batch_size: int, img_size: int):
    """DataLoader cho classification từ ảnh thô."""
    transform = build_transform(img_size)

    classes = sorted(set(
        os.path.basename(os.path.dirname(p)) for p in splits["train"]
    ))

    train_ds = RawImageDataset(splits["train"], classes, transform)
    val_ds   = RawImageDataset(splits["val"],   classes, transform)

    return (
        DataLoader(train_ds, batch_size=batch_size, shuffle=True,  num_workers=0),
        DataLoader(val_ds,   batch_size=batch_size, shuffle=False, num_workers=0),
        classes,
    )


# ============================================================
# OPTIMIZER
# ============================================================

def build_optimizer(name: str, params, lr: float):
    if name == "Adam":
        return optim.Adam(params, lr=lr)
    elif name == "SGD":
        return optim.SGD(params, lr=lr, momentum=0.9)
    elif name == "RMSprop":
        return optim.RMSprop(params, lr=lr)
    elif name == "AdamW":
        return optim.AdamW(params, lr=lr)
    raise ValueError(f"Unknown optimizer: {name}")


# ============================================================
# OPTUNA OBJECTIVE
# ============================================================

def cls_objective(trial, cfg: dict, splits: dict,
                  parent_run_id: str, device: str) -> float:
    """Optuna objective cho classification."""
    optuna_cfg   = cfg["optuna_tuning"]
    training_cfg = cfg["training"]
    max_epochs   = optuna_cfg["max_num_epochs"]
    batch_size   = cfg["data"]["batch_size"]
    img_size     = cfg["data"]["img_size"]

    model_name = trial.suggest_categorical("model",     cfg["models"])
    lr         = trial.suggest_float("lr", training_cfg["lr_min"],
                                           training_cfg["lr_max"], log=True)
    opt_name   = trial.suggest_categorical("optimizer", training_cfg["optimizer_choices"])

    with mlflow.start_run(run_name=f"trial_{trial.number}", nested=True):
        mlflow.log_params({
            "trial":     trial.number,
            "model":     model_name,
            "lr":        lr,
            "optimizer": opt_name,
        })

        train_loader, val_loader, classes = build_cls_loaders(splits, batch_size, img_size)
        num_classes = len(classes)
        model       = build_model(model_name, num_classes, freeze_backbone=False).to(device)

        criterion = nn.CrossEntropyLoss()
        optimizer = build_optimizer(
            opt_name,
            filter(lambda p: p.requires_grad, model.parameters()),
            lr,
        )

        best_f1    = 0.0
        best_state = None

        for epoch in range(1, max_epochs + 1):
            model.train()
            for x, y in train_loader:
                x, y = x.to(device), y.to(device)
                optimizer.zero_grad()
                loss = criterion(model(x), y)
                loss.backward()
                optimizer.step()

            model.eval()
            all_preds, all_labels = [], []
            val_loss = 0.0
            with torch.no_grad():
                for x, y in val_loader:
                    x, y = x.to(device), y.to(device)
                    out   = model(x)
                    val_loss += criterion(out, y).item() * x.size(0)
                    all_preds.extend(out.argmax(1).cpu().tolist())
                    all_labels.extend(y.cpu().tolist())

            val_loss /= len(val_loader.dataset)
            val_f1    = f1_score(all_labels, all_preds, average="macro", zero_division=0)
            val_acc   = sum(p == l for p, l in zip(all_preds, all_labels)) / len(all_labels)

            mlflow.log_metrics({
                "val_f1":   val_f1,
                "val_acc":  val_acc,
                "val_loss": val_loss,
            }, step=epoch)

            if val_f1 > best_f1:
                best_f1    = val_f1
                best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

            trial.report(val_f1, epoch)
            if trial.should_prune():
                raise optuna.TrialPruned()

        mlflow.log_metric("best_val_f1", best_f1)

        if best_state:
            model.load_state_dict(best_state)
            model.eval()
            mlflow.pytorch.log_model(model, artifact_path="model")

    return best_f1


# ============================================================
# TEST EVALUATION
# ============================================================

def evaluate_cls_test(cfg: dict, splits: dict, best_run_id: str, device: str):
    """Load best model từ MLflow, evaluate trên test set classification."""
    batch_size = cfg["data"]["batch_size"]
    img_size   = cfg["data"]["img_size"]

    model_uri = f"runs:/{best_run_id}/model"
    model     = mlflow.pytorch.load_model(model_uri).to(device)
    model.eval()

    classes     = sorted(set(os.path.basename(os.path.dirname(p)) for p in splits["train"]))
    test_ds     = RawImageDataset(splits["test"], classes, build_transform(img_size))
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False, num_workers=0)

    all_preds, all_labels = [], []
    with torch.no_grad():
        for x, y in test_loader:
            x = x.to(device)
            all_preds.extend(model(x).argmax(1).cpu().tolist())
            all_labels.extend(y.tolist())

    test_f1  = f1_score(all_labels, all_preds, average="macro", zero_division=0)
    test_acc = sum(p == l for p, l in zip(all_preds, all_labels)) / len(all_labels)

    mlflow.log_metrics({"test_f1": test_f1, "test_acc": test_acc})
    print(f"  test_f1  : {test_f1:.4f}")
    print(f"  test_acc : {test_acc:.4f}")
