# Hướng Dẫn Sử Dụng

---

## Cấu hình `params.yaml`

Không sửa trực tiếp file trong `src/config/`. Copy ra rồi chỉnh:

```bash
cp src/config/params_config_cls.yaml src/params.yaml   # Classification
cp src/config/params_config_dct.yaml src/params.yaml   # Detection
```

### Classification
```yaml
pipeline:
  model_type: "classification"
  task_name: "ten_bai_toan"           # Tên đăng ký trên MLflow

data:
  batch_size: 32
  img_size: 224

embedding:
  model: "MobileNetV3Small"           # Dùng cho drift detection

optuna_tuning:
  n_trials: 50
  max_num_epochs: 50
  storage_db: "sqlite:///optuna_mlops.db"
  pruner: "median"

training:
  optimizer_choices: ["Adam", "SGD", "RMSprop", "AdamW"]
  lr_min: 1.0e-5
  lr_max: 1.0e-2

models:
  - "ResNet18"
  - "ResNet50"
  - "MobileNetV3Small"
  - "EfficientNetB0"
  - "SimpleCNN"

mlflow:
  experiment_base_name: "generic-vision-pipeline"
```

### Detection
```yaml
pipeline:
  model_type: "detection"
  task_name: "ten_bai_toan"

data:
  batch_size: 32
  img_size: 640

optuna_tuning:
  n_trials: 50
  max_num_epochs: 50
  storage_db: "sqlite:///optuna_mlops.db"
  pruner: "median"

training:
  optimizer_choices: ["AdamW", "SGD", "Adam"]
  lr_min: 1.0e-5
  lr_max: 1.0e-2

models:
  - "YOLOv8n"
  - "YOLOv8s"
  - "YOLOv8m"

mlflow:
  experiment_base_name: "generic-vision-pipeline"
```

---

## Khi Có Data Mới

### Cách 1 — Upload qua Labeling Tool (http://localhost:3001)

Mở tab **Upload**, chọn folder. Tool tự detect format:

**Classification — ImageFolder:**
```
my_dataset/
  cat/img1.jpg       ← subfolder = class name
  dog/img2.jpg
  bird/img3.jpg
```
→ Tự động gắn nhãn theo tên subfolder. Ảnh ở root folder → UNLABELED, gắn tay sau.

**Detection — YOLO format:**
```
my_dataset/
  classes.txt        ← tên class theo thứ tự index (1 dòng/class)
  images/img1.jpg    ← ảnh
  labels/img1.txt    ← class_idx cx cy w h (normalized 0-1)
```
→ Tự động tạo class, import bbox, mark LABELED. Ảnh không có label → UNLABELED.

**File thường (không có folder):** upload nhiều file → tất cả UNLABELED, gắn nhãn sau trong tab Label.

### Cách 2 — Gắn nhãn mới qua Labeling Tool

```bash
# 1. Mở Labeling Tool: http://localhost:3001
#    Upload ảnh → gắn nhãn → submit

# 2. Tạo snapshot — bấm trong app: tab Progress → "Tạo Snapshot"
# → tạo snapshot_vX.json + dataset_vX.json + test_vX.json trên MinIO

# 3. Cập nhật version + push → CI/CD tự chạy
echo "v1" > dataset_version.txt
git add dataset_version.txt
git commit -m "dataset v1"
git tag v1.0
git push origin main --tags
```

---

## Khi Có Code / Config Mới

```bash
# Sửa bất kỳ file nào trong src/, src/params.yaml, hoặc src/models/*.py
git add .
git commit -m "mo ta thay doi"
git push origin main
# → CI/CD detect thay đổi → train lại → deploy API mới
```

**Thêm model custom** — không cần rebuild image:

1. Tạo `src/models/custom2.py` với class model
2. `git add src/models/custom2.py && git commit && git push`
3. CI/CD cập nhật ConfigMap `model-code` từ `src/models/` → inject vào container lúc runtime

