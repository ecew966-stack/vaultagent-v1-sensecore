from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Iterator, Protocol

from src.delegation.schemas import (
    Confidentiality, EntityType, Integrity, KnowledgeAtom,
    KnowledgeDocument, TaskRequest
)


class DatasetLoader(Protocol):
    def load(self) -> Iterator[dict[str, Any]]:
        ...

    def to_task_request(self, sample: dict[str, Any]) -> TaskRequest:
        ...

    def to_knowledge_documents(self, sample: dict[str, Any]) -> list[KnowledgeDocument]:
        ...

    def get_gold_answer(self, sample: dict[str, Any]) -> str:
        ...


class KQAProLoader:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.sensitive_entity_types = {
            "city": EntityType.CITY,
            "town": EntityType.CITY,
            "city of the United States": EntityType.CITY,
            "award ceremony": EntityType.EVENT,
            "patient": EntityType.PERSON,
            "student": EntityType.PERSON,
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
        purposes = policy_info.get("allowed_purposes", ["answer_query"])
        return TaskRequest(
            task_id=sample["sample_id"],
            user_query=task_info["user_query"],
            purpose=purposes[0],
            cloud_use_allowed=policy_info.get("allowed_sinks") != ["LOCAL_MODEL"],
            local_capability=0.3,
            complexity=0.8 if task_info["task_type"] == "multi_hop_reasoning" else 0.5,
            policy_budget=0.4,
            metadata={
                "privacy_scope_id": f"kqa-{sample['sample_id'][:8]}",
                "domain": task_info["domain"],
                "task_type": task_info["task_type"],
                "is_attack": sample.get("attack") is not None,
            }
        )

    def to_knowledge_documents(self, sample: dict[str, Any]) -> list[KnowledgeDocument]:
        docs = []
        private_graph = sample["input"].get("private_graph", {})
        capsule = sample["input"].get("capsule", {})
        entity_mapping = capsule.get("entity_mapping", {})

        for entity in private_graph.get("entities", []):
            entity_id = entity["entity_id"]
            token = entity_mapping.get(entity_id, f"TOKEN_{entity_id[:8].upper()}")
            entity_type = self.sensitive_entity_types.get(entity["entity_type"], EntityType.OTHER)

            attributes = []
            for attr in private_graph.get("attributes", []):
                if attr["entity_id"] == entity_id:
                    unit = attr.get("unit", "")
                    attributes.append(f"{attr['key']}: {attr['value']}{(' ' + unit) if unit else ''}")

            content = f"[{token}] is a {entity['entity_type']} named {entity['name']}. "
            content += "; ".join(attributes)

            docs.append(KnowledgeDocument(
                doc_id=f"kqa-{entity_id}",
                content=content,
                source=f"KQA-Pro/{sample['source']['source_id']}",
                confidentiality=self._determine_confidentiality(entity),
                integrity=Integrity.TRUSTED,
                allowed_purposes=sample["policy"].get("allowed_purposes", ["answer_query"]),
                allowed_sinks=sample["policy"].get("allowed_sinks", ["LOCAL_MODEL"]),
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
                allowed_purposes=sample["policy"].get("allowed_purposes", ["answer_query"]),
                allowed_sinks=sample["policy"].get("allowed_sinks", ["LOCAL_MODEL"]),
            ))

        return docs

    def get_gold_answer(self, sample: dict[str, Any]) -> str:
        rehydration = sample["gold"].get("gold_rehydration", {})
        return str(rehydration.get("rehydrated_result", {}).get("answer", "unknown"))

    def _determine_confidentiality(self, entity: dict) -> Confidentiality:
        entity_type = entity.get("entity_type", "").lower()
        if "patient" in entity_type or "student" in entity_type:
            return Confidentiality.SECRET
        if "city" in entity_type or "town" in entity_type:
            return Confidentiality.CONFIDENTIAL
        return Confidentiality.PUBLIC


class SyntheticLoader:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> Iterator[dict[str, Any]]:
        if self.path.is_dir():
            for f in sorted(self.path.glob("*.json")):
                data = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for item in data:
                        yield item
                else:
                    yield data
        else:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                for item in data:
                    yield item
            else:
                yield data

    def to_task_request(self, sample: dict[str, Any]) -> TaskRequest:
        task_data = sample["task"]
        return TaskRequest(
            task_id=task_data["task_id"],
            user_query=task_data["user_query"],
            purpose=task_data.get("purpose", "planning"),
            cloud_use_allowed=task_data.get("cloud_use_allowed", True),
            local_capability=task_data.get("local_capability", 0.3),
            complexity=task_data.get("complexity", 0.7),
            policy_budget=task_data.get("policy_budget", 0.4),
            metadata=task_data.get("metadata", {}),
        )

    def to_knowledge_documents(self, sample: dict[str, Any]) -> list[KnowledgeDocument]:
        docs = []
        for doc_data in sample.get("documents", []):
            docs.append(KnowledgeDocument(
                doc_id=doc_data.get("doc_id", "unknown"),
                content=doc_data.get("content", ""),
                source=doc_data.get("source", "synthetic"),
                confidentiality=Confidentiality(doc_data.get("confidentiality", "PUBLIC")),
                integrity=Integrity(doc_data.get("integrity", "TRUSTED")),
                allowed_purposes=doc_data.get("allowed_purposes", []),
                allowed_sinks=doc_data.get("allowed_sinks", ["LOCAL_MODEL"]),
            ))
        return docs

    def get_gold_answer(self, sample: dict[str, Any]) -> str:
        return sample.get("gold_answer", "unknown")


class UnifiedDatasetLoader:
    def __init__(self, paths: list[str | Path]) -> None:
        self.loaders: list[tuple[DatasetLoader, str]] = []
        for path in paths:
            path_obj = Path(path)
            loader_type = self._detect_loader(path_obj)
            if loader_type == "kqa_pro":
                self.loaders.append((KQAProLoader(path_obj), "KQA-Pro"))
            else:
                self.loaders.append((SyntheticLoader(path_obj), "Synthetic"))

    def _detect_loader(self, path: Path) -> str:
        if path.suffix == ".jsonl":
            return "kqa_pro"
        return "synthetic"

    def load(self) -> Iterator[tuple[dict[str, Any], str]]:
        for loader, source_name in self.loaders:
            for sample in loader.load():
                yield sample, source_name

    def to_task_request(self, sample: dict[str, Any], source_name: str) -> TaskRequest:
        for loader, name in self.loaders:
            if name == source_name:
                task = loader.to_task_request(sample)
                task.metadata["source"] = source_name
                return task
        raise ValueError(f"Unknown source: {source_name}")

    def to_knowledge_documents(self, sample: dict[str, Any], source_name: str) -> list[KnowledgeDocument]:
        for loader, name in self.loaders:
            if name == source_name:
                docs = loader.to_knowledge_documents(sample)
                for doc in docs:
                    doc.source = f"{source_name}/{doc.source}"
                return docs
        raise ValueError(f"Unknown source: {source_name}")

    def get_gold_answer(self, sample: dict[str, Any], source_name: str) -> str:
        for loader, name in self.loaders:
            if name == source_name:
                return loader.get_gold_answer(sample)
        return "unknown"

    def count_samples(self) -> int:
        count = 0
        for _ in self.load():
            count += 1
        return count


def load_unified_dataset(paths: list[str | Path]) -> list[dict[str, Any]]:
    loader = UnifiedDatasetLoader(paths)
    tasks = []
    for sample, source_name in loader.load():
        task = loader.to_task_request(sample, source_name)
        docs = loader.to_knowledge_documents(sample, source_name)
        gold_answer = loader.get_gold_answer(sample, source_name)
        tasks.append({
            "task": task.model_dump(mode="json"),
            "documents": [d.model_dump(mode="json") for d in docs],
            "gold_answer": gold_answer,
            "source": source_name,
            "security": sample.get("security", {}),
            "attack": sample.get("attack", None),
        })
    return tasks


if __name__ == "__main__":
    paths = [
        Path(__file__).parent.parent / "candidate_50_v7_final.jsonl",
        Path(__file__).parent.parent / "data/kqa_pro_enhanced/sensitive_samples.jsonl",
        Path(__file__).parent.parent / "data/normal_tasks",
        Path(__file__).parent.parent / "data/attack_tasks",
    ]

    loader = UnifiedDatasetLoader(paths)
    print(f"Total samples: {loader.count_samples()}")

    for sample, source in loader.load():
        task = loader.to_task_request(sample, source)
        docs = loader.to_knowledge_documents(sample, source)
        gold = loader.get_gold_answer(sample, source)
        print(f"[{source}] {task.task_id[:20]}... | Query: {task.user_query[:40]}... | Docs: {len(docs)} | Gold: {gold[:20]}")