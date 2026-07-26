# 上机前验收清单

- [ ] `.env` 未提交 Git
- [ ] 生产环境 Mock=false
- [ ] 生产环境 Experiment Overrides=false
- [ ] Qwen `/v1/models` 可访问
- [ ] Qwen 端口未暴露公网
- [ ] DeepSeek Key 用 Secret 注入
- [ ] doctor 通过
- [ ] pytest 通过
- [ ] smoke test 通过
- [ ] Mode 2/3 Payload 无原始值
- [ ] 非法 Slot 被拒绝
- [ ] 伪造、跨任务、过期 Token 被拒绝
- [ ] Prompt Injection 触发 Local Only
- [ ] 最终输出无 Token
- [ ] Audit Chain 有效
- [ ] 首轮只使用合成数据
- [ ] 已记录 GPU、镜像、模型、Prompt、Policy 和 Git