```yaml
# Thêm vào models list trong params.yaml
models:
  - "ResNet18"
  - "MyCustomModel"   # tên class trong custom.py hoặc custom2.py
```

---

## Chạy Thủ Công

Dùng khi muốn test nhanh mà không push lên GitHub:

```bash
# Cập nhật ConfigMaps
kubectl create configmap model-code --from-file=src/models/ -n mlops --dry-run=client -o yaml | kubectl apply -f -
kubectl create configmap model-params --from-file=params.yaml=src/params.yaml -n mlops --dry-run=client -o yaml | kubectl apply -f -
DATASET_VERSION=$(cat dataset_version.txt | tr -d '[:space:]')
kubectl create configmap dataset-version --from-literal=DATASET_VERSION=$DATASET_VERSION -n mlops --dry-run=client -o yaml | kubectl apply -f -

# Xóa trainer Job cũ rồi deploy lại
kubectl delete job trainer -n mlops --ignore-not-found
helm upgrade mlops mlops_chart/ --namespace mlops \
  --set trainer.enabled=true --set api.enabled=true

# Theo dõi log
kubectl logs -n mlops -l job-name=trainer -c trainer -f

# Sau khi trainer xong, restart API
kubectl rollout restart deployment/api -n mlops
```

---

## CI/CD Pipeline

```
git push origin main
        ↓
GitHub Actions trigger khi:
  src/**, src/params.yaml, dataset_version.txt thay đổi
  hoặc bấm tay trên GitHub UI (workflow_dispatch)
        ↓
Kiểm tra dataset_version.txt
  ├── Rỗng → skip (v0.0, chưa có snapshot)
  └── Có version → chạy full pipeline:
        1. Build Docker images nếu stable files thay đổi
        2. Load images vào Minikube
        3. Tạo ConfigMaps: model-code, model-params, dataset-version
        4. Xóa trainer Job cũ
        5. helm upgrade → trainer Job chạy:
           download dataset → train (Optuna × N trials) → MLflow
        6. Đợi trainer complete
        7. Restart API → health check
        ↓
Model mới đang serve tại http://localhost:8000
```

---

## Luồng MLOps Tổng Thể

```
[Đội gắn nhãn]
  Labeling Tool → MinIO (raw-images) + PostgreSQL (metadata)
                          │
                   POST /snapshots → MinIO registry (snapshot/dataset/test vX)
                          │
[Code/Config] → GitHub Actions
                          │
              ConfigMaps: model-code | model-params | dataset-version
                          │
                   [Trainer Job]
                   registry_loader: download MinIO + PostgreSQL
                   Optuna × N trials → MLflow nested runs
                   Save reference_embeddings.npy
                          │
                   [MLflow] → alias "champion"
                          │
                   [FastAPI] → serve predict
                   Log ~10% ảnh vào raw-data-lake
                          │
                   [Prometheus + Grafana] → monitor
                          │
                   Cuối ngày: extract embedding → so sánh với reference
                   Drift cao? → Alert → gắn nhãn mới → snapshot → train lại
```

---

## Quản Lý Version Data

| Tag | Ý nghĩa |
|-----|---------|
| `v0.0` | Project skeleton, chưa có data |
| `v1.0` | Dataset đầu tiên |
| `v2.0` | Dataset cập nhật lần 2 |

**Rollback về dataset cũ:**

```bash
git checkout v1.0 -- dataset_version.txt
git commit -m "rollback to dataset v1"
git push origin main
# → CI/CD tự trigger train lại với snapshot v1
```

---

## Dùng Template Cho Project Mới

```bash
git clone https://github.com/mnhut0550/mlops_1.git my_project
cd my_project

git remote remove origin
git remote add origin https://github.com/<you>/my_project.git

git checkout --orphan fresh
git add .
git commit -m "init from mlops template"
git push origin fresh:main

cp src/config/params_config_cls.yaml src/params.yaml
# Chỉnh task_name, models, credentials trong values.yaml

.\setup.ps1   # Windows
./setup.sh    # Linux/macOS
```
