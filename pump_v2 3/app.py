import traceback
import uuid

import streamlit as st

st.set_page_config(page_title="Petrol Pump", page_icon="⛽", layout="wide")

from core import auth, config  # noqa: E402
from core.log import get_logger  # noqa: E402
from views import attendant, diagnostics, login, manager, owner  # noqa: E402

log = get_logger()

NAV = {
    "owner": [
        ("Approvals", manager.approvals), ("Duty", manager.duty), ("Nozzle Assignment", manager.assign),
        ("Users", owner.users), ("Nozzles", owner.nozzles_page), ("Fuel Rates", owner.rates_page),
        ("Diagnostics", diagnostics.render),
    ],
    "manager": [
        ("Approvals", manager.approvals), ("Duty", manager.duty), ("Nozzle Assignment", manager.assign),
        ("Diagnostics", diagnostics.render),
    ],
    "salesman": [
        ("My Duty", attendant.home), ("Sale Entry", attendant.sale_entry), ("Payment Breakup", attendant.breakup),
    ],
}


def show_page(fn, role):
    """Any crash is logged with a short reference and shown, never swallowed."""
    try:
        fn()
    except Exception as exc:  # StopException / RerunException are not Exceptions
        ref = uuid.uuid4().hex[:8]
        log.error("PAGE CRASH ref=%s page=%s: %s\n%s", ref, getattr(fn, "__name__", "?"), exc, traceback.format_exc())
        st.error(f"This page crashed. Reference: **{ref}** (tell the owner/manager).")
        if role in ("owner", "manager"):
            with st.expander("Technical detail"):
                st.code(traceback.format_exc())


def main():
    missing = config.missing_required()
    if missing:
        st.error("App is not configured. Missing: " + ", ".join(missing))
        st.write("Add them in `.env` (local) or Streamlit → Settings → Secrets. See README.")
        st.stop()

    user = auth.current_user()
    if not user:
        restored = auth.restore()
        if restored.ok:
            st.rerun()
        login.render(flash=restored.error)
        st.stop()

    role = user["role"]
    pages = NAV[role]
    with st.sidebar:
        st.markdown(f"### ⛽ {user['name']}")
        st.caption(role.upper())
        label = st.radio("Menu", [p[0] for p in pages], key=f"nav_{role}", label_visibility="collapsed")
        st.divider()
        if st.button("Logout", use_container_width=True):
            auth.logout()
            st.rerun()

    st.title(label)
    show_page(dict(pages)[label], role)


main()
