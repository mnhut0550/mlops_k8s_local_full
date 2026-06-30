"""
train.py
Chạy: python train.py --config params.yaml
"""

import argparse
import os
import traceback

import torch
import mlflow
import mlflow.pytorch
from mlflow import MlflowClient

import optuna
from optuna.samplers import TPESampler
from optuna.pruners import MedianPruner, HyperbandPruner

from config.load import load_config
from registry_loader import download_dataset, save_embeddings_to_registry
from cls_trainer import cls_objective, evaluate_cls_test
from dct_trainer import dct_objective, evaluate_dct_test


# ============================================================
# ARGPARSE
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(description="MLOps Training Pipeline")
    parser.add_argument("--config", type=str, required=True,
                        help="Path to params config yaml (e.g. params.yaml)")
    parser.add_argument("--dataset-version", type=str, default=None,
                        help="Registry dataset version (e.g. v3). "
                             "Overrides DATASET_VERSION env var.")
    return parser.parse_args()


# ============================================================
# CONFIG
# ============================================================

def load_and_validate_config(config_path: str):
    if not os.path.isfile(config_path):
        raise FileNotFoundError(f"Config not found: {config_path}")

    cfg = load_config(config_path)

    model_type = cfg.get("pipeline", {}).get("model_type", "").lower()
    if model_type not in ("classification", "detection"):
        raise ValueError(
            f"pipeline.model_type must be 'classification' or 'detection', got: '{model_type}'"
        )

    print("\n" + "=" * 60)
    print("CONFIG LOADED")
    print("=" * 60)
    print(f"  Config file : {config_path}")
    print(f"  model_type  : {model_type}")
    print(f"  task_name   : {cfg['pipeline']['task_name']}")
    print(f"  data_dir    : {cfg['data']['data_dir']}")

    return cfg, model_type


# ============================================================
# DATASET
# ============================================================

LOCAL_DATA_DIR = "/tmp/labeling-data"

def load_dataset_from_registry(cfg: dict, model_type: str,
                                dataset_version: str) -> tuple[dict, list[str]]:
    splits, class_names = download_dataset(
        dataset_version=dataset_version,
        local_dir=LOCAL_DATA_DIR,
        model_type=model_type,
    )

    if not splits["train"]:
        raise RuntimeError(
            f"Train set rỗng sau khi download dataset {dataset_version}. "
            "Kiểm tra PostgreSQL annotations và MinIO."
        )

    cfg["data"]["data_dir"] = LOCAL_DATA_DIR
    return splits, class_names


# ============================================================
# TEST EVALUATION
# ============================================================

def _evaluate_test(cfg: dict, model_type: str, splits: dict, class_names: list[str],
                   best_run_id: str, best_params: dict, device: str):
    print("\n" + "=" * 60)
    print("TEST SET EVALUATION")
    print("=" * 60)

    if not splits.get("test"):
        print("  WARNING: test set trống, bỏ qua.")
        return

    if model_type == "classification":
        evaluate_cls_test(cfg, splits, best_run_id, device)
    else:
        evaluate_dct_test(cfg, splits, class_names, best_run_id, best_params)


# ============================================================
# OPTUNA + MLFLOW
# ============================================================

def run_optuna_mlflow(cfg: dict, model_type: str, splits: dict,
                      class_names: list[str], dataset_version: str):
    optuna_cfg  = cfg["optuna_tuning"]
    mlflow_cfg  = cfg["mlflow"]
    task_name   = cfg["pipeline"]["task_name"]
    n_trials    = optuna_cfg["n_trials"]
    storage_db  = optuna_cfg.get("storage_db", "sqlite:///optuna_mlops.db")
    pruner_name = optuna_cfg.get("pruner", "median")
    device      = "cuda" if torch.cuda.is_available() else "cpu"

    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    mlflow.set_experiment(f"{mlflow_cfg['experiment_base_name']}/{task_name}")

    pruner = HyperbandPruner() if pruner_name == "hyperband" else MedianPruner()

    study = optuna.create_study(
        study_name=task_name,
        direction="maximize",
        sampler=TPESampler(),
        pruner=pruner,
        storage=storage_db,
        load_if_exists=True,
    )

    with mlflow.start_run(run_name=f"{task_name}_study") as parent_run:
        parent_run_id = parent_run.info.run_id

        mlflow.log_params({
            "model_type":      model_type,
            "task_name":       task_name,
            "dataset_version": dataset_version,
            "train_size":      len(splits["train"]),
            "val_size":        len(splits["val"]),
            "test_size":       len(splits.get("test", [])),
            "num_classes":     len(class_names),
            "n_trials":        n_trials,
            "pruner":          pruner_name,
        })

        if model_type == "classification":
            objective = lambda trial: cls_objective(
                trial, cfg, splits, parent_run_id, device
            )
        else:
            objective = lambda trial: dct_objective(
                trial, cfg, splits, class_names, parent_run_id, device
            )

        study.optimize(objective, n_trials=n_trials)

        best = study.best_trial
        mlflow.log_params({f"best_{k}": v for k, v in best.params.items()})
        mlflow.log_metric(
            "best_val_f1" if model_type == "classification" else "best_mAP50",
            best.value,
        )

        print("\n" + "=" * 60)
        print("OPTUNA COMPLETE")
        print("=" * 60)
        print(f"  Best trial  : #{best.number}")
        print(f"  Best value  : {best.value:.4f}")
        print(f"  Best params : {best.params}")

        client     = MlflowClient()
        model_name = task_name

        try:
            client.create_registered_model(model_name)
        except Exception:
            pass

        runs = mlflow.search_runs(
            experiment_names=[f"{mlflow_cfg['experiment_base_name']}/{task_name}"],
            filter_string=f"tags.mlflow.parentRunId = '{parent_run_id}' "
                          f"AND params.trial = '{best.number}'",
        )

        if runs.empty:
            print("\n  WARNING: Không tìm được best run để register model.")
            return

        best_run_id = runs.iloc[0]["run_id"]
        model_uri   = f"runs:/{best_run_id}/model"

        version = client.create_model_version(
            name=model_name,
            source=model_uri,
            run_id=best_run_id,
            tags={"task": task_name, "trial": str(best.number)},
        )

        client.set_registered_model_alias(
            name=model_name,
            alias="champion",
            version=version.version,
        )

        print(f"\n  Registered  : {model_name} v{version.version} → alias 'champion'")

        _evaluate_test(
            cfg=cfg,
            model_type=model_type,
            splits=splits,
            class_names=class_names,
            best_run_id=best_run_id,
            best_params=best.params,
            device=device,
        )


# ============================================================
# MAIN
# ============================================================

def main():
    args = parse_args()

    cfg, model_type = load_and_validate_config(args.config)

    dataset_version = args.dataset_version or os.getenv("DATASET_VERSION")
    if not dataset_version:
        raise RuntimeError(
            "Cần chỉ định dataset version. "
            "Dùng --dataset-version v3 hoặc env var DATASET_VERSION=v3"
        )

    splits, class_names = load_dataset_from_registry(cfg, model_type, dataset_version)

    save_embeddings_to_registry(splits["train"], splits["val"], cfg)

    run_optuna_mlflow(cfg, model_type, splits, class_names, dataset_version)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
