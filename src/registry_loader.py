"""
registry_loader.py
Download dataset từ MinIO registry + PostgreSQL → build local data directory.
Thay thế DVC pull trong trainer pipeline.
"""

import json
import os
import random
import shutil
from pathlib import Path
from typing import Optional

import boto3
import numpy as np
import psycopg2
from botocore.client import Config
from psycopg2.extras import RealDictCursor


# ============================================================
# CONFIG (từ env — giống labeling backend)
# ============================================================

MINIO_URL       = os.getenv("MINIO_URL",        "http://localhost:9000")
MINIO_ACCESS    = os.getenv("MINIO_ACCESS_KEY",  "minioadmin")
MINIO_SECRET    = os.getenv("MINIO_SECRET_KEY",  "minioadmin")
MINIO_BUCKET    = os.getenv("MINIO_BUCKET",      "raw-images")
REGISTRY_BUCKET = os.getenv("REGISTRY_BUCKET",   "mlops-registry")
DB_URL          = os.getenv("DATABASE_URL",
                             "postgresql://postgres:postgres@localhost:5432/labeling")

EMB_MAX_SAMPLES = 250_000   # tối đa ảnh để extract embedding


# ============================================================
# HELPERS
# ============================================================

def _s3():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_URL,
        aws_access_key_id=MINIO_ACCESS,
        aws_secret_access_key=MINIO_SECRET,
        config=Config(signature_version="s3v4"),
    )


def _db():
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)


def _read_registry_json(s3, key: str) -> dict:
    body = s3.get_object(Bucket=REGISTRY_BUCKET, Key=key)["Body"].read()
    return json.loads(body)


def _safe_fname(image_id: str, original: str) -> str:
    """UUID + ext gốc để đảm bảo unique filename."""
    ext = Path(original).suffix.lower() or ".jpg"
    return f"{image_id}{ext}"


def _download_img(s3, minio_path: str, dest: str):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    s3.download_file(MINIO_BUCKET, minio_path, dest)


# ============================================================
# MAIN ENTRY: download_dataset
# ============================================================

def download_dataset(
    dataset_version: str,
    local_dir: str,
    model_type: str,
) -> tuple[dict, list[str]]:
    """
    Đọc dataset_vX.json + test_vX.json từ MinIO registry.
    Query PostgreSQL lấy minio_path + annotations.
    Download ảnh → local_dir, viết labels (YOLO) hoặc organize folder (cls).

    Returns:
        splits     : {"train": [paths], "val": [paths], "test": [paths]}
        class_names: list tên class theo thứ tự index (dùng cho YOLO nc/names)
    """
    s3   = _s3()
    conn = _db()
    cur  = conn.cursor()

    print(f"\n{'='*60}")
    print(f"REGISTRY LOADER — dataset {dataset_version}")
    print(f"{'='*60}")

    # ── 1. Load dataset + test JSON ───────────────────────────
    dataset  = _read_registry_json(s3, f"datasets/dataset_{dataset_version}.json")
    train_ids = dataset["train_ids"]
    val_ids   = dataset["val_ids"]
    print(f"  train: {len(train_ids):,}  val: {len(val_ids):,}")

    try:
        test_doc = _read_registry_json(s3, f"benchmarks/test_{dataset_version}.json")
        test_ids = test_doc["image_ids"]
        print(f"  test : {len(test_ids):,}")
    except Exception:
        test_ids = []
        print("  test : 0  (benchmark not found)")

    all_ids = list(set(train_ids + val_ids + test_ids))

    if not all_ids:
        cur.close(); conn.close()
        print("  WARNING: dataset rỗng — không có image_id nào.")
        return {"train": [], "val": [], "test": []}, []

    # ── 2. Query image metadata ───────────────────────────────
    ph = ",".join(["%s"] * len(all_ids))
    cur.execute(
        f"SELECT image_id::text, minio_path, filename FROM images "
        f"WHERE image_id::text IN ({ph})",
        all_ids,
    )
    img_meta = {r["image_id"]: dict(r) for r in cur.fetchall()}

    # ── 3. Query classes (class_id → name, sorted by class_id) ─
    cur.execute("SELECT class_id, name FROM classes ORDER BY class_id")
    class_rows   = cur.fetchall()
    class_names  = [r["name"] for r in class_rows]
    # YOLO index: sort by class_id ascending → idx 0,1,2,...
    class_to_idx = {r["name"]: i for i, r in enumerate(class_rows)}

    # ── 4. Query annotations ──────────────────────────────────
    cur.execute(
        f"""SELECT a.image_id::text, c.name AS class_name, a.bbox
            FROM annotations a
            JOIN classes c ON a.class_id = c.class_id
            WHERE a.image_id::text IN ({ph})""",
        all_ids,
    )
    ann_map: dict[str, list] = {}
    for r in cur.fetchall():
        ann_map.setdefault(r["image_id"], []).append(dict(r))

    cur.close()
    conn.close()

    # ── 5. Xóa local_dir cũ (fresh download) ─────────────────
    if os.path.exists(local_dir):
        shutil.rmtree(local_dir)
    os.makedirs(local_dir, exist_ok=True)

    # ── 6. Download theo format ───────────────────────────────
    if model_type == "classification":
        splits = _download_cls(
            s3, local_dir,
            train_ids, val_ids, test_ids,
            img_meta, ann_map,
        )
    else:
        splits = _download_dct(
            s3, local_dir,
            train_ids, val_ids, test_ids,
            img_meta, ann_map, class_to_idx,
        )

    print(f"\n  Downloaded → {local_dir}")
    print(f"  train: {len(splits['train']):,}  "
          f"val: {len(splits['val']):,}  "
          f"test: {len(splits['test']):,}")
    return splits, class_names


