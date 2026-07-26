"""Quick test to verify _select_mode and entity scanning."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from src.api.routers.tasks import _select_mode, _scan_entities, _filter_entities_by_kb, _load_mock_kb
from src.core.settings import Settings

settings = Settings()

# Test queries
test_queries = [
    ("Demo2-学生诊断", "王同学数学42分链式法则混淆，李老师建议增加针对性练习。请诊断学习问题并制定个性化辅导方案。"),
    ("Demo3-团队分工", "智能体安全项目即将启动，请根据张教授的安全架构专长和李工程师的系统实现能力，制定前两周工作分工方案。"),
    ("Demo4-预算审查", "智能体安全项目总预算120万元，其中硬件设备45万元、模型服务30万元。请评估预算分配是否合理并给出优化建议。"),
    ("小仲马-公知", "分析一下小仲马这个人物，他的代表作品和文学成就。"),
    ("Demo5-公开知识", "澳大利亚的首都是什么？尼罗河有多长？贝多芬的月光奏鸣曲是什么时期的作品？"),
]

print("=" * 80)
print("Cloud settings check:")
print(f"  cloud_enabled = {settings.cloud_enabled}")
print(f"  cloud_api_key set = {bool(settings.cloud_api_key and settings.cloud_api_key.get_secret_value())}")
print(f"  cloud_base_url = {settings.cloud_base_url}")
print("=" * 80)

for name, query in test_queries:
    print(f"\n{'='*80}")
    print(f"  {name}: {query}")
    print(f"{'='*80}")
    
    # Simulate mock KB injection
    mock_kb = _load_mock_kb()
    kb_text = " ".join(d.get("content", "") for d in mock_kb)
    
    # Step 1: Scan entities
    ents = _scan_entities(query)
    print(f"  Entities scanned from query: {len(ents)}")
    for e in ents:
        print(f"    - {e['entity']} ({e['type']}) → {e['operation']}")
    
    # Step 2: Filter against KB
    kb_ents = _filter_entities_by_kb(ents, mock_kb)
    print(f"  After KB filter: {len(kb_ents)}")
    for e in kb_ents:
        print(f"    - {e['entity']} ({e['type']})")
    
    # Step 3: Check KB relevance
    import re
    _query_words = set()
    for _m in re.finditer(r'[\u4e00-\u9fff]{2,}', query):
        _word = _m.group(0)
        for _i in range(len(_word) - 1):
            _query_words.add(_word[_i:_i + 2])
    
    hits = [w for w in _query_words if w in kb_text]
    print(f"  2-char window KB hits: {hits}")
    
    # Step 4: Scan KB doc entities
    if kb_ents or hits:
        kb_doc_ents = _scan_entities(kb_text, use_bare_names=False)
        kb_doc_ents = _filter_entities_by_kb(kb_doc_ents, mock_kb)
        print(f"  KB doc entities: {len(kb_doc_ents)}")
        for e in kb_doc_ents[:15]:
            print(f"    - {e['entity']} ({e['type']})")
    else:
        print(f"  KB doc entities: NOT scanned (no relevance)")
    
    # Step 5: Mock KB injection check
    _query_ents_inj = _scan_entities(query, use_bare_names=False)
    has_kb_ref = any(e["entity"] in kb_text for e in _query_ents_inj)
    print(f"  Mock KB would be injected: {has_kb_ref}")
    if has_kb_ref:
        print(f"    Query ents in KB: {[e['entity'] for e in _query_ents_inj if e['entity'] in kb_text]}")
    
    # Step 6: Full _select_mode call (without documents → uses mock KB)
    mode, reasons = _select_mode(
        user_query=query,
        documents=[],
        cloud_use_allowed=True,
        local_capability=0.5,
        complexity=0.5,
        policy_budget=0.4,
        settings=settings,
    )
    print(f"  MODE (no docs): {mode}")
    for r in reasons:
        print(f"    reason: {r}")
    
    # Step 7: Full _select_mode call (WITH mock KB injected as docs)
    mock_docs = [{k: v for k, v in d.items() if k in ("content", "doc_id", "confidentiality", "source", "allowed_purposes", "allowed_sinks", "integrity")} for d in mock_kb]
    mode2, reasons2 = _select_mode(
        user_query=query,
        documents=mock_docs,
        cloud_use_allowed=True,
        local_capability=0.5,
        complexity=0.5,
        policy_budget=0.4,
        settings=settings,
    )
    print(f"  MODE (with KB docs): {mode2}")
    for r in reasons2:
        print(f"    reason: {r}")
