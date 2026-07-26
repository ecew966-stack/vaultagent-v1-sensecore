# SenseCore 远程算力平台部署指南

## 架构说明

```
┌──────────────────────┐         SSH 隧道        ┌──────────────────────┐
│      本地开发机       │◄───────────────────────►│     远程算力平台      │
│                      │                         │                      │
│  VaultAgent CLI      │                         │  vLLM (Qwen-7B)      │
│  测试脚本            │                         │  http://127.0.0.1:8000│
│                      │                         │                      │
│  http://127.0.0.1:8000 │─────────────────────►│  VaultAgent API       │
│  http://127.0.0.1:8080  │─────────────────────►│  http://0.0.0.0:8080 │
└──────────────────────┘                         └──────────────────────┘
```

## 部署步骤

### 第一步：在远程算力平台部署

```bash
# 1. 登录远程主机
ssh user@compute-node.example.com

# 2. 克隆项目
git clone <your-repo-url>
cd vaultagent-v0.2-sensecore

# 3. 一键部署
bash deploy/sensecore/deploy_all.sh

# 4. 配置 API 密钥（首次部署后）
vim .env
# 设置 VAULTAGENT_CLOUD_API_KEY=你的 DeepSeek API 密钥
```

### 第二步：本地连接远程服务

```bash
# 建立 SSH 端口转发
bash deploy/sensecore/remote_connect.sh user@compute-node.example.com 8080

# 新开终端，运行测试
python scripts/smoke_test.py
python scripts/doctor.py
```

### 第三步：运行实验

```bash
# 使用远程模型运行实验
python experiments/run_experiment.py \
    --tasks data/unified_dataset.jsonl \
    --unified \
    --baselines LOCAL_ONLY CLOUD_PLAN_LOCAL_EXECUTION PROTECTED_CONTEXT_CLOUD_REASONING
```

## SLURM 批量任务（可选）

```bash
# 修改 sbatch 配置（按实际情况调整）
vim deploy/sensecore/vllm_qwen.sbatch

# 提交任务
sbatch deploy/sensecore/vllm_qwen.sbatch

# 查看任务状态
squeue -u $USER

# 查看日志
cat logs/qwen-<job-id>.out
```

## 环境变量说明

| 变量 | 说明 | 示例值 |
|------|------|--------|
| `MODEL_CACHE` | 模型缓存目录 | `/workspace/model-cache` |
| `STATE_DIR` | 状态存储目录 | `/workspace/vaultagent-state` |
| `QWEN_MODEL` | 本地模型名称 | `Qwen/Qwen3-8B` |
| `QWEN_PORT` | 本地模型端口 | `8000` |
| `VAULTAGENT_CLOUD_API_KEY` | 云端 API 密钥 | `sk-xxx` |

## 安全注意事项

1. **禁止公网暴露**：vLLM 端口（8000）仅绑定 127.0.0.1，通过 SSH 隧道访问
2. **API 密钥保护**：`.env` 文件加入 `.gitignore`，不要提交到版本控制
3. **访问控制**：建议使用 VPN 或内网 IP 访问远程平台
4. **日志审计**：定期检查 `logs/` 目录下的日志文件

## 服务启动清单

| 服务 | 地址 | 用途 |
|------|------|------|
| vLLM | http://127.0.0.1:8000/v1 | 本地模型推理 |
| VaultAgent API | http://0.0.0.0:8080 | 安全委托框架 |
| Streamlit | http://0.0.0.0:8501 | 数据流监控 |
| Qdrant | http://127.0.0.1:6333 | 向量检索（可选） |