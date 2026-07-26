# 安全模型

已实施：

1. 云端输入必须经过 OutboundMonitor；
2. 私有原始 Atom 出现在 Payload 时拒绝；
3. SECRET 默认 BLOCK；
4. Token 使用任务密钥派生；
5. 映射使用 AES-256-GCM；
6. 云端结果必须回显 Task ID 和 Delegation ID；
7. 未知、过期、跨任务、错误位置 Token 拒绝恢复；
8. 云端不得增加字段、操作或 Slot；
9. 恢复只在本地；
10. 最终答案不得残留 Token；
11. 安全异常逐级回退，不追加原始上下文；
12. 审计日志使用哈希链。

不能声称：阻止所有语义推断、NER 零漏检、绝对不可关联、本地系统失陷后仍安全、模型不会幻觉、Exposure Score 已科学校准。
