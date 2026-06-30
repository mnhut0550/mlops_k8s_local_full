"""
dct_trainer.py
Detection training helpers: YOLO data yaml, Optuna objective, test evaluation.
"""

import os

import torch
import mlflow
import optuna


# ============================================================
# YOLO DATA YAML
# ============================================================

def make_yolo_data_yaml(data_dir: str, splits: dict, class_names: list[str]) -> str:
    """Tạo data.yaml cho ultralytics. class_names lấy từ registry (thứ tự = index)."""
    import yaml as _yaml

    tmp_dir = os.path.join(data_dir, "_optuna_tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    train_txt = os.path.join(tmp_dir, "train.txt")
    val_txt   = os.path.join(tmp_dir, "val.txt")
    test_txt  = os.path.join(tmp_dir, "test.txt")

    with open(train_txt, "w") as f:
        f.write("\n".join(splits["train"]))
    with open(val_txt, "w") as f:
        f.write("\n".join(splits["val"]))
    with open(test_txt, "w") as f:
        f.write("\n".join(splits.get("test", [])))

    data = {
        "train": train_txt,
        "val":   val_txt,
        "test":  test_txt,
        "nc":    len(class_names),
        "names": class_names,
    }

    yaml_path = os.path.join(tmp_dir, "data.yaml")
    with open(yaml_path, "w") as f:
        _yaml.dump(data, f)

    return yaml_path


# ============================================================
# OPTUNA OBJECTIVE
# ============================================================

def dct_objective(trial, cfg: dict, splits: dict, class_names: list[str],
                  parent_run_id: str, device: str) -> float:
    """Optuna objective cho detection (ultralytics YOLO)."""
    try:
        from ultralytics import YOLO
    except ImportError:
        raise RuntimeError("ultralytics not installed. Run: pip install ultralytics")

    optuna_cfg   = cfg["optuna_tuning"]
    training_cfg = cfg["training"]
    max_epochs   = optuna_cfg["max_num_epochs"]
    data_dir     = cfg["data"]["data_dir"]
    img_size     = cfg["data"]["img_size"]

    model_name = trial.suggest_categorical("model", cfg["models"])
    lr         = trial.suggest_float("lr", training_cfg["lr_min"],
                                           training_cfg["lr_max"], log=True)
    opt_name   = trial.suggest_categorical(
        "optimizer",
        training_cfg.get("optimizer_choices", ["AdamW", "SGD", "Adam"])
    )

    try:
        from ultralytics.utils import SETTINGS
        SETTINGS.update({"mlflow": False})
    except Exception:
        pass

    data_yaml = make_yolo_data_yaml(data_dir, splits, class_names)

    with mlflow.start_run(run_name=f"trial_{trial.number}", nested=True):
        mlflow.log_params({
            "trial":     trial.number,
            "model":     model_name,
            "lr":        lr,
            "optimizer": opt_name,
        })

        best_map50  = [0.0]
        pruned_flag = [False]

        def on_val_end(trainer):
            epoch   = trainer.epoch + 1
            map50   = float(trainer.metrics.get("metrics/mAP50(B)", 0.0))
            map5095 = float(trainer.metrics.get("metrics/mAP50-95(B)", 0.0))
            prec    = float(trainer.metrics.get("metrics/precision(B)", 0.0))
            rec     = float(trainer.metrics.get("metrics/recall(B)", 0.0))

            mlflow.log_metrics({
                "mAP50":     map50,
                "mAP50_95":  map5095,
                "precision": prec,
                "recall":    rec,
            }, step=epoch)

            if map50 > best_map50[0]:
                best_map50[0] = map50

            trial.report(map50, epoch)
            if trial.should_prune():
                pruned_flag[0] = True
                trainer.stopper.possible_stop = True

        yolo = YOLO(f"{model_name.lower()}.pt")
        yolo.add_callback("on_val_end", on_val_end)

        yolo.train(
            data=data_yaml,
            epochs=max_epochs,
            imgsz=img_size,
            batch=cfg["data"]["batch_size"],
            lr0=lr,
            optimizer=opt_name,
            device=0 if torch.cuda.is_available() else "cpu",
            verbose=False,
        )

        if pruned_flag[0]:
            raise optuna.TrialPruned()

        mlflow.log_metric("best_mAP50", best_map50[0])

        try:
            best_weights = str(yolo.trainer.best)
            if os.path.isfile(best_weights):
                mlflow.log_artifact(best_weights, artifact_path="weights")
        except Exception as e:
            print(f"  WARNING: Could not log YOLO weights: {e}")

    return best_map50[0]


# ============================================================
# TEST EVALUATION
# ============================================================

def evaluate_dct_test(cfg: dict, splits: dict, class_names: list[str],
                      best_run_id: str, best_params: dict):
    """Load best YOLO weights từ MLflow, evaluate trên test set detection."""
    try:
        from ultralytics import YOLO
    except ImportError:
        print("  ultralytics not installed, skip test eval.")
        return

    model_name = best_params["model"]
    data_yaml  = make_yolo_data_yaml(cfg["data"]["data_dir"], splits, class_names)

    try:
        local_weights = mlflow.artifacts.download_artifacts(f"runs:/{best_run_id}/weights/best.pt")
        yolo = YOLO(local_weights)
    except Exception as e:
        print(f"  WARNING: Cannot load trained weights ({e}), dùng pretrained fallback.")
        yolo = YOLO(f"{model_name.lower()}.pt")

    results      = yolo.val(data=data_yaml, split="test", verbose=False)
    test_map50   = float(results.box.map50)
    test_map5095 = float(results.box.map)

    mlflow.log_metrics({"test_mAP50": test_map50, "test_mAP50_95": test_map5095})
    print(f"  test_mAP50    : {test_map50:.4f}")
    print(f"  test_mAP50_95 : {test_map5095:.4f}")
