from __future__ import annotations
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

class ExecutionMode(StrEnum):
    LOCAL_ONLY = "LOCAL_ONLY"
    CLOUD_PLAN_LOCAL_EXECUTION = "CLOUD_PLAN_LOCAL_EXECUTION"
    PROTECTED_CONTEXT_CLOUD_REASONING = "PROTECTED_CONTEXT_CLOUD_REASONING"

class Confidentiality(StrEnum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    SECRET = "SECRET"

class Integrity(StrEnum):
    TRUSTED = "TRUSTED"
    UNTRUSTED = "UNTRUSTED"

class DocumentRole(StrEnum):
    DATA_ONLY = "DATA_ONLY"
    SYSTEM = "SYSTEM"

class EntityType(StrEnum):
    PERSON = "PERSON"
    PROJECT = "PROJECT"
    ORGANIZATION = "ORGANIZATION"
    BUDGET = "BUDGET"
    SCORE = "SCORE"
    PHONE = "PHONE"
    EMAIL = "EMAIL"
    ID = "ID"
    CREDENTIAL = "CREDENTIAL"
    HEALTH = "HEALTH"
    ADDRESS = "ADDRESS"
    MISCONCEPTION = "MISCONCEPTION"
    TECHNICAL_SECRET = "TECHNICAL_SECRET"
    PUBLIC_FACT = "PUBLIC_FACT"
    OTHER = "OTHER"

class ProtectionOperation(StrEnum):
    KEEP_PUBLIC = "KEEP_PUBLIC"
    TOKENIZE = "TOKENIZE"
    GENERALIZE = "GENERALIZE"
    PREDICATE = "PREDICATE"
    LOCAL_SUMMARIZE = "LOCAL_SUMMARIZE"
    BLOCK = "BLOCK"

class TaskRequest(StrictModel):
    task_id: str = Field(default_factory=lambda: f"task-{uuid4().hex[:12]}")
    user_query: str
    purpose: str = "planning"
    cloud_use_allowed: bool = True
    local_capability: float = Field(default=0.5, ge=0, le=1)
    complexity: float = Field(default=0.5, ge=0, le=1)
    policy_budget: float = Field(default=0.4, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

class KnowledgeDocument(StrictModel):
    doc_id: str
    content: str
    source: str
    confidentiality: Confidentiality = Confidentiality.CONFIDENTIAL
    integrity: Integrity = Integrity.TRUSTED
    role: DocumentRole = DocumentRole.DATA_ONLY
    allowed_purposes: list[str] = Field(default_factory=list)
    allowed_sinks: list[str] = Field(default_factory=lambda: ["LOCAL_MODEL"])

class KnowledgeAtom(StrictModel):
    atom_id: str
    value: str
    type: EntityType
    source: str
    sensitivity: Confidentiality
    integrity: Integrity
    attributes: dict[str, Any] = Field(default_factory=dict)

class Relation(StrictModel):
    subject: str
    predicate: str
    object: str
    sensitivity: Confidentiality = Confidentiality.CONFIDENTIAL
    source: str | None = None

class TaskNode(StrictModel):
    node_id: str
    operation: str
    private_slots: list[str] = Field(default_factory=list)
    allowed_sinks: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)

class TaskGraph(StrictModel):
    task_id: str
    nodes: list[TaskNode]
    private_atom_ids: list[str] = Field(default_factory=list)
    source_to_sink: dict[str, list[str]] = Field(default_factory=dict)

class TaskContract(StrictModel):
    task_id: str
    delegation_id: str = Field(default_factory=lambda: f"deleg-{uuid4().hex[:16]}")
    purpose: str
    task_type: str
    public_goal: str
    learner_abstraction: dict[str, Any] = Field(default_factory=dict)
    declared_private_slots: list[str]
    allowed_operations: list[str]
    maximum_steps: int = Field(default=8, ge=1, le=32)
    output_schema: str = "PlanIR-v2"
    allowed_sinks: list[str] = Field(default_factory=lambda: ["CLOUD_PLANNER"])

class PlanStep(StrictModel):
    step_id: int
    operation: str
    requires: list[str] = Field(default_factory=list)

class CloudPlan(StrictModel):
    task_id: str
    delegation_id: str
    strategy: str
    steps: list[PlanStep]

class ProtectedEntity(StrictModel):
    id: str
    type: EntityType
    attributes: dict[str, Any] = Field(default_factory=dict)
    sensitivity: Confidentiality = Confidentiality.CONFIDENTIAL

class ProtectedRelation(StrictModel):
    subject: str
    predicate: str
    object: str
    sensitivity: Confidentiality = Confidentiality.CONFIDENTIAL

class ProtectedContext(StrictModel):
    task_id: str
    delegation_id: str = Field(default_factory=lambda: f"deleg-{uuid4().hex[:16]}")
    purpose: str
    operation: str
    constraints: dict[str, Any] = Field(default_factory=dict)
    entities: list[ProtectedEntity] = Field(default_factory=list)
    relations: list[ProtectedRelation] = Field(default_factory=list)
    allowed_operations: list[str] = Field(default_factory=list)
    policy_version: str = "cssd-v2"

class ReasoningStep(StrictModel):
    step_id: int
    actor: str | None = None
    operation: str
    target: str | None = None
    rationale: str | None = None
    requires: list[str] = Field(default_factory=list)

class CloudReasoningResult(StrictModel):
    task_id: str
    delegation_id: str
    result_type: str
    steps: list[ReasoningStep]

class BoundSlot(StrictModel):
    name: str
    atom_ids: list[str]
    local_values: list[str]
    sources: list[str]

class ExecutionTrace(StrictModel):
    mode: ExecutionMode
    route_reasons: list[str] = Field(default_factory=list)
    fallback_chain: list[str] = Field(default_factory=list)
    task_graph: dict[str, Any] = Field(default_factory=dict)
    cloud_payload: dict[str, Any] | None = None
    cloud_payload_hash: str | None = None
    protection_decisions: list[dict[str, Any]] = Field(default_factory=list)
    security_events: list[dict[str, Any]] = Field(default_factory=list)
    model_calls: list[dict[str, Any]] = Field(default_factory=list)
    audit_hash: str | None = None

class TaskResponse(StrictModel):
    task_id: str
    mode: ExecutionMode
    answer: str
    trace: ExecutionTrace

class VaultMetadata(StrictModel):
    task_id: str
    token: str
    entity_type: EntityType
    source: str
    allowed_purposes: list[str]
    allowed_outputs: list[str]
    expires_at: datetime
    status: str = "active"
    policy_version: str = "cssd-v2"

    def is_expired(self) -> bool:
        current = datetime.now(timezone.utc)
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return current >= expires
