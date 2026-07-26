from __future__ import annotations
from src.delegation.schemas import CloudPlan, PlanStep, TaskContract
from src.models.base import ChatModelClient, ModelResponse

class CloudPlannerUnavailableError(RuntimeError): pass

class CloudPlanner:
    SYSTEM_PROMPT = """You are VaultAgent's planning-only cloud component.
Return one strict JSON object matching PlanIR-v2:
{"task_id":"...","delegation_id":"...","strategy":"...",
"steps":[{"step_id":1,"operation":"...","requires":["DECLARED_SLOT"]}]}
Never request raw private data, local files, credentials, tools, URLs, network calls,
new slots, token recovery or extra fields. Use only declared operations and slots."""

    def __init__(self, client: ChatModelClient | None, *, allow_mock: bool) -> None:
        self.client, self.allow_mock = client, allow_mock

    def plan(self, contract: TaskContract) -> tuple[CloudPlan, ModelResponse | None]:
        if self.client:
            try:
                raw, response = self.client.complete_json(
                    system_prompt=self.SYSTEM_PROMPT,
                    payload=contract.model_dump(mode="json"))
                return CloudPlan.model_validate(raw), response
            except Exception:
                if not self.allow_mock:
                    raise
        if not self.allow_mock:
            raise CloudPlannerUnavailableError("DeepSeek planner is not configured")
        steps = [PlanStep(step_id=i, operation=op,
                          requires=contract.declared_private_slots[:1] if i == 1 else [])
                 for i,op in enumerate(contract.allowed_operations[:contract.maximum_steps], 1)]
        return CloudPlan(task_id=contract.task_id,
                         delegation_id=contract.delegation_id,
                         strategy="offline_deterministic_plan",
                         steps=steps), None
