from __future__ import annotations
from functools import lru_cache
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import Field
from src.agent.controller import VaultAgentController
from src.core.settings import Settings
from src.delegation.schemas import KnowledgeDocument, StrictModel, TaskRequest, TaskResponse
from src.api.routers import (
    tasks_router,
    knowledge_router,
    security_router,
    benchmarks_router,
    events_router,
)

class RunRequest(StrictModel):
    task: TaskRequest
    documents: list[KnowledgeDocument] = Field(default_factory=list)

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

@lru_cache(maxsize=1)
def get_controller() -> VaultAgentController:
    return VaultAgentController(get_settings())

app = FastAPI(title="VaultAgent API",version="0.2.0",
              description="Qwen-local + DeepSeek-cloud secure delegation.")

# ── CORS Middleware ─────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id", "X-Timestamp"],
)

# ── Include API Routers ─────────────────────────────────────────────────────

app.include_router(tasks_router)
app.include_router(knowledge_router)
app.include_router(security_router)
app.include_router(benchmarks_router)
app.include_router(events_router)

# ── Backward-compatible routes ──────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status":"ok","service":"vaultagent","version":"0.2.0"}

@app.get("/ready")
def ready():
    status=get_controller().system_status()
    settings=get_settings()
    local_ok=status["local_model"]["reachable"] or settings.allow_mock_models or not settings.local_required
    cloud_ok=status["cloud_model"]["reachable"] or settings.allow_mock_models or not settings.cloud_enabled
    if not(local_ok and cloud_ok and status["audit_chain_valid"]):
        raise HTTPException(status_code=503,detail=status)
    return {"ready":True,"details":status}

@app.get("/system/status")
def system_status_root():
    """Root-level system status (used by frontend)."""
    settings = get_settings()
    if settings.allow_mock_models:
        return {
            "mock_models_allowed": True,
            "policy_version": "cssd-v2.1",
            "environment": "demo",
            "state_dir": "./data/vaultagent_state",
            "local_model": {"status": "ready", "model": "Qwen2.5-7B-Instruct", "device": "cuda:0 (H100)"},
            "cloud_model": {"status": "connected", "model": "DeepSeek V3 / v4-pro", "provider": "DeepSeek API"},
            "audit_chain_valid": True,
        }
    try:
        return get_controller().system_status()
    except Exception:
        return {
            "mock_models_allowed": False,
            "local_model": {"model": "Qwen2.5-7B-Instruct"},
            "cloud_model": {"model": "-"},
            "audit_chain_valid": False,
        }

@app.get("/v1/audit/verify")
def verify_audit():
    return {"valid":get_controller().audit.verify()}

@app.post("/v1/tasks/run",response_model=TaskResponse)
def run_task(request: RunRequest):
    return get_controller().run(request.task,request.documents)
