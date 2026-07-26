from __future__ import annotations
from src.delegation.schemas import CloudReasoningResult, ProtectedContext, ReasoningStep
from src.models.base import ChatModelClient, ModelResponse

class ProtectedReasonerUnavailableError(RuntimeError): pass

class ProtectedCloudReasoner:
    SYSTEM_PROMPT = """You are VaultAgent's protected-context reasoner.
Return one strict JSON object:
{"task_id":"...","delegation_id":"...","result_type":"protected_plan",
"steps":[{"step_id":1,"actor":"existing id or null","operation":"allowed operation",
"target":"existing id or null","rationale":"short protected-view rationale"}]}
Reason only over supplied JSON. Do not create, alter, split, infer or request recovery
of identifiers. Do not request tools, files, URLs or raw private data."""

    def __init__(self, client: ChatModelClient | None, *, allow_mock: bool) -> None:
        self.client, self.allow_mock = client, allow_mock

    def reason(self, context: ProtectedContext
               ) -> tuple[CloudReasoningResult, ModelResponse | None]:
        if self.client:
            try:
                raw, response = self.client.complete_json(
                    system_prompt=self.SYSTEM_PROMPT,
                    payload=context.model_dump(mode="json"))
                return CloudReasoningResult.model_validate(raw), response
            except Exception:
                if not self.allow_mock:
                    raise
        if not self.allow_mock:
            raise ProtectedReasonerUnavailableError("DeepSeek reasoner is not configured")
        actors = [e.id for e in context.entities
                  if e.type.value in {"PERSON","ORGANIZATION"}]
        targets = [e.id for e in context.entities
                   if e.type.value in {"PROJECT","PUBLIC_FACT"}]
        fallback = targets[0] if targets else (context.entities[0].id if context.entities else None)
        steps = [ReasoningStep(step_id=i,
                               actor=actors[(i-1)%len(actors)] if actors else None,
                               operation=op, target=fallback,
                               rationale="Derived only from protected semantic view")
                 for i,op in enumerate(context.allowed_operations[:4], 1)]
        return CloudReasoningResult(task_id=context.task_id,
                                    delegation_id=context.delegation_id,
                                    result_type="protected_plan",
                                    steps=steps), None
