# 配置说明

## Qwen

- `LOCAL_ENABLED`：启用本地 Qwen；
- `LOCAL_REQUIRED`：Qwen 不可用时是否失败；
- `LOCAL_BASE_URL`：vLLM `/v1` 地址；
- `LOCAL_MODEL`：与 `served-model-name` 一致；
- `LOCAL_ENABLE_THINKING`：仅在 checkpoint 支持时开启。

## DeepSeek

- `CLOUD_ENABLED`：允许云端委托；
- `CLOUD_API_KEY`：只通过 Secret/环境变量注入；
- `CLOUD_MODEL`：默认 `deepseek-v4-flash`；
- `CLOUD_THINKING`：结构化协议默认关闭，减少格式漂移。

## 策略

`configs/policies.yaml` 控制数据类型、保护操作、Sink、TTL、允许属性和关系、最大步骤及暴露预算。

增加实体类型时必须同步修改 Schema、Labeler、Policy、Abstraction 和测试。
