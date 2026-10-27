import streamlit as st

from core import auth
from core.ui import run
from repo import users


def show():
    st.title("⛽ Petrol Pump")
    if not users.list_profiles(role="owner"):
        _first_owner()
        return
    with st.form("login"):
        login_id = st.text_input("Login ID or email")
        password = st.text_input("Password", type="password")
        ok = st.form_submit_button("Log in", type="primary", use_container_width=True)
    if ok:
        if not login_id or not password:
            st.error("Please enter both login ID and password.")
            return
        success, msg = auth.login(login_id, password)
        if success:
            st.rerun()
        st.error(msg)
    st.caption("Salesmen can log in only during an active shift.")


def _first_owner():
    """New database: create the Owner account first (shown only once)."""
    st.info("First-time setup: create the Owner account.")
    with st.form("first_owner"):
        name = st.text_input("Owner name")
        login_id = st.text_input("Login ID", help="For example: owner")
        pw = st.text_input("Password (minimum 6 characters)", type="password")
        pw2 = st.text_input("Confirm password", type="password")
        ok = st.form_submit_button("Create Owner account", type="primary")
    if ok:
        if pw != pw2:
            st.error("Passwords do not match.")
            return
        if users.list_profiles(role="owner"):
            st.rerun()
        run(users.create_user, name, login_id, pw, "owner", None, None,
            success="Owner account created. Please log in.")
