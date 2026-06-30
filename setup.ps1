# setup.ps1
# Run once when setting up a new project on Windows
# Requirement:
#   - GitHub repo đã tạo và remote đã kết nối (git remote set-url origin ...)
#   - GitHub Actions runner đang chạy (Listening for Jobs)
#
# Usage:
#   .\setup.ps1

$ErrorActionPreference = "Stop"

# Tên project — đổi tại đây nếu muốn dùng prefix khác cho Docker image
$PROJECT = "mlops-local"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   MLOps Stack Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# =========================================================
# Step 1: Check required tools
# =========================================================

Write-Host "[1/6] Checking tools..." -ForegroundColor Yellow

$tools = @("minikube", "helm", "kubectl", "docker", "git")

foreach ($tool in $tools) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Host "ERROR: $tool is not installed. Please install it first." -ForegroundColor Red
        exit 1
    }
}

Write-Host "OK: All required tools are ready" -ForegroundColor Green

# =========================================================
# Step 2: Ensure Minikube is running
# =========================================================

Write-Host ""
Write-Host "[2/6] Checking Minikube..." -ForegroundColor Yellow

$status = minikube status --format="{{.Host}}" 2>$null

if ($status -ne "Running") {
    Write-Host "Minikube is not running. Starting..." -ForegroundColor Yellow
    minikube start --memory=4096 --cpus=2
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to start Minikube!" -ForegroundColor Red
        exit 1
    }
}

Write-Host "OK: Minikube is running" -ForegroundColor Green

# =========================================================
# Step 3: Build Docker images
# =========================================================
#
# Builds base, trainer, api, labeling-backend, labeling-frontend.
# None of these depend on dataset.
#
# =========================================================

Write-Host ""
Write-Host "[3/6] Building Docker images..." -ForegroundColor Yellow

$baseTag    = "${PROJECT}-base:latest"
$trainerTag = "${PROJECT}-trainer:latest"
$apiTag     = "${PROJECT}-api:latest"

# Build thẳng vào Docker daemon của Minikube — tránh minikube image load cho image lớn (base có PyTorch)
Write-Host "  Switching Docker context to Minikube daemon..." -ForegroundColor Gray
& minikube docker-env --shell powershell | Invoke-Expression

Write-Host "Building $baseTag..." -ForegroundColor Cyan
docker build -f docker/Dockerfile.base -t $baseTag .
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Failed to build $baseTag!" -ForegroundColor Red; exit 1 }

Write-Host "Building $trainerTag..." -ForegroundColor Cyan
docker build -f docker/Dockerfile.trainer --build-arg BASE_IMAGE=$baseTag -t $trainerTag .
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Failed to build $trainerTag!" -ForegroundColor Red; exit 1 }

Write-Host "Building $apiTag..." -ForegroundColor Cyan
docker build -f docker/Dockerfile.api --build-arg BASE_IMAGE=$baseTag -t $apiTag .
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Failed to build $apiTag!" -ForegroundColor Red; exit 1 }

Write-Host "Building labeling-backend:latest..." -ForegroundColor Cyan
docker build -f labeling/backend/Dockerfile -t labeling-backend:latest .
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Failed to build labeling-backend!" -ForegroundColor Red; exit 1 }

Write-Host "Building labeling-frontend:latest..." -ForegroundColor Cyan
docker build -f labeling/frontend/Dockerfile -t labeling-frontend:latest .
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Failed to build labeling-frontend!" -ForegroundColor Red; exit 1 }


Write-Host "OK: Images built into Minikube daemon" -ForegroundColor Green

# =========================================================
# Step 4: Deploy stack via Helm
# =========================================================
#
# Deploys MinIO, MLflow, Prometheus, Grafana, Labeling Tool.
# Trainer/API are disabled until dataset_version.txt has content.
#
# =========================================================

Write-Host ""
Write-Host "[4/6] Deploying stack via Helm..." -ForegroundColor Yellow

$release = helm list -n mlops --short 2>$null

if ($release -contains "mlops") {
    Write-Host "Stack already exists, skipping." -ForegroundColor Gray
} else {
    helm install mlops mlops_chart/ --namespace mlops --create-namespace
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Helm install failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host "OK: Helm install completed" -ForegroundColor Green
}

