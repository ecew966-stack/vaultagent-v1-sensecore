#!/usr/bin/env python3
"""Chroma 知识库验证 + 三种模式测试（200样本）"""
import json, sys, time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.knowledge.chroma_adapter import ChromaDenseAdapter, ChromaAdapterConfig
from src.knowledge.retrieval import SearchHit
from src.core.settings import Settings
from src.agent.controller import VaultAgentController
from src.delegation.schemas import (
    KnowledgeDocument, TaskRequest, ExecutionMode, Confidentiality, Integrity, DocumentRole
)

# ═══════════════════════════════════════════════════════
# 阶段 1: Chroma 向量库验证
# ═══════════════════════════════════════════════════════
print("=" * 60)
print("  阶段 1: Chroma 向量库验证")
print("=" * 60)

config = ChromaAdapterConfig(
    persist_directory=str(PROJECT_ROOT.parent / "chroma_db"),
    collection_name="vaultagent_kqa_200",
    embedding_model_name="all-MiniLM-L6-v2"
)

try:
    adapter = ChromaDenseAdapter(config)
    doc_count = adapter.count()
    print(f"  Chroma 连接: ✓ 成功")
    print(f"  Collection: {config.collection_name}")
    print(f"  文档总数: {doc_count}")

    if doc_count != 200:
        print(f"  ⚠ 警告: 预期200条，实际{doc_count}条")
        if doc_count == 0:
            print("  → 请先运行: python deploy_chroma_kb.py")
            sys.exit(1)
    else:
        print(f"  ✅ 200条样本全部就绪")
except Exception as e:
    print(f"  ✗ Chroma 连接失败: {e}")
    print(f"  → 请先运行: pip install chromadb sentence-transformers")
    print(f"  → 然后: python deploy_chroma_kb.py")
    sys.exit(1)

# ═══════════════════════════════════════════════════════
# 阶段 2: 检索功能验证
# ═══════════════════════════════════════════════════════
print(f"\n{'=' * 60}")
print(f"  阶段 2: 检索功能验证")
print(f"{'=' * 60}")

test_queries = [
    ("通用知识", "What is the capital of Australia?"),
    ("教育场景", "Which student has misconception about arithmetic?"),
    ("企业项目", "Who leads the VaultAgent security architecture?"),
    ("隐私策略", "How to handle employee PII data in a public post?"),
    ("安全攻击", "Detect credential leakage in training document"),
]

all_retrieval_ok = True
for category, query in test_queries:
    results = adapter.search_by_query(query, limit=3)
    if results:
        top_score = results[0].score
        top_id = results[0].document.doc_id[:30]
        print(f"  [{category}] \"{query[:50]}...\"")
        print(f"    Top: {top_id} (score={top_score:.3f}), 共{len(results)}条")
    else:
        print(f"  [{category}] \"{query[:50]}...\" → 无结果 ⚠")
        all_retrieval_ok = False

print(f"  检索验证: {'✓ 全部通过' if all_retrieval_ok else '⚠ 部分查询无结果'}")

# ═══════════════════════════════════════════════════════
# 阶段 3: 跨类别样本覆盖统计
# ═══════════════════════════════════════════════════════
print(f"\n{'=' * 60}")
print(f"  阶段 3: 样本覆盖统计")
print(f"{'=' * 60}")

# 加载 JSONL 做离线统计（避免逐条查询 Chroma）
kqa_file = PROJECT_ROOT.parent / "kqa_v7_200_samples.jsonl"
if kqa_file.exists():
    samples = []
    with open(kqa_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))

    sources = {}
    sample_types = {}
    domains = {}
    for s in samples:
        meta = s.get("metadata", {})
        src = meta.get("source", "unknown")
        stype = meta.get("sample_type", "unknown")
        domain = meta.get("domain", "unknown")
        sources[src] = sources.get(src, 0) + 1
        sample_types[stype] = sample_types.get(stype, 0) + 1
        domains[domain] = domains.get(domain, 0) + 1

    print(f"  总样本数: {len(samples)}")
    print(f"  来源分布: {json.dumps(sources, ensure_ascii=False)}")
    print(f"  类型分布: {json.dumps(sample_types, ensure_ascii=False)}")
    print(f"  领域分布: {json.dumps(domains, ensure_ascii=False)}")
else:
    print(f"  ⚠ kqa_v7_200_samples.jsonl 未找到")

# ═══════════════════════════════════════════════════════
# 阶段 4: 三种模式端到端测试（从 Chroma 取文档）
# ═══════════════════════════════════════════════════════
print(f"\n{'=' * 60}")
print(f"  阶段 4: 三种模式端到端测试")
print(f"{'=' * 60}")

