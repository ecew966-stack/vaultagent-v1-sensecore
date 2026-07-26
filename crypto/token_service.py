from __future__ import annotations
import hashlib, hmac, json, re
from typing import Any
from src.crypto.key_derivation import derive_task_key
from src.delegation.schemas import EntityType

TOKEN_PATTERN = re.compile(r"^\[(?P<type>[A-Z_]+)_(?P<digest>[0-9A-F]{12,32})\]$")

def canonicalize(value: Any) -> bytes:
    if isinstance(value, str):
        return " ".join(value.strip().split()).casefold().encode("utf-8")
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")

class TaskScopedTokenService:
    def __init__(self, master_key: bytes, digest_chars: int = 16) -> None:
        if digest_chars < 12:
            raise ValueError("digest_chars must be >= 12")
        self.master_key, self.digest_chars = master_key, digest_chars

    def issue(self, task_id: str, entity_type: EntityType, value: Any) -> str:
        task_key = derive_task_key(self.master_key, task_id)
        digest = hmac.new(task_key, canonicalize(value), hashlib.sha256).hexdigest()
        return f"[{entity_type.value}_{digest[:self.digest_chars].upper()}]"

    @staticmethod
    def parse(token: str) -> tuple[EntityType, str] | None:
        match = TOKEN_PATTERN.fullmatch(token)
        if not match:
            return None
        return EntityType(match.group("type")), match.group("digest")
