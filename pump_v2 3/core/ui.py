import streamlit as st


def show_error(result, message: str = None):
    """Show a failed Result: friendly line + the real reason + where it came from."""
    st.error(message or result.error or "Something went wrong.")
    if result.error and message:
        st.caption(f"Reason: {result.error}")
    if result.where:
        st.caption(f"Where: {result.where}  ·  full details in Diagnostics → Recent errors")


def money(value) -> str:
    try:
        return f"₹{float(value or 0):,.2f}"
    except (TypeError, ValueError):
        return "₹0.00"


def liters(value) -> str:
    try:
        return f"{float(value or 0):,.2f} L"
    except (TypeError, ValueError):
        return "0.00 L"
