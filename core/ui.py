"""Chhote UI helpers."""
import streamlit as st

from core.calc import CalcError, D, q2
from core.db import FUEL_LABELS, AppError


def rs(value) -> str:
    """₹1,23,456.78 (Indian grouping)."""
    v = q2(value)
    sign = "-" if v < 0 else ""
    whole, frac = f"{abs(v):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    return f"{sign}₹{whole}.{frac}"


def lt(value) -> str:
    return f"{q2(value):,.2f} L"


def fuel(ft) -> str:
    return FUEL_LABELS.get(ft, ft or "-")


def run(fn, *args, success: str | None = None, rerun: bool = True, **kwargs):
    """Kaam chalao; AppError ho to saaf message dikhao. Safal ho to True."""
    try:
        result = fn(*args, **kwargs)
    except (AppError, CalcError) as exc:
        st.error(str(exc))
        return False
    except Exception as exc:   # noqa: BLE001
        st.error("Kuch gadbad hui. Dobara try karein.")
        with st.expander("Detail (Owner/Manager ke liye)"):
            st.code(str(exc))
        return False
    if success:
        st.session_state["_flash"] = success
    if rerun:
        st.rerun()
    return result if result is not None else True


def flash():
    msg = st.session_state.pop("_flash", None)
    if msg:
        st.success(msg)


def num(label, key, value=0.0, step=0.01, min_value=0.0, help=None):
    """Number input jo Decimal deta hai (2 decimal)."""
    v = st.number_input(label, min_value=min_value, value=float(value or 0), step=step,
                        format="%.2f", key=key, help=help)
    return q2(D(str(v)))


STATUS_LABELS = {
    "pending": "🟡 Manager ke paas", "hold": "⏸️ Hold", "reopened": "🔄 Wapas bheja",
    "approved": "✅ Approved", "rejected": "❌ Rejected",
}


def status_label(status) -> str:
    return STATUS_LABELS.get(status or "pending", str(status))
