"""Logging that you can actually read.

- logs/app.log (rotating file) for history
- an in-memory ring buffer shown on the Diagnostics page
Every error in the app goes through here with a short where-tag.
"""
import collections
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

from core.timeutil import IST

_BUFFER = collections.deque(maxlen=500)
_TRACE = collections.deque(maxlen=200)
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")


class _MemoryHandler(logging.Handler):
    def emit(self, record):
        _BUFFER.append({
            "time": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "message": record.getMessage(),
        })


def get_logger() -> logging.Logger:
    logger = logging.getLogger("pump")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    logger.propagate = False
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    mem = _MemoryHandler()
    logger.addHandler(mem)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        fh = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception:
        pass  # read-only disk: the in-memory buffer still works
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    return logger


def trace(where: str, ok: bool, ms: float, error: str = ""):
    _TRACE.append({
        "time": datetime.now(IST).strftime("%H:%M:%S"),
        "where": where,
        "ok": ok,
        "ms": round(ms),
        "error": error,
    })


def recent_logs(level: str = None, n: int = 100):
    rows = list(_BUFFER)
    if level:
        rows = [r for r in rows if r["level"] == level]
    return rows[-n:][::-1]


def recent_trace(n: int = 100, only_failed: bool = False):
    rows = list(_TRACE)
    if only_failed:
        rows = [r for r in rows if not r["ok"]]
    return rows[-n:][::-1]


def tail_file(lines: int = 200) -> str:
    try:
        with open(LOG_FILE, encoding="utf-8") as fh:
            return "".join(fh.readlines()[-lines:])
    except Exception:
        return ""
