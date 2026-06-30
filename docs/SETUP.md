# Lần Đầu Setup

> Chỉ cần làm một lần. Script `setup.ps1` / `setup.sh` tự động hóa phần lớn.

---

## Bước 1 — Clone project

```bash
git clone https://github.com/mnhut0550/mlops_1.git
cd mlops_1
```

---

## Bước 2 — Cài tools

### Docker Desktop
- Windows/macOS: https://www.docker.com/products/docker-desktop
- Vào Settings → Resources → Memory: tối thiểu **4GB**

### Minikube
```bash
# macOS
brew install minikube

# Windows (PowerShell — chạy với quyền Admin)
curl -LO https://github.com/kubernetes/minikube/releases/latest/download/minikube-windows-amd64.exe
move minikube-windows-amd64.exe C:\Windows\System32\minikube.exe

# Linux
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube
```

### kubectl
```bash
# macOS
brew install kubectl

# Windows
winget install kubectl

# Linux
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install kubectl /usr/local/bin/kubectl
```

### Helm
```bash
# macOS
brew install helm

# Windows (PowerShell — chạy với quyền Admin)
curl -LO https://get.helm.sh/helm-v3.17.0-windows-amd64.zip
Expand-Archive helm-v3.17.0-windows-amd64.zip -DestinationPath helm-tmp
move helm-tmp\windows-amd64\helm.exe C:\Windows\System32\helm.exe
Remove-Item -Recurse helm-tmp, helm-v3.17.0-windows-amd64.zip

# Linux
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

### Windows Terminal *(Windows — cần để chạy port-forward.ps1)*

```powershell
# Kiểm tra đã có chưa
wt --version

# Chưa có thì cài:
winget install Microsoft.WindowsTerminal
```

### tmux *(Linux/macOS — cần để chạy port-forward.sh)*
```bash
# macOS
brew install tmux

# Ubuntu/Debian
sudo apt install tmux
```

### Kiểm tra tất cả

```powershell
# Windows
docker version; minikube version; kubectl version --client; helm version
```

```bash
# Linux / macOS
docker version && minikube version && kubectl version --client && helm version
```

---

## Bước 3 — Cấu hình credentials

Copy `mlops_chart/values.example.yaml` thành `mlops_chart/values.yaml` rồi điền thông tin thật:

```bash
cp mlops_chart/values.example.yaml mlops_chart/values.yaml
```

```yaml
secret:
  minioRootUser: "your_user"          # tối thiểu 3 ký tự
  minioRootPassword: "your_pass"      # tối thiểu 8 ký tự
  awsAccessKeyId: "your_user"         # phải trùng minioRootUser
  awsSecretAccessKey: "your_pass"     # phải trùng minioRootPassword
  grafanaPassword: "your_pass"
  labelingDbPassword: "your_db_pass"
  githubToken: "ghp_..."              # GitHub Personal Access Token

labeling:
  githubRepo: "your-username/your-repo"  # owner/repo
  githubBranch: "main"
```

**Tạo GitHub Personal Access Token:**
1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token → chọn scope **`repo`** (full control)
3. Copy token → điền vào `secret.githubToken`

> **⚠️ Nếu đổi `labeling.backend.port`:** phải cập nhật thêm `labeling/frontend/nginx.conf` dòng `proxy_pass http://labeling-backend:<port>/` cho khớp — file này không đọc từ values.yaml.

> **Lưu ý:** `mlops_chart/values.yaml` chứa credentials — chỉ dùng cho private repo. Nếu repo public thì thêm vào `.gitignore`.

---

## Bước 4 — Tạo `src/params.yaml`

```bash
# Classification
cp src/config/params_config_cls.yaml src/params.yaml

# Hoặc Detection
cp src/config/params_config_dct.yaml src/params.yaml
```

Chỉnh `task_name`, `models`, `n_trials`, `max_num_epochs` theo nhu cầu.

