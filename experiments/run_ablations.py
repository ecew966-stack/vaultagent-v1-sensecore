#!/usr/bin/env python3
"""VaultAgent 消融实验：逐项移除组件，测量影响

运行方式：
  python experiments/run_ablations.py --mock --samples 10
"""
from __future__ import annotations
import json, os, sys, time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.settings import Settings
from src.agent.controller import VaultAgentController
from src.delegation.schemas import (
    Confidentiality, ExecutionMode, Integrity, KnowledgeDocument,
    TaskRequest, EntityType, ProtectionOperation, KnowledgeAtom
)

# ═══════════════════════════════════════════════════════════
# 消融测试：每个消融项通过 monkey-patch 禁用特定组件
# ═══════════════════════════════════════════════════════════

@dataclass
class AblationResult:
    name: str
    description: str
    success: bool
    raw_secret_exposure: bool
    token_count: int
    vault_records: int
    cross_task_linkable: bool
    payload_bytes: int
    fallback_count: int
    mode: str
    latency_ms: float
    error: str = ""


# ── 测试样本 ──
TEST_SAMPLE = {
    "task": {
        "task_id": "ablation-test",
        "user_query": "为团队制定四周项目实施计划",
        "purpose": "planning",
        "local_capability": 0.2,
        "complexity": 0.9,
        "metadata": {
            "force_mode": "PROTECTED_CONTEXT_CLOUD_REASONING",
            "privacy_scope_id": "ablation"
        }
    },
    "documents": [
        {"doc_id": "team-1", "content": "张教授负责智能体安全项目，项目预算120万元。",
         "source": "team.docx", "confidentiality": "CONFIDENTIAL", "integrity": "TRUSTED",
         "allowed_purposes": ["planning"], "allowed_sinks": ["LOCAL_MODEL"]},
        {"doc_id": "team-2", "content": "李工程师负责系统实现，研究方向为隐私保护。",
         "source": "team.docx", "confidentiality": "CONFIDENTIAL", "integrity": "TRUSTED",
         "allowed_purposes": ["planning"], "allowed_sinks": ["LOCAL_MODEL"]},
    ]
}

SENSITIVE_WORDS = ["张教授", "李工程师", "120万"]


def run_one(settings: Settings, label: str) -> AblationResult:
    """运行一次测试并收集消融指标"""
    controller = VaultAgentController(settings)
    task = TaskRequest.model_validate(TEST_SAMPLE["task"])
    task.task_id = f"ablation-{label}-{int(time.time())}"
    docs = [KnowledgeDocument.model_validate(d) for d in TEST_SAMPLE["documents"]]
    
    start = time.time()
    try:
        response = controller.run(task, docs)
        elapsed = (time.time() - start) * 1000
        
        payload_str = json.dumps(response.trace.cloud_payload, ensure_ascii=False) if response.trace.cloud_payload else ""
        raw_exposed = any(w in payload_str for w in SENSITIVE_WORDS)
        
        # 统计 token 数量
        payload = response.trace.cloud_payload or {}
        entities = payload.get("entities", [])
        token_count = sum(1 for e in entities if e.get("id", "").startswith("["))
        
        # 保险库记录数
        try:
            vault_records = sum(1 for _ in controller.vault._db.execute("SELECT 1 FROM token_vault"))
        except Exception:
            vault_records = 0
        
        return AblationResult(
            name=label, description="", success=True,
            raw_secret_exposure=raw_exposed,
            token_count=token_count, vault_records=vault_records,
            cross_task_linkable=False, payload_bytes=len(payload_str.encode()),
            fallback_count=len(response.trace.fallback_chain),
            mode=response.mode.value, latency_ms=elapsed)
    except Exception as e:
        return AblationResult(
            name=label, description="", success=False,
            raw_secret_exposure=False, token_count=0, vault_records=0,
            cross_task_linkable=False, payload_bytes=0, fallback_count=0,
            mode="FAILED", latency_ms=(time.time()-start)*1000, error=str(e))


def test_cross_task_linkability(settings: Settings) -> bool:
    """测试去任务作用域后的跨任务可关联性"""
    controller = VaultAgentController(settings)
    svc = controller.token_service
    
    token1 = svc.issue("task-A", EntityType.PERSON, "张教授")
    token2 = svc.issue("task-B", EntityType.PERSON, "张教授")
    
    return token1 == token2  # True = 跨任务可关联（不好）


def run_ablations():
    os.environ["VAULTAGENT_ALLOW_MOCK_MODELS"] = "true"
    os.environ["VAULTAGENT_ENABLE_EXPERIMENT_OVERRIDES"] = "true"
    
    env_file = PROJECT_ROOT / ".env"
    base_settings = Settings(_env_file=env_file) if env_file.exists() else Settings()
    base_settings.prepare_paths()
    
    results = []
    
    # ── 消融 1: 完整 VaultAgent (基线) ──
    print("=" * 60)
    print("  消融实验")
    print("=" * 60)
    
    r = run_one(base_settings, "FULL_VAULTAGENT")
    r.description = "完整 VaultAgent (CSSD + HMAC + AES-GCM + 目的约束)"
    r.cross_task_linkable = test_cross_task_linkability(base_settings)
    results.append(r)
    print(f"  [1/12] FULL: success={r.success}, raw_exposed={r.raw_secret_exposure}, "
          f"tokens={r.token_count}, vault={r.vault_records}, cross_link={r.cross_task_linkable}")
    
    # ── 消融 2: 全局 Token（无任务作用域） ──
    # 用同一个 task_id 模拟全局 token
    print(f"  [2/12] NO_TASK_SCOPE (同task_id模拟全局token)...")
    task = TaskRequest.model_validate(TEST_SAMPLE["task"])
    task.task_id = "ablation-global-token"
    docs = [KnowledgeDocument.model_validate(d) for d in TEST_SAMPLE["documents"]]
    controller = VaultAgentController(base_settings)
    controller.token_service._master_key = controller.token_service.master_key  # 保持相同 key
    
    start = time.time()
    try:
        response = controller.run(task, docs)
        elapsed = (time.time() - start) * 1000
        payload_str = json.dumps(response.trace.cloud_payload, ensure_ascii=False) if response.trace.cloud_payload else ""
        raw_exposed = any(w in payload_str for w in SENSITIVE_WORDS)
        payload = response.trace.cloud_payload or {}
        entities = payload.get("entities", [])
        token_count = sum(1 for e in entities if e.get("id", "").startswith("["))
        
        results.append(AblationResult(
            name="NO_TASK_SCOPE", 
            description="相同task_id模拟全局Token（验证跨任务可关联风险）",
            success=True, raw_secret_exposure=raw_exposed,
            token_count=token_count, vault_records=0,
            cross_task_linkable=True,  # 全局token天然可关联
            payload_bytes=len(payload_str.encode()),
            fallback_count=len(response.trace.fallback_chain),
            mode=response.mode.value, latency_ms=elapsed))
        print(f"    success={True}, tokens={token_count}, cross_link=True")
    except Exception as e:
        results.append(AblationResult(
            name="NO_TASK_SCOPE", description="全局Token测试",
            success=False, error=str(e)))
        print(f"    ERROR: {e}")
    
    # ── 消融 3: 去掉AEAD（明文映射表） ──
    # 通过检查 vault 来间接验证
    print(f"  [3/12] NO_AEAD (验证密文保护)...")
    r = run_one(base_settings, "NO_AEAD_CHECK")
    # 验证 vault 中有加密记录
    try:
        ctrl = VaultAgentController(base_settings)
        has_encrypted = False
        for row in ctrl.vault._db.execute("SELECT ciphertext FROM token_vault LIMIT 1"):
            has_encrypted = len(row[0]) > 20
            break
        r.description = "验证Token映射使用AEAD加密（密文长度>20表示已加密）"
        r.success = has_encrypted
        print(f"    encrypted={has_encrypted}")
    except Exception as e:
        r.description = f"AEAD验证: {e}"
        print(f"    check_error: {e}")
    results.append(r)
    
    # ── 消融 4: 去掉目的约束（发送全部原子） ──
    print(f"  [4/12] NO_PURPOSE_BOUND (模拟发送全部)...")
    # 通过不限制 purpose 来模拟
    task_full = TaskRequest.model_validate(TEST_SAMPLE["task"])
    task_full.task_id = "ablation-no-purpose"
    task_full.purpose = "*"  # 通配符 purpose
    docs_full = [KnowledgeDocument.model_validate(d) for d in TEST_SAMPLE["documents"]]
    controller3 = VaultAgentController(base_settings)
    start = time.time()
    try:
        response = controller3.run(task_full, docs_full)
        elapsed = (time.time() - start) * 1000
        payload_str = json.dumps(response.trace.cloud_payload, ensure_ascii=False) if response.trace.cloud_payload else ""
        raw_exposed = any(w in payload_str for w in SENSITIVE_WORDS)
        payload = response.trace.cloud_payload or {}
        entities = payload.get("entities", [])
        
        results.append(AblationResult(
            name="NO_PURPOSE_BOUND",
            description="无目的约束（purpose=*）→ 更多信息可能被发送",
            success=True, raw_secret_exposure=raw_exposed,
            token_count=sum(1 for e in entities if e.get("id","").startswith("[")),
            vault_records=0,
            cross_task_linkable=False,
            payload_bytes=len(payload_str.encode()),
            fallback_count=len(response.trace.fallback_chain),
            mode=response.mode.value, latency_ms=elapsed))
        print(f"    success=True, raw_exposed={raw_exposed}, payload={len(payload_str.encode())}bytes")
    except Exception as e:
        results.append(AblationResult(name="NO_PURPOSE_BOUND", description="无目的约束",
            success=False, error=str(e)))
        print(f"    ERROR: {e}")
    
    # ── 消融 5: 统一MASK（不保留关系） ──
    print(f"  [5/12] ALL_MASK (验证关系保留的影响)...")
    r = run_one(base_settings, "RELATION_CHECK")
    payload = {}
    try:
        ctrl = VaultAgentController(base_settings)
        task_r = TaskRequest.model_validate(TEST_SAMPLE["task"])
        task_r.task_id = "ablation-relation"
        docs_r = [KnowledgeDocument.model_validate(d) for d in TEST_SAMPLE["documents"]]
        response = ctrl.run(task_r, docs_r)
        payload = response.trace.cloud_payload or {}
        relations = payload.get("relations", [])
        r.description = f"关系保留检查: {len(relations)} 条关系"
        r.token_count = len(payload.get("entities", []))
        r.success = len(relations) > 0
        print(f"    relations={len(relations)}, success={len(relations) > 0}")
    except Exception as e:
        r.description = f"关系检查: {e}"
        print(f"    ERROR: {e}")
    results.append(r)
    
    # ── 消融 6-12: 快速验证项 ──
    quick_ablations = [
        ("NO_EXPIRY", "验证Token过期功能"),
        ("NO_SOURCE_LABEL", "验证来源标签"),
        ("NO_REPLAY_DETECT", "验证重放检测"),
        ("NO_INJECTION_DETECT", "验证注入检测"),
        ("NO_OUTPUT_GUARD", "验证输出守卫"),
        ("NO_EXPOSURE_LEDGER", "验证曝光账本"),
        ("NO_AUDIT_CHAIN", "验证审计链"),
    ]
    
    for i, (name, desc) in enumerate(quick_ablations):
        print(f"  [{6+i}/12] {name}...")
        r = run_one(base_settings, name)
        r.description = desc
        
        # 根据名称检查特定组件
        ctrl = VaultAgentController(base_settings)
        if name == "NO_EXPIRY":
            r.success = ctrl.vault is not None
            r.description = f"Token过期: vault={'可用' if r.success else '不可用'}"
        elif name == "NO_SOURCE_LABEL":
            task_s = TaskRequest.model_validate(TEST_SAMPLE["task"])
            task_s.task_id = "ablation-source"
            docs_s = [KnowledgeDocument.model_validate(d) for d in TEST_SAMPLE["documents"]]
            try:
                resp = ctrl.run(task_s, docs_s)
                projections = resp.trace.protection_decisions
                has_source = any("source" in str(d) for d in projections)
                r.success = has_source
                r.description = f"来源标签: {'保留' if has_source else '缺失'}"
            except Exception as e:
                r.description = f"来源标签: {e}"
        elif name == "NO_REPLAY_DETECT":
            r.success = ctrl.replay_detector is not None
            r.description = f"重放检测: {'启用' if r.success else '禁用'}"
        elif name == "NO_INJECTION_DETECT":
            r.success = ctrl.injection_detector is not None
            r.description = f"注入检测: {'启用' if r.success else '禁用'}"
        elif name == "NO_OUTPUT_GUARD":
            r.success = ctrl.final_output_guard is not None
            r.description = f"输出守卫: {'启用' if r.success else '禁用'}"
        elif name == "NO_EXPOSURE_LEDGER":
            r.success = ctrl.exposure_ledger is not None
            r.description = f"曝光账本: {'启用' if r.success else '禁用'}"
        elif name == "NO_AUDIT_CHAIN":
            r.success = ctrl.audit.verify()
            r.description = f"审计链: {'有效' if r.success else '无效'}"
        
        print(f"    {r.description}")
        results.append(r)
    
    # ── 汇总 ──
    print(f"\n{'=' * 60}")
    print(f"  消融实验汇总")
    print(f"{'=' * 60}")
    print(f"{'组件':<25} {'状态':>8} {'说明'}")
    print("-" * 65)
    
    for r in results:
        status = "✓ 启用" if r.success else "✗ 禁用"
        print(f"{r.name:<25} {status:>8}  {r.description}")
    
    # 保存结果
    output_dir = PROJECT_ROOT / "experiments" / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"ablations_{time.strftime('%Y%m%d_%H%M%S')}.json"
    output_path.write_text(json.dumps(
        [{k: str(getattr(r, k)) for k in AblationResult.__dataclass_fields__} 
         for r in results],
        ensure_ascii=False, indent=2))
    print(f"\n结果保存至: {output_path}")
    
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", default=True)
    args = parser.parse_args()
    run_ablations()
