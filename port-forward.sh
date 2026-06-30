#!/usr/bin/env bash
# port-forward.sh
# Mở port-forward theo profile — không public tất cả cùng lúc.
#
# Profile:
#   core   (mặc định) — Labeling, API, MLflow, Grafana  (dung hang ngay)
#   dev    — Postgres, MinIO, Backend API    (truy cap truc tiep DB / storage)
#   all    — Tat ca
#
# Luu y: Tat ca services dung ClusterIP — truy cap qua port-forward (localhost)
#         labeling-frontend dung local port 3001 (tranh trung voi grafana :3000)
#
# Yêu cầu: tmux
#   macOS : brew install tmux
#   Ubuntu: sudo apt install tmux
#
# Usage:
#   ./port-forward.sh              # profile: core
#   ./port-forward.sh dev
#   ./port-forward.sh all

set -euo pipefail

PROFILE="${1:-core}"

declare -a CORE_NAMES=("labeling-front" "api" "mlflow" "grafana")
declare -a CORE_FWDS=("svc/labeling-frontend 3001:3000" "svc/api-service 8000:8000" "svc/mlflow-service 5000:5000" "svc/grafana-service 3000:3000")

declare -a DEV_NAMES=("postgres" "minio-s3" "labeling-back" "minio-console")
declare -a DEV_FWDS=("svc/labeling-postgres 5432:5432" "svc/minio-service 9000:9000" "svc/labeling-backend 8001:8001" "svc/minio-service 9001:9001")

declare -a NAMES=()
declare -a FWDS=()

case "$PROFILE" in
    core)
        NAMES=("${CORE_NAMES[@]}")
        FWDS=("${CORE_FWDS[@]}")
        ;;
    dev)
        NAMES=("${DEV_NAMES[@]}")
        FWDS=("${DEV_FWDS[@]}")
        ;;
    all)
        NAMES=("${CORE_NAMES[@]}" "${DEV_NAMES[@]}")
        FWDS=("${CORE_FWDS[@]}" "${DEV_FWDS[@]}")
        ;;
    *)
        echo "ERROR: Profile khong hop le: $PROFILE"
        echo "       Chon: core | dev | all"
        exit 1
        ;;
esac

if ! command -v tmux &>/dev/null; then
    echo "ERROR: tmux chua duoc cai."
    echo "  macOS : brew install tmux"
    echo "  Ubuntu: sudo apt install tmux"
    exit 1
fi

mk_status=$(minikube status --format="{{.Host}}" 2>/dev/null || true)
if [ "$mk_status" != "Running" ]; then
    echo "ERROR: Minikube chua chay. Chay: minikube start"
    exit 1
fi

tmux kill-session -t mlops 2>/dev/null || true

echo "Profile: $PROFILE (${#NAMES[@]} services)"

first=true
for i in "${!NAMES[@]}"; do
    name="${NAMES[$i]}"
    fwd="${FWDS[$i]}"
    if $first; then
        tmux new-session -d -s mlops -n "$name"
        tmux send-keys -t "mlops:$name" "kubectl port-forward -n mlops $fwd" Enter
        first=false
    else
        tmux new-window -t mlops -n "$name"
        tmux send-keys -t "mlops:$name" "kubectl port-forward -n mlops $fwd" Enter
    fi
done

tmux select-window -t mlops:0

echo ""
case "$PROFILE" in
    core)
        echo "  Labeling Tool : http://localhost:3001"
        echo "  API /predict  : http://localhost:8000/docs"
        echo "  MLflow        : http://localhost:5000"
        echo "  Grafana       : http://localhost:3000"
        ;;
    dev)
        echo "  PostgreSQL    : localhost:5432"
        echo "  MinIO S3 API  : http://localhost:9000"
        echo "  Labeling API  : http://localhost:8001"
        echo "  MinIO Console : http://localhost:9001"
        ;;
    all)
        echo "  Labeling Tool : http://localhost:3001"
        echo "  API /predict  : http://localhost:8000/docs"
        echo "  MLflow        : http://localhost:5000"
        echo "  Grafana       : http://localhost:3000"
        echo "  PostgreSQL    : localhost:5432"
        echo "  MinIO S3 API  : http://localhost:9000"
        echo "  Labeling API  : http://localhost:8001"
        echo "  MinIO Console : http://localhost:9001"
        ;;
esac

echo ""
echo "Chuyen tab: Ctrl+B so | Detach: Ctrl+B D | Tat het: tmux kill-session -t mlops"
echo ""

tmux attach -t mlops
