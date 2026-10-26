import functools

import streamlit as st

from core.auth import current_user


def require(*roles):
    """@require("owner","manager") above a page's render()."""
    def wrap(fn):
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            user = current_user()
            if not user:
                st.error("Please log in.")
                st.stop()
            if user["role"] not in roles:
                st.error("You do not have access to this page.")
                st.stop()
            return fn(*args, **kwargs)
        return inner
    return wrap
