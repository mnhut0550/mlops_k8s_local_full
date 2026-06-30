"""
Labeling Tool Backend
FastAPI + PostgreSQL + MinIO
"""

import base64
import json
import os
import random
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import requests as http_requests
import yaml

import boto3
from botocore.client import Config
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor


# ============================================================
# CONFIG
# ============================================================

DB_URL       = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/labeling")
MINIO_URL    = os.getenv("MINIO_URL", "http://localhost:9000")
MINIO_ACCESS = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET     = os.getenv("MINIO_BUCKET", "raw-images")
REGISTRY_BUCKET  = os.getenv("REGISTRY_BUCKET", "mlops-registry")
PRESIGN_TTL      = int(os.getenv("PRESIGN_TTL", "3600"))  # seconds
PARAMS_PATH      = os.getenv("PARAMS_PATH", "/config/params.yaml")

GITHUB_TOKEN  = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO   = os.getenv("GITHUB_REPO", "")   # format: owner/repo
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")


# ============================================================
# DB + MINIO HELPERS
# ============================================================

def get_db(retries: int = 10, delay: float = 2.0):
    import time
    for i in range(retries):
        try:
            return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
        except psycopg2.OperationalError as e:
            if i == retries - 1:
                raise
            print(f"[DB] Postgres chưa sẵn sàng ({i+1}/{retries}), thử lại sau {delay}s... ({e})")
            time.sleep(delay)


def get_minio():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_URL,
        aws_access_key_id=MINIO_ACCESS,
        aws_secret_access_key=MINIO_SECRET,
        config=Config(signature_version="s3v4"),
    )


