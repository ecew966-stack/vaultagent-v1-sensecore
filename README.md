# VaultAgent v0.2 — Qwen Local + DeepSeek Cloud + SenseCore

本版本面向“先在 Trae 补充代码，再部署到商汤大装置”的工作流。Qwen 小模型通过 vLLM 部署在本地电脑、实验室服务器或商汤 GPU 节点；DeepSeek API 只接收 Mode 2 的抽象任务合同或 Mode 3 的保护上下文。原始知识、Token Vault、恢复和最终私有化生成保留在可信域。

## 已完成

- 三种执行模式和逐级回退；
- Qwen 本地 OpenAI-compatible 客户端；
- DeepSeek API JSON 客户端；
- Task Graph、Private Slot Binder；
- 知识原子化和规则关系抽取；
- 六种保护操作；
- HKDF、HMAC 任务 Token、AES-GCM Token Vault；
- Delegation ID、持久化重放检测；
- 出站 Reference Monitor、Exposure Ledger；
- 本地恢复、最终输出检查、哈希链审计；
- FastAPI、Streamlit、CLI、Docker、SenseCore/Slurm 模板；
- 正常任务、攻击任务、自动测试。

## Trae 中先运行

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,demo]"
pytest
python scripts/doctor.py
python scripts/smoke_test.py
uvicorn src.api.main:app --host 0.0.0.0 --port 8080
```

另开终端：

```bash
streamlit run demo/app.py
```

默认使用 Mock 模型，只验证流程，不代表真实模型效果。

## 启动本地 Qwen

GPU 机器上：

```bash
bash scripts/start_qwen_vllm.sh
```

`.env`：

```env
VAULTAGENT_LOCAL_ENABLED=true
VAULTAGENT_LOCAL_REQUIRED=true
VAULTAGENT_LOCAL_BASE_URL=http://127.0.0.1:8000/v1
VAULTAGENT_LOCAL_MODEL=Qwen/Qwen3-8B
```

## 启用 DeepSeek

```env
VAULTAGENT_CLOUD_ENABLED=true
VAULTAGENT_CLOUD_API_KEY=你的密钥
VAULTAGENT_CLOUD_MODEL=deepseek-v4-flash
```

## 商汤大装置

按顺序阅读：

1. `docs/00_CURRENT_STATUS.md`
2. `docs/02_SENSECORE_DEPLOYMENT.md`
3. `deploy/sensecore/README.md`
4. `docs/09_ACCEPTANCE_CHECKLIST.md`

运行：

```bash
python scripts/doctor.py
python scripts/smoke_test.py
pytest
```

当前仍是研究原型，不应使用真实未成年人或企业隐私数据做首轮测试。
