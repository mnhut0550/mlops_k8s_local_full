#!/usr/bin/env bash
# setup.sh
# Run once when setting up a new project on Linux/macOS
# Requirement:
#   - GitHub repo đã tạo và remote đã kết nối (git remote set-url origin ...)
#   - GitHub Actions runner đang chạy (Listening for Jobs)
#
# Usage:
#   chmod +x setup.sh && ./setup.sh

set -euo pipefail

# Tên project — đổi tại đây nếu muốn dùng prefix khác cho Docker image
PROJECT="mlops-local"

echo ""
echo "========================================"
echo "   MLOps Stack Setup"
echo "========================================"
echo ""

# =========================================================
# Step 1: Check required tools
# =========================================================

echo "[1/6] Checking tools..."

tools=(minikube helm kubectl docker git)

for tool in "${tools[@]}"; do
    if ! command -v "$tool" &>/dev/null; then
        echo "ERROR: $tool is not installed. Please install it first."
        exit 1
    fi
done

echo "OK: All required tools are ready"

# =========================================================
# Step 2: Ensure Minikube is running
# =========================================================

echo ""
echo "[2/6] Checking Minikube..."

status=$(minikube status --format="{{.Host}}" 2>/dev/null || true)

if [ "$status" != "Running" ]; then
    echo "Minikube is not running. Starting..."
    minikube start --memory=4096 --cpus=2
fi

echo "OK: Minikube is running"

# =========================================================
# Step 3: Build Docker images
# =========================================================
#
# Builds base, trainer, api, labeling-backend, labeling-frontend.
# None of these depend on dataset.
#
# =========================================================

echo ""
echo "[3/6] Building Docker images..."

# Build thẳng vào Docker daemon của Minikube — tránh minikube image load cho image lớn (base có PyTorch)
echo "  Switching Docker context to Minikube daemon..."
eval "$(minikube docker-env)"

echo "Building ${PROJECT}-base:latest..."
docker build -f docker/Dockerfile.base -t "${PROJECT}-base:latest" .

echo "Building ${PROJECT}-trainer:latest..."
docker build -f docker/Dockerfile.trainer \
    --build-arg BASE_IMAGE="${PROJECT}-base:latest" \
    -t "${PROJECT}-trainer:latest" .

echo "Building ${PROJECT}-api:latest..."
docker build -f docker/Dockerfile.api \
    --build-arg BASE_IMAGE="${PROJECT}-base:latest" \
    -t "${PROJECT}-api:latest" .

echo "Building labeling-backend:latest..."
docker build -f labeling/backend/Dockerfile -t labeling-backend:latest .

echo "Building labeling-frontend:latest..."
docker build -f labeling/frontend/Dockerfile -t labeling-frontend:latest .


echo "OK: Images built into Minikube daemon"

# =========================================================
# Step 4: Deploy stack via Helm
# =========================================================
#
# Deploys MinIO, MLflow, Prometheus, Grafana, Labeling Tool,
# Monitoring Dashboard.
# Trainer/API are disabled until dataset_version.txt has content.
#
# =========================================================

echo ""
echo "[4/6] Deploying stack via Helm..."

if helm list -n mlops --short 2>/dev/null | grep -q "^mlops$"; then
    echo "Stack already exists, skipping."
else
    helm install \
        mlops \
        mlops_chart/ \
        --namespace mlops \
        --create-namespace

    echo "OK: Helm install completed"
fi

# Tạo model-params ConfigMap từ src/params.yaml
# Labeling backend mount ConfigMap này — nếu không có thì Pod bị treo ContainerCreating
if [ ! -f "src/params.yaml" ]; then
    echo "WARNING: src/params.yaml not found — skipping model-params ConfigMap."
    echo "         Tạo src/params.yaml từ src/config/params_config_cls.yaml rồi chạy:"
    echo "         kubectl create configmap model-params --from-file=params.yaml=src/params.yaml -n mlops"
else
    kubectl create configmap model-params --from-file=params.yaml=src/params.yaml -n mlops --dry-run=client -o yaml | kubectl apply -f -
    echo "OK: model-params ConfigMap created"
fi

# =========================================================
# Step 5: Wait for services
# =========================================================

echo ""
echo "[5/6] Waiting for services..."

echo "  Waiting for MinIO..."
kubectl rollout status statefulset/minio -n mlops --timeout=120s
kubectl wait pod -n mlops -l app=minio --for=condition=Ready --timeout=120s

echo "  Waiting for Labeling Postgres..."
kubectl rollout status statefulset/labeling-postgres -n mlops --timeout=300s
kubectl wait pod -n mlops -l app=labeling-postgres --for=condition=Ready --timeout=300s

echo "  Waiting for Labeling backend..."
kubectl rollout status deployment/labeling-backend -n mlops --timeout=300s


echo "OK: Services are ready"

# =========================================================
# Step 6: Push v0.0 to GitHub
# =========================================================
#
# Push skeleton without data.
# dataset_version.txt is empty → CI/CD will skip the pipeline.
# Data enters through the Labeling Tool, not from local filesystem.
#
# =========================================================

echo ""
echo "[6/6] Pushing v0.0 to GitHub..."

if [ ! -d ".git" ]; then
    echo "WARNING: Thư mục này chưa có git repo."
    echo "         Chạy các lệnh sau rồi chạy lại setup:"
    echo "           git init"
    echo "           git remote add origin https://github.com/<you>/my_project.git"
    echo "           git branch -M main"
    echo "         Sau đó chạy lại ./setup.sh"
    exit 1
fi

branch=$(git rev-parse --abbrev-ref HEAD)

git add .

if ! git diff --cached --quiet; then
    git commit -m "init project"
fi

git tag v0.0 2>/dev/null || true
git push origin "$branch" --tags

echo "OK: v0.0 pushed to GitHub"

echo ""
echo "========================================"
echo "   Setup completed!"
echo "========================================"
echo ""
echo "Next steps:"
echo ""
echo "  1. Chạy port-forward:"
echo "       chmod +x port-forward.sh && ./port-forward.sh"
echo ""
echo "  2. Mở các app:"
echo "       Labeling Tool → http://localhost:3001"
echo "       API /predict  → http://localhost:8000/docs"
echo "       Grafana       → http://localhost:3000  (admin / giá trị grafanaPassword)"
echo "       MLflow        → http://localhost:5000"
echo ""
echo "  3. Tạo snapshot đầu tiên:"
echo "       Vào http://localhost:3001 → tab Progress → nhấn 'Tạo Snapshot'"
echo "       → tạo snapshot_v1.json + dataset_v1.json + test_v1.json trên MinIO registry"
echo ""
echo "  4. Update dataset_version.txt và push để trigger CI/CD:"
echo "       echo 'v1' > dataset_version.txt"
echo "       git add dataset_version.txt"
echo "       git commit -m 'dataset v1'"
echo "       git tag v1.0"
echo "       git push origin $branch --tags"
echo ""
echo "  CI/CD sẽ tự động train sau khi push."
