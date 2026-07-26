"""Test Demo4 end-to-end via API - verify only 4 entities protected."""
import urllib.request, json, time

query = "智能体安全项目总预算120万元，其中硬件设备45万元、模型服务30万元。请评估预算分配是否合理并给出优化建议。"

# Create
data = json.dumps({
    "task_id": "test-d4",
    "user_query": query,
    "purpose": "resource_allocation",
    "cloud_use_allowed": True,
}).encode()
req = urllib.request.Request("http://localhost:8080/api/v1/tasks", data=data,
                             headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req, timeout=10) as resp:
    rd = json.loads(resp.read())
    task_id = rd["data"]["task_id"]

# Execute
time.sleep(0.5)
data2 = json.dumps({}).encode()
req2 = urllib.request.Request(f"http://localhost:8080/api/v1/tasks/{task_id}/execute",
                              data=data2, headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req2, timeout=120) as resp:
    r2 = json.loads(resp.read())
    d = r2["data"]
    print(f"MODE: {d['mode']}")
    print(f"REASONS: {d.get('mode_reasons', [])}")

    df = d.get("data_flow", {})
    print(f"\nProtected entity count: {df.get('protected_entity_count', 0)}")
    protected = [e["entity"] for e in df.get("entities", [])]
    print(f"Protected entities: {protected}")

    # Verify we protect exactly the query entities (4-5), not 17
    expected = {"智能体安全项目", "120万元", "45万元", "30万元"}
    actual = set(protected)
    print(f"\nExpected:  {expected}")
    print(f"Actual:    {actual}")
    extra = actual - expected
    missing = expected - actual
    if not extra and not missing:
        print("PERFECT: Only query entities protected!")
    else:
        if extra:
            print(f"EXTRA (should NOT be protected): {extra}")
        if missing:
            print(f"MISSING (should be protected): {missing}")

    # Show protected query
    pq = df.get("protected_query", "")
    print(f"\nProtected query: {pq}")
    print(f"\nOriginal query:  {query}")
