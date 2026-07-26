import httpx

query = "张三的期末考试成绩和教师反馈意见怎么样，帮我制定一个辅导计划"
payload = {
    "user_query": query,
    "purpose": "planning",
    "cloud_use_allowed": True,
    "local_capability": 0.5,
    "complexity": 0.6,
    "policy_budget": 0.4,
}

r = httpx.post("http://127.0.0.1:8080/api/v1/tasks", json=payload, timeout=10)
tid = r.json()["data"]["task_id"]
r2 = httpx.post(f"http://127.0.0.1:8080/api/v1/tasks/{tid}/execute", json={}, timeout=120)
d = r2.json()["data"]
answer = d["answer"]
mode = d["mode"]

print(f"Mode: {mode}")
print(f"Answer length: {len(answer)}")
print()

# Show the key sections
sections = answer.split("\n\n")
for s in sections:
    s = s.strip()
    if "数据流向" in s or "PERSON_" in s or "保护" in s:
        print(s[:500])
        print("...")
        print()
    if "回答:" in s or "AI" in s:
        print("=== AI Answer ===")
        print(s[300:])
        print()
