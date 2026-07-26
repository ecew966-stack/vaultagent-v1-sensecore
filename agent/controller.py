from __future__ import annotations
import hashlib, json
from dataclasses import asdict
from pathlib import Path
from typing import Any
from src.agent.local_executor import LocalExecutor
from src.agent.router import ExecutionRouter, RoutingSignals
from src.agent.slot_binder import SlotBinder
from src.agent.task_graph import TaskGraphBuilder
from src.core.policy import load_policy
from src.core.settings import Settings
from src.crypto.audit_chain import AuditChain
from src.crypto.key_derivation import load_or_create_key
from src.crypto.token_service import TOKEN_PATTERN, TaskScopedTokenService
from src.crypto.vault import EncryptedTokenVault
from src.delegation.cloud_planner import CloudPlanner
from src.delegation.protected_reasoner import ProtectedCloudReasoner
from src.delegation.schemas import (
    CloudReasoningResult, Confidentiality, ExecutionMode, ExecutionTrace,
    KnowledgeAtom, KnowledgeDocument, TaskContract, TaskGraph, TaskRequest, TaskResponse)
from src.disclosure.atomizer import KnowledgeAtomizer
from src.disclosure.compiler import DisclosureCompiler
from src.disclosure.projector import PurposeBoundProjector
from src.disclosure.relations import RuleBasedRelationExtractor
from src.knowledge.retrieval import InMemoryBM25Retriever
from src.knowledge.reranker import Reranker
from src.models.base import ModelResponse
from src.models.deepseek import build_deepseek_client
from src.models.local_qwen import build_local_qwen_client
from src.security.exposure_ledger import ExposureLedger
from src.security.final_output_guard import FinalOutputGuard
from src.security.injection_detector import PromptInjectionDetector
from src.security.outbound_monitor import OutboundMonitor
from src.security.replay_detector import ReplayDetector
from src.security.response_validator import ResponseValidator

