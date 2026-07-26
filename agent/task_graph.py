from __future__ import annotations
from src.delegation.schemas import Confidentiality, EntityType, KnowledgeAtom, TaskGraph, TaskNode, TaskRequest

class TaskGraphBuilder:
    TYPE_TO_SLOT = {
        EntityType.PERSON: "PRIVATE_PERSON_CONTEXT",
        EntityType.PROJECT: "PRIVATE_PROJECT_CONTEXT",
        EntityType.BUDGET: "PRIVATE_BUDGET_CONTEXT",
        EntityType.SCORE: "PRIVATE_SCORE_CONTEXT",
        EntityType.MISCONCEPTION: "RECENT_ERROR_EXAMPLE",
        EntityType.HEALTH: "PRIVATE_HEALTH_CONTEXT",
        EntityType.ADDRESS: "PRIVATE_ADDRESS_CONTEXT",
    }

    def build(self, task: TaskRequest, atoms: list[KnowledgeAtom]) -> TaskGraph:
        query = task.user_query.casefold()
        if any(k in query for k in ["学习", "辅导", "tutor", "remediation"]):
            operations = ["diagnose_error", "sequence_scaffolds",
                          "generate_practice", "schedule_review"]
        else:
            operations = ["identify_dependencies", "assign_roles",
                          "order_milestones", "review_security_design"]
        private_slots = sorted({
            self.TYPE_TO_SLOT.get(atom.type, f"PRIVATE_{atom.type.value}_CONTEXT")
            for atom in atoms if atom.type != EntityType.PUBLIC_FACT
        })
        nodes, previous = [], None
        for index, operation in enumerate(operations, start=1):
            node_id = f"node-{index}"
            nodes.append(TaskNode(node_id=node_id, operation=operation,
                                  private_slots=private_slots if index == 1 else [],
                                  allowed_sinks=["LOCAL_MODEL", "CLOUD_PLANNER", "PROTECTED_CLOUD"],
                                  dependencies=[previous] if previous else []))
            previous = node_id
        source_to_sink = {}
        for atom in atoms:
            sinks = ["LOCAL_MODEL", "DISCLOSURE_COMPILER"]
            if atom.sensitivity != Confidentiality.PUBLIC:
                sinks.append("TOKEN_VAULT")
            if atom.type in {EntityType.PERSON, EntityType.PROJECT, EntityType.BUDGET, EntityType.MISCONCEPTION}:
                sinks.append("PROTECTED_CLOUD")
            if atom.type in {EntityType.CREDENTIAL, EntityType.ID, EntityType.PHONE, EntityType.HEALTH, EntityType.ADDRESS}:
                sinks = ["LOCAL_MODEL"]
            source_to_sink[atom.atom_id] = sorted(set(sinks))
        return TaskGraph(task_id=task.task_id, nodes=nodes,
                         private_atom_ids=[a.atom_id for a in atoms],
                         source_to_sink=source_to_sink)
