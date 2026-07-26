#!/usr/bin/env bash
set -euo pipefail
MODEL="${QWEN_MODEL:-Qwen/Qwen3-8B}"
HOST="${QWEN_HOST:-127.0.0.1}"
PORT="${QWEN_PORT:-8000}"
TP="${QWEN_TENSOR_PARALLEL_SIZE:-1}"
GPU_MEMORY="${QWEN_GPU_MEMORY_UTILIZATION:-0.85}"
MAX_MODEL_LEN="${QWEN_MAX_MODEL_LEN:-8192}"
MODEL_CACHE="${MODEL_CACHE:-$HOME/.cache/huggingface}"
mkdir -p "$MODEL_CACHE"
export HF_HOME="$MODEL_CACHE"
[[ "${VLLM_USE_MODELSCOPE:-false}" == "true" ]] && export VLLM_USE_MODELSCOPE=true
command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi || true
command -v vllm >/dev/null 2>&1 || {
  echo "vLLM is not installed. Install a CUDA-compatible build or use its container."
  exit 1
}
exec vllm serve "$MODEL" --host "$HOST" --port "$PORT" \
  --tensor-parallel-size "$TP" --gpu-memory-utilization "$GPU_MEMORY" \
  --max-model-len "$MAX_MODEL_LEN" --served-model-name "$MODEL"
