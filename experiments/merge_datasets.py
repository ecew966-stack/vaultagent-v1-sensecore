from __future__ import annotations
import json
from pathlib import Path

from dataset_loader import UnifiedDatasetLoader


def main():
    project_root = Path(__file__).parent.parent

    paths = [
        project_root / "candidate_50_v7_final.jsonl",
        project_root / "data/kqa_pro_enhanced/sensitive_samples.jsonl",
        project_root / "data/normal_tasks",
        project_root / "data/attack_tasks",
    ]

    loader = UnifiedDatasetLoader(paths)
    print(f"Loading datasets from {len(paths)} sources...")

    merged_samples = []
    sample_count = 0
    source_counts = {}

    for sample, source_name in loader.load():
        task = loader.to_task_request(sample, source_name)
        docs = loader.to_knowledge_documents(sample, source_name)
        gold_answer = loader.get_gold_answer(sample, source_name)

        unified_sample = {
            "schema_version": "v0.1",
            "sample_id": task.task_id,
            "source": {"dataset": source_name, "source_id": task.task_id},
            "task": {
                "domain": task.metadata.get("domain", "general"),
                "task_type": task.metadata.get("task_type", "reasoning"),
                "user_query": task.user_query,
            },
            "policy": {
                "policy_id": f"policy-{task.task_id}",
                "allowed_purposes": [task.purpose],
                "allowed_sinks": ["LOCAL_MODEL"] if not task.cloud_use_allowed else ["LOCAL_MODEL", "cloud_reasoner"],
                "max_disclosure_level": "public",
                "allowed_operations": ["ASSERT_SINGLE", "COMPARE", "FILTER", "QUERY_ATTRIBUTE", "SELECT", "SELECT_ALL", "VERIFY_PREDICATE"],
                "constraints": {
                    "purpose": task.purpose,
                    "allowed_relations": [],
                    "allowed_attributes": [],
                    "allowed_entity_types": [],
                    "forbidden_attributes": ["student_name", "exact_score", "full_dialogue", "raw_identity"],
                },
            },
            "input": {
                "question": task.user_query,
                "private_graph": {
                    "entities": [],
                    "relations": [],
                    "attributes": [],
                },
                "capsule": {
                    "capsule_id": f"capsule-{task.task_id}",
                    "entity_mapping": {},
                    "protected_statements": [],
                },
            },
            "gold": {
                "gold_structured_result": {
                    "result_type": "protected_answer",
                    "content": {"answer": gold_answer},
                    "confidence": 1.0,
                },
                "gold_rehydration": {
                    "authorized_fields": ["answer"],
                    "token_mapping": {},
                    "rehydrated_result": {"answer": gold_answer},
                },
            },
            "security": sample.get("security", {"raw_identity_values_allowed_in_cloud": False, "should_accept": True}),
            "attack": sample.get("attack", None),
            "knowledge_documents": [d.model_dump(mode="json") for d in docs],
        }

        merged_samples.append(unified_sample)
        sample_count += 1
        source_counts[source_name] = source_counts.get(source_name, 0) + 1

    output_path = project_root / "data/unified_dataset.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        for sample in merged_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    print(f"\n=== Merge Complete ===")
    print(f"Total samples: {sample_count}")
    print(f"Output: {output_path}")
    print("\nSource distribution:")
    for source, count in sorted(source_counts.items()):
        print(f"  {source}: {count}")


if __name__ == "__main__":
    main()