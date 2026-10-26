"""Petrol Pump v2 — Streamlit + Supabase.   Chalayein:  streamlit run app.py"""
import streamlit as st

st.set_page_config(page_title="Petrol Pump", page_icon=":material/local_gas_station:", layout="wide")

from core import auth, session  # noqa: E402
from core.db import ROLE_LABELS  # noqa: E402
from views import expenses, login, manager, money, owner, reports, salesman, stock  # noqa: E402


def menu(role):
    P = st.Page
    mgr = [
        P(manager.dashboard, title="Dashboard", icon=":material/home:", url_path="home", default=True),
        P(manager.settlement_page, title="Settlement", icon=":material/receipt_long:", url_path="settlement"),
        P(manager.duty_page, title="Duty / Nozzle", icon=":material/badge:", url_path="duty"),
        P(manager.testing_page, title="Testing", icon=":material/science:", url_path="testing"),
        P(manager.credit_page, title="Credit Party", icon=":material/menu_book:", url_path="credit"),
        P(money.page, title="Money Control", icon=":material/account_balance_wallet:", url_path="money"),
        P(stock.page, title="Stock", icon=":material/oil_barrel:", url_path="stock"),
        P(expenses.page, title="Kharcha", icon=":material/payments:", url_path="kharcha"),
        P(reports.page, title="Reports", icon=":material/bar_chart:", url_path="reports"),
    ]
    if role == "owner":
        return {"Roz ka kaam": mgr, "Setup (Owner)": [
            P(owner.rates_page, title="Fuel Rate", icon=":material/currency_rupee:", url_path="rates"),
            P(owner.nozzles_page, title="Nozzles", icon=":material/local_gas_station:", url_path="nozzles"),
            P(owner.tanks_page, title="Tanks", icon=":material/propane_tank:", url_path="tanks"),
            P(owner.users_page, title="Users", icon=":material/group:", url_path="users"),
            P(owner.settings_page, title="Settings", icon=":material/settings:", url_path="settings"),
            P(owner.system_page, title="System / Backup", icon=":material/shield:", url_path="system"),
        ]}
    if role == "manager":
        return mgr
    return [
        P(salesman.duty_page, title="Meri Duty", icon=":material/local_gas_station:", url_path="meri-duty", default=True),
        P(salesman.entries_page, title="Meri Entries", icon=":material/list:", url_path="entries"),
    ]


def main():
    try:
        user = auth.current_user()
    except RuntimeError as exc:   # secrets missing
        st.error(str(exc))
        st.stop()

    if not user:
        login.show()
        return

    session.keep()
    with st.sidebar:
        st.markdown(f"**{user['name']}**  \n{ROLE_LABELS.get(user['role'])}")
        if st.button("Logout", use_container_width=True):
            auth.logout()
            st.rerun()
    st.navigation(menu(user["role"])).run()


main()
