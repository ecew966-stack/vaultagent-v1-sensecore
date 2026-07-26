# Trae / 本地开发流程

```bash
cp .env.example .env
bash scripts/bootstrap.sh
pytest
python scripts/doctor.py
python scripts/smoke_test.py
```

开发阶段保持：

```env
VAULTAGENT_ALLOW_MOCK_MODELS=true
VAULTAGENT_LOCAL_ENABLED=false
VAULTAGENT_CLOUD_ENABLED=false
```

优先修改：

- `src/knowledge/labeling.py`
- `src/disclosure/relations.py`
- `src/agent/task_graph.py`
- `src/agent/slot_binder.py`
- `src/security/final_output_guard.py`
- `experiments/`

接入 DeepSeek 时先只用合成数据，检查 `trace.cloud_payload` 不含原始值。接入 Qwen 后再把 `LOCAL_REQUIRED` 设为 true。

正式配置：

```env
VAULTAGENT_ENVIRONMENT=production
VAULTAGENT_ALLOW_MOCK_MODELS=false
VAULTAGENT_ENABLE_EXPERIMENT_OVERRIDES=false
```
