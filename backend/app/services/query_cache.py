"""In-memory TTL cache for Oracle / agent responses.

Demo + repeat-query optimization. Same (user, question) within the TTL window
returns the cached response instead of re-running retrieval + LLM. Keeps
synthesis fast on stage when judges or the presenter re-run the same query.

Process-local (no Redis) — fine for single-replica Railway deploys. Switch to
Redis with the same get/set interface if we ever scale beyond one worker.
"""

import time
import hashlib
import threading
from typing import Optional, Any

_TTL_SEC = 1800
_MAX_ENTRIES = 256

_lock = threading.Lock()
_store: dict[str, tuple[float, Any]] = {}


def _make_key(user_email: str, question: str) -> str:
    norm_q = " ".join((question or "").strip().lower().split())
    norm_u = (user_email or "").strip().lower()
    return hashlib.sha256(f"{norm_u}|{norm_q}".encode()).hexdigest()


def get(user_email: str, question: str) -> Optional[Any]:
    key = _make_key(user_email, question)
    now = time.time()
    with _lock:
        entry = _store.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if now >= expires_at:
            _store.pop(key, None)
            return None
        return value


def set(user_email: str, question: str, value: Any, ttl: int = _TTL_SEC) -> None:
    key = _make_key(user_email, question)
    expires_at = time.time() + ttl
    with _lock:
        if len(_store) >= _MAX_ENTRIES:
            now = time.time()
            expired = [k for k, (exp, _) in _store.items() if exp < now]
            for k in expired:
                _store.pop(k, None)
            if len(_store) >= _MAX_ENTRIES:
                oldest_key = min(_store, key=lambda k: _store[k][0])
                _store.pop(oldest_key, None)
        _store[key] = (expires_at, value)


def clear() -> int:
    with _lock:
        n = len(_store)
        _store.clear()
        return n
