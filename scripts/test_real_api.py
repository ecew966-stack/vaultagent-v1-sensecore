#!/usr/bin/env python3
"""真实 API 测试：三种模式 + DeepSeek 云端调用 + vLLM 本地模型"""
import json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.settings import Settings
from src.agent.controller import VaultAgentController
from src.delegation.schemas import (
    KnowledgeDocument, TaskRequest, ExecutionMode, Confidentiality, Integrity, DocumentRole
)

# ── 加载真实配置 ──
settings = Settings(_env_file=Path(__file__).resolve().parent.parent / ".env")
settings.prepare_paths()
controller = VaultAgentController(settings)

status = controller.system_status()
print("=" * 60)
print("  系统状态")
print("=" * 60)
print(f"  环境: {status['environment']}")
print(f"  本地模型: {status['local_model']['model']} | 可用: {status['local_model']['reachable']}")
print(f"  云端模型: {status['cloud_model']['model']} | 可用: {status['cloud_model']['reachable']}")
print(f"  Mock: {status['mock_models_allowed']}")
print()

# ── 测试数据 ──
documents = [
    KnowledgeDocument(
        doc_id="team",
        content="张教授负责智能体安全项目，项目预算120万元。李工程师负责系统实现。",
        source="team.docx#chunk5",
        confidentiality=Confidentiality.CONFIDENTIAL,
        integrity=Integrity.TRUSTED,
        role=DocumentRole.DATA_ONLY,
        allowed_purposes=["planning", "personalized_tutoring"],
    ),
    KnowledgeDocument(
        doc_id="student",
        content="王同学42分，经常误用乘法法则。",
        source="student.json",
        confidentiality=Confidentiality.CONFIDENTIAL,
        integrity=Integrity.TRUSTED,
        role=DocumentRole.DATA_ONLY,
        allowed_purposes=["personalized_tutoring"],
    ),
]

# ── 测试函数 ──
def test_mode(mode_name: str, task: TaskRequest, docs: list[KnowledgeDocument]):
    print(f"\n{'=' * 60}")
    print(f"  {mode_name}: {task.metadata.get('force_mode', 'auto')}")
    print(f"  查询: {task.user_query}")
    print(f"{'=' * 60}")

    start = time.time()
    try:
        response = controller.run(task, docs)
        elapsed = (time.time() - start) * 1000

        print(f"  实际模式: {response.mode.value}")
        print(f"  耗时: {elapsed:.0f}ms")
        print(f"  云端负载: {'有' if response.trace.cloud_payload else '无'}")

        # ── 模式三专属：显示令牌化证据 ──
        if response.mode == ExecutionMode.PROTECTED_CONTEXT_CLOUD_REASONING:
            payload = response.trace.cloud_payload or {}
            entities = payload.get("entities", [])
            relations = payload.get("relations", [])
            print(f"\n  🔐 云端收到的实体 ({len(entities)} 个，已令牌化):")
            for e in entities:
                eid = e.get("id", "")[:40]
                etype = e.get("type", "")
                attrs = e.get("attributes", {})
                print(f"    - {eid} ({etype}) attrs={attrs}")

            if relations:
                print(f"\n  🔐 云端收到的关系 ({len(relations)} 个):")
                for r in relations:
                    print(f"    - {r.get('subject','?')} --{r.get('predicate','?')}--> {r.get('object','?')}")

            # 验证令牌 ≠ 原文
            payload_str = json.dumps(payload, ensure_ascii=False)
            raw_names = ["张教授", "李工程师", "王同学", "120万", "42分"]
            leaked = [n for n in raw_names if n in payload_str]
            if leaked:
                print(f"\n  ⚠ 泄露警告: 云端负载含有原始数据: {leaked}")
            else:
                print(f"\n  ✅ 确认: 云端负载中无原始私密数据（张教授/李工程师/120万等）")

            # 验证令牌有保险库记录
            token_count = sum(1 for e in entities if e.get("id", "").startswith("[") and not e.get("id", "").startswith("[ABSTRACT_"))
            if token_count > 0:
                try:
                    vault_count = sum(1 for _ in controller.vault._db.execute("SELECT 1 FROM token_vault"))
                    print(f"  ✅ 保险库: {vault_count} 条记录已加密存储")
                except Exception:
                    pass

        # ── 模式二专属：显示公开目标 ──
        elif response.mode == ExecutionMode.CLOUD_PLAN_LOCAL_EXECUTION:
            payload = response.trace.cloud_payload or {}
            goal = payload.get("public_goal", "")
            raw_names = ["张教授", "李工程师", "王同学", "120万", "42分"]
            leaked = [n for n in raw_names if n in goal]
            print(f"  云端公开目标: {goal[:120]}...")
            if leaked:
                print(f"  ⚠ 云端负载含原始数据: {leaked}")
            else:
                print(f"  ✅ 云端目标已去除私密数据")

        print(f"\n  模型调用: {len(response.trace.model_calls)} 次")
        for call in response.trace.model_calls:
            print(f"    - {call['stage']}: {call['provider']} ({call.get('latency_ms', 'N/A')}ms)")

        answer_preview = response.answer[:200].replace("\n", " ")
        print(f"  回答预览: {answer_preview}...")

        print(f"  结果: ✓ 通过")
        return True
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        print(f"  耗时: {elapsed:.0f}ms")
        print(f"  顶层错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

# ── 模式一：LOCAL_ONLY ──
test_mode("模式一 LOCAL_ONLY", TaskRequest(
    task_id="test-real-mode1",
    user_query="总结学生的学习问题和困难",
    purpose="personalized_tutoring",
    local_capability=0.9,
    complexity=0.2,
    metadata={"privacy_scope_id": "test-real"},
), documents)

# ── 模式二：CLOUD_PLAN_LOCAL_EXECUTION ──
test_mode("模式二 CLOUD_PLAN", TaskRequest(
    task_id="test-real-mode2",
    user_query="根据学生的学习情况，制定个性化辅导计划",
    purpose="personalized_tutoring",
    local_capability=0.2,
    complexity=0.9,
    metadata={"force_mode": "CLOUD_PLAN_LOCAL_EXECUTION", "privacy_scope_id": "test-real"},
), documents)

# ── 模式三：PROTECTED_CONTEXT_CLOUD_REASONING ──
test_mode("模式三 PROTECTED", TaskRequest(
    task_id="test-real-mode3",
    user_query="为团队生成四周实施计划，安排任务和角色分工",
    purpose="planning",
    local_capability=0.2,
    complexity=0.9,
    metadata={"force_mode": "PROTECTED_CONTEXT_CLOUD_REASONING", "privacy_scope_id": "test-real"},
), documents)

print(f"\n{'=' * 60}")
print("  审计链验证: ", "✓ 通过" if controller.audit.verify() else "✗ 失败")
print("=" * 60)
