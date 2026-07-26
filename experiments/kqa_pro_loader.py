from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Iterator

from src.delegation.schemas import (
    Confidentiality, EntityType, Integrity, KnowledgeAtom,
    KnowledgeDocument, TaskRequest
)


class KQAProLoader:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.sensitive_entity_types = {
            "city": EntityType.CITY,
            "town": EntityType.CITY,
            "city of the United States": EntityType.CITY,
            "award ceremony": EntityType.EVENT,
        }

    def load(self) -> Iterator[dict[str, Any]]:
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def to_task_request(self, sample: dict[str, Any]) -> TaskRequest:
        task_info = sample["task"]
        policy_info = sample["policy"]
        return TaskRequest(
            task_id=sample["sample_id"],
            user_query=task_info["user_query"],
            purpose=policy_info["allowed_purposes"][0] if policy_info["allowed_purposes"] else "answer_relational_query",
            cloud_use_allowed=True,
            local_capability=0.3,
            complexity=0.8 if task_info["task_type"] == "multi_hop_reasoning" else 0.5,
            policy_budget=0.4,
            metadata={
                "privacy_scope_id": f"kqa-{sample['sample_id'][:8]}",
                "domain": task_info["domain"],
                "task_type": task_info["task_type"],
            }
        )

    def to_knowledge_documents(self, sample: dict[str, Any]) -> list[KnowledgeDocument]:
        docs = []
        private_graph = sample["input"]["private_graph"]
        capsule = sample["input"]["capsule"]
        entity_mapping = capsule.get("entity_mapping", {})

        for entity in private_graph.get("entities", []):
            entity_id = entity["entity_id"]
            token = entity_mapping.get(entity_id, f"TOKEN_{entity_id[:8].upper()}")
            entity_type = self.sensitive_entity_types.get(entity["entity_type"], EntityType.OTHER)

            attributes = []
            for attr in private_graph.get("attributes", []):
                if attr["entity_id"] == entity_id:
                    attributes.append(f"{attr['key']}: {attr['value']}")

            content = f"[{token}] is a {entity['entity_type']} named {entity['name']}. "
            content += "; ".join(attributes)

            docs.append(KnowledgeDocument(
                doc_id=f"kqa-{entity_id}",
                content=content,
                source=f"KQA-Pro/{sample['source']['source_id']}",
                confidentiality=self._determine_confidentiality(entity),
                integrity=Integrity.TRUSTED,
                allowed_purposes=sample["policy"].get("allowed_purposes", ["answer_relational_query"]),
                allowed_sinks=["LOCAL_MODEL", "cloud_reasoner"],
            ))

        for relation in private_graph.get("relations", []):
            subject_token = entity_mapping.get(relation.get("subject"), "TOKEN_SUBJECT")
            object_token = entity_mapping.get(relation.get("object"), "TOKEN_OBJECT")
            docs.append(KnowledgeDocument(
                doc_id=f"kqa-rel-{relation.get('relation_id', 'unknown')}",
                content=f"[{subject_token}] {relation.get('predicate', 'related_to')} [{object_token}]",
                source=f"KQA-Pro/{sample['source']['source_id']}",
                confidentiality=Confidentiality.INTERNAL,
                integrity=Integrity.TRUSTED,
                allowed_purposes=sample["policy"].get("allowed_purposes", ["answer_relational_query"]),
                allowed_sinks=["LOCAL_MODEL", "cloud_reasoner"],
            ))

        return docs

    def to_knowledge_atoms(self, sample: dict[str, Any]) -> list[KnowledgeAtom]:
        atoms = []
        private_graph = sample["input"]["private_graph"]
        capsule = sample["input"]["capsule"]
        entity_mapping = capsule.get("entity_mapping", {})

        for entity in private_graph.get("entities", []):
            entity_id = entity["entity_id"]
            token = entity_mapping.get(entity_id, f"TOKEN_{entity_id[:8].upper()}")
            entity_type = self.sensitive_entity_types.get(entity["entity_type"], EntityType.OTHER)

            atoms.append(KnowledgeAtom(
                atom_id=f"entity-{entity_id}",
                value=entity["name"],
                type=entity_type,
                source=f"KQA-Pro/{sample['source']['source_id']}",
                sensitivity=self._determine_confidentiality(entity),
                integrity=Integrity.TRUSTED,
                token=token,
            ))

        for attr in private_graph.get("attributes", []):
            entity_id = attr["entity_id"]
            token = entity_mapping.get(entity_id, f"TOKEN_{entity_id[:8].upper()}")

            atoms.append(KnowledgeAtom(
                atom_id=f"attr-{entity_id}-{attr['key']}",
                value=str(attr["value"]),
                type=EntityType.ATTRIBUTE,
                source=f"KQA-Pro/{sample['source']['source_id']}",
                sensitivity=Confidentiality.PUBLIC,
                integrity=Integrity.TRUSTED,
                token=token,
            ))

        return atoms

    def _determine_confidentiality(self, entity: dict) -> Confidentiality:
        entity_type = entity.get("entity_type", "").lower()
        if "city" in entity_type or "town" in entity_type:
            return Confidentiality.CONFIDENTIAL
        return Confidentiality.PUBLIC

    def get_gold_rehydration(self, sample: dict[str, Any]) -> dict[str, str]:
        return sample["gold"].get("gold_rehydration", {}).get("token_mapping", {})

    def get_gold_answer(self, sample: dict[str, Any]) -> str:
        rehydration = sample["gold"].get("gold_rehydration", {})
        return str(rehydration.get("rehydrated_result", {}).get("answer", "unknown"))


def load_kqa_pro_dataset(path: str | Path) -> tuple[list[TaskRequest], list[list[KnowledgeDocument]], list[list[KnowledgeAtom]]]:
    loader = KQAProLoader(path)
    tasks = []
    documents_list = []
    atoms_list = []

    for sample in loader.load():
        tasks.append(loader.to_task_request(sample))
        documents_list.append(loader.to_knowledge_documents(sample))
        atoms_list.append(loader.to_knowledge_atoms(sample))

    return tasks, documents_list, atoms_list


if __name__ == "__main__":
    loader = KQAProLoader(Path(__file__).parent.parent / "candidate_50_v7_final.jsonl")
    count = 0
    for sample in loader.load():
        task = loader.to_task_request(sample)
        docs = loader.to_knowledge_documents(sample)
        atoms = loader.to_knowledge_atoms(sample)
        gold = loader.get_gold_answer(sample)
        print(f"Sample {count + 1}: {task.task_id}")
        print(f"  Query: {task.user_query[:60]}...")
        print(f"  Gold Answer: {gold}")
        print(f"  Documents: {len(docs)}, Atoms: {len(atoms)}")
        count += 1
    print(f"\nTotal samples: {count}")