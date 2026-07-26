# 商汤大装置部署说明

## 推荐拓扑

```text
SenseCore GPU Node / Trusted VPC
├── Qwen + vLLM       127.0.0.1:8000
├── VaultAgent API    0.0.0.0:8080
├── Streamlit Demo    0.0.0.0:8501
├── Token Vault
└── Audit / results

External
└── DeepSeek HTTPS API
```

Qwen 端口只允许 localhost 或可信 VPC。DeepSeek 需要出站 HTTPS 权限。

## 部署

```bash
unzip vaultagent-v0.2-sensecore.zip
cd vaultagent-v0.2-sensecore
cp .env.sensecore.example .env

mkdir -p /workspace/model-cache
mkdir -p /workspace/vaultagent-state
mkdir -p /workspace/vaultagent-results

python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,demo]"

python3.11 -m venv .venv-vllm
source .venv-vllm/bin/activate
pip install -r requirements-vllm.txt
```

启动 Qwen：

```bash
source .venv-vllm/bin/activate
export MODEL_CACHE=/workspace/model-cache
bash deploy/sensecore/start_qwen_gpu_node.sh
```

检查：

```bash
curl http://127.0.0.1:8000/v1/models
```

启动应用：

```bash
source .venv/bin/activate
python scripts/doctor.py
pytest
python scripts/smoke_test.py
bash scripts/start_api.sh
```

另一个终端：

```bash
source .venv/bin/activate
bash scripts/start_demo.sh
```

多 GPU 时设置 `QWEN_TENSOR_PARALLEL_SIZE`。它必须与实际分配的 GPU 数量一致。

`vllm_qwen.sbatch` 是 Slurm/SCC 模板，必须按账号修改分区、GPU 资源、CPU、内存、时长、环境和端口策略。

模型缓存、状态和实验结果应放在持久存储。不要用真实未成年人数据做首次上机测试。
