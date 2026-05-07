"""Lightweight profiler for the briefing pipeline.

Schreibt Zeitstempel-Marker für jeden MCP-Tool-Call und für den Modul-Load
in /home/claude/data/profile.log. Atomares append (os.write < PIPE_BUF),
funktioniert auch mit mehreren parallel laufenden MCP-Server-Subprozessen.

Zweck: 30-38s Trigger-Latenz aufschlüsseln (Cold-Start vs Tool-Calls vs
LLM-Reasoning). Reine Diagnose — kann bei Bedarf vollständig wieder
entfernt werden, ohne Funktionsverhalten zu ändern.

Format pro Zeile (~120 Bytes, atomar bis PIPE_BUF=4096):
    2026-05-07T20:34:12.345+00:00 pid=12345 weather.get_weather ENTER
    2026-05-07T20:34:14.789+00:00 pid=12345 weather.get_weather EXIT dur=2.444s
    2026-05-07T20:34:10.000+00:00 pid=12345 weather MODULE_LOAD
"""
import functools
import os
import time
from datetime import datetime, timezone

PROF_PATH = "/home/claude/data/profile.log"
_FD = None


def _fd() -> int:
    global _FD
    if _FD is None:
        os.makedirs(os.path.dirname(PROF_PATH), exist_ok=True)
        _FD = os.open(PROF_PATH, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    return _FD


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _emit(line: str) -> None:
    try:
        os.write(_fd(), (line + "\n").encode())
    except Exception:
        pass


def module_load(server: str) -> None:
    _emit(f"{_now_iso()} pid={os.getpid()} {server} MODULE_LOAD")


def profile(label: str):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            pid = os.getpid()
            _emit(f"{_now_iso()} pid={pid} {label} ENTER")
            try:
                return fn(*args, **kwargs)
            finally:
                dt = time.perf_counter() - t0
                _emit(f"{_now_iso()} pid={pid} {label} EXIT dur={dt:.3f}s")

        return wrapper

    return deco
