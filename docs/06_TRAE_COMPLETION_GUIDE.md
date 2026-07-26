# 建议交给 Trae 的后续任务

## P0

1. 增加教育实体：学号、班级、家庭背景、特殊需求、教师反馈、真实错题、课程编号。
2. 每种实体增加正负测试语料。
3. 扩展关系：`struggles_with`、`requires_prerequisite`、`received_feedback`、`improved_on`。
4. LocalExecutor 增加证据引用和缺失证据拒答。
5. DeepSeek JSON 失败只允许一次格式修复，不增加上下文。
6. 增加非法 Slot、Token 注入、Token 残留测试。
7. API 使用稳定错误码且不泄露路径。

## P1

1. BGE-M3 + Qdrant dense/sparse；
2. 本地 Reranker；
3. `A_required` 标注格式；
4. Disclosure Precision/Recall；
5. Static Pseudonym、Typed Placeholder、NER Masking 基线；
6. 攻击批量运行器；
7. 保存模型、Prompt、Git、随机种子、GPU 和耗时；
8. 置信区间和显著性检验。

推荐 Trae 提示词：

“先阅读 README、docs/00_CURRENT_STATUS.md 和 docs/05_SECURITY_MODEL.md。任何修改不得让 DeepSeek 直接访问本地知识库、Token Vault、工具或原始检索结果。新增功能必须有 pytest，安全失败必须 fail closed。”
