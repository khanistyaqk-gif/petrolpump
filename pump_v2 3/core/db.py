"""The ONLY place that talks to Supabase.

Every query goes through run(). It never raises and never hides a failure:
it returns a Result with ok/data/error, logs the failure with a `where` tag,
and records timing in the query trace shown on the Diagnostics page.
"""
import time
from functools import lru_cache

from core import config
from core.log import get_logger, trace

log = get_logger()


class Result:
    __slots__ = ("ok", "data", "error", "where")

    def __init__(self, ok, data=None, error=None, where=""):
        self.ok = ok
        self.data = data
        self.error = error
        self.where = where

    def __bool__(self):
        return self.ok

    @property
    def rows(self):
        if isinstance(self.data, list):
            return self.data
        return [] if self.data is None else [self.data]

    @property
    def first(self):
        rows = self.rows
        return rows[0] if rows else None

    def __repr__(self):
        return f"Result(ok={self.ok}, where={self.where!r}, error={self.error!r}, rows={len(self.rows)})"


def fail(error: str, where: str = "") -> Result:
    """Make a failed Result for business-rule errors (also logged)."""
    log.warning("%s: %s", where or "rule", error)
    return Result(False, error=error, where=where)


def ok(data=None, where: str = "") -> Result:
    return Result(True, data=data, where=where)


def _explain(exc: Exception) -> str:
    parts = []
    for key in ("message", "details", "hint", "code"):
        value = getattr(exc, key, None)
        if value:
            parts.append(f"{key}={value}")
    if parts:
        return "; ".join(str(p) for p in parts)
    return str(exc) or type(exc).__name__


@lru_cache(maxsize=1)
def _data_client():
    from supabase import create_client
    url = config.get("SUPABASE_URL")
    key = config.get("SUPABASE_SERVICE_KEY") or config.get("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and a Supabase key are not configured")
    return create_client(url, key)


def auth_client():
    """
    Client for email/password sign-in.
    With a service key: a fresh throw-away client so the data client never
    holds anyone's login. Without it: the shared client (legacy behaviour,
    needed when your RLS policies depend on the signed-in user).
    """
    if config.has_service_key():
        from supabase import create_client
        return create_client(config.get("SUPABASE_URL"), config.get("SUPABASE_ANON_KEY"))
    return _data_client()


def run(where: str, build) -> Result:
    """
    run("shifts.start", lambda c: c.table("shifts").insert({...}).execute())
    `build` gets the client and must return the executed response.
    """
    started = time.perf_counter()
    try:
        response = build(_data_client())
        data = getattr(response, "data", response)
        trace(where, True, (time.perf_counter() - started) * 1000)
        return Result(True, data=data, where=where)
    except Exception as exc:
        message = _explain(exc)
        trace(where, False, (time.perf_counter() - started) * 1000, message)
        log.error("DB %s failed: %s", where, message)
        return Result(False, error=message, where=where)
