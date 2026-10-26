import streamlit as st

from repo import profiles


def names_by_id():
    res = profiles.list_all()
    if not res.ok:
        return {}
    return {p["id"]: p.get("name") or p["id"][:8] for p in res.rows}


def flash(kind: str, text: str):
    """Show a message after st.rerun()."""
    st.session_state["_flash"] = (kind, text)


def show_flash():
    item = st.session_state.pop("_flash", None)
    if item:
        getattr(st, item[0])(item[1])


def table(rows, cols):
    """DataFrame with only the wanted columns that exist (a missing column
    must not crash a page; Diagnostics → Schema check reports it)."""
    import pandas as pd
    df = pd.DataFrame(rows)
    return df[[c for c in cols if c in df.columns]]
