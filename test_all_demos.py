#!/usr/bin/env python3
"""Test all demos — verify only user query entities are protected."""
import json, httpx, re

BASE = "http://127.0.0.1:8000"

DEMOS = [
    {
        "name": "Demo2-学生诊断",
        "query": "王同学数学42分链式法则混淆，李老师建议增加针对性练习。请诊断学习问题并制定个性化辅导方案。",
        "expected": {"王同学", "李老师", "42分"},
    },
    {
        "name": "Demo3-团队分工",
        "query": "智能体安全项目即将启动，请根据张教授的安全架构专长和李工程师的系统实现能力，制定前两周工作分工方案。",
        "expected": {"智能体安全项目", "张教授", "李工程师"},
    },
    {
        "name": "Demo4-预算审查",
        "query": "智能体安全项目总预算120万元，其中硬件设备45万元、模型服务30万元。请评估预算分配是否合理并给出优化建议。",
        "expected": {"智能体安全项目", "120万元", "45万元", "30万元"},
    },
    {
        "name": "小仲马-公知",
        "query": "分析一下小仲马这个人物，他的代表作品和文学成就。",
        "expected": set(),  # public knowledge, no entities to protect
    },
    {
        "name": "Demo5-公开知识",
        "query": "澳大利亚的首都是什么？尼罗河有多长？贝多芬的月光奏鸣曲是什么时期的作品？",
        "expected": set(),  # public knowledge, no entities to protect
    },
]

for demo in DEMOS:
    print(f"\n{'='*60}")
    print(f"Testing: {demo['name']}")
    print(f"Query: {demo['query'][:80]}...")
    
    # Submit
    resp = httpx.post(f"{BASE}/api/v1/tasks", json={
        "user_query": demo["query"],
        "purpose": "planning",
        "cloud_use_allowed": True,
        "local_capability": 0.5,
        "complexity": 0.5,
        "policy_budget": 0.5,
    }, timeout=30)
    tid = resp.json()["data"]["task_id"]
    
    # Execute
    resp2 = httpx.post(f"{BASE}/api/v1/tasks/{tid}/execute", json={}, timeout=120)
    d = resp2.json()["data"]
    mode = d.get("mode", "N/A")
    mode_reasons = d.get("mode_reasons", [])
    
    print(f"  Mode: {mode}")
    
    # Get data_flow if available
    df = d.get("data_flow", {})
    if df:
        ents = df.get("entities", [])
        entity_names = [e["entity"] for e in ents]
        print(f"  Protected entities ({len(ents)}): {entity_names}")
        
        actual = set(entity_names)
        extra = actual - demo["expected"]
        missing = demo["expected"] - actual
        if not extra and not missing:
            print(f"  >>> PASS: Correct protection scope")
        else:
            if extra:
                print(f"  >>> FAIL - EXTRA: {extra}")
            if missing:
                print(f"  >>> FAIL - MISSING: {missing}")
    else:
        # Check answer text for entity counts
        answer = d.get("answer", "")
        m = re.search(r'(\d+)\s*个敏感实体', answer)
        if m:
            count = int(m.group(1))
            expected_count = len(demo["expected"])
            print(f"  Answer shows {count} scanned entities (expected {expected_count})")
            if count == expected_count:
                print(f"  >>> PASS: Entity count matches")
            else:
                print(f"  >>> FAIL: Got {count}, expected {expected_count}")
        else:
            # Check mode for public knowledge - should be direct cloud
            if demo["expected"] == set():
                if mode == "LOCAL_ONLY" and any("无KB实体" in r or "直接云端" in r for r in mode_reasons):
                    print(f"  >>> PASS: Public knowledge, no entities to protect")
                elif mode == "PROTECTED_CONTEXT_CLOUD_REASONING":
                    # Check if 0 entities mentioned
                    if "0 个敏感实体" in answer or "零CSSD" in answer:
                        print(f"  >>> PASS: Mode 3 with zero overhead for public knowledge")
                    else:
                        print(f"  >>> WARNING: Mode 3 but no entity count found")
                else:
                    print(f"  >>> OK: Mode={mode}")
            else:
                print(f"  >>> WARNING: No entity count found in answer")
    
    print(f"  Mode reasons: {mode_reasons[:2]}")
