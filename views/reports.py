"""Reports: print, daily summary, period sales, salesman, profit/loss, party statement. Every table exports to CSV."""
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
    f = c1.date_input("From", value=t - timedelta(days=days), key=f"{key}_f").isoformat()
    to = c2.date_input("To", value=t, key=f"{key}_t").isoformat()
    return f, to


def _table(df: pd.DataFrame, name: str):
    st.dataframe(df, hide_index=True, use_container_width=True)
    st.download_button("⬇️ CSV", df.to_csv(index=False).encode("utf-8-sig"), file_name=f"{name}.csv",
                       mime="text/csv", key=f"dl_{name}")


def settlement_download(settlement_id, key, label="🖨️ Settlement report"):
    d = reports.settlement_print_data(settlement_id)
    if not d:
        st.error("Settlement not found.")
        return
    html = printout.settlement_html(d, reports.pump_info())
    st.download_button(label, html.encode("utf-8"), mime="text/html", key=key, use_container_width=True,
                       file_name=f"settlement_{d['salesman']}_{d['settlement']['date']}_{settlement_id}.html")


def print_tab():
    st.caption("The file will download → open it in your browser → click **🖨️ Print** at the top (or Save as PDF).")
    d = st.date_input("Shift date", value=date.fromisoformat(today_ist()), key="pr_d").isoformat()
    data = reports.day_summary_data(d)

    st.subheader("Daily salesman summary")
    if data["rows"]:
        st.download_button("🖨️ Daily summary", printout.day_summary_html(data, reports.pump_info()).encode("utf-8"),
                           file_name=f"salesman_summary_{d}.html", mime="text/html", type="primary",
                           key=f"day_{d}", use_container_width=True)
        t = data["total"]
        st.write(f"{len(data['rows'])} shifts · Sale **{rs(t['sale'])}** · Cash handed over **{rs(t['cash_jama'])}** · "
                 f"{short_excess_label(t['difference'])}")
    else:
        st.info("No approved shifts for this date.")
    if data["pending"]:
        st.warning("Pending approval (not in the summary): " + ", ".join(p["salesman"] for p in data["pending"]))

    st.subheader("Settlement report per salesman")
    for s in reports.approved_settlements(d, d):
        c1, c2 = st.columns([3, 2])
        c1.write(f"**{(s.get('profiles') or {}).get('name')}** · {rs(s['meter_total'])} · "
                 f"{short_excess_label(s['difference'])}")
        with c2:
            settlement_download(s["id"], key=f"st_{s['id']}", label="🖨️ Report")


def closing_tab():
    """Owner: din ke ant ki poori position."""
    d = st.date_input("Date", value=date.fromisoformat(today_ist()), key="cl_d").isoformat()
    data = reports.owner_closing_data(d)
    st.download_button("🖨️ Print day closing report",
                       printout.owner_closing_html(data, reports.pump_info()).encode("utf-8"),
                       file_name=f"day_closing_{d}.html", mime="text/html", type="primary",
                       key=f"cl_{d}", use_container_width=True)
    p = data["payments"]
    cash = next((r["closing"] for r in data["money"] if r["account"] == "cash"), ZERO)
    bank = sum((r["closing"] for r in data["money"] if r["account"] == "bank"), ZERO)
    c = st.columns(4)
    c[0].metric("Total sale", rs(p["meter_total"]))
    c[1].metric("Cash in hand", rs(cash))
    c[2].metric("All banks", rs(bank))
    c[3].metric("Credit receivable", rs(data["party_total"]))
    for a in data["alerts"]:
        st.warning(a)

    st.subheader("Sale")
    if data["sale"]:
        st.dataframe(pd.DataFrame([{"Fuel": fuel(r["fuel"]), "Avg rate": rs(r["rate"]) if r["rate"] else "—",
                                    "Litres": lt(r["liters"]), "Testing": lt(r["testing"]), "Amount": rs(r["amount"])}
                                   for r in data["sale"]]), hide_index=True, use_container_width=True)
    else:
        st.info("No approved sale for this date.")
    st.subheader("Closing stock")
    st.dataframe(pd.DataFrame([{"Tank": f"{r['tank'] or ''} ({fuel(r['fuel'])})", "Opening": lt(r["opening"]),
                                "Purchase": lt(r["inward"]), "Sale": lt(r["sale"]),
                                "Dip / correction": lt(r["dip_adjust"] + r["correction"]), "Closing": lt(r["closing"]),
                                "Dip (physical)": lt(r["dip_physical"]) if r["dip_physical"] is not None else "—"}
                               for r in data["stock"]]), hide_index=True, use_container_width=True)
    st.subheader("Cash, bank, Paytm, CCMS, oil company")
    st.dataframe(pd.DataFrame([{"Account": r["name"], "Opening": rs(r["opening"]),
                                "Change": rs(r["closing"] - r["opening"]), "Closing": rs(r["closing"])}
                               for r in data["money"]]), hide_index=True, use_container_width=True)
    st.subheader(f"Credit parties · total {rs(data['party_total'])}")
    if data["parties"]:
        st.dataframe(pd.DataFrame([{"Party": r["party"] + (" ⚠️" if r["over"] else ""), "Opening": rs(r["opening"]),
                                    "Credit today": rs(r["given"]), "Received today": rs(r["received"]),
                                    "Closing": rs(r["closing"])} for r in data["parties"]]),
                     hide_index=True, use_container_width=True)
    if data["expenses"]:
        st.subheader(f"Expenses · {rs(data['expense_total'])}")
        st.dataframe(pd.DataFrame([{"Category": e["category"], "Description": e["description"],
                                    "Paid by": e["mode"], "Amount": rs(e["amount"])} for e in data["expenses"]]),
                     hide_index=True, use_container_width=True)


