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
        login_id = st.text_input("Login ID ya Email")
        password = st.text_input("Password", type="password")
        ok = st.form_submit_button("Login", type="primary", use_container_width=True)
    if ok:
        if not login_id or not password:
            st.error("Login ID aur password dono bharein.")
            return
        success, msg = auth.login(login_id, password)
        if success:
            st.rerun()
        st.error(msg)
    st.caption("Salesman: login sirf duty chalu hone par hoga.")


def _first_owner():
    """Naya database: sabse pehle Owner account (sirf ek baar dikhta hai)."""
    st.info("Pehli baar setup: Owner account banayein.")
    with st.form("first_owner"):
        name = st.text_input("Owner ka naam")
        login_id = st.text_input("Login ID", help="Jaise: owner")
        pw = st.text_input("Password (kam se kam 6)", type="password")
        pw2 = st.text_input("Password dobara", type="password")
        ok = st.form_submit_button("Owner account banayein", type="primary")
    if ok:
        if pw != pw2:
            st.error("Dono password match nahi kar rahe.")
            return
        if users.list_profiles(role="owner"):
            st.rerun()
        run(users.create_user, name, login_id, pw, "owner", None, None,
            success="Owner account ban gaya. Ab login karein.")
