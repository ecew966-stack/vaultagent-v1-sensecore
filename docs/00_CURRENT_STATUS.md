# 当前代码包括什么、还缺什么

## 已完成

VaultAgent v0.2 已形成可执行研究骨架：三种执行模式、Qwen 本地客户端、DeepSeek 云端客户端、严格 JSON 协议、Task Graph、Slot Binder、知识原子化、规则关系抽取、目的约束投影、任务作用域 HMAC Token、HKDF、AES-256-GCM Token Vault、Delegation ID、持久化重放检测、出站 Reference Monitor、Exposure Ledger、本地恢复、最终输出检查、哈希链审计、FastAPI、Streamlit、CLI、Docker、SenseCore/Slurm 模板、正常任务、攻击任务和自动测试。

本地 Qwen 与 DeepSeek 均通过 OpenAI-compatible HTTP 接口连接。开发阶段可使用确定性 Mock；正式实验必须关闭 Mock。Mode 2 的 DeepSeek 只接收公开目标、抽象状态和 Slot 名；Mode 3 只接收 Token、允许属性、允许关系和抽象值。恢复后的真实内容只交给本地 Qwen。

## 当前残缺

1. 敏感识别仍以规则为主，不能覆盖中文姓名歧义、教育隐私和组合敏感信息。
2. 关系抽取为规则原型，尚无复杂句、跨文档关系和共指解析。
3. 默认检索仍是本地 BM25；Qdrant 只提供 adapter，尚未完成 BGE-M3 dense+sparse+reranker。
4. Task Graph 使用模板操作，尚未实现“本地 Qwen 生成候选图 + 规则验证”。
5. Disclosure Necessity 主要依赖类型规则，尚缺 `A_required` 人工金标准。
6. 本地 Qwen 的证据一致性、引用完整性和幻觉评分尚未独立实现。
7. Exposure Ledger 使用启发式风险分数，尚未通过攻击数据校准。
8. DeepSeek/Qwen 的真实效果、吞吐、失败率和费用尚未实测。
9. 商汤 GPU 镜像、CUDA、队列、网络和持久存储需按账号适配。
10. 尚未完成 VaultAgentBench-v0、完整基线、人工评价和统计分析。

## 上机前必须补充

- 教育领域 NER、真实数据 Schema、关系抽取和实验脚本；
- 用合成数据跑通全部测试；
- 确认 CUDA/vLLM/Qwen 兼容；
- 确认 DeepSeek 出站网络和密钥注入；
- 关闭 Mock；
- 运行 doctor、smoke test、pytest；
- 记录模型版本、镜像摘要、GPU、Prompt、Policy 和随机种子。
