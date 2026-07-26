from __future__ import annotations
import json, os, sqlite3, threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from src.delegation.schemas import EntityType, VaultMetadata

class VaultError(RuntimeError): pass
class UnknownTokenError(VaultError): pass
class UnauthorizedRecoveryError(VaultError): pass
class ExpiredTokenError(VaultError): pass
class CrossTaskTokenError(VaultError): pass

class EncryptedTokenVault:
    def __init__(self, db_path: str | Path, key: bytes) -> None:
        if len(key) != 32:
            raise ValueError("AES-256-GCM requires a 32-byte key")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.aead = AESGCM(key)
        self._lock = threading.RLock()
        with self._connect() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS token_vault (
                token TEXT PRIMARY KEY, task_id TEXT NOT NULL, nonce BLOB NOT NULL,
                ciphertext BLOB NOT NULL, entity_type TEXT NOT NULL, source TEXT NOT NULL,
                allowed_purposes TEXT NOT NULL, allowed_outputs TEXT NOT NULL,
                expires_at TEXT NOT NULL, status TEXT NOT NULL,
                policy_version TEXT NOT NULL, created_at TEXT NOT NULL)""")
            con.execute("CREATE INDEX IF NOT EXISTS idx_vault_task ON token_vault(task_id)")

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    @staticmethod
    def _aad(metadata: VaultMetadata) -> bytes:
        return json.dumps({"task_id": metadata.task_id, "token": metadata.token,
                           "entity_type": metadata.entity_type.value,
                           "policy_version": metadata.policy_version},
                          sort_keys=True, separators=(",", ":")).encode("utf-8")

    def put(self, *, task_id: str, token: str, value: str, entity_type: EntityType,
            source: str, allowed_purposes: list[str], allowed_outputs: list[str],
            ttl_seconds: int = 3600, policy_version: str = "cssd-v2",
            extra_metadata: dict[str, Any] | None = None) -> VaultMetadata:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        metadata = VaultMetadata(task_id=task_id, token=token, entity_type=entity_type,
                                 source=source, allowed_purposes=allowed_purposes,
                                 allowed_outputs=allowed_outputs, expires_at=expires_at,
                                 policy_version=policy_version)
        plaintext = json.dumps({"value": value, "metadata": extra_metadata or {}},
                               ensure_ascii=False, sort_keys=True).encode("utf-8")
        nonce = os.urandom(12)
        ciphertext = self.aead.encrypt(nonce, plaintext, self._aad(metadata))
        with self._lock, self._connect() as con:
            con.execute("""INSERT OR REPLACE INTO token_vault
                (token, task_id, nonce, ciphertext, entity_type, source, allowed_purposes,
                 allowed_outputs, expires_at, status, policy_version, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (token, task_id, nonce, ciphertext, entity_type.value, source,
                 json.dumps(allowed_purposes), json.dumps(allowed_outputs),
                 expires_at.isoformat(), "active", policy_version,
                 datetime.now(timezone.utc).isoformat()))
        return metadata

    def get_metadata(self, token: str) -> VaultMetadata:
        with self._connect() as con:
            row = con.execute("SELECT * FROM token_vault WHERE token = ?", (token,)).fetchone()
        if row is None:
            raise UnknownTokenError(token)
        return VaultMetadata(task_id=row["task_id"], token=row["token"],
                             entity_type=EntityType(row["entity_type"]), source=row["source"],
                             allowed_purposes=json.loads(row["allowed_purposes"]),
                             allowed_outputs=json.loads(row["allowed_outputs"]),
                             expires_at=datetime.fromisoformat(row["expires_at"]),
                             status=row["status"], policy_version=row["policy_version"])

    def rehydrate(self, token: str, *, task_id: str, purpose: str, output: str) -> str:
        metadata = self.get_metadata(token)
        if metadata.task_id != task_id:
            raise CrossTaskTokenError(token)
        if metadata.status != "active":
            raise UnauthorizedRecoveryError(f"Token status is {metadata.status}")
        if metadata.is_expired():
            raise ExpiredTokenError(token)
        if purpose not in metadata.allowed_purposes or output not in metadata.allowed_outputs:
            raise UnauthorizedRecoveryError("Purpose or output is not authorized")
        with self._connect() as con:
            row = con.execute("SELECT nonce, ciphertext FROM token_vault WHERE token = ?",
                              (token,)).fetchone()
        try:
            plaintext = self.aead.decrypt(row["nonce"], row["ciphertext"], self._aad(metadata))
        except Exception as exc:
            raise UnauthorizedRecoveryError("Vault integrity verification failed") from exc
        return str(json.loads(plaintext.decode("utf-8"))["value"])

    def revoke_task(self, task_id: str) -> int:
        with self._lock, self._connect() as con:
            cursor = con.execute("UPDATE token_vault SET status='revoked' WHERE task_id=? AND status='active'",
                                 (task_id,))
            return cursor.rowcount

    def list_task_tokens(self, task_id: str) -> list[str]:
        with self._connect() as con:
            rows = con.execute("SELECT token FROM token_vault WHERE task_id=? AND status='active'",
                               (task_id,)).fetchall()
        return [row["token"] for row in rows]
