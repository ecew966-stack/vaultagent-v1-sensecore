#!/usr/bin/env python3
"""Test Demo4 entity protection — should only protect 4 entities from user query."""
import json, httpx, re

BASE = "http://127.0.0.1:8000"

# Submit task
resp = httpx.post(f"{BASE}/api/v1/tasks", json={
    "user_query": "智能体安全项目总预算120万元，其中硬件设备45万元、模型服务30万元。请评估预算分配是否合理并给出优化建议。",
    "purpose": "planning",
    "cloud_use_allowed": True,
    "local_capability": 0.5,
    "complexity": 0.5,
    "policy_budget": 0.5,
})
data = resp.json()
print(f"Submit response keys: {list(data.keys())}")
task_id = data.get("data", {}).get("task_id", "unknown")
print(f"Task ID: {task_id}")

# Execute with mode override
resp2 = httpx.post(f"{BASE}/api/v1/tasks/{task_id}/execute", json={
    "mode_override": "PROTECTED_CONTEXT_CLOUD_REASONING",
}, timeout=120)
result = resp2.json()
print(f"Execute status: {resp2.status_code}")
if resp2.status_code != 200:
    print(f"Error detail: {json.dumps(result, ensure_ascii=False, indent=2)[:500]}")
print(f"Execute response keys: {list(result.keys())}")

d = result.get("data", result)  # fallback to full response
print(f"Mode: {d.get('mode', 'N/A')}")
print(f"Mode Reasons: {d.get('mode_reasons', [])}")

df = d.get("data_flow", {})
if df:
    print(f"\nData Flow:")
    print(f"  encrypted: {df.get('encrypted')}")
    print(f"  protected_entity_count: {df.get('protected_entity_count')}")
    ents = df.get("entities", [])
    entity_names = [e["entity"] for e in ents]
    print(f"  entities ({len(ents)}): {entity_names}")
    
    expected = {"智能体安全项目", "120万元", "45万元", "30万元"}
    actual = set(entity_names)
    extra = actual - expected
    missing = expected - actual
    if not extra and not missing:
        print("  >>> PERFECT: Only query entities protected!")
    else:
        if extra:
            print(f"  >>> EXTRA (should NOT be protected): {extra}")
        if missing:
            print(f"  >>> MISSING (should be protected): {missing}")
else:
    print("\n  No data_flow in response")
    answer = d.get("answer", "")
    m1 = re.search(r'(\d+)\s*个实体已保护', answer)
    if m1:
        print(f"  Answer mentions {m1.group(1)} protected entities")
    m2 = re.search(r'本地扫描到\s*(\d+)\s*个敏感实体', answer)
    if m2:
        print(f"  Answer shows {m2.group(1)} scanned entities")
    m3 = re.search(r'protected_entity_count.*?(\d+)', answer)
    if m3:
        print(f"  protected_entity_count: {m3.group(1)}")
    # Count entity tokens in answer
    tokens = re.findall(r'\[(?:PERSON|PROJECT|BUDGET|ORG|SCORE|ADDRESS|LOC)_\w+\]', answer)
    if tokens:
        print(f"  Token-like patterns in answer: {len(tokens)}")
        for t in tokens[:5]:
            print(f"    {t}")