# ============================================================
# CLASSIFICATION — ImageFolder
# ============================================================

def _download_cls(s3, local_dir, train_ids, val_ids, test_ids,
                  img_meta, ann_map) -> dict:
    """
    local_dir/
      train/<class_name>/<uuid>.jpg
      val/<class_name>/<uuid>.jpg
      test/<class_name>/<uuid>.jpg
    """
    splits = {"train": [], "val": [], "test": []}

    for split, ids in [("train", train_ids), ("val", val_ids), ("test", test_ids)]:
        for iid in ids:
            meta = img_meta.get(iid)
            anns = ann_map.get(iid, [])
            if not meta or not anns:
                continue

            class_name = anns[0]["class_name"]   # cls: 1 label per image
            fname      = _safe_fname(iid, meta["filename"])
            dest       = os.path.join(local_dir, split, class_name, fname)

            _download_img(s3, meta["minio_path"], dest)
            splits[split].append(dest)

    return splits


# ============================================================
# DETECTION — YOLO format
# ============================================================

def _download_dct(s3, local_dir, train_ids, val_ids, test_ids,
                  img_meta, ann_map, class_to_idx) -> dict:
    """
    local_dir/
      images/train/<uuid>.jpg  +  labels/train/<uuid>.txt
      images/val/<uuid>.jpg    +  labels/val/<uuid>.txt
      images/test/<uuid>.jpg   +  labels/test/<uuid>.txt

    YOLO label format: class_idx cx cy w h  (normalized 0-1)
    bbox trong PostgreSQL: {x, y, w, h, image_w, image_h} — pixel coords
    """
    splits = {"train": [], "val": [], "test": []}

    for split, ids in [("train", train_ids), ("val", val_ids), ("test", test_ids)]:
        for iid in ids:
            meta = img_meta.get(iid)
            anns = ann_map.get(iid, [])
            if not meta or not anns:
                continue

            fname    = _safe_fname(iid, meta["filename"])
            img_dest = os.path.join(local_dir, "images", split, fname)
            lbl_dest = os.path.join(local_dir, "labels", split,
                                    Path(fname).stem + ".txt")

            _download_img(s3, meta["minio_path"], img_dest)

            # Viết YOLO label
            os.makedirs(os.path.dirname(lbl_dest), exist_ok=True)
            lines = []
            for ann in anns:
                bbox = ann.get("bbox")
                if not bbox:
                    continue
                iw = float(bbox.get("image_w") or 1)
                ih = float(bbox.get("image_h") or 1)
                if iw <= 0 or ih <= 0:
                    continue

                idx = class_to_idx.get(ann["class_name"], 0)
                cx  = (bbox["x"] + bbox["w"] / 2) / iw
                cy  = (bbox["y"] + bbox["h"] / 2) / ih
                nw  = bbox["w"] / iw
                nh  = bbox["h"] / ih

                # Clamp to [0, 1]
                cx, cy, nw, nh = (
                    max(0.0, min(1.0, cx)),
                    max(0.0, min(1.0, cy)),
                    max(0.0, min(1.0, nw)),
                    max(0.0, min(1.0, nh)),
                )
                lines.append(f"{idx} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")

            with open(lbl_dest, "w") as f:
                f.write("\n".join(lines))

            splits[split].append(img_dest)

    return splits


# ============================================================
# EMBEDDINGS — extract + upload to registry
# ============================================================

def save_embeddings_to_registry(
    train_paths: list[str],
    val_paths:   list[str],
    cfg:         dict,
):
    """
    Extract embedding toàn bộ labeled data (train + val) → upload lên MinIO
    registry/current-train-emb/reference_embeddings.npy.

    Gộp train+val vì đây là data model đã học từ — distribution của chúng
    đại diện cho những gì model expect thấy trong production. Test set
    không gộp vì được giữ độc lập để benchmark.

    Sample tối đa EMB_MAX_SAMPLES ảnh nếu dataset lớn.
    """
    from embedding_utils import extract_embeddings  # import lazy (tránh circular)

    model_name = cfg.get("embedding", {}).get("model", "MobileNetV3Small")
    img_size   = cfg["data"]["img_size"]
    batch_size = cfg["data"]["batch_size"]

    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        device = "cpu"

    print(f"\n{'='*60}")
    print("SAVING EMBEDDINGS TO REGISTRY")
    print(f"{'='*60}")
    print(f"  Backbone : {model_name}")

    # Gộp train + val thành một reference pool rồi sample
    all_paths  = train_paths + val_paths
    sample     = (random.sample(all_paths, EMB_MAX_SAMPLES)
                  if len(all_paths) > EMB_MAX_SAMPLES else all_paths)

    print(f"  reference: {len(sample):,} / {len(all_paths):,}  (train={len(train_paths):,} + val={len(val_paths):,})")

    ref_emb = extract_embeddings(sample, model_name, img_size, batch_size, device)

    # Lưu tạm + upload
    os.makedirs("/tmp/embeddings", exist_ok=True)
    np.save("/tmp/embeddings/reference_embeddings.npy", ref_emb)

    # Upload lên MinIO registry — overwrite (luôn là embedding của run hiện tại)
    s3 = _s3()
    s3.upload_file(
        "/tmp/embeddings/reference_embeddings.npy",
        REGISTRY_BUCKET,
        "current-train-emb/reference_embeddings.npy",
    )
    print("  Uploaded : current-train-emb/reference_embeddings.npy")
