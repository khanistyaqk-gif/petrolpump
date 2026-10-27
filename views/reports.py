"""Reports: din ka hisaab, period sale, salesman, profit/loss, party statement. Har table CSV mein."""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from core import auth
from core.calc import ZERO, short_excess_label
from core.db import today_ist
from core import printout
from core.ui import fuel, lt, rs
from repo import accounts, credit, money, reports

MGR = ("owner", "manager")


def _range(key, days=6):
    t = date.fromisoformat(today_ist())
    c1, c2 = st.columns(2)
    f = c1.date_input("Se", value=t - timedelta(days=days), key=f"{key}_f").isoformat()
    to = c2.date_input("Tak", value=t, key=f"{key}_t").isoformat()
    return f, to


def _table(df: pd.DataFrame, name: str):
    st.dataframe(df, hide_index=True, use_container_width=True)
    st.download_button("⬇️ CSV", df.to_csv(index=False).encode("utf-8-sig"), file_name=f"{name}.csv",
                       mime="text/csv", key=f"dl_{name}")


def settlement_download(settlement_id, key, label="🖨️ Settlement report"):
    d = reports.settlement_print_data(settlement_id)
    if not d:
        st.error("Hisaab nahi mila.")
        return
    html = printout.settlement_html(d, reports.pump_info())
    st.download_button(label, html.encode("utf-8"), mime="text/html", key=key, use_container_width=True,
                       file_name=f"settlement_{d['salesman']}_{d['settlement']['date']}_{settlement_id}.html")


def print_tab():
    st.caption("File download hogi → browser mein kholo → upar **🖨️ Print** dabao (ya Save as PDF).")
    d = st.date_input("Tarikh (duty ki)", value=date.fromisoformat(today_ist()), key="pr_d").isoformat()
    data = reports.day_summary_data(d)

    st.subheader("Din ka salesman-wise summary")
    if data["rows"]:
        st.download_button("🖨️ Din ka summary", printout.day_summary_html(data, reports.pump_info()).encode("utf-8"),
                           file_name=f"salesman_summary_{d}.html", mime="text/html", type="primary",
                           key=f"day_{d}", use_container_width=True)
        t = data["total"]
        st.write(f"{len(data['rows'])} duty · Sale **{rs(t['sale'])}** · Cash jama **{rs(t['cash_jama'])}** · "
                 f"{short_excess_label(t['difference'])}")
    else:
        st.info("Is tarikh ki koi approved duty nahi.")
    if data["pending"]:
        st.warning("Approve baaki (summary mein nahi): " + ", ".join(p["salesman"] for p in data["pending"]))

    st.subheader("Har salesman ka settlement")
    for s in reports.approved_settlements(d, d):
        c1, c2 = st.columns([3, 2])
        c1.write(f"**{(s.get('profiles') or {}).get('name')}** · {rs(s['meter_total'])} · "
                 f"{short_excess_label(s['difference'])}")
        with c2:
            settlement_download(s["id"], key=f"st_{s['id']}", label="🖨️ Report")


