#!/usr/bin/env bash
set -euo pipefail
export MODEL_CACHE="${MODEL_CACHE:-/workspace/model-cache}"
export QWEN_MODEL="${QWEN_MODEL:-Qwen/Qwen3-8B}"
export QWEN_HOST="${QWEN_HOST:-127.0.0.1}"
export QWEN_PORT="${QWEN_PORT:-8000}"
export QWEN_TENSOR_PARALLEL_SIZE="${QWEN_TENSOR_PARALLEL_SIZE:-1}"
export QWEN_GPU_MEMORY_UTILIZATION="${QWEN_GPU_MEMORY_UTILIZATION:-0.85}"
export QWEN_MAX_MODEL_LEN="${QWEN_MAX_MODEL_LEN:-8192}"
bash scripts/start_qwen_vllm.sh
