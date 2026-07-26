# 常见问题

`/ready` 503：运行 `python scripts/doctor.py`，检查 `curl 127.0.0.1:8000/v1/models`。

vLLM CUDA 报错：vLLM、PyTorch、CUDA Driver 必须匹配，优先使用商汤验证过的镜像。

模型名不存在：`.env` 的 `LOCAL_MODEL` 必须与 vLLM `served-model-name` 一致。

DeepSeek 失败：检查 EIP/NAT、API Key、Base URL、模型名和 429。失败时系统回退，不追加私有原文。

Mode 3 回退：检查 SECRET、原始 Atom、JSON Schema、Token TTL、Delegation ID 和 Exposure Budget。
