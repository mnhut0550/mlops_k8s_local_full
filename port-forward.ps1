# port-forward.ps1
# Usage:
#   .\port-forward.ps1              # core (mac dinh)
#   .\port-forward.ps1 -Profile dev
#   .\port-forward.ps1 -Profile all
#
# Profile:
#   core  - Labeling, API, MLflow, Grafana  (dung hang ngay)
#   dev   - Postgres, MinIO, Backend API    (truy cap truc tiep DB / storage)
#   all   - Tat ca
#
# Luu y: Tat ca services dung ClusterIP — truy cap qua port-forward (localhost)
#         labeling-frontend dung local port 3001 (tranh trung voi grafana :3000)
#
# Yeu cau: Windows Terminal
#   Windows 11 : co san
#   Windows 10 : winget install Microsoft.WindowsTerminal
# Kiem tra   : wt --version

param(
    [ValidateSet("core","dev","all")]
    [string]$Profile = "core"
)

$CORE = @(
    @{ name="labeling-front"; fwd="svc/labeling-frontend 3001:3000" }
    @{ name="api";            fwd="svc/api-service       8000:8000" }
    @{ name="mlflow";         fwd="svc/mlflow-service    5000:5000" }
    @{ name="grafana";        fwd="svc/grafana-service   3000:3000" }
)
$DEV  = @(
    @{ name="postgres";       fwd="svc/labeling-postgres 5432:5432" }
    @{ name="minio-s3";       fwd="svc/minio-service     9000:9000" }
    @{ name="labeling-back";  fwd="svc/labeling-backend  8001:8001" }
    @{ name="minio-console";  fwd="svc/minio-service     9001:9001" }
)

if     ($Profile -eq "core") { $svcs = $CORE }
elseif ($Profile -eq "dev")  { $svcs = $DEV }
else                          { $svcs = $CORE + $DEV }

if (-not (Get-Command wt -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Windows Terminal (wt) chua cai." -ForegroundColor Red
    Write-Host "  Windows 10: winget install Microsoft.WindowsTerminal" -ForegroundColor Yellow
    exit 1
}

$mkStatus = minikube status --format="{{.Host}}" 2>$null
if ($mkStatus -ne "Running") {
    Write-Host "ERROR: Minikube chua chay. Chay: minikube start" -ForegroundColor Red
    exit 1
}

Write-Host "Profile: $Profile ($($svcs.Count) services)" -ForegroundColor Cyan

wt --window 0 new-tab --title $svcs[0].name -- powershell -NoExit -Command "kubectl port-forward -n mlops $($svcs[0].fwd)"
Start-Sleep -Milliseconds 800

for ($i = 1; $i -lt $svcs.Count; $i++) {
    wt --window 0 new-tab --title $svcs[$i].name -- powershell -NoExit -Command "kubectl port-forward -n mlops $($svcs[$i].fwd)"
    Start-Sleep -Milliseconds 400
}

Write-Host ""
if ($Profile -in @("core", "all")) {
    Write-Host "  Labeling Tool : http://localhost:3001" -ForegroundColor White
    Write-Host "  API /predict  : http://localhost:8000/docs" -ForegroundColor White
    Write-Host "  MLflow        : http://localhost:5000" -ForegroundColor White
    Write-Host "  Grafana       : http://localhost:3000" -ForegroundColor White
}
if ($Profile -in @("dev", "all")) {
    Write-Host "  PostgreSQL    : localhost:5432" -ForegroundColor Gray
    Write-Host "  MinIO S3 API  : http://localhost:9000" -ForegroundColor Gray
    Write-Host "  Labeling API  : http://localhost:8001" -ForegroundColor Gray
    Write-Host "  MinIO Console : http://localhost:9001" -ForegroundColor Gray
}