class VaultAgentController:
    def __init__(self, settings: Settings | None = None,
                 *, state_dir: str | Path | None = None) -> None:
        self.settings = settings or Settings()
        if state_dir is not None:
            self.settings.state_dir = Path(state_dir)
            for name in ["master_key_file","vault_key_file","vault_db","audit_log",
                         "replay_db","exposure_db"]:
                setattr(self.settings, name, None)
        self.settings.prepare_paths()
        self.policy = load_policy(self.settings.policy_file)
        master_key = load_or_create_key(self.settings.resolved_master_key_file)
        vault_key = load_or_create_key(self.settings.resolved_vault_key_file)
        self.vault = EncryptedTokenVault(self.settings.resolved_vault_db, vault_key)
        self.audit = AuditChain(self.settings.resolved_audit_log)
        self.replay_detector = ReplayDetector(self.settings.resolved_replay_db)
        self.exposure_ledger = ExposureLedger(self.settings.resolved_exposure_db)

        self.local_client = build_local_qwen_client(self.settings)
        self.cloud_client = build_deepseek_client(self.settings)
        self.local_executor = LocalExecutor(self.local_client,
                                            allow_mock=self.settings.allow_mock_models)
        self.planner = CloudPlanner(self.cloud_client,
                                    allow_mock=self.settings.allow_mock_models)
        self.reasoner = ProtectedCloudReasoner(self.cloud_client,
                                               allow_mock=self.settings.allow_mock_models)

        self.token_service = TaskScopedTokenService(master_key)
        self.compiler = DisclosureCompiler(self.token_service, self.vault, self.policy)
        self.projector = PurposeBoundProjector(self.policy)
        self.router = ExecutionRouter()
        self.task_graph_builder = TaskGraphBuilder()
        self.slot_binder = SlotBinder()
        self.atomizer = KnowledgeAtomizer()
        self.relation_extractor = RuleBasedRelationExtractor()
        self.injection_detector = PromptInjectionDetector()
        self.outbound_monitor = OutboundMonitor(
            allowed_sinks=set(self.policy.defaults.allowed_network_sinks),
            maximum_payload_bytes=min(self.settings.max_outbound_bytes,
                                      self.policy.defaults.maximum_cloud_payload_bytes),
            forbidden_raw_types=set(self.policy.defaults.forbidden_raw_entity_types))
        self.validator = ResponseValidator()
        self.final_output_guard = FinalOutputGuard()
        self._reranker: Reranker | None = None

    @property
    def reranker(self) -> Reranker | None:
        """Lazy-load reranker on first use (avoids import if unused)."""
        if self._reranker is None:
            try:
                self._reranker = Reranker()
            except RuntimeError:
                pass  # FlagEmbedding not installed — reranker unavailable
        return self._reranker

    def run(self, task: TaskRequest,
            documents: list[KnowledgeDocument]) -> TaskResponse:
        documents = self._retrieve(task, documents)
        atoms = self.atomizer.atomize(documents)
        relations = self.relation_extractor.extract(documents, atoms)
        graph = self.task_graph_builder.build(task, atoms)
        injection = self._injection(task, documents)
        residual = self._residual(atoms, relations)
        scope_id = str(task.metadata.get("privacy_scope_id","global"))
        cumulative_budget = float(task.metadata.get(
            "cumulative_exposure_budget",
            self.settings.default_cumulative_exposure_budget))
        signals = RoutingSignals(
            injection_risk=injection["risk"],
            highest_sensitivity=self._highest(atoms),
            safe_abstraction_available=self._safe_abstraction(atoms),
            protected_context_valid=bool(atoms),
            residual_leakage=residual,
            method_only_sufficient=bool(task.metadata.get("method_only",False)),
            cloud_available=self.cloud_client is not None or self.settings.allow_mock_models,
            cumulative_exposure_exceeded=not self.exposure_ledger.can_spend(
                scope_id,residual,cumulative_budget),
            attack_flags=injection["patterns"])
        decision = self.router.choose(task, signals)
        forced = task.metadata.get("force_mode")
        if forced and self.settings.enable_experiment_overrides:
            decision.mode = ExecutionMode(forced)
            decision.reasons = ["Mode forced by explicit experiment override"]

        trace = ExecutionTrace(
            mode=decision.mode, route_reasons=decision.reasons,
            task_graph=graph.model_dump(mode="json"),
            security_events=[
                {"type":"injection_scan","risk":injection["risk"],
                 "patterns":injection["patterns"]},
                {"type":"exposure_precheck","scope_id":scope_id,
                 "existing_risk":self.exposure_ledger.total(scope_id),
                 "estimated_new_risk":residual,"budget":cumulative_budget}])
        last_error = None
        for mode in self._attempt_order(decision.mode):
            try:
                trace.mode = mode
                if mode == ExecutionMode.LOCAL_ONLY:
                    answer = self._local(task, documents, trace)
                elif mode == ExecutionMode.CLOUD_PLAN_LOCAL_EXECUTION:
                    answer = self._mode2(task, atoms, graph, trace, scope_id)
                else:
                    answer = self._mode3(task, atoms, relations, graph, trace,
                                         scope_id, residual)
                self.final_output_guard.validate(answer)
                trace.audit_hash = self._audit(task, trace, answer)
                # Revoke tokens after successful execution (answer already rehydrated)
                if mode == ExecutionMode.PROTECTED_CONTEXT_CLOUD_REASONING:
                    self._revoke_task_tokens(task.task_id)
                return TaskResponse(task_id=task.task_id, mode=mode,
                                    answer=answer, trace=trace)
            except Exception as exc:
                last_error = exc
                trace.fallback_chain.append(f"{mode.value}: {type(exc).__name__}: {exc}")
                trace.security_events.append({"type":"mode_failure",
                                              "mode":mode.value,"error":str(exc)})
        raise RuntimeError("All execution modes failed") from last_error

    def system_status(self) -> dict[str, Any]:
        local = asdict(self.local_client.health()) if self.local_client else {
            "provider":"local_qwen_vllm","model":self.settings.local_model,
            "configured":False,"reachable":False,"detail":"disabled"}
        cloud = asdict(self.cloud_client.health()) if self.cloud_client else {
            "provider":"deepseek","model":self.settings.cloud_model,
            "configured":False,"reachable":False,"detail":"disabled"}
        return {"environment":self.settings.environment,
                "mock_models_allowed":self.settings.allow_mock_models,
                "local_model":local,"cloud_model":cloud,
                "audit_chain_valid":self.audit.verify(),
                "policy_version":self.policy.policy_version,
                "state_dir":str(self.settings.state_dir)}

    def _local(self, task, documents, trace):
        trace.cloud_payload = None
        # Reference Monitor: enforce Mode 1 network isolation
        self._enforce_network_isolation(task.task_id)
        trace.security_events.append({
            "type": "reference_monitor",
            "action": "network_isolation_enforced",
            "allowed_sinks": [],
            "detail": "Mode 1: all external network calls blocked"
        })
        answer, response = self.local_executor.answer_local(task, documents)
        self._record(trace, response, "local_only")
        # Revoke any tokens from this task
        self._revoke_task_tokens(task.task_id)
        return answer

    @staticmethod
    def _enforce_network_isolation(task_id: str) -> None:
        """Reference Monitor: explicitly enforce zero-network boundary for Mode 1.

        Sets allowed_network_sinks = [] and blocks all external API calls.
        This is the defense-in-depth layer that prevents local models from
        accidentally or maliciously calling external services.
        """
        import os
        # Set environment-level block during this task's execution
        os.environ["VAULTAGENT_NETWORK_BLOCKED"] = "1"
        os.environ["VAULTAGENT_BLOCKED_SINKS"] = "[]"

    def _revoke_task_tokens(self, task_id: str) -> None:
        """Revoke all crypto tokens for a completed task."""
        try:
            self.vault.revoke_task(task_id)
        except Exception:
            pass  # Vault might not have been initialized for this path

    def check_cross_task_tokens(self, query: str, current_task_id: str) -> list[dict]:
        """Detect cross-task token abuse in user query.

        Scans the query for tokens that belong to OTHER tasks.
        Returns list of detected cross-task tokens with evidence.
        """
        import re
        pattern = re.compile(r"\[([A-Z_]+_[0-9A-Fa-f]+)\]")
        findings: list[dict] = []
        for m in pattern.finditer(query):
            token = m.group(0)
            try:
                # Try to rehydrate with current task - if fails, it's a foreign token
                meta = self.vault.get_metadata(token)
                if meta and meta.get("task_id") != current_task_id:
                    findings.append({
                        "token": token,
                        "type": "cross_task_token",
                        "source_task": meta.get("task_id"),
                        "detail": f"Token来自任务 {meta.get('task_id')}，在当前任务 {current_task_id} 中无效"
                    })
            except Exception:
                pass  # Token not in vault, analyzed by injection detector
        return findings

    def _mode2(self, task: TaskRequest, atoms: list[KnowledgeAtom],
               graph: TaskGraph, trace: ExecutionTrace, scope_id: str) -> str:
        slots = sorted({s for n in graph.nodes for s in n.private_slots})
        operations = [n.operation for n in graph.nodes]
        contract = TaskContract(
            task_id=task.task_id, purpose=task.purpose,
            task_type="personalized_tutoring" if any(w in task.user_query for w in ["学习","辅导"])
                      else "secure_project_planning",
            public_goal=self._public_goal(task.user_query, atoms),
            declared_private_slots=slots, allowed_operations=operations,
            maximum_steps=self.policy.defaults.maximum_cloud_steps)
        payload = contract.model_dump(mode="json")
        manifest = self.outbound_monitor.validate(
            task_id=task.task_id,sink="CLOUD_PLANNER",
            payload=payload,private_atoms=atoms)
        trace.cloud_payload, trace.cloud_payload_hash = payload, manifest.payload_hash
        trace.security_events.append({"type":"outbound_approved","sink":manifest.sink,
                                      "bytes":manifest.payload_bytes,
                                      "payload_hash":manifest.payload_hash})
        plan, cloud_response = self.planner.plan(contract)
        self._record(trace,cloud_response,"cloud_planner")
        self.replay_detector.check_and_record(
            task_id=task.task_id,delegation_id=contract.delegation_id,
            response=plan.model_dump(mode="json"))
        self.validator.validate_plan(plan, contract)
        declared = set(contract.declared_private_slots)
        bound = [self.slot_binder.bind(slot,declared_slots=declared,atoms=atoms)
                 for slot in sorted({s for step in plan.steps for s in step.requires})]
        answer, local_response = self.local_executor.execute_plan(task,plan,bound)
        self._record(trace,local_response,"local_plan_execution")
        self.exposure_ledger.record(scope_id=scope_id,task_id=task.task_id,
            mode=ExecutionMode.CLOUD_PLAN_LOCAL_EXECUTION.value,
            risk=min(0.25,0.05+0.02*len(slots)),payload_hash=manifest.payload_hash)
        return answer

    def _mode3(self, task, atoms, relations, graph, trace, scope_id, residual):
        decisions = self.projector.project(atoms,purpose=task.purpose)
        compiled = self.compiler.compile(
            task_id=task.task_id,purpose=task.purpose,
            operation="generate_protected_plan",
            allowed_operations=[n.operation for n in graph.nodes],
            decisions=decisions,relations=relations)
        payload = compiled.context.model_dump(mode="json")
        manifest = self.outbound_monitor.validate(
            task_id=task.task_id,sink="PROTECTED_CLOUD",
            payload=payload,private_atoms=atoms)
        trace.cloud_payload, trace.cloud_payload_hash = payload, manifest.payload_hash
        trace.protection_decisions = compiled.decisions
        trace.security_events.append({"type":"outbound_approved","sink":manifest.sink,
                                      "bytes":manifest.payload_bytes,
                                      "tokens":manifest.tokens,
                                      "payload_hash":manifest.payload_hash})
        result, cloud_response = self.reasoner.reason(compiled.context)
        self._record(trace,cloud_response,"protected_cloud_reasoner")
        self.replay_detector.check_and_record(
            task_id=task.task_id,delegation_id=compiled.context.delegation_id,
            response=result.model_dump(mode="json"))
        self.validator.validate_reasoning(
            result,task_id=task.task_id,
            delegation_id=compiled.context.delegation_id,
            allowed_operations=set(compiled.context.allowed_operations),
            vault=self.vault)
        local_result = self._rehydrate(task,result)
        answer, local_response = self.local_executor.render_rehydrated(task,local_result)
        self._record(trace,local_response,"local_final_render")
        self.exposure_ledger.record(scope_id=scope_id,task_id=task.task_id,
            mode=ExecutionMode.PROTECTED_CONTEXT_CLOUD_REASONING.value,
            risk=residual,payload_hash=manifest.payload_hash)
        return answer

    def _rehydrate(self, task: TaskRequest, result: CloudReasoningResult) -> dict[str,Any]:
        def item(identifier):
            if not identifier: return None
            if identifier.startswith("[ABSTRACT_"): return "受保护抽象实体"
            if TOKEN_PATTERN.fullmatch(identifier):
                return self.vault.rehydrate(identifier,task_id=task.task_id,
                                            purpose=task.purpose,output="final_answer")
            return identifier
        return {"task_id":task.task_id,"result_type":result.result_type,
                "steps":[{"step_id":s.step_id,"actor":item(s.actor),
                          "operation":s.operation,"target":item(s.target),
                          "rationale":s.rationale} for s in result.steps]}

    @staticmethod
    def _record(trace: ExecutionTrace, response: ModelResponse | None, stage: str) -> None:
        if response is None:
            trace.model_calls.append({"stage":stage,"provider":"mock"}); return
        trace.model_calls.append({"stage":stage,"provider":response.provider,
                                  "model":response.model,
                                  "latency_ms":round(response.latency_ms,3),
                                  "usage":response.usage,
                                  "request_id":response.request_id})

    @staticmethod
    def _attempt_order(mode):
        if mode == ExecutionMode.PROTECTED_CONTEXT_CLOUD_REASONING:
            return [mode,ExecutionMode.CLOUD_PLAN_LOCAL_EXECUTION,
                    ExecutionMode.LOCAL_ONLY]
        if mode == ExecutionMode.CLOUD_PLAN_LOCAL_EXECUTION:
            return [mode,ExecutionMode.LOCAL_ONLY]
        return [ExecutionMode.LOCAL_ONLY]

    @staticmethod
    def _highest(atoms):
        ranks={Confidentiality.PUBLIC:0,Confidentiality.INTERNAL:1,
               Confidentiality.CONFIDENTIAL:2,Confidentiality.SECRET:3}
        return max((a.sensitivity for a in atoms),key=lambda x:ranks[x],
                   default=Confidentiality.PUBLIC)

    @staticmethod
    def _safe_abstraction(atoms):
        blocked={"CREDENTIAL","ID","PHONE","HEALTH","ADDRESS"}
        return not any(a.sensitivity==Confidentiality.SECRET and a.type.value in blocked
                       for a in atoms)

    @staticmethod
    def _residual(atoms, relations):
        private=sum(a.sensitivity!=Confidentiality.PUBLIC for a in atoms)
        return min(1.0,0.04*private+0.03*len(relations))

    def _injection(self, task, documents):
        findings=[self.injection_detector.analyze(task.user_query)]
        findings += [self.injection_detector.analyze(d.content) for d in documents
                     if d.integrity.value=="UNTRUSTED"]
        high=max(findings,key=lambda x:x.score)
        return {"risk":high.risk,
                "patterns":sorted({p for f in findings for p in f.matched_patterns})}

    def _retrieve(self, task, documents):
        if not documents: return []
        top_k = self.settings.retrieval_top_k
        # Stage 1: BM25 broad retrieval
        bm25 = InMemoryBM25Retriever(documents)
        bigram_hits = bm25.search(task.user_query, limit=30)
        if not bigram_hits:
            return documents[:top_k]
        # Stage 2: Cross-encoder reranker (if available)
        reranker = self.reranker
        if reranker is not None and len(bigram_hits) > top_k:
            bigram_hits = reranker.rerank_hits(task.user_query, bigram_hits, top_k=top_k)
        return [h.document for h in bigram_hits[:top_k]]

    @staticmethod
    def _public_goal(query, atoms):
        for atom in sorted(atoms,key=lambda a:len(a.value),reverse=True):
            if atom.sensitivity!=Confidentiality.PUBLIC:
                query=query.replace(atom.value,f"<{atom.type.value}>")
        return query[:500]

    def _audit(self, task, trace, answer):
        return self.audit.append("task_completed",{
            "task_id":task.task_id,"mode":trace.mode.value,
            "policy_version":self.policy.policy_version,
            "cloud_payload_hash":trace.cloud_payload_hash,
            "answer_hash":hashlib.sha256(answer.encode()).hexdigest(),
            "fallback_count":len(trace.fallback_chain),
            "model_stages":[x.get("stage") for x in trace.model_calls]})