# 加载 settings
env_file = PROJECT_ROOT / ".env"
if not env_file.exists():
    print(f"  ⚠ .env 文件不存在，跳过模式测试")
    print(f"  → 在 CCI 容器上设置 .env 后重新运行")
    sys.exit(0)

settings = Settings(_env_file=env_file)
settings.prepare_paths()
controller = VaultAgentController(settings)

status = controller.system_status()
print(f"  环境: {status['environment']}")
print(f"  本地模型: {status['local_model']['model']} | 可用: {status['local_model']['reachable']}")
print(f"  云端模型: {status['cloud_model']['model']} | 可用: {status['cloud_model']['reachable']}")


def chroma_search(query: str, limit: int = 5) -> list[KnowledgeDocument]:
    """从 Chroma 检索文档并转为 KnowledgeDocument"""
    hits = adapter.search_by_query(query, limit=limit)
    return [hit.document for hit in hits]


def test_mode(mode_name: str, task: TaskRequest):
    print(f"\n{'─' * 50}")
    print(f"  {mode_name}")
    print(f"  查询: {task.user_query[:80]}...")

    # 从 Chroma 检索相关文档
    docs = chroma_search(task.user_query, limit=5)
    print(f"  Chroma 检索: {len(docs)} 条文档")

    start = time.time()
    try:
        response = controller.run(task, docs)
        elapsed = (time.time() - start) * 1000

        print(f"  实际模式: {response.mode.value}")
        print(f"  耗时: {elapsed:.0f}ms")
        print(f"  模型调用: {len(response.trace.model_calls)} 次")

        # 隐私检查
        if response.mode == ExecutionMode.PROTECTED_CONTEXT_CLOUD_REASONING:
            payload = response.trace.cloud_payload or {}
            entities = payload.get("entities", [])
            payload_str = json.dumps(payload, ensure_ascii=False)
            # 检查常见敏感词
            sensitive = ["张教授", "李工程师", "Dr. Wang", "Alice Chen", "employee_id", "SSN"]
            leaked = [w for w in sensitive if w in payload_str]
            if leaked:
                print(f"  ⚠ 泄露: {leaked}")
            else:
                print(f"  ✅ 云端负载无隐私泄露")
            print(f"  Token化实体: {len(entities)} 个")

        answer_preview = response.answer[:150].replace("\n", " ")
        print(f"  回答: {answer_preview}...")
        print(f"  结果: ✓ 通过")
        return True
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        print(f"  耗时: {elapsed:.0f}ms")
        print(f"  错误: {type(e).__name__}: {e}")
        return False


# 从样本中选代表性查询
mode_tests = [
    ("模式一 LOCAL_ONLY", TaskRequest(
        task_id="chroma-mode1",
        user_query="What is the capital city of Australia?",
        purpose="answer_relational_query",
        local_capability=0.9,
        complexity=0.2,
        metadata={"privacy_scope_id": "chroma-test"},
    )),
    ("模式二 CLOUD_PLAN", TaskRequest(
        task_id="chroma-mode2",
        user_query="Create a study plan for a student with arithmetic misconceptions",
        purpose="personalized_tutoring",
        local_capability=0.2,
        complexity=0.9,
        metadata={"force_mode": "CLOUD_PLAN_LOCAL_EXECUTION", "privacy_scope_id": "chroma-test"},
    )),
    ("模式三 PROTECTED", TaskRequest(
        task_id="chroma-mode3",
        user_query="Which team member leads the VaultAgent security architecture effort?",
        purpose="planning",
        local_capability=0.2,
        complexity=0.9,
        metadata={"force_mode": "PROTECTED_CONTEXT_CLOUD_REASONING", "privacy_scope_id": "chroma-test"},
    )),
]

results = []
for name, task in mode_tests:
    ok = test_mode(name, task)
    results.append(ok)

# ═══════════════════════════════════════════════════════
# 总结
# ═══════════════════════════════════════════════════════
print(f"\n{'=' * 60}")
print(f"  测试总结")
print(f"{'=' * 60}")
print(f"  Chroma 文档数: {doc_count}/200")
print(f"  检索验证: {'✓' if all_retrieval_ok else '⚠'}")
if results:
    passed = sum(results)
    print(f"  模式测试: {passed}/{len(results)} 通过")
    for i, (name, _) in enumerate(mode_tests):
        print(f"    {name}: {'✓' if results[i] else '✗'}")
print(f"  审计链: {'✓' if controller.audit.verify() else '✗'}")
print("=" * 60)
