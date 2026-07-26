# 代码与系统架构

```text
Task
 -> Controller
 -> Retrieval
 -> Atomizer + Relation Extractor
 -> Task Graph
 -> Router
    -> Mode 1 LocalExecutor(Qwen)
    -> Mode 2 TaskContract -> DeepSeek Planner -> Validator
              -> SlotBinder -> LocalExecutor(Qwen)
    -> Mode 3 Projector -> Compiler -> OutboundMonitor
              -> DeepSeek Reasoner -> Validator
              -> Token Vault Rehydration -> LocalExecutor(Qwen)
 -> FinalOutputGuard
 -> AuditChain
```

可信域：Controller、Qwen/vLLM、本地知识库、Token Vault、Reference Monitor、Slot Binder 和 Audit。

不可信：DeepSeek 输出、网页/上传文件中的指令、外部 Token、模型工具请求和跨任务结果。
