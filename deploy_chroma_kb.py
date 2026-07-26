import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.knowledge.chroma_adapter import ChromaDenseAdapter, ChromaAdapterConfig
from src.knowledge.ingestion import DocumentIngestor
from src.delegation.schemas import Confidentiality, Integrity, KnowledgeDocument


def flatten_kqa_sample(sample: dict) -> KnowledgeDocument:
    """将 KQA 样本展平为可检索的 KnowledgeDocument"""
    sample_id = sample["sample_id"]
    question = sample["question"]
    atoms = sample.get("atoms", [])
    policy = sample.get("policy", {})
    gold_answer = sample.get("gold_answer", "")
    metadata = sample.get("metadata", {})
    
    # 构建 atoms 摘要
    atoms_summary = []
    for atom in atoms:
        kind = atom.get("kind", "")
        subject = atom.get("subject", "")
        predicate = atom.get("predicate", "")
        obj = atom.get("object", "")
        value = atom.get("value", "")
        
        if kind == "entity":
            etype = atom.get("subject_type", "")
            name = atom.get("metadata", {}).get("name", "")
            atoms_summary.append(f"[ENTITY] {name or subject} ({etype})")
        elif kind == "attribute":
            subject_name = atom.get("metadata", {}).get("subject_name", subject)
            atoms_summary.append(f"[ATTR] {subject_name}.{predicate} = {value}")
        elif kind == "relation":
            subj_name = atom.get("metadata", {}).get("subject_name", subject)
            obj_name = atom.get("metadata", {}).get("object_name", obj)
            atoms_summary.append(f"[REL] {subj_name} {predicate} {obj_name}")
    
    # 构建 policy 摘要
    policy_purpose = policy.get("purpose", "")
    allowed_types = ", ".join(policy.get("allowed_entity_types", []))
    policy_summary = f"Purpose: {policy_purpose}; Allowed Types: {allowed_types}"
    
    # 构建完整内容
    content_parts = [
        f"Question: {question}",
        f"Policy: {policy_summary}",
        f"Atoms: {' | '.join(atoms_summary) if atoms_summary else 'None'}",
        f"Answer: {gold_answer if gold_answer else 'Unknown'}"
    ]
    
    content = "\n".join(content_parts)
    
    # 确定敏感性
    source = metadata.get("source", "")
    sample_type = metadata.get("sample_type", "")
    
    if sample_type == "privacy_policy" or sample_type == "security_attack":
        confidentiality = Confidentiality.INTERNAL
    else:
        confidentiality = Confidentiality.CONFIDENTIAL
    
    # 获取来源信息
    domain = metadata.get("domain", "")
    task_type = metadata.get("task_type", "")
    
    return KnowledgeDocument(
        doc_id=sample_id,
        content=content,
        source=f"kqa_v7_200_samples.jsonl#{sample_id}",
        confidentiality=confidentiality,
        integrity=Integrity.TRUSTED,
        allowed_purposes=["knowledge_retrieval", "question_answering", "policy_compliance"],
        allowed_sinks=["LOCAL_MODEL", "PROTECTED_CONTEXT_CLOUD_REASONING"]
    )


def load_kqa_samples(file_path: str) -> list[dict]:
    """加载 KQA JSONL 文件"""
    samples = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples


def main():
    # 配置参数
    kqa_file = os.path.join(os.path.dirname(__file__), "..", "kqa_v7_200_samples.jsonl")
    chroma_dir = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
    collection_name = "vaultagent_kqa_200"
    
    print(f"=== Chroma 知识库部署启动 ===")
    print(f"KQA 样本文件: {kqa_file}")
    print(f"Chroma 存储目录: {chroma_dir}")
    print(f"Collection 名称: {collection_name}")
    
    # 加载样本
    print("\n[1/3] 加载 KQA 样本...")
    samples = load_kqa_samples(kqa_file)
    print(f"加载成功: {len(samples)} 条样本")
    
    # 转换为 KnowledgeDocument
    print("\n[2/3] 转换样本为可检索文档...")
    documents = []
    for i, sample in enumerate(samples):
        doc = flatten_kqa_sample(sample)
        documents.append(doc)
        if (i + 1) % 50 == 0:
            print(f"  已转换: {i + 1}/{len(samples)}")
    print(f"转换完成: {len(documents)} 个文档")
    
    # 初始化 Chroma 适配器
    print("\n[3/3] 初始化 Chroma 并导入数据...")
    config = ChromaAdapterConfig(
        persist_directory=chroma_dir,
        collection_name=collection_name,
        embedding_model_name="all-MiniLM-L6-v2"
    )
    
    adapter = ChromaDenseAdapter(config)
    
    # 清空已有数据（可选）
    if adapter.count() > 0:
        print(f"  检测到已有 {adapter.count()} 条记录，将先清空...")
        adapter.delete_collection()
        adapter = ChromaDenseAdapter(config)
    
    # 批量导入
    batch_size = 50
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        adapter.add_documents(batch)
        print(f"  已导入: {min(i + batch_size, len(documents))}/{len(documents)}")
    
    # 验证
    count = adapter.count()
    print(f"\n=== 导入完成 ===")
    print(f"Collection: {collection_name}")
    print(f"文档总数: {count}")
    print(f"Chroma 存储路径: {chroma_dir}")
    
    # 测试检索
    print("\n=== 测试检索 ===")
    test_queries = [
        "What is the capital of France?",
        "Which student has misconception MISC_ARITH_01?",
        "Which city has a larger population?",
        "How to handle privacy policy for employee data?"
    ]
    
    for query in test_queries:
        results = adapter.search_by_query(query, limit=2)
        if results:
            print(f"\n查询: {query}")
            for hit in results:
                print(f"  得分: {hit.score:.3f} | ID: {hit.document.doc_id[:20]}...")
        else:
            print(f"\n查询: {query} -> 无结果")


if __name__ == "__main__":
    main()
