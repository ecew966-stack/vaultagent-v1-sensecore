from __future__ import annotations
import json, os, platform, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.agent.controller import VaultAgentController
from src.core.settings import Settings

def version(command: str, args: list[str], timeout: int = 10):
    if not shutil.which(command): return None
    try:
        r=subprocess.run([command,*args],capture_output=True,text=True,
                         timeout=timeout,check=False)
        return (r.stdout or r.stderr).strip().splitlines()[0]
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"

def check_file(path: Path) -> dict:
    exists = path.exists()
    readable = exists and path.is_file() and os.access(path, os.R_OK)
    return {"exists": exists, "readable": readable, "path": str(path)}

def check_directory(path: Path) -> dict:
    exists = path.exists()
    writable = exists and path.is_dir() and os.access(path, os.W_OK)
    return {"exists": exists, "writable": writable, "path": str(path)}

def check_env_vars(prefix: str = "VAULTAGENT_") -> dict:
    vars_found = {}
    for key, value in os.environ.items():
        if key.startswith(prefix):
            masked = "******" if "KEY" in key or "SECRET" in key else value[:50]
            vars_found[key] = masked
    return vars_found

def check_imports() -> dict:
    imports = {}
    modules = ["fastapi", "pydantic", "pydantic_settings", "cryptography",
               "httpx", "sqlalchemy", "streamlit", "qdrant_client"]
    for mod in modules:
        try:
            __import__(mod)
            imports[mod] = {"available": True}
        except ImportError as exc:
            imports[mod] = {"available": False, "error": str(exc)}
    return imports

def main():
    settings=Settings()
    report={"version":"0.2.0","python":sys.version,"platform":platform.platform(),
            "cwd":str(Path.cwd()),"architecture":platform.machine()}
    report["environment"]={
        "env_file":str(settings.model_config.get("env_file",".env")),
        "environment":settings.environment,
        "vaultagent_vars":check_env_vars()
    }
    report["dependencies"]={
        "docker":version("docker",["--version"]),
        "nvidia_smi":version("nvidia-smi",["--query-gpu=name","--format=csv,noheader"]),
        "vllm":version("vllm",["--version"]),
        "python_modules":check_imports()
    }
    report["files"]={
        "policy_file":check_file(settings.policy_file),
        "state_dir":check_directory(settings.state_dir),
        "master_key":check_file(settings.resolved_master_key_file),
        "vault_key":check_file(settings.resolved_vault_key_file),
        "vault_db":check_file(settings.resolved_vault_db),
        "audit_log":check_file(settings.resolved_audit_log),
        "replay_db":check_file(settings.resolved_replay_db),
        "exposure_db":check_file(settings.resolved_exposure_db),
        "models_yaml":check_file(ROOT/"configs/models.yaml"),
        "experiments_yaml":check_file(ROOT/"configs/experiments.yaml"),
        "policies_yaml":check_file(ROOT/"configs/policies.yaml")
    }
    try:
        controller=VaultAgentController(settings)
        report["system_status"]=controller.system_status()
        report["audit_chain_valid"]=controller.audit.verify()
    except Exception as exc:
        report["controller_error"]=str(exc)
        report["system_status"]={"error":str(exc)}
        report["audit_chain_valid"]=False
    report["security_checks"]={
        "policy_exists":settings.policy_file.exists(),
        "state_writable":settings.state_dir.exists() and os.access(settings.state_dir, os.W_OK),
        "production_mock_disabled":not(settings.environment=="production" and settings.allow_mock_models),
        "local_required_but_disabled":not(settings.local_required and not settings.local_enabled),
        "cloud_enabled_without_key":not(settings.cloud_enabled and not settings.cloud_api_key)
    }
    report["model_config"]={
        "local_enabled":settings.local_enabled,
        "local_model":settings.local_model,
        "local_base_url":settings.local_base_url,
        "cloud_enabled":settings.cloud_enabled,
        "cloud_model":settings.cloud_model,
        "cloud_base_url":settings.cloud_base_url,
        "qdrant_enabled":settings.qdrant_enabled,
        "qdrant_url":settings.qdrant_url,
        "allow_mock_models":settings.allow_mock_models,
        "enable_experiment_overrides":settings.enable_experiment_overrides
    }
    report["ok"]=all([
        settings.policy_file.exists(),
        settings.state_dir.exists() and os.access(settings.state_dir, os.W_OK),
        not(settings.environment=="production" and settings.allow_mock_models),
        not(settings.local_required and not settings.local_enabled)
    ])
    print(json.dumps(report,ensure_ascii=False,indent=2))
    sys.exit(0 if report["ok"] else 1)
if __name__=="__main__": main()
