# Petrol Pump v2 (core)

Streamlit + Supabase. Same Supabase tables as the old app, so existing users, nozzles, rates and sales keep working.
This is the **core**: login, users, nozzles, fuel rates, duty, nozzle assignment, sale entry, payment breakup (cash / Paytm / CCMS) and manager approval with closing meter readings.
Credit parties, stock, money control and reports are added later, one module at a time, on the same structure.

## Run
1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill it (on Streamlit Cloud: Settings → Secrets).
3. `streamlit run app.py`
4. Log in as owner → **Diagnostics → Schema check**. It must be all green before anything else.

## How it is built (why problems are easy to find)
```
app.py          menu per role; any page crash is logged with a reference id
core/db.py      the ONLY code that talks to Supabase. Never raises, never hides an error
core/auth.py    login / session / logout (small)
core/log.py     logs/app.log + in-memory buffer + query trace
repo/           one file per table: just queries
services/       the rules (calc.py is pure maths)
views/          screens: owner.py, manager.py, attendant.py, diagnostics.py
tests/          python -m unittest discover -s tests -t .
```
Rule: a query that fails returns `Result(ok=False, error=..., where="shifts.start")`. The screen shows the real reason and the `where` tag, and the same line is in Diagnostics → Recent errors.

## When something is wrong, look here
| Problem | Where to look |
|---|---|
| Login fails | The login screen now says why: Supabase refused (wrong password / unconfirmed email), no profile for that UUID (UUID is shown), user inactive, or salesman has no active duty |
| Page shows an error with `Where: xyz` | Diagnostics → Recent errors, search for `xyz` |
| "column ... does not exist" / permission denied | Diagnostics → Schema check (lists the exact columns), then check `SUPABASE_SERVICE_KEY` / RLS |
| Strange behaviour (two nozzles on one duty, sale blocked) | Diagnostics → Data checks |
| Slow page | Diagnostics → Query trace (ms per query) |
| Page crashed ("Reference: ab12cd34") | Diagnostics → Log file, search the reference |

## Roles
- **Owner**: everything below + Users, Nozzles, Fuel Rates
- **Manager**: Approvals, Duty, Nozzle Assignment, Diagnostics
- **Salesman**: My Duty, Sale Entry, Payment Breakup (can log in only while his duty is active)

## Flow
Manager starts duty → assigns nozzle (opening reading = nozzle's current reading) → salesman adds sales (rate locked from Fuel Rates) → submits cash/Paytm/CCMS that must equal total → manager enters closing readings; meter sale must equal payment → Approve (updates nozzle readings, ends assignments) or Hold / Reject (salesman enters fresh sale).

## Security
- Session token holds only the user id and is signed with `APP_SESSION_SECRET`; role and active flag are re-read from the database on every restore.
- Set `SUPABASE_SERVICE_KEY`, redeploy, then run `sql/rls_lockdown.sql` so the public anon key reads nothing.
- Without the service key the app runs in "legacy mode" (shared login session). It works with your current RLS, but two people logged in together can interfere. Diagnostics → Health tells you which mode you are in.

## Known limits
- Supabase REST has no multi-table transactions. Approval writes in a safe order and the status changes last, so if it stops halfway the message lists what was done and pressing Approve again is safe.
- Refresh keeps you logged in (token in the URL `?s=`). Closing the tab logs you out. Do not share a logged-in URL.
- Credit sales / cash given to creditor are not in this core; `credit_amount` is stored as 0.
