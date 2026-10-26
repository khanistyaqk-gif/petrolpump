import streamlit as st

from core import auth
from core.ui import show_error


def render(flash=None):
    st.title("⛽ Petrol Pump")
    st.subheader("Login")
    if flash:
        st.warning(flash)

    with st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        go = st.form_submit_button("Login", type="primary")

    if go:
        result = auth.login(email, password)
        if result.ok:
            st.rerun()
        else:
            show_error(result)
