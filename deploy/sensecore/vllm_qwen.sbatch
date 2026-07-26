#!/usr/bin/env bash
#SBATCH --job-name=vaultagent-qwen
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:1
#SBATCH --mem=64G
#SBATCH --time=08:00:00
#SBATCH --output=logs/qwen-%j.out
#SBATCH --error=logs/qwen-%j.err
set -euo pipefail
mkdir -p logs /workspace/model-cache
source .venv-vllm/bin/activate
export MODEL_CACHE=/workspace/model-cache
export QWEN_MODEL="${QWEN_MODEL:-Qwen/Qwen3-8B}"
export QWEN_HOST=0.0.0.0
export QWEN_PORT="${QWEN_PORT:-8000}"
bash scripts/start_qwen_vllm.sh
