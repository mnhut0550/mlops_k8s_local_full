# MLOps Pipeline — Classification & Detection (Kubernetes)

Template MLOps đầy đủ cho **phân loại ảnh (Classification)** và **phát hiện vật thể (Detection)**, chạy trên Kubernetes local với Helm.

---

## Tại sao cần MLOps?

Train model xong là bước khởi đầu, không phải kết thúc:

- Train đi train lại nhiều lần — không nhớ lần nào tốt nhất
- Data thay đổi — không biết model đang chạy trên data version nào
- Không có công cụ thống nhất cho đội gắn nhãn
- Model production — không biết có đang hoạt động đúng không

MLOps tự động hóa toàn bộ pipeline:

```
Data → Label → Train → Evaluate → Deploy → Monitor → (Retrain khi cần)
```

---

## Các thành phần

| Component | Vai trò |
|-----------|---------|
| **Labeling Tool** | Web app gắn nhãn nội bộ — Upload, vẽ bbox / chọn class, theo dõi tiến độ |
| **MLflow** | Tracking experiments, so sánh trials, quản lý model alias `champion` |
| **MinIO** | S3-compatible storage — lưu ảnh, model artifacts, snapshots/datasets |
| **FastAPI** | Serve model `POST /predict` — classification label / detection boxes |
| **Prometheus + Grafana** | Monitor request rate, latency, error rate |
| **GitHub Actions** | CI/CD — tự động train + deploy khi push code/data |

---

## Yêu cầu

- **Docker Desktop** (Settings → Resources → Memory ≥ 4GB)
- **Minikube**, **kubectl**, **Helm**, **Git**
- **Python 3.11+** — chạy scripts cục bộ
- **Windows Terminal** (Windows) hoặc **tmux** (Linux/macOS) — để chạy port-forward

---

## Cấu trúc project

```
mlops_local_k8s/
├── .github/workflows/mlops_pipeline.yml  # CI/CD pipeline
├── src/
│   ├── train.py                          # Orchestration: config, dataset, Optuna, MLflow
│   ├── cls_trainer.py                    # Classification trainer
│   ├── dct_trainer.py                    # Detection trainer
│   ├── registry_loader.py                # Download dataset từ MinIO + PostgreSQL
│   ├── embedding_utils.py                # Extract embedding (drift detection)
│   ├── models/
│   │   ├── models.py                     # Factory build_model() — baked vào image
│   │   ├── pretrained.py                 # Backbones registry — inject qua ConfigMap
│   │   ├── custom.py                     # Custom models — inject qua ConfigMap
│   │   └── utils.py                      # Shared utils — inject qua ConfigMap
│   ├── params.yaml                       # Config người dùng tạo (copy từ src/config/)
│   └── config/
│       ├── load.py
│       ├── params_config_cls.yaml        # Example config — Classification
│       └── params_config_dct.yaml        # Example config — Detection
├── serving/app.py                        # FastAPI serving
├── labeling/
│   ├── backend/                          # FastAPI + PostgreSQL
│   └── frontend/                         # Vue 3 + Nginx
├── docker/
│   ├── Dockerfile.base                   # Base image (PyTorch)
│   ├── Dockerfile.trainer
│   └── Dockerfile.api
├── mlops_chart/                          # Helm chart
│   ├── values.example.yaml               # Copy thành values.yaml
│   └── templates/
├── requirements/
├── setup.ps1                            # Setup lần đầu — Windows
├── setup.sh                             # Setup lần đầu — Linux/macOS
├── port-forward.ps1                     # Mở port-forwards — Windows
└── port-forward.sh                      # Mở port-forwards — Linux/macOS
```

### Stable vs Dynamic files

| File | Loại | Cách deploy |
|------|------|-------------|
| `src/train.py`, `cls_trainer.py`, `dct_trainer.py` | Stable | Baked vào Docker image |
| `src/registry_loader.py`, `embedding_utils.py` | Stable | Baked vào Docker image |
| `src/models/models.py`, `src/config/` | Stable | Baked vào Docker image |
| `src/models/pretrained.py`, `custom.py`, `utils.py` | Dynamic | Inject qua ConfigMap lúc runtime |

---

## Tài liệu

- [docs/SETUP.md](docs/SETUP.md) — Cài tools, cấu hình, chạy setup script lần đầu
- [docs/USAGE.md](docs/USAGE.md) — Thêm data, thêm model, chạy thủ công, CI/CD flow
