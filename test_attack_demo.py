"""Test attack demo endpoints."""
import urllib.request, json

for attack in ("prompt_injection", "token_replay", "undeclared_slot"):
    req = urllib.request.Request(
        f"http://localhost:8080/api/v1/security/attack-demo/{attack}",
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    d = data["data"]
    print(f"=== {d['title']} ===")
    print(f"  Detected: {d['detected']}")
    print(f"  Blocked: {d['blocked']}")
    print(f"  Overall Risk: {d['overall_risk']}")
    for det in d.get("detection_details", []):
        print(f"  {det['detector']}: {det['verdict']}")
    print()