def init_db():
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS images (
            image_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            minio_path TEXT NOT NULL,
            filename   TEXT NOT NULL,
            status     VARCHAR(20) DEFAULT 'UNLABELED',
            task_type  VARCHAR(20) DEFAULT 'detection',
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS classes (
            class_id   SERIAL PRIMARY KEY,
            name       VARCHAR(100) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS annotations (
            annotation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            image_id      UUID REFERENCES images(image_id) ON DELETE CASCADE,
            class_id      INT REFERENCES classes(class_id) ON DELETE SET NULL,
            bbox          JSONB,
            annotator     VARCHAR(100) DEFAULT 'anonymous',
            created_at    TIMESTAMP DEFAULT NOW()
        );
    """)
    conn.commit()
    cur.close()
    conn.close()


def migrate_db():
    """Schema migration: label VARCHAR → class_id FK + train_sessions table."""
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='annotations' AND column_name='class_id'
            ) THEN
                ALTER TABLE annotations
                    ADD COLUMN class_id INT REFERENCES classes(class_id) ON DELETE SET NULL;
            END IF;

            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='annotations' AND column_name='label'
            ) THEN
                ALTER TABLE annotations DROP COLUMN label;
            END IF;
        END$$;

        CREATE TABLE IF NOT EXISTS train_sessions (
            id            SERIAL PRIMARY KEY,
            snapshot_id   VARCHAR(20) NOT NULL,
            triggered_at  TIMESTAMP DEFAULT NOW(),
            triggered_by  VARCHAR(100) DEFAULT 'anonymous'
        );
    """)
    conn.commit()
    cur.close()
    conn.close()


def ensure_bucket():
    s3 = get_minio()
    try:
        s3.head_bucket(Bucket=MINIO_BUCKET)
    except Exception:
        s3.create_bucket(Bucket=MINIO_BUCKET)


def ensure_registry_bucket():
    s3 = get_minio()
    try:
        s3.head_bucket(Bucket=REGISTRY_BUCKET)
    except Exception:
        s3.create_bucket(Bucket=REGISTRY_BUCKET)


# ============================================================
# APP LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    migrate_db()
    ensure_bucket()
    ensure_registry_bucket()
    yield


app = FastAPI(title="Labeling Tool API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# SCHEMAS
# ============================================================

class AnnotationIn(BaseModel):
    image_id:  str
    class_id:  int
    bbox:      Optional[dict] = None   # {x, y, w, h, image_w, image_h} — None nếu classification
    annotator: Optional[str] = "anonymous"

class ClassIn(BaseModel):
    name: str

class ClassUpdateIn(BaseModel):
    name: str

class ClassEnsureIn(BaseModel):
    names: list[str]


# ============================================================
# ROUTES — IMAGES
# ============================================================

@app.post("/images/upload")
async def upload_images(
    files:       list[UploadFile] = File(...),
    task_type:   str              = Query("classification", enum=["detection", "classification"]),
    class_names: list[str]        = Form(default=[]),
    annotator:   str              = Query("upload"),
):
    """
    Upload nhiều ảnh lên MinIO.
    Nếu class_names[] được gửi kèm (1 tên/file), tự động tạo class và annotation luôn.
    Dùng cho folder upload có cấu trúc: cat/img.jpg → class "cat".
    """
    s3   = get_minio()
    conn = get_db()
    cur  = conn.cursor()

    # Cache class_id để tránh query lặp
    class_cache: dict[str, int] = {}

    def get_or_create_class(name: str) -> int:
        if name in class_cache:
            return class_cache[name]
        cur.execute(
            """INSERT INTO classes (name)
               VALUES (%s)
               ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
               RETURNING class_id""",
            (name.strip(),),
        )
        class_id = cur.fetchone()["class_id"]
        class_cache[name] = class_id
        return class_id

    uploaded     = 0
    auto_labeled = 0
    images_list  = []

    for i, file in enumerate(files):
        ext        = os.path.splitext(file.filename)[1].lower()
        object_key = f"{uuid.uuid4()}{ext}"
        data       = await file.read()

        s3.put_object(
            Bucket=MINIO_BUCKET,
            Key=object_key,
            Body=data,
            ContentType=file.content_type or "image/jpeg",
        )

        class_name = class_names[i].strip() if i < len(class_names) else ""
        status     = "LABELED" if class_name else "UNLABELED"

        cur.execute(
            """INSERT INTO images (minio_path, filename, task_type, status)
               VALUES (%s, %s, %s, %s) RETURNING image_id""",
            (object_key, file.filename, task_type, status),
        )
        image_id = str(cur.fetchone()["image_id"])
        images_list.append({"image_id": image_id, "filename": file.filename})

        if class_name:
            class_id = get_or_create_class(class_name)
            cur.execute(
                """INSERT INTO annotations (image_id, class_id, annotator)
                   VALUES (%s, %s, %s)""",
                (image_id, class_id, annotator),
            )
            auto_labeled += 1

        uploaded += 1

    conn.commit()
    cur.close()
    conn.close()
    return {"uploaded": uploaded, "auto_labeled": auto_labeled, "images": images_list}


@app.get("/images/next")
def get_next_image(task_type: str = Query("detection")):
    """Lấy ảnh tiếp theo chưa label."""
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        """SELECT image_id, minio_path, filename, status, task_type
           FROM images
           WHERE status = 'UNLABELED' AND task_type = %s
           ORDER BY created_at ASC
           LIMIT 1""",
        (task_type,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return {"image": None}

    s3  = get_minio()
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": MINIO_BUCKET, "Key": row["minio_path"]},
        ExpiresIn=PRESIGN_TTL,
    )
    return {"image": {**dict(row), "image_id": str(row["image_id"]), "url": url}}


@app.get("/images")
def list_images(
    status:    Optional[str] = None,
    task_type: Optional[str] = None,
    limit:     int = 50,
    offset:    int = 0,
):
    """Danh sách ảnh với filter."""
    conn   = get_db()
    cur    = conn.cursor()
    where  = []
    params = []

    if status:
        where.append("status = %s"); params.append(status)
    if task_type:
        where.append("task_type = %s"); params.append(task_type)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    cur.execute(
        f"SELECT image_id, filename, status, task_type, created_at FROM images {where_sql} ORDER BY created_at DESC LIMIT %s OFFSET %s",
        params + [limit, offset],
    )
    rows = cur.fetchall()

    cur.execute(f"SELECT COUNT(*) as total FROM images {where_sql}", params)
    total = cur.fetchone()["total"]

    cur.close()
    conn.close()
    return {"total": total, "images": [dict(r) | {"image_id": str(r["image_id"])} for r in rows]}


@app.get("/images/{image_id}/url")
def get_image_url(image_id: str):
    """Lấy presigned URL cho ảnh."""
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("SELECT minio_path FROM images WHERE image_id = %s", (image_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        raise HTTPException(404, "Image not found")

    s3  = get_minio()
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": MINIO_BUCKET, "Key": row["minio_path"]},
        ExpiresIn=PRESIGN_TTL,
    )
    return {"url": url}


# ============================================================
# ROUTES — ANNOTATIONS
# ============================================================

@app.post("/annotations")
def submit_annotation(body: AnnotationIn):
    """Submit annotation cho 1 ảnh. Tự động mark ảnh là LABELED."""
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        """INSERT INTO annotations (image_id, class_id, bbox, annotator)
           VALUES (%s, %s, %s, %s)""",
        (body.image_id, body.class_id,
         psycopg2.extras.Json(body.bbox) if body.bbox else None,
         body.annotator),
    )
    cur.execute("UPDATE images SET status = 'LABELED' WHERE image_id = %s", (body.image_id,))
    conn.commit()
    cur.close()
    conn.close()
    return {"ok": True}


@app.post("/annotations/batch")
def submit_annotations_batch(annotations: list[AnnotationIn]):
    """Submit nhiều bbox cho 1 ảnh (detection có nhiều object)."""
    if not annotations:
        raise HTTPException(400, "Empty annotations")

    conn = get_db()
    cur  = conn.cursor()
    for ann in annotations:
        cur.execute(
            """INSERT INTO annotations (image_id, class_id, bbox, annotator)
               VALUES (%s, %s, %s, %s)""",
            (ann.image_id, ann.class_id,
             psycopg2.extras.Json(ann.bbox) if ann.bbox else None,
             ann.annotator),
        )
    unique_ids = list({ann.image_id for ann in annotations})
    for img_id in unique_ids:
        cur.execute("UPDATE images SET status = 'LABELED' WHERE image_id = %s", (img_id,))
    conn.commit()
    cur.close()
    conn.close()
    return {"ok": True, "count": len(annotations)}


@app.get("/annotations/{image_id}")
def get_annotations(image_id: str):
    """Lấy tất cả annotation của 1 ảnh, JOIN với classes để trả về tên class."""
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        """SELECT a.annotation_id, a.image_id, a.class_id, c.name AS class_name,
                  a.bbox, a.annotator, a.created_at
           FROM annotations a
           LEFT JOIN classes c ON a.class_id = c.class_id
           WHERE a.image_id = %s
           ORDER BY a.created_at""",
        (image_id,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {"annotations": [
        dict(r) | {
            "annotation_id": str(r["annotation_id"]),
            "image_id":      str(r["image_id"]),
        } for r in rows
    ]}


# ============================================================
# ROUTES — CLASSES
# ============================================================

@app.get("/classes")
def list_classes():
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM classes ORDER BY name")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {"classes": [dict(r) for r in rows]}


@app.post("/classes")
def add_class(body: ClassIn):
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO classes (name) VALUES (%s) RETURNING class_id, name",
            (body.name.strip(),),
        )
        row = cur.fetchone()
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        raise HTTPException(400, f"Class '{body.name}' already exists")
    finally:
        cur.close()
        conn.close()
    return dict(row)


@app.put("/classes/{class_id}")
def rename_class(class_id: int, body: ClassUpdateIn):
    """Đổi tên class. Tất cả annotation đang dùng class_id này tự động theo tên mới."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            "UPDATE classes SET name = %s WHERE class_id = %s RETURNING class_id, name",
            (body.name.strip(), class_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, f"Class {class_id} not found")
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        raise HTTPException(400, f"Tên '{body.name}' đã tồn tại")
    finally:
        cur.close()
        conn.close()
    return dict(row)


@app.delete("/classes/{class_id}")
def delete_class(class_id: int):
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("DELETE FROM classes WHERE class_id = %s", (class_id,))
    conn.commit()
    cur.close()
    conn.close()
    return {"ok": True}


@app.post("/classes/ensure")
def ensure_classes(body: ClassEnsureIn):
    """
    Bulk upsert classes từ list tên (ví dụ: classes.txt của YOLO).
    Trả về {name: class_id} map.
    """
    conn = get_db()
    cur  = conn.cursor()
    result: dict[str, int] = {}
    for name in body.names:
        name = name.strip()
        if not name:
            continue
        cur.execute(
            """INSERT INTO classes (name)
               VALUES (%s)
               ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
               RETURNING class_id, name""",
            (name,),
        )
        row = cur.fetchone()
        result[row["name"]] = row["class_id"]
    conn.commit()
    cur.close()
    conn.close()
    return {"classes": result}


# ============================================================
# ROUTES — PROGRESS
# ============================================================

@app.get("/progress")
def get_progress():
    """Thống kê progress labeling."""
    conn = get_db()
    cur  = conn.cursor()

    cur.execute("""
        SELECT
            status,
            task_type,
            COUNT(*) as count
        FROM images
        GROUP BY status, task_type
        ORDER BY task_type, status
    """)
    rows = cur.fetchall()

    cur.execute("""
        SELECT annotator, COUNT(*) as count
        FROM annotations
        GROUP BY annotator
        ORDER BY count DESC
    """)
    annotators = cur.fetchall()

    cur.close()
    conn.close()
    return {
        "by_status":    [dict(r) for r in rows],
        "by_annotator": [dict(r) for r in annotators],
    }


@app.get("/stats")
def get_stats():
    """Stats dùng cho Progress.vue."""
    conn = get_db()
    cur  = conn.cursor()

    # Totals
    cur.execute("SELECT COUNT(*) as total, SUM(CASE WHEN status='LABELED' THEN 1 ELSE 0 END) as labeled FROM images")
    row = cur.fetchone()
    total, labeled = row["total"], row["labeled"] or 0

    # By task
    cur.execute("""
        SELECT task_type,
               COUNT(*) as total,
               SUM(CASE WHEN status='LABELED' THEN 1 ELSE 0 END) as labeled
        FROM images GROUP BY task_type
    """)
    by_task = {}
    for r in cur.fetchall():
        by_task[r["task_type"]] = {"total": r["total"], "labeled": r["labeled"] or 0}

    # By annotator
    cur.execute("""
        SELECT a.annotator,
               COUNT(DISTINCT a.image_id) as images_labeled,
               COUNT(*) as annotations
        FROM annotations a GROUP BY a.annotator ORDER BY annotations DESC
    """)
    by_annotator = [dict(r) for r in cur.fetchall()]

    # By class
    cur.execute("""
        SELECT c.name AS label, COUNT(*) as count
        FROM annotations a
        JOIN classes c ON a.class_id = c.class_id
        GROUP BY c.name ORDER BY count DESC
    """)
    by_class = [dict(r) for r in cur.fetchall()]

    cur.close()
    conn.close()
    return {
        "total":        total,
        "labeled":      labeled,
        "unlabeled":    total - labeled,
        "by_task":      by_task,
        "by_annotator": by_annotator,
        "by_class":     by_class,
    }


# ============================================================
# ROUTES — SNAPSHOTS  (internal — blocked at nginx)
# ============================================================

def _now_ts() -> str:
    """Timestamp đến microsecond, ISO 8601 với Z suffix — tương thích PostgreSQL."""
    now = datetime.now(timezone.utc)
    return now.strftime('%Y-%m-%dT%H:%M:%S.') + f"{now.microsecond:06d}Z"




def _load_params() -> dict:
    """Đọc params.yaml. Trả về {} nếu không tìm thấy (dev local)."""
    try:
        with open(PARAMS_PATH) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


def _load_all_test_ids(s3) -> set:
    """Gom tất cả image_id đã nằm trong bất kỳ test set nào."""
    excluded = set()
    try:
        resp = s3.list_objects_v2(Bucket=REGISTRY_BUCKET, Prefix="benchmarks/test_")
        for obj in resp.get("Contents", []):
            if not obj["Key"].endswith(".json"):
                continue
            body = s3.get_object(Bucket=REGISTRY_BUCKET, Key=obj["Key"])["Body"].read()
            excluded.update(json.loads(body).get("image_ids", []))
    except Exception:
        pass
    return excluded


def _put_json(s3, key: str, doc: dict):
    s3.put_object(
        Bucket=REGISTRY_BUCKET,
        Key=key,
        Body=json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )


@app.post("/snapshots", status_code=201)
def create_snapshot():
    """
    Tạo 3 file cùng lúc cho version yymmdd.hhmmss:
      - snapshots/snapshot_<id>.json
      - benchmarks/test_<id>.json
      - datasets/dataset_<id>.json

    test_<id> = sample(all_snapshot - test_ids_cũ, test_ratio%)
    dataset_<id> = split(remaining, val_ratio, seed)
    """
    # ── 1. Thời điểm snapshot ─────────────────────────────────
    ts          = _now_ts()
    snapshot_id = datetime.now().strftime("%y%m%d.%H%M%S")

    # ── 2. Đọc params ─────────────────────────────────────────
    params     = _load_params()
    data_cfg   = params.get("data", {})
    test_ratio = float(data_cfg.get("test_ratio", 0.2))
    val_ratio  = float(data_cfg.get("val_ratio",  0.2))
    seed       = data_cfg.get("seed", random.randint(0, 99_999))

    # ── 3. Query ảnh LABELED trước thời điểm snapshot ─────────
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        """SELECT image_id::text FROM images
           WHERE status = 'LABELED' AND created_at < %s
           ORDER BY created_at""",
        (ts,),
    )
    all_ids = [r["image_id"] for r in cur.fetchall()]
    cur.close()
    conn.close()

    # ── 4. Loại bỏ ảnh đã nằm trong test set cũ ───────────────
    s3       = get_minio()
    excluded = _load_all_test_ids(s3)
    pool     = [i for i in all_ids if i not in excluded]

    # ── 5. Sample test set ────────────────────────────────────
    rng     = random.Random(seed)
    n_test  = round(len(pool) * test_ratio)
    test_ids = rng.sample(pool, n_test) if n_test <= len(pool) else pool[:]

    # ── 6. Split train / val từ phần còn lại ─────────────────
    test_set    = set(test_ids)
    train_val   = [i for i in pool if i not in test_set]
    n_val       = round(len(train_val) * val_ratio)
    val_ids     = rng.sample(train_val, n_val) if n_val <= len(train_val) else train_val[:]
    val_set     = set(val_ids)
    train_ids   = [i for i in train_val if i not in val_set]

    # ── 7. Tính class distribution cho toàn bộ pool ───────────
    conn2 = get_db()
    cur2  = conn2.cursor()
    cur2.execute(
        """SELECT c.name, COUNT(*) as cnt
           FROM annotations a
           JOIN images i ON a.image_id = i.image_id
           JOIN classes c ON a.class_id = c.class_id
           WHERE i.status = 'LABELED' AND i.created_at < %s
           GROUP BY c.name
           ORDER BY cnt DESC""",
        (ts,),
    )
    class_dist = [{"class": r["name"], "count": r["cnt"]} for r in cur2.fetchall()]
    cur2.close()
    conn2.close()

    # ── 8. Tạo 3 document ─────────────────────────────────────
    snapshot_doc = {
        "snapshot_id":        snapshot_id,
        "created_at":         ts,
        "total_images":       len(all_ids),
        "class_distribution": class_dist,
        "query": {
            "status":         "LABELED",
            "created_before": ts,
        },
    }

    test_doc = {
        "name":       f"test_{snapshot_id}",
        "num_images": len(test_ids),
        "image_ids":  test_ids,
    }

    dataset_doc = {
        "snapshot_id": snapshot_id,
        "num_images":  len(train_ids) + len(val_ids),
        "num_seeding": seed,
        "train_ids":   train_ids,
        "val_ids":     val_ids,
    }

    # ── 9. Lưu lên MinIO ──────────────────────────────────────
    _put_json(s3, f"snapshots/snapshot_{snapshot_id}.json", snapshot_doc)
    _put_json(s3, f"benchmarks/test_{snapshot_id}.json",    test_doc)
    _put_json(s3, f"datasets/dataset_{snapshot_id}.json",   dataset_doc)

    return {
        "snapshot": snapshot_doc,
        "benchmark": test_doc,
        "dataset":   dataset_doc,
    }


@app.get("/snapshots")
def list_snapshots():
    """Danh sách snapshot, sort theo version tăng dần."""
    s3 = get_minio()
    try:
        resp     = s3.list_objects_v2(Bucket=REGISTRY_BUCKET, Prefix="snapshots/")
        contents = resp.get("Contents", [])
    except Exception:
        return {"snapshots": []}

    snapshots = []
    for obj in contents:
        if not obj["Key"].endswith(".json"):
            continue
        try:
            body = s3.get_object(Bucket=REGISTRY_BUCKET, Key=obj["Key"])["Body"].read()
            snapshots.append(json.loads(body))
        except Exception:
            pass

    snapshots.sort(key=lambda x: x["snapshot_id"])
    return {"snapshots": snapshots}


@app.get("/snapshots/{snapshot_id}")
def get_snapshot(snapshot_id: str):
    """Đọc snapshot + dataset + benchmark cho 1 version, vd: /snapshots/v1"""
    s3  = get_minio()
    def _read(key):
        try:
            return json.loads(s3.get_object(Bucket=REGISTRY_BUCKET, Key=key)["Body"].read())
        except Exception:
            return None

    snap = _read(f"snapshots/snapshot_{snapshot_id}.json")
    if not snap:
        raise HTTPException(404, f"Snapshot '{snapshot_id}' not found")

    return {
        "snapshot":  snap,
        "benchmark": _read(f"benchmarks/test_{snapshot_id}.json"),
        "dataset":   _read(f"datasets/dataset_{snapshot_id}.json"),
    }


# ============================================================
# ROUTES — TRAIN
# ============================================================

class TrainStartIn(BaseModel):
    snapshot_id:  Optional[str] = None   # None → tạo snapshot mới
    triggered_by: Optional[str] = "anonymous"


def _github_push_version(snapshot_id: str):
    """Ghi dataset_version.txt lên GitHub qua API → trigger CI/CD."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        raise HTTPException(500, "GITHUB_TOKEN hoặc GITHUB_REPO chưa được cấu hình")

    url     = f"https://api.github.com/repos/{GITHUB_REPO}/contents/dataset_version.txt"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github.v3+json",
    }

    # Lấy SHA hiện tại (cần để update)
    r   = http_requests.get(url, headers=headers)
    sha = r.json().get("sha") if r.ok else None

    payload = {
        "message": f"chore: train snapshot {snapshot_id}",
        "content": base64.b64encode(snapshot_id.encode()).decode(),
        "branch":  GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha

    resp = http_requests.put(url, json=payload, headers=headers)
    if not resp.ok:
        raise HTTPException(502, f"GitHub API lỗi: {resp.text}")


@app.get("/train/history")
def get_train_history():
    """Lịch sử các lần trigger train."""
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "SELECT id, snapshot_id, triggered_at, triggered_by FROM train_sessions ORDER BY triggered_at DESC"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {"history": [dict(r) for r in rows]}


@app.post("/train/start", status_code=201)
def start_train(body: TrainStartIn):
    """
    Trigger training:
    - snapshot_id=None  → tạo snapshot mới rồi train
    - snapshot_id='260630.194523'  → dùng snapshot có sẵn, chỉ push version
    """
    if body.snapshot_id:
        # Dùng snapshot có sẵn
        snapshot_id = body.snapshot_id
    else:
        # Tạo snapshot mới (gọi lại logic create_snapshot)
        result      = create_snapshot()
        snapshot_id = result["snapshot"]["snapshot_id"]

    # Push dataset_version.txt lên GitHub → CI/CD tự chạy
    _github_push_version(snapshot_id)

    # Lưu lịch sử
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "INSERT INTO train_sessions (snapshot_id, triggered_by) VALUES (%s, %s) RETURNING id, triggered_at",
        (snapshot_id, body.triggered_by or "anonymous"),
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return {
        "ok":          True,
        "snapshot_id": snapshot_id,
        "session_id":  row["id"],
        "triggered_at": str(row["triggered_at"]),
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():
    return {"status": "ok"}
