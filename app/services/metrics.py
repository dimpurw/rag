"""
Metrics ringan, in-memory, per proses — dipakai untuk dashboard usage
dan observability dasar. Untuk production sungguhan dengan multi-instance,
ganti dengan Prometheus client (prometheus-client) + endpoint /metrics format standar.
"""
import threading
import time
from collections import defaultdict, deque

_lock = threading.Lock()
_counters: dict[str, int] = defaultdict(int)
_recent_durations_ms: deque = deque(maxlen=500)
_start_time = time.time()


def increment(counter_name: str, n: int = 1) -> None:
    with _lock:
        _counters[counter_name] += n


def record_latency_ms(duration_ms: float) -> None:
    with _lock:
        _recent_durations_ms.append(duration_ms)


def snapshot() -> dict:
    with _lock:
        durations = list(_recent_durations_ms)
        counters = dict(_counters)

    avg_ms = sum(durations) / len(durations) if durations else 0.0
    uptime_seconds = time.time() - _start_time

    return {
        "uptime_seconds": round(uptime_seconds, 1),
        "total_uploads": counters.get("uploads", 0),
        "total_queries": counters.get("queries", 0),
        "total_chats": counters.get("chats", 0),
        "total_errors": counters.get("errors", 0),
        "total_requests_tracked": len(durations),
        "avg_response_time_ms": round(avg_ms, 1),
    }