# Tạo model-params ConfigMap từ src/params.yaml
# Labeling backend mount ConfigMap này — nếu không có thì Pod bị treo ContainerCreating
if (-not (Test-Path "src/params.yaml")) {
    Write-Host "WARNING: src/params.yaml not found — skipping model-params ConfigMap." -ForegroundColor Yellow
    Write-Host "         Tạo src/params.yaml từ src/config/params_config_cls.yaml rồi chạy:" -ForegroundColor Yellow
    Write-Host "         kubectl create configmap model-params --from-file=params.yaml=src/params.yaml -n mlops" -ForegroundColor Gray
} else {
    kubectl create configmap model-params --from-file=params.yaml=src/params.yaml -n mlops --dry-run=client -o yaml | kubectl apply -f -
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create model-params ConfigMap!" -ForegroundColor Red
        exit 1
    }
    Write-Host "OK: model-params ConfigMap created" -ForegroundColor Green
}

# =========================================================
# Step 5: Wait for services
# =========================================================

Write-Host ""
Write-Host "[5/6] Waiting for services..." -ForegroundColor Yellow

Write-Host "  Waiting for MinIO..."
kubectl rollout status statefulset/minio -n mlops --timeout=300s
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: MinIO rollout failed!" -ForegroundColor Red
    exit 1
}

kubectl wait pod -n mlops -l app=minio --for=condition=Ready --timeout=300s
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: MinIO timeout!" -ForegroundColor Red
    exit 1
}

Write-Host "  Waiting for Labeling Postgres..."
kubectl rollout status statefulset/labeling-postgres -n mlops --timeout=300s
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Labeling Postgres rollout failed!" -ForegroundColor Red
    exit 1
}

kubectl wait pod -n mlops -l app=labeling-postgres --for=condition=Ready --timeout=300s
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Labeling Postgres timeout!" -ForegroundColor Red
    exit 1
}

Write-Host "  Waiting for Labeling backend..."
kubectl rollout status deployment/labeling-backend -n mlops --timeout=300s
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Labeling backend rollout failed!" -ForegroundColor Red
    exit 1
}

Write-Host "OK: Services are ready" -ForegroundColor Green

# =========================================================
# Step 6: Push v0.0 to GitHub
# =========================================================
#
# Push skeleton without data.
# dataset_version.txt is empty → CI/CD will skip the pipeline.
# Data enters through the Labeling Tool, not from local filesystem.
#
# =========================================================

Write-Host ""
Write-Host "[6/6] Pushing v0.0 to GitHub..." -ForegroundColor Yellow

if (-not (Test-Path ".git")) {
    Write-Host "WARNING: Thư mục này chưa có git repo." -ForegroundColor Yellow
    Write-Host "         Chạy các lệnh sau rồi chạy lại setup:" -ForegroundColor Yellow
    Write-Host "           git init" -ForegroundColor Gray
    Write-Host "           git remote add origin https://github.com/<you>/my_project.git" -ForegroundColor Gray
    Write-Host "           git branch -M main" -ForegroundColor Gray
    Write-Host "         Sau đó chạy lại .\setup.ps1" -ForegroundColor Yellow
    exit 1
}

$branch = git rev-parse --abbrev-ref HEAD

git add .

# git diff --cached --quiet exits 1 khi có staged changes — không phải lỗi thật
$staged = git diff --cached --quiet 2>$null; $hasStagedChanges = ($LASTEXITCODE -ne 0)
if ($hasStagedChanges) {
    git commit -m "init project"
}

git tag v0.0 2>$null
git push origin $branch --tags

Write-Host "OK: v0.0 pushed to GitHub" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Setup completed!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Next steps:" -ForegroundColor White
Write-Host ""
Write-Host "  1. Chạy port-forward:" -ForegroundColor White
Write-Host "       .\port-forward.ps1" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. Mở các app:" -ForegroundColor White
Write-Host "       Labeling Tool → http://localhost:3001" -ForegroundColor Gray
Write-Host "       API /predict  → http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "       Grafana       → http://localhost:3000  (admin / giá trị grafanaPassword)" -ForegroundColor Gray
Write-Host "       MLflow        → http://localhost:5000" -ForegroundColor Gray
Write-Host ""
Write-Host "  3. Upload ảnh + gắn nhãn → tab Train → nhấn Train để trigger CI/CD" -ForegroundColor White
Write-Host ""
Write-Host "  CI/CD sẽ tự động train sau khi push." -ForegroundColor Gray
