# VaultAgent v0.2

## 面向云端辅助 AI 智能体的本地知识安全委托框架

> **一句话**：VaultAgent 让你在用 DeepSeek 等云端大模型做复杂推理时，本地知识库里的敏感数据（人名、预算、成绩、项目名）不出网，云端只能看到密码学 Token 和保护后的区间值。

---

## 这项目解决什么问题

AI 智能体时代有个死结：**本地小模型能力不够，云端大模型不敢把私有数据发过去**。

现有方案全是坑：
- **纯本地部署**：7B 模型做复杂推理基本废的
- **正则脱敏**：`张教授` → `[MASK]`，云端连这是人还是项目都分不清
- **Prompt 约束**："请不要泄露隐私"——一句话就能绕过去

VaultAgent 的做法：**不靠 Prompt，靠密码学**。HMAC-SHA-256 给每个实体的每个任务生成不同 Token，AES-256-GCM 加密存映射关系，云端拿 Token 做推理但永远解不开真实身份。换个任务同一个人的 Token 就变了，跨任务关联攻击直接废掉。

---

## 三种执行模式

| 模式 | 云端能看到什么 | 什么时候用 |
|------|---------------|-----------|
| **模式一 Local Only** | 什么也看不到 | 有注入攻击 / 数据是 SECRET 级 / 用户不让联网 |
| **模式二 Cloud Planning** | 任务目标 + "这里有个私有 Slot" | 云端出计划，本地拿真实数据执行 |
| **模式三 Protected Context** | `[PERSON_7A3F2B]` + 角色/区间/关系 | 云端在保护视图中推理，本地恢复真相 |

三种模式串行回退——模式三不行降模式二，模式二不行降模式一，**绝不会为了完成任务多泄露一点数据**。

---

## 目录结构

```
vaultagent-v0.2-sensecore/
├── src/
│   ├── agent/             # 智能体控制器（模式路由、任务图、本地执行、Slot绑定）
│   ├── crypto/            # 密码学核心（HKDF密钥派生、HMAC-SHA-256 Token、AES-256-GCM保险库、SHA-256审计链）
│   ├── knowledge/         # 知识处理（11类敏感实体识别/中文人名检测/BM25检索/Reranker重排序）
│   ├── disclosure/        # 披露控制管道（原子化→投影→编译→关系提取→语义抽象）
│   ├── security/          # 六层纵深防御（注入检测/出站监控/重放检测/返回验证/曝光追踪/输出守护）
│   ├── delegation/        # 云端委托（数据模型/CloudPlanner/ProtectedReasoner）
│   ├── models/            # 模型客户端（OpenAI兼容/DeepSeek/Qwen）
│   ├── api/               # FastAPI服务（17个端点，5级降级策略）
│   └── core/              # 配置（Settings/策略加载器）
├── frontend/              # React + TypeScript 前端（7个页面）
├── demo/                  # Streamlit 快速演示
├── data/                  # 数据集（14篇知识库 + 10个正常任务 + 7个攻击用例）
├── tests/                 # 30个自动化测试用例
├── configs/               # YAML配置（模型/策略/实验/部署）
├── deploy/                # SenseCore / Slurm 部署模板
├── scripts/               # 运维脚本
├── pyproject.toml
└── 项目.md                # 完整项目方案（2200+行）
```

---

## 快速开始

```bash
# 1. 环境
cp .env.example .env
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev,demo]"

# 2. 测试
pytest                              # 30/30 全部通过

# 3. 启动后端 API
uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# 4. 启动前端（新终端）
cd frontend && npm install && npm run dev
# 打开 http://localhost:5173

# 5. 或启动 Streamlit Demo（新终端）
streamlit run demo/app.py
```

默认使用 **Mock 模式**（`allow_mock_models=true`），不连真实模型也能跑通完整管道。替换 `.env` 中的 API Key 即可接入真实 DeepSeek。

---

## 核心能力一览

### CSSD 密码学保护管道

```
用户输入 → 实体扫描 → KB交叉验证 → HMAC-SHA-256 Token签发 
→ AES-256-GCM 保险库加密存储 → 保护查询构建 → DeepSeek调用 
→ Token白名单验证 → 保险库授权恢复 → SHA-256审计链记录
```

### 11 类敏感实体识别

| 类型 | 保护策略 | 示例 |
|------|---------|------|
| 人名 | Token化 | 张教授 → `[PERSON_A8F31C]` |
| 项目/组织 | Token化 | 智能体安全项目 → `[ORG_29D13E]` |
| 金额 | 区间化 ±20% | 120万元 → 96-144万元 |
| 分数/评分 | 区间化 ±15分 | 42分 → 27-57分 |
| 手机/邮箱/身份证/密码/疾病/地址 | **阻断** | 直接不出网 |

500+ 中文姓氏检测 + 100+ 防误判词表 + 粒子剥离。

### 六层纵深防御

注入扫描 → 模式路由 → 披露投影 → 出站监控 → 返回验证 → 输出守护  
**六道硬安全门，一道不通过数据就出不去。**

### 30 个自动化测试全通过

- 密码学模块：Token 稳定性 / 跨任务隔离 / Vault 拒绝跨任务恢复
- 安全模块：15 项攻击测试（注入/伪造/过期/重放/越权等全部阻断）
- 端到端：模式三云端 Payload 零原始值泄漏

---

## 启用真实模型

```env
# DeepSeek（云端，不可信域）
VAULTAGENT_CLOUD_ENABLED=true
VAULTAGENT_CLOUD_API_KEY=sk-xxxxxxxx
VAULTAGENT_CLOUD_MODEL=deepseek-v4-flash

# Qwen + vLLM（本地，可信域）
VAULTAGENT_LOCAL_ENABLED=true
VAULTAGENT_LOCAL_BASE_URL=http://127.0.0.1:8000/v1
VAULTAGENT_LOCAL_MODEL=Qwen/Qwen3-8B
```

---

## 商汤大装置部署

```bash
# GPU 节点启动 Qwen
bash deploy/sensecore/start_qwen_gpu_node.sh

# 部署全部服务
bash deploy/sensecore/deploy_all.sh
```

详见 `deploy/sensecore/` 和 `configs/deployment.sensecore.yaml`。

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端框架 | FastAPI + Pydantic v2 |
| 密码学 | HMAC-SHA-256 · AES-256-GCM · HKDF-SHA256 · SHA-256 哈希链 |
| 模型推理 | vLLM（本地 Qwen）· DeepSeek API（云端） |
| 知识检索 | BM25 + BGE-Reranker-v2-m3 · Qdrant/ChromaDB（可选） |
| 前端 | React 18 · TypeScript · Tailwind CSS · Framer Motion · Recharts |
| 实验/Demo | Streamlit · KaTeX |
| 部署 | Docker Compose · Slurm · 商汤 CCI |
| Python | 3.11+ · cryptography 库（禁止自研密码） |

---

## 注意事项

- 当前是**研究原型 v0.2**，首轮测试只使用合成数据
- 不应使用真实未成年人或企业隐私数据做首轮测试
- 密码学原语基于 Python `cryptography` 库，禁止替换为自研实现
- Mock 模式下的回答不代表真实模型效果，仅验证管道完整性
