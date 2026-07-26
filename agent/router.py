from __future__ import annotations
from dataclasses import dataclass, field
from src.delegation.schemas import Confidentiality, ExecutionMode, TaskRequest

@dataclass(slots=True)
class RoutingSignals:
    injection_risk: str = "low"
    highest_sensitivity: Confidentiality = Confidentiality.PUBLIC
    safe_abstraction_available: bool = True
    protected_context_valid: bool = True
    residual_leakage: float = 0.2
    method_only_sufficient: bool = False
    cloud_available: bool = False
    cumulative_exposure_exceeded: bool = False
    attack_flags: list[str] = field(default_factory=list)

@dataclass(slots=True)
class RouteDecision:
    mode: ExecutionMode
    reasons: list[str]

class ExecutionRouter:
    def choose(self, task: TaskRequest, signals: RoutingSignals) -> RouteDecision:
        if signals.injection_risk == "high":
            return RouteDecision(ExecutionMode.LOCAL_ONLY, ["High prompt-injection risk"])
        if signals.cumulative_exposure_exceeded:
            return RouteDecision(ExecutionMode.LOCAL_ONLY, ["Cumulative exposure budget exceeded"])
        if not task.cloud_use_allowed:
            return RouteDecision(ExecutionMode.LOCAL_ONLY, ["Cloud use is not authorized"])
        if not signals.cloud_available:
            return RouteDecision(ExecutionMode.LOCAL_ONLY, ["Cloud model is not configured"])
        if signals.highest_sensitivity == Confidentiality.SECRET and not signals.safe_abstraction_available:
            return RouteDecision(ExecutionMode.LOCAL_ONLY,
                                 ["SECRET data has no approved safe abstraction"])
        if task.local_capability >= 0.75 and task.complexity <= 0.7:
            return RouteDecision(ExecutionMode.LOCAL_ONLY,
                                 ["Estimated local capability is sufficient"])
        if signals.method_only_sufficient:
            return RouteDecision(ExecutionMode.CLOUD_PLAN_LOCAL_EXECUTION,
                                 ["Cloud is needed only for method/plan generation"])
        if signals.protected_context_valid and signals.residual_leakage <= task.policy_budget:
            return RouteDecision(ExecutionMode.PROTECTED_CONTEXT_CLOUD_REASONING,
                                 ["Protected context fits the task leakage budget"])
        if signals.safe_abstraction_available:
            return RouteDecision(ExecutionMode.CLOUD_PLAN_LOCAL_EXECUTION,
                                 ["Protected reasoning exceeds budget; abstract planning remains possible"])
        return RouteDecision(ExecutionMode.LOCAL_ONLY, ["Fail-closed routing fallback"])