> **Hai tên cần đồng bộ thủ công:**
>
> | Giá trị | Nơi đặt | Mặc định |
> |---|---|---|
> | `pipeline.task_name` | `src/params.yaml` | `"ten_bai_toan"` |
> | `configmap.modelName` | `mlops_chart/values.yaml` | `"ten_bai_toan"` |
>
> Hai giá trị này phải **giống hệt nhau** — `task_name` là tên model đăng ký trong MLflow; `modelName` là tên API dùng để load model khi serving.
>
> | Giá trị | Nơi đặt | Mặc định |
> |---|---|---|
> | `PROJECT` | `setup.ps1` / `setup.sh` (dòng đầu) | `"mlops-local"` |
> | `trainer.image` | `values.yaml` | `"mlops-local-trainer:latest"` |
> | `api.image` | `values.yaml` | `"mlops-local-api:latest"` |
>
> Nếu đổi `PROJECT` thì cập nhật image names tương ứng trong `values.yaml` và workflow.

---

## Bước 5 — Tạo GitHub repo và kết nối

1. Vào github.com → **New repository** → Private → **Không check** "Add README"
2. Kết nối:
```bash
git remote remove origin
git remote add origin https://github.com/<you>/my_project.git
```

---

## Bước 6 — Setup CI/CD runner

> Mở một terminal riêng. Runner phải đang chạy thì CI/CD mới hoạt động.

```
1. GitHub repo → Settings → Actions → Runners → New self-hosted runner
2. Chọn OS của máy
3. Tạo thư mục riêng (KHÔNG trong project):
   mkdir C:\actions-runner   (Windows)
   mkdir ~/actions-runner    (Linux/macOS)
4. Chạy từng lệnh GitHub hướng dẫn
5. Chạy ./run.cmd (Windows) hoặc ./run.sh (Linux/macOS)
6. Thấy "Listening for Jobs" là sẵn sàng
```

---

## Bước 7 — Chạy setup script

```powershell
# Windows
.\setup.ps1
```

```bash
# Linux / macOS
chmod +x setup.sh && ./setup.sh
```

Script tự động: khởi động Minikube → build images → deploy Helm stack → tạo ConfigMap → đợi services → **push v0.0 lên GitHub**.

---

## Truy cập services sau setup

> **Windows + Docker driver:** NodePort không route ra host, phải dùng port-forward.

Chạy port-forward (giữ terminal mở):

```powershell
# Windows
.\port-forward.ps1              # core (mặc định)
.\port-forward.ps1 -Profile dev # dev tools
.\port-forward.ps1 -Profile all # tất cả
```

```bash
# Linux / macOS
chmod +x port-forward.sh && ./port-forward.sh       # core
./port-forward.sh dev                                # dev tools
./port-forward.sh all                                # tất cả
```

**core** — dùng hàng ngày:

| Service | URL | Ghi chú |
|---------|-----|---------|
| **Labeling Tool** | http://localhost:3001 | Upload → Label → Progress |
| **API** | http://localhost:8000/docs | Chỉ available sau khi train xong |
| **MLflow** | http://localhost:5000 | Experiments → runs, Models → champion |
| **Grafana** | http://localhost:3000 | admin / `grafanaPassword` |

> `api-service` chỉ tồn tại sau khi CI/CD chạy xong lần đầu và deploy model. Nếu port-forward báo `api-service not found`, chạy lại `.\port-forward.ps1` sau khi train xong.

**dev** — truy cập trực tiếp DB / storage:

| Service | URL | Ghi chú |
|---------|-----|---------|
| **PostgreSQL** | localhost:5432 | `labelingDbPassword` |
| **MinIO S3 API** | http://localhost:9000 | S3-compatible endpoint |
| **Labeling Backend** | http://localhost:8001 | Debug API trực tiếp |
| **MinIO Console** | http://localhost:9001 | `minioRootUser` / `minioRootPassword` |
