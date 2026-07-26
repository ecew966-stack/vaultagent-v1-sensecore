from __future__ import annotations
import base64, os
from pathlib import Path
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

def derive_task_key(master_key: bytes, task_id: str, length: int = 32) -> bytes:
    if len(master_key) < 32:
        raise ValueError("master_key must contain at least 256 bits")
    return HKDF(algorithm=hashes.SHA256(), length=length,
                salt=task_id.encode("utf-8"),
                info=b"VaultAgent-Token-v2").derive(master_key)

def load_or_create_key(path: str | Path, *, length: int = 32) -> bytes:
    key_path = Path(path)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        key = base64.urlsafe_b64decode(key_path.read_text(encoding="utf-8").strip().encode("ascii"))
        if len(key) != length:
            raise ValueError(f"Invalid key length in {key_path}")
        return key
    key = os.urandom(length)
    key_path.write_text(base64.urlsafe_b64encode(key).decode("ascii"), encoding="utf-8")
    try:
        key_path.chmod(0o600)
    except OSError:
        pass
    return key
