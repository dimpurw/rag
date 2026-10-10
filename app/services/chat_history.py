"""
Penyimpanan riwayat percakapan sederhana, in-memory, per proses.

CATATAN PRODUCTION: Implementasi ini cocok untuk single-instance/demo/portofolio.
Untuk production dengan multi-instance atau perlu persistensi antar-restart,
ganti dengan Redis (redis-py) atau database (contoh: tabel `chat_sessions`).
Struktur fungsi di bawah sengaja dibuat sebagai satu-satunya titik akses,
supaya penggantian ke Redis/DB nanti cukup mengubah file ini saja.
"""
import threading
from collections import defaultdict, deque

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.core.config import get_settings

_lock = threading.Lock()
_store: dict[str, deque] = defaultdict(lambda: deque(maxlen=get_settings().max_history_turns * 2))


def get_history_messages(session_id: str) -> list[BaseMessage]:
    with _lock:
        return list(_store[session_id])


def append_turn(session_id: str, question: str, answer: str) -> None:
    with _lock:
        _store[session_id].append(HumanMessage(content=question))
        _store[session_id].append(AIMessage(content=answer))


def clear_session(session_id: str) -> None:
    with _lock:
        _store.pop(session_id, None)


def list_active_sessions() -> list[str]:
    with _lock:
        return list(_store.keys())
