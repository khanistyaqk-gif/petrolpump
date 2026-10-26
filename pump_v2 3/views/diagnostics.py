"""Start here when something does not work. Every check says what is wrong and
what to do about it."""
import time

import pandas as pd
import streamlit as st

from core import config
from core.auth import current_user
from core.db import run
from core.log import LOG_FILE, recent_logs, recent_trace, tail_file
from core.perms import require
from core.schema import FUEL_TYPES, REQUIRED
from core.timeutil import today_ist
from repo import rates


def _health():
    st.subheader("Settings")
    rows = config.check()
    st.dataframe(pd.DataFrame(rows)[["name", "required", "value", "purpose"]], use_container_width=True, hide_index=True)
    if config.missing_required():
        st.error("Missing required settings: " + ", ".join(config.missing_required()))
    if config.has_service_key():
        st.success("Mode: service key. All users can log in at the same time. Make sure sql/rls_lockdown.sql has been run.")
    else:
        st.warning("Mode: legacy (no SUPABASE_SERVICE_KEY). The login session is shared by everybody, so two people "
                   "logged in at once can interfere with each other. Set SUPABASE_SERVICE_KEY to fix this.")
    secret = config.get("APP_SESSION_SECRET")
    if not secret or len(secret) < 16:
        st.warning("APP_SESSION_SECRET is not set (or shorter than 16 chars). Everyone is logged out whenever the app restarts.")

    st.subheader("Connection")
    started = time.perf_counter()
    r = run("diag.ping", lambda c: c.table("profiles").select("id").limit(1).execute())
    ms = round((time.perf_counter() - started) * 1000)
    if r.ok:
        st.success(f"Database reachable ({ms} ms).")
    else:
        st.error(f"Database NOT reachable: {r.error}")


def _schema():
    st.caption("Checks that every table and column this app needs exists and is readable.")
    if not st.button("Run schema check", key="run_schema"):
        return
    problems = 0
    for table, cols in REQUIRED.items():
        r = run(f"diag.schema.{table}", lambda c, t=table, cl=cols: c.table(t).select(",".join(cl)).limit(1).execute())
        if r.ok:
            st.success(f"{table}: OK")
            continue
        problems += 1
        missing = []
        for col in cols:
            one = run(f"diag.schema.{table}.{col}", lambda c, t=table, cc=col: c.table(t).select(cc).limit(1).execute())
            if not one.ok:
                missing.append(f"{col} ({one.error})")
        st.error(f"{table}: PROBLEM")
        if missing:
            st.write("Columns with problems:")
            for m in missing:
                st.code(m)
        else:
            st.code(r.error)
    if problems == 0:
        st.balloons()
    else:
        st.info("A permission error usually means RLS blocks the key in use (set SUPABASE_SERVICE_KEY). "
                "A 'column does not exist' error means the table differs from what this app expects.")


def _data_checks():
    st.caption("Looks for data that makes the app behave strangely.")
    found = False

    act = run("diag.data.shifts", lambda c: c.table("shifts").select("id,salesman_id").eq("is_active", True).execute())
    if act.ok:
        seen = {}
        for s in act.rows:
            seen.setdefault(s["salesman_id"], []).append(s["id"])
        for sid, ids in seen.items():
            if len(ids) > 1:
                found = True
                st.error(f"Salesman {sid} has {len(ids)} active duties: {ids}. End the extra ones.")
    else:
        st.error(f"Could not check duties: {act.error}")

    asg = run("diag.data.assignments", lambda c: c.table("shift_assignments").select("id,nozzle_id,shift_id").eq("is_active", True).execute())
    if asg.ok:
        by_nozzle, active_shifts = {}, {s["id"] for s in act.rows} if act.ok else set()
        for a in asg.rows:
            by_nozzle.setdefault(a["nozzle_id"], []).append(a["id"])
            if act.ok and a["shift_id"] not in active_shifts:
                found = True
                st.error(f"Assignment {a['id']} is active but its duty #{a['shift_id']} has ended.")
        for nid, ids in by_nozzle.items():
            if len(ids) > 1:
                found = True
                st.error(f"Nozzle {nid} is assigned {len(ids)} times at once: {ids}.")
    else:
        st.error(f"Could not check assignments: {asg.error}")

    noz = run("diag.data.nozzles", lambda c: c.table("nozzles").select("fuel_type,is_active").execute())
    if noz.ok:
        for fuel in sorted({n["fuel_type"] for n in noz.rows if n.get("is_active", True)}):
            r = rates.current(fuel, today_ist())
            if r.ok and not r.first:
                found = True
                st.error(f"Fuel '{fuel}' has an active nozzle but no rate for today. Owner → Fuel Rates.")
    pend = run("diag.data.pending", lambda c: c.table("settlements").select("id,status,date").in_("status", ["pending", "hold"]).execute())
    if pend.ok and pend.rows:
        st.info(f"{len(pend.rows)} settlement(s) are waiting for manager approval.")
    if not found:
        st.success("No data problems found.")


def _errors():
    level = st.selectbox("Level", ["ERROR", "WARNING", "INFO", "all"], key="log_level")
    rows = recent_logs(None if level == "all" else level, 200)
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.success("Nothing logged at this level since the app started.")


def _trace():
    only = st.checkbox("Only failed queries", value=True, key="trace_failed")
    rows = recent_trace(150, only_failed=only)
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.success("No queries to show.")


def _file():
    text = tail_file(300)
    if text:
        st.code(text, language="text")
        st.download_button("Download log", text, file_name="pump_app_log.txt")
    else:
        st.info(f"No log file yet ({LOG_FILE}). The 'Recent errors' tab still works.")


def _session():
    u = dict(current_user() or {})
    st.json(u)


@require("owner", "manager")
def render():
    tabs = st.tabs(["Health", "Schema check", "Data checks", "Recent errors", "Query trace", "Log file", "Me"])
    for tab, fn in zip(tabs, (_health, _schema, _data_checks, _errors, _trace, _file, _session)):
        with tab:
            fn()