def page():
    me = auth.require(*MGR)
    st.header("📊 Reports")
    names = ["🖨️ Print", "Daily summary", "Period sales", "Salesman", "Profit / Loss", "Party statement"]
    if me["role"] == "owner":
        names = ["📋 Day closing"] + names
    tabs = st.tabs(names)
    if me["role"] == "owner":
        with tabs[0]:
            closing_tab()
        tabs = tabs[1:]

    with tabs[0]:
        print_tab()
    tabs = tabs[1:]

    with tabs[0]:
        d = st.date_input("Date", value=date.fromisoformat(today_ist()), key="ds_d").isoformat()
        r = reports.daily_summary(d)
        p = r["payments"]
        c = st.columns(3)
        c[0].metric("Total sales", rs(p["meter_total"]))
        c[1].metric("Shifts settled", len(r["settlements"]))
        c[2].metric("Short / excess", short_excess_label(p["difference"]))
        if r["fuel"]:
            _table(pd.DataFrame([{"Fuel": fuel(ft), "Litres": lt(v["liters"]), "Amount": rs(v["amount"]),
                                  "Testing": lt(v["testing"])} for ft, v in r["fuel"].items()]), f"fuel_{d}")
        st.subheader("Payments")
        _table(pd.DataFrame([{"Cash": rs(p["cash_amount"]), "Cash advance to parties": rs(p["cash_given_to_creditor_amount"]),
                              "Paytm": rs(p["paytm_amount"]), "CCMS": rs(p["ccms_amount"]),
                              "Credit sales": rs(p["credit_amount"])}]), f"payment_{d}")
        st.subheader("Money movements")
        if r["flows"]:
            _table(pd.DataFrame([{"Account": money.ACCOUNT_LABELS[a], "Transaction": money.KIND_LABELS.get(k, k),
                                  "Amount": rs(v)} for (a, k), v in sorted(r["flows"].items())]), f"flows_{d}")
        st.subheader(f"Balances (end of {d})")
        banks, oils = accounts.name_maps()
        _table(pd.DataFrame([{
            "Account": money.ACCOUNT_LABELS[a] + (f" · {banks.get(ref)}" if a == "bank" else "")
            + (f" · {oils.get(ref)}" if a == "oil" else ""), "Balance": rs(v)}
            for (a, ref), v in sorted(r["balances"].items(), key=lambda x: (x[0][0], str(x[0][1])))]), f"balance_{d}")

    with tabs[1]:
        f, t = _range("ps")
        data = reports.period_sales(f, t)
        if data:
            _table(pd.DataFrame([{"Date": x["date"], "Fuel": fuel(x["fuel_type"]), "Litres": float(x["liters"]),
                                  "Amount": float(x["amount"])} for x in data]), f"sale_{f}_{t}")
            st.metric("Total", rs(sum((x["amount"] for x in data), ZERO)))
        else:
            st.info("No approved sales in this period.")

    with tabs[2]:
        f, t = _range("sm")
        data = reports.salesman_rows(f, t)
        if data:
            _table(pd.DataFrame([{"Date": x["date"], "Salesman": x["salesman"], "Sale": float(x["meter"]),
                                  "Cash": float(x["cash"]), "Paytm": float(x["paytm"]), "CCMS": float(x["ccms"]),
                                  "Credit": float(x["credit"]), "Short(+)/Excess(−)": float(x["difference"])}
                                 for x in data]), f"salesman_{f}_{t}")
        else:
            st.info("No approved shifts.")

    with tabs[3]:
        f, t = _range("pl", days=29)
        r = reports.pnl(f, t)
        c = st.columns(4)
        c[0].metric("Sales", rs(r["sales"]))
        c[1].metric("Cost of fuel sold", rs(r["cost"]))
        c[2].metric("Expenses", rs(r["expenses"]))
        c[3].metric("Net profit", rs(r["net_profit"]))
        st.caption("Cost = litres sold × latest purchase rate of that fuel (invoice amount ÷ litres).")
        if r["missing_cost"]:
            st.warning("No purchase invoice found for these fuels, so their cost is taken as 0: "
                       + ", ".join(fuel(x) for x in r["missing_cost"]))
        if r["by_category"]:
            _table(pd.DataFrame([{"Expense category": k, "Amount": float(v)} for k, v in r["by_category"].items()]),
                   f"expenses_{f}_{t}")

    with tabs[4]:
        parties = credit.list_parties()
        if not parties:
            st.info("No credit parties.")
            return
        pid = st.selectbox("Party", [p["id"] for p in parties],
                           format_func=lambda i: next(p["name"] for p in parties if p["id"] == i))
        f, t = _range("pt", days=29)
        s = credit.statement(pid, f, t)
        st.write(f"Opening: **{rs(s['opening'])}** · Closing: **{rs(s['closing'])}**")
        label = {"opening": "Opening balance", "sale": "Fuel on credit", "cash_given": "Cash advance",
                 "payment_received": "Payment received"}
        if s["lines"]:
            _table(pd.DataFrame([{"Date": x["date"], "Transaction": label.get(x["type"], x["type"]),
                                  "Debit (+)": float(x["delta"]) if x["delta"] > 0 else None,
                                  "Credit (−)": float(-x["delta"]) if x["delta"] < 0 else None,
                                  "Balance": float(x["balance"]), "Remarks": x.get("note") or ""}
                                 for x in s["lines"]]), f"party_{pid}_{f}_{t}")
