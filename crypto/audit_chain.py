from __future__ import annotations
import hashlib, json, threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

class AuditChain:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    @staticmethod
    def _hash(payload: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                         separators=(",", ":")).encode("utf-8")).hexdigest()

    def _last_hash(self) -> str:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return "0" * 64
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return json.loads(lines[-1])["event_hash"] if lines else "0" * 64

    def append(self, event_type: str, payload: dict[str, Any]) -> str:
        with self._lock:
            record = {"timestamp": datetime.now(timezone.utc).isoformat(),
                      "event_type": event_type, "payload": payload,
                      "previous_hash": self._last_hash()}
            record["event_hash"] = self._hash(record)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            return record["event_hash"]

    def verify(self) -> bool:
        previous = "0" * 64
        if not self.path.exists():
            return True
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip(): continue
            record = json.loads(line)
            event_hash = record.pop("event_hash")
            if record["previous_hash"] != previous or self._hash(record) != event_hash:
                return False
            previous = event_hash
        return True
