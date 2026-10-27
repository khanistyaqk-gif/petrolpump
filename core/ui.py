"""Small UI helpers."""
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
    """Run an action; show a clean message on AppError. Returns True on success."""
    try:
        result = fn(*args, **kwargs)
    except (AppError, CalcError) as exc:
        st.error(str(exc))
        return False
    except Exception as exc:   # noqa: BLE001
        st.error("Something went wrong. Please try again.")
        with st.expander("Technical details (Owner / Manager)"):
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
    """Number input that returns a Decimal (2 decimals)."""
    v = st.number_input(label, min_value=min_value, value=float(value or 0), step=step,
                        format="%.2f", key=key, help=help)
    return q2(D(str(v)))


STATUS_LABELS = {
    "pending": "🟡 Pending approval", "hold": "⏸️ On hold", "reopened": "🔄 Returned to salesman",
    "approved": "✅ Approved", "rejected": "❌ Rejected",
    "reversed": "↩️ Reversed", "deleted": "🗑 Deleted", "cancelled": "✖ Cancelled",
}


def status_label(status) -> str:
    return STATUS_LABELS.get(status or "pending", str(status))


def correction_box(key, items, describe, action, me_id, *, title="↩️ Reverse an entry", button="Reverse",
                   note="A reverse entry is posted with today's date. The original entry stays in the records.",
                   success="Entry reversed."):
    """Owner tool: pick one entry, tick confirm, press button. items = list of dicts with 'id'."""
    if not items:
        return
    with st.expander(title):
        st.caption(note)
        by_id = {i["id"]: i for i in items}
        sel = st.selectbox("Entry", list(by_id), format_func=lambda i: describe(by_id[i]), key=f"{key}_sel")
        sure = st.checkbox("I have checked — this entry was a mistake", key=f"{key}_ok")
        if st.button(button, key=f"{key}_btn", disabled=not sure, type="primary"):
            run(action, sel, me_id, success=success)