def page():
    auth.require(*MGR)
    st.header("📊 Reports")
    tabs = st.tabs(["🖨️ Print", "Din ka hisaab", "Period sale", "Salesman", "Profit / Loss", "Party statement"])

    with tabs[0]:
        print_tab()
    tabs = tabs[1:]

    with tabs[0]:
        d = st.date_input("Tarikh", value=date.fromisoformat(today_ist()), key="ds_d").isoformat()
        r = reports.daily_summary(d)
        p = r["payments"]
        c = st.columns(3)
        c[0].metric("Kul sale", rs(p["meter_total"]))
        c[1].metric("Duty settle", len(r["settlements"]))
        c[2].metric("Short / excess", short_excess_label(p["difference"]))
        if r["fuel"]:
            _table(pd.DataFrame([{"Fuel": fuel(ft), "Litre": lt(v["liters"]), "Amount": rs(v["amount"]),
                                  "Testing": lt(v["testing"])} for ft, v in r["fuel"].items()]), f"fuel_{d}")
        st.subheader("Payment")
        _table(pd.DataFrame([{"Cash": rs(p["cash_amount"]), "Creditor ko cash": rs(p["cash_given_to_creditor_amount"]),
                              "Paytm": rs(p["paytm_amount"]), "CCMS": rs(p["ccms_amount"]),
                              "Credit (udhaar)": rs(p["credit_amount"])}]), f"payment_{d}")
        st.subheader("Paise ki aawak / jaawak")
        if r["flows"]:
            _table(pd.DataFrame([{"Account": money.ACCOUNT_LABELS[a], "Kaam": money.KIND_LABELS.get(k, k),
                                  "Amount": rs(v)} for (a, k), v in sorted(r["flows"].items())]), f"flows_{d}")
        st.subheader(f"Balance ({d} ke end mein)")
        banks, oils = accounts.name_maps()
        _table(pd.DataFrame([{
            "Account": money.ACCOUNT_LABELS[a] + (f" · {banks.get(ref)}" if a == "bank" else "")
            + (f" · {oils.get(ref)}" if a == "oil" else ""), "Balance": rs(v)}
            for (a, ref), v in sorted(r["balances"].items(), key=lambda x: (x[0][0], str(x[0][1])))]), f"balance_{d}")

    with tabs[1]:
        f, t = _range("ps")
        data = reports.period_sales(f, t)
        if data:
            _table(pd.DataFrame([{"Tarikh": x["date"], "Fuel": fuel(x["fuel_type"]), "Litre": float(x["liters"]),
                                  "Amount": float(x["amount"])} for x in data]), f"sale_{f}_{t}")
            st.metric("Kul", rs(sum((x["amount"] for x in data), ZERO)))
        else:
            st.info("Is samay mein koi approved sale nahi.")

    with tabs[2]:
        f, t = _range("sm")
        data = reports.salesman_rows(f, t)
        if data:
            _table(pd.DataFrame([{"Tarikh": x["date"], "Salesman": x["salesman"], "Sale": float(x["meter"]),
                                  "Cash": float(x["cash"]), "Paytm": float(x["paytm"]), "CCMS": float(x["ccms"]),
                                  "Credit": float(x["credit"]), "Short(+)/Excess(−)": float(x["difference"])}
                                 for x in data]), f"salesman_{f}_{t}")
        else:
            st.info("Koi approved duty nahi.")

    with tabs[3]:
        f, t = _range("pl", days=29)
        r = reports.pnl(f, t)
        c = st.columns(4)
        c[0].metric("Sale", rs(r["sales"]))
        c[1].metric("Fuel ki laagat", rs(r["cost"]))
        c[2].metric("Kharcha", rs(r["expenses"]))
        c[3].metric("Net profit", rs(r["net_profit"]))
        st.caption("Laagat = bika litre × us fuel ka aakhri tanker rate (bill ÷ litre).")
        if r["missing_cost"]:
            st.warning("In fuel ka koi tanker bill nahi, laagat 0 maani: " + ", ".join(fuel(x) for x in r["missing_cost"]))
        if r["by_category"]:
            _table(pd.DataFrame([{"Kharcha": k, "Amount": float(v)} for k, v in r["by_category"].items()]),
                   f"kharcha_{f}_{t}")

    with tabs[4]:
        parties = credit.list_parties()
        if not parties:
            st.info("Koi party nahi.")
            return
        pid = st.selectbox("Party", [p["id"] for p in parties],
                           format_func=lambda i: next(p["name"] for p in parties if p["id"] == i))
        f, t = _range("pt", days=29)
        s = credit.statement(pid, f, t)
        st.write(f"Opening: **{rs(s['opening'])}** · Closing: **{rs(s['closing'])}**")
        label = {"opening": "Opening", "sale": "Fuel udhaar", "cash_given": "Cash diya", "payment_received": "Payment mila"}
        if s["lines"]:
            _table(pd.DataFrame([{"Tarikh": x["date"], "Kaam": label.get(x["type"], x["type"]),
                                  "Lena (+)": float(x["delta"]) if x["delta"] > 0 else None,
                                  "Mila (−)": float(-x["delta"]) if x["delta"] < 0 else None,
                                  "Balance": float(x["balance"]), "Note": x.get("note") or ""}
                                 for x in s["lines"]]), f"party_{pid}_{f}_{t}")
