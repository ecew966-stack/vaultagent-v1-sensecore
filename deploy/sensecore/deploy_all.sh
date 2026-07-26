#!/usr/bin/env bash
set -euo pipefail

export VAULTAGENT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
export MODEL_CACHE="${MODEL_CACHE:-/workspace/model-cache}"
export STATE_DIR="${STATE_DIR:-/workspace/vaultagent-state}"
export LOG_DIR="${LOG_DIR:-$VAULTAGENT_ROOT/logs}"

mkdir -p "$MODEL_CACHE" "$STATE_DIR" "$LOG_DIR"

echo "============================================"
echo "  VaultAgent 远程算力平台部署脚本               "
echo "============================================"
echo ""

echo "[1/5] 检查 Python 环境..."
if ! command -v python3.11 &> /dev/null; then
    echo "  警告: python3.11 未找到，使用 python3"
    PYTHON=python3
else
    PYTHON=python3.11
fi

echo "[2/5] 创建虚拟环境..."
if [ ! -d "$VAULTAGENT_ROOT/.venv" ]; then
    echo "  创建主虚拟环境..."
    "$PYTHON" -m venv "$VAULTAGENT_ROOT/.venv"
fi

if [ ! -d "$VAULTAGENT_ROOT/.venv-vllm" ]; then
    echo "  创建 vLLM 虚拟环境..."
    "$PYTHON" -m venv "$VAULTAGENT_ROOT/.venv-vllm"
fi

echo "[3/5] 安装依赖..."
source "$VAULTAGENT_ROOT/.venv/bin/activate"
echo "  安装 VaultAgent..."
pip install -e ".[dev,demo]" --quiet

source "$VAULTAGENT_ROOT/.venv-vllm/bin/activate"
echo "  安装 vLLM..."
pip install vllm torch --quiet

echo "[4/5] 配置环境..."
if [ ! -f "$VAULTAGENT_ROOT/.env" ]; then
    echo "  复制配置文件..."
    cp "$VAULTAGENT_ROOT/.env.sensecore" "$VAULTAGENT_ROOT/.env"
    echo "  提示: 请编辑 .env 文件配置你的 API 密钥"
fi

echo "[5/5] 启动服务..."

echo ""
echo "============================================"
echo "  服务启动信息                                 "
echo "============================================"
echo ""
echo "  本地模型 (vLLM):  http://127.0.0.1:8000/v1"
echo "  VaultAgent API:   http://0.0.0.0:8080"
echo "  数据流监控:       http://0.0.0.0:8501"
echo ""
echo "============================================"

source "$VAULTAGENT_ROOT/.venv-vllm/bin/activate"
bash "$VAULTAGENT_ROOT/scripts/start_qwen_vllm.sh" &
echo "  vLLM 服务已启动 (PID: $!)"

sleep 10

source "$VAULTAGENT_ROOT/.venv/bin/activate"
bash "$VAULTAGENT_ROOT/scripts/start_api.sh" &
echo "  VaultAgent API 已启动 (PID: $!)"

echo ""
echo "所有服务已启动！按 Ctrl+C 停止。"
trap "echo '正在停止服务...'; kill %1 %2 2>/dev/null; exit 0" SIGINT
wait