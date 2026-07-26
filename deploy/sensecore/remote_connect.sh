#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 2 ]; then
    echo "用法: $0 <远程主机> <远程端口>"
    echo ""
    echo "示例:"
    echo "  $0 user@compute-node.example.com 8000"
    echo "  $0 user@gpu-cluster 8080"
    exit 1
fi

REMOTE_HOST="$1"
REMOTE_PORT="$2"

echo "============================================"
echo "  VaultAgent 远程连接脚本                      "
echo "============================================"
echo ""
echo "  远程主机: $REMOTE_HOST"
echo "  远程端口: $REMOTE_PORT"
echo ""

echo "[1/3] 检查 SSH 连接..."
if ! ssh -q "$REMOTE_HOST" "echo 'SSH 连接成功'" 2>/dev/null; then
    echo "  错误: 无法连接到远程主机"
    echo "  请确保 SSH 密钥已配置"
    exit 1
fi

echo "[2/3] 建立端口转发..."
echo ""
echo "  本地端口映射:"
echo "    本地模型:  http://127.0.0.1:8000/v1  -> 远程 vLLM"
echo "    VaultAgent: http://127.0.0.1:8080     -> 远程 API"
echo ""
echo "  按 Ctrl+C 断开连接"
echo ""

ssh -L 8000:127.0.0.1:8000 -L 8080:127.0.0.1:8080 -N "$REMOTE_HOST"

echo ""
echo "连接已断开"
exit 0