"""Quick test: verify _select_mode routes each demo correctly."""
import sys
sys.path.insert(0, ".")

from src.api.routers.tasks import _select_mode, _scan_entities, _filter_entities_by_kb, _load_mock_kb
from src.core.settings import Settings
from unittest.mock import MagicMock

# ── Fake settings that reports cloud as available ──
fake_settings = MagicMock(spec=Settings)
fake_settings.cloud_enabled = True
fake_settings.cloud_api_key = MagicMock()
fake_settings.cloud_api_key.get_secret_value.return_value = "sk-test-key"

DEMO_QUERIES = [
    ("Demo2-学生诊断",  "王同学数学42分链式法则混淆，李老师建议增加针对性练习。请诊断学习问题并制定个性化辅导方案。"),
    ("Demo3-团队分工",  "智能体安全项目即将启动，请根据张教授的安全架构专长和李工程师的系统实现能力，制定前两周工作分工方案。"),
    ("Demo4-预算审查",  "智能体安全项目总预算120万元，其中硬件设备45万元、模型服务30万元。请评估预算分配是否合理并给出优化建议。"),
    ("Demo1-小仲马",   "分析一下小仲马这个人物，他的代表作品和文学成就。"),
    ("Demo5-公开知识",  "澳大利亚的首都是什么？尼罗河有多长？贝多芬的月光奏鸣曲是什么时期的作品？"),
]

mock_kb = _load_mock_kb()
kb_text = " ".join(d.get("content", "") for d in mock_kb)

print("=" * 80)
print("VaultAgent Demo 模式选择 & 实体保护测试")
print("=" * 80)
print(f"合成知识库文档数: {len(mock_kb)}")
print(f"合成知识库总长度: {len(kb_text)} 字符")
print()

all_ok = True
for label, query in DEMO_QUERIES:
    mode, reasons = _select_mode(
        user_query=query,
        documents=[],  # simulate no explicit docs
        cloud_use_allowed=True,
        local_capability=0.5,
        complexity=0.5,
        policy_budget=0.4,
        settings=fake_settings,
    )

    # ── Scan entities ──
    entities = _scan_entities(query)
    kb_entities = _filter_entities_by_kb(entities, mock_kb)

    print(f"[{label}]")
    print(f"  查询: {query[:60]}...")
    print(f"  选择模式: {mode}")
    print(f"  选择依据:")
    for r in reasons:
        print(f"    · {r}")
    print(f"  扫描到实体 ({len(entities)}): {[e['entity'] for e in entities]}")
    print(f"  KB匹配实体 ({len(kb_entities)}): {[(e['entity'], e['type'], e['operation']) for e in kb_entities]}")

    # Verify expected modes
    expected_modes = {
        "Demo2": "PROTECTED_CONTEXT_CLOUD_REASONING",  # Mode 3
        "Demo3": "CLOUD_PLAN_LOCAL_EXECUTION",          # Mode 2
        "Demo4": "PROTECTED_CONTEXT_CLOUD_REASONING",  # Mode 3
        "Demo1": "LOCAL_ONLY",                          # 公知→本地→Stage 2直调
        "Demo5": "LOCAL_ONLY",                          # 公知→本地→Stage 2直调
    }

    exp = expected_modes.get(label.split("-")[0])
    if exp:
        status = "✓" if mode == exp else "✗ 错误!"
        if mode != exp:
            all_ok = False
    else:
        status = "?"

    # Verify expected entities
    expected_entities = {
        "Demo2": {"王同学", "李老师", "42分"},
        "Demo3": {"张教授", "李工程师", "智能体安全项目"},
        "Demo4": {"120万元", "45万元", "30万元"},
        "Demo1": set(),
        "Demo5": set(),
    }
    exp_ents = expected_entities.get(label.split("-")[0], set())
    found_texts = {e["entity"] for e in kb_entities}
    missing = exp_ents - found_texts
    extra = found_texts - exp_ents if exp_ents else set()
    ent_status = ""
    if exp_ents:
        if not missing:
            ent_status = f"  实体保护: ✓ (全部 {len(exp_ents)} 个已保护)"
        else:
            ent_status = f"  实体保护: ✗ 缺失! 需要保护但未检测到: {missing}"
            all_ok = False

    print(f"  模式结果: {status} (期望 {exp})")
    if ent_status:
        print(ent_status)
    if extra:
        print(f"  额外实体 (KB扫描被动发现): {extra}")
    print()

print("=" * 80)
if all_ok:
    print("全部通过!")
else:
    print("存在失败, 请检查 ✗")
print("=" * 80)
