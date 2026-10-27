"""
Print hone wali reports (A4 HTML). Browser mein kholo -> Print / Save as PDF.
Sirf formatting — data repo/reports.py se aata hai.
"""
from datetime import datetime
from html import escape

from core.calc import ZERO, D, q2, short_excess_label
from core.db import FUEL_LABELS, IST

CSS = """
@page { size: A4; margin: 12mm; }
* { box-sizing: border-box; }
body { font-family: Arial, Helvetica, sans-serif; color: #111; font-size: 12px; margin: 0; padding: 16px; }
.sheet { max-width: 190mm; margin: 0 auto; }
.head { display: flex; justify-content: space-between; align-items: flex-end; border-bottom: 2px solid #111;
        padding-bottom: 6px; margin-bottom: 10px; }
.head h1 { font-size: 18px; margin: 0; }
.head .sub { color: #444; font-size: 11px; }
.title { font-size: 15px; font-weight: bold; margin: 0 0 2px; text-align: right; }
.meta { display: grid; grid-template-columns: repeat(3, 1fr); gap: 4px 12px; margin: 8px 0 12px; }
.meta div span { color: #555; }
h2 { font-size: 13px; margin: 14px 0 4px; border-bottom: 1px solid #999; padding-bottom: 2px; }
table { width: 100%; border-collapse: collapse; }
th, td { border: 1px solid #999; padding: 4px 6px; }
th { background: #eee; text-align: left; font-size: 11px; }
td.n, th.n { text-align: right; white-space: nowrap; }
tr.total td { font-weight: bold; background: #f5f5f5; }
.box { border: 2px solid #111; padding: 8px 10px; margin-top: 10px; font-size: 13px; }
.box b { font-size: 14px; }
.short { color: #b00; } .excess { color: #06c; } .ok { color: #070; }
.sign { display: flex; justify-content: space-between; margin-top: 46px; }
.sign div { width: 30%; border-top: 1px solid #111; text-align: center; padding-top: 4px; }
.foot { margin-top: 14px; color: #666; font-size: 10px; text-align: center; }
.warn { border: 1px dashed #b00; color: #b00; padding: 6px; margin-top: 8px; }
.bar { max-width: 190mm; margin: 0 auto 10px; text-align: right; }
.btn { padding: 10px 18px; font-size: 15px; background: #14b8a6; color: #fff; border: 0; border-radius: 6px;
       cursor: pointer; }
body.wide .sheet, body.wide .bar { max-width: 277mm; }
body.wide th, body.wide td { padding: 2px 5px; font-size: 10.5px; }
body.wide h2 { margin: 8px 0 3px; font-size: 12px; }
body.wide p { margin: 3px 0; }
body.wide .sign { margin-top: 30px; }
body.wide .box { margin-top: 8px; padding: 6px 10px; }
.box, .sign, tr { break-inside: avoid; }
.end { break-inside: avoid; }
@media print { .bar { display: none; } body { padding: 0; } }
"""


def _rs(v) -> str:
    v = q2(v)
    sign = "-" if v < 0 else ""
    whole, frac = f"{abs(v):.2f}".split(".")
    if len(whole) > 3:
        head, tail, parts = whole[:-3], whole[-3:], []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    return f"{sign}₹{whole}.{frac}"


def _l(v) -> str:
    return f"{q2(v):,.2f}"


def _e(v) -> str:
    return escape(str(v if v is not None else ""))


def _time(iso) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(IST)
        return dt.strftime("%d-%m-%Y %I:%M %p")
    except ValueError:
        return _e(iso)


def _date(d) -> str:
    try:
        return datetime.fromisoformat(str(d)).strftime("%d-%m-%Y")
    except ValueError:
        return _e(d)


def _diff_html(diff) -> str:
    d = q2(diff)
    cls = "short" if d > 0 else "excess" if d < 0 else "ok"
    return f'<span class="{cls}">{_e(short_excess_label(d))}</span>'


def _page(title, pump, body, wide=False) -> str:
    name = _e(pump.get("name") or "Petrol Pump")
    addr = _e(pump.get("address") or "")
    printed = datetime.now(IST).strftime("%d-%m-%Y %I:%M %p")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{_e(title)}</title>
<style>{CSS}{"@page { size: A4 landscape; }" if wide else ""}</style></head><body class="{'wide' if wide else ''}">
<div class="bar"><button class="btn" onclick="window.print()">🖨️ Print</button></div>
<div class="sheet">
<div class="head"><div><h1>{name}</h1><div class="sub">{addr}</div></div>
<div><p class="title">{_e(title)}</p><div class="sub">Printed: {printed}</div></div></div>
{body}
<div class="foot">Petrol Pump v2 · Computer-generated report</div>
</div></body></html>"""


# ------------------------------------------------------------------ 1 salesman ka settlement
def settlement_html(d: dict, pump: dict) -> str:
    s = d["settlement"]
    readings = s.get("nozzle_readings") or []
    rows, t_l, t_a, t_t = [], ZERO, ZERO, ZERO
    for r in readings:
        t_l += D(r.get("net_sale_liters"))
        t_a += D(r.get("sale_amount"))
        t_t += D(r.get("testing_liters"))
        rows.append(f"""<tr><td>{_e(r.get('nozzle_name'))}</td><td>{_e(FUEL_LABELS.get(r.get('fuel_type'), r.get('fuel_type')))}</td>
<td class="n">{_l(r.get('opening'))}</td><td class="n">{_l(r.get('closing'))}</td>
<td class="n">{_l(r.get('testing_liters'))}</td><td class="n">{_l(r.get('net_sale_liters'))}</td>
<td class="n">{_rs(r.get('rate'))}</td><td class="n">{_rs(r.get('sale_amount'))}</td></tr>""")
    rows.append(f"""<tr class="total"><td colspan="4">Total</td><td class="n">{_l(t_t)}</td><td class="n">{_l(t_l)}</td>
<td></td><td class="n">{_rs(t_a)}</td></tr>""")

    credit_rows = d.get("credit") or []
    if credit_rows:
        cr = "".join(f"""<tr><td>{_e(c['party'])}</td><td>{'Fuel on credit' if c['type'] == 'sale' else 'Cash advance'}</td>
<td>{_e(c.get('note'))}</td><td class="n">{_rs(c['amount'])}</td></tr>""" for c in credit_rows)
        credit_html = f"""<h2>Credit sales</h2><table><tr><th>Party</th><th>Type</th><th>Vehicle / note</th>
<th class="n">Amount</th></tr>{cr}</table>"""
    else:
        credit_html = ""

    pay = [("Cash", s.get("cash_amount")), ("Paytm / UPI", s.get("paytm_amount")),
           ("CCMS / Card", s.get("ccms_amount")), ("Credit (fuel on credit)", s.get("credit_amount"))]
    pay_total = q2(sum((D(v) for _, v in pay), ZERO))
    pay_rows = "".join(f'<tr><td>{k}</td><td class="n">{_rs(v)}</td></tr>' for k, v in pay)
    status = "✅ Approved" if s.get("status") == "approved" else f"⚠️ {_e(s.get('status'))} (not yet approved)"

    body = f"""
<div class="meta">
<div><span>Salesman:</span> <b>{_e(d['salesman'])}</b></div>
<div><span>Shift date:</span> <b>{_date(s.get('date'))}</b></div>
<div><span>Settlement no.:</span> <b>#{_e(s.get('id'))}</b></div>
<div><span>Shift started:</span> {_time(d.get('started_at'))}</div>
<div><span>Approved at:</span> {_time(s.get('approved_at'))}</div>
<div><span>Status:</span> {status}</div>
</div>
<h2>Nozzle readings</h2>
<table><tr><th>Nozzle</th><th>Fuel</th><th class="n">Opening</th><th class="n">Closing</th><th class="n">Testing (L)</th>
<th class="n">Sale (L)</th><th class="n">Rate</th><th class="n">Amount</th></tr>{''.join(rows)}</table>
<h2>Payment</h2>
<table><tr><th>Mode</th><th class="n">Amount</th></tr>{pay_rows}
<tr class="total"><td>Total payment</td><td class="n">{_rs(pay_total)}</td></tr></table>
{credit_html}
<div class="box">
Sale as per meter: <b>{_rs(s.get('meter_total'))}</b> &nbsp;·&nbsp; Payment: <b>{_rs(pay_total)}</b>
&nbsp;·&nbsp; Difference: <b>{_diff_html(s.get('difference'))}</b><br>
Cash advanced to credit parties: {_rs(s.get('cash_given_to_creditor_amount'))} &nbsp;·&nbsp;
<b>Cash to be handed to Manager: {_rs(s.get('cash_transfer_expected'))}</b>
</div>
<div class="sign"><div>Salesman<br>{_e(d['salesman'])}</div><div>Manager<br>{_e(d.get('approver') or '')}</div>
<div>Owner</div></div>"""
    return _page("Salesman Settlement", pump, body)


# ------------------------------------------------------------------ din ka salesman-wise summary
def day_summary_html(d: dict, pump: dict) -> str:
    fuels = d["fuels"]
    fuel_heads = "".join(f'<th class="n">{_e(FUEL_LABELS.get(f, f))} (L)</th>' for f in fuels)
    body_rows = []
    for r in d["rows"]:
        fuel_cells = "".join(f'<td class="n">{_l(r["liters"].get(f, 0))}</td>' for f in fuels)
        body_rows.append(f"""<tr><td>{_e(r['salesman'])}</td>{fuel_cells}<td class="n">{_rs(r['sale'])}</td>
<td class="n">{_rs(r['cash'])}</td><td class="n">{_rs(r['paytm'])}</td><td class="n">{_rs(r['ccms'])}</td>
<td class="n">{_rs(r['credit'])}</td><td class="n">{_rs(r['cash_given'])}</td><td class="n">{_rs(r['cash_jama'])}</td>
<td class="n">{_diff_html(r['difference'])}</td></tr>""")
    t = d["total"]
    fuel_tot = "".join(f'<td class="n">{_l(t["liters"].get(f, 0))}</td>' for f in fuels)
    body_rows.append(f"""<tr class="total"><td>Total ({len(d['rows'])})</td>{fuel_tot}<td class="n">{_rs(t['sale'])}</td>
<td class="n">{_rs(t['cash'])}</td><td class="n">{_rs(t['paytm'])}</td><td class="n">{_rs(t['ccms'])}</td>
<td class="n">{_rs(t['credit'])}</td><td class="n">{_rs(t['cash_given'])}</td><td class="n">{_rs(t['cash_jama'])}</td>
<td class="n">{_diff_html(t['difference'])}</td></tr>""")

    pending = d.get("pending") or []
    pend_html = ""
    if pending:
        pend_html = '<div class="warn">⚠️ Pending approval (not included in this summary): ' + ", ".join(
            f"{_e(p['salesman'])} ({_e(p['status'])})" for p in pending) + "</div>"

    credit_html = ""
    cl = d.get("credit") or []
    if cl:
        f_t = q2(sum((c["fuel"] for c in cl), ZERO))
        c_t = q2(sum((c["cash"] for c in cl), ZERO))
        lines = "".join(f"""<tr><td>{_e(c['party'])}</td><td>{_e(c['salesman'])}</td><td>{_e(c['note'])}</td>
<td class="n">{_rs(c['fuel']) if c['fuel'] else '—'}</td><td class="n">{_rs(c['cash']) if c['cash'] else '—'}</td>
<td class="n">{_rs(c['fuel'] + c['cash'])}</td></tr>""" for c in cl)
        parties = d.get("credit_by_party") or []
        party_rows = "".join(f"""<tr><td>{_e(p['party'])}</td><td class="n">{_rs(p['fuel'])}</td>
<td class="n">{_rs(p['cash'])}</td><td class="n">{_rs(p['fuel'] + p['cash'])}</td></tr>""" for p in parties)
        credit_html = f"""
<h2>Credit sales (today)</h2>
<table><tr><th>Party</th><th>Salesman</th><th>Vehicle / slip</th><th class="n">Fuel on credit</th>
<th class="n">Cash advance</th><th class="n">Total</th></tr>{lines}
<tr class="total"><td colspan="3">Total ({len(cl)})</td><td class="n">{_rs(f_t)}</td><td class="n">{_rs(c_t)}</td>
<td class="n">{_rs(f_t + c_t)}</td></tr></table>
<h2>Party-wise total</h2>
<table><tr><th>Party</th><th class="n">Fuel on credit</th><th class="n">Cash advance</th><th class="n">Total</th></tr>{party_rows}</table>"""
    else:
        credit_html = "<h2>Credit sales (today)</h2><p>No credit sales today.</p>"

    mode_label = {"cash": "Cash", "bank": "Bank", "paytm": "Paytm / UPI", "ccms": "CCMS"}
    rec = d.get("received") or []
    if rec:
        rec_rows = "".join(f"""<tr><td>{_e(r['party'])}</td><td>{mode_label.get(r['mode'], _e(r['mode']))}
{(' · ' + _e(r['bank'])) if r.get('bank') else ''}</td><td>{_e(r['ref'])}</td><td>{_e(r['note'])}</td>
<td class="n">{_rs(r['amount'])}</td></tr>""" for r in rec)
        bm = d.get("received_by_mode") or {}
        mode_tot = " &nbsp;·&nbsp; ".join(f"{mode_label[k]}: <b>{_rs(v)}</b>" for k, v in bm.items() if v)
        rec_total = q2(sum((r["amount"] for r in rec), ZERO))
        received_html = f"""
<h2>Payments received from credit parties (today)</h2>
<table><tr><th>Party</th><th>Mode</th><th>Reference / UTR</th><th>Note</th><th class="n">Amount</th></tr>{rec_rows}
<tr class="total"><td colspan="4">Total ({len(rec)})</td><td class="n">{_rs(rec_total)}</td></tr></table>
<p>{mode_tot}</p>"""
    else:
        received_html = "<h2>Payments received from credit parties (today)</h2><p>No payments received today.</p>"

    inf = d.get("inflow") or {}
    inflow_html = f"""
<h2>Total collection for the day (salesmen + credit parties)</h2>
<table><tr><th>Mode</th><th class="n">From salesmen</th><th class="n">From credit parties</th><th class="n">Total</th></tr>
<tr><td>Cash (with Manager)</td><td class="n">{_rs(t['cash_jama'])}</td>
<td class="n">{_rs((d.get('received_by_mode') or {}).get('cash', 0))}</td><td class="n"><b>{_rs(inf.get('cash', 0))}</b></td></tr>
<tr><td>Paytm / UPI</td><td class="n">{_rs(t['paytm'])}</td>
<td class="n">{_rs((d.get('received_by_mode') or {}).get('paytm', 0))}</td><td class="n">{_rs(inf.get('paytm', 0))}</td></tr>
<tr><td>CCMS</td><td class="n">{_rs(t['ccms'])}</td>
<td class="n">{_rs((d.get('received_by_mode') or {}).get('ccms', 0))}</td><td class="n">{_rs(inf.get('ccms', 0))}</td></tr>
<tr><td>Bank</td><td class="n">—</td>
<td class="n">{_rs((d.get('received_by_mode') or {}).get('bank', 0))}</td><td class="n">{_rs(inf.get('bank', 0))}</td></tr>
</table>"""

    body = f"""
<div class="meta"><div><span>Date:</span> <b>{_date(d['date'])}</b></div>
<div><span>Approved shifts:</span> <b>{len(d['rows'])}</b></div><div></div></div>
<h2>Salesman-wise</h2>
<table><tr><th>Salesman</th>{fuel_heads}<th class="n">Sale</th><th class="n">Cash</th><th class="n">Paytm</th>
<th class="n">CCMS</th><th class="n">Credit</th><th class="n">Cash advance</th><th class="n">Cash handed over</th>
<th class="n">Short / Excess</th></tr>{''.join(body_rows)}</table>
{pend_html}
{credit_html}
{received_html}
{inflow_html}
<div class="end"><div class="box">Total sale for the day: <b>{_rs(t['sale'])}</b> &nbsp;·&nbsp; Total cash with Manager: <b>{_rs(inf.get('cash', t['cash_jama']))}</b>
&nbsp;·&nbsp; Net difference: <b>{_diff_html(t['difference'])}</b></div>
<div class="sign"><div>Manager</div><div></div><div>Owner</div></div></div>"""
    return _page("Daily Salesman Summary", pump, body, wide=True)


# ------------------------------------------------------------------ Owner: day closing position
def owner_closing_html(d: dict, pump: dict) -> str:
    fl = lambda f: _e(FUEL_LABELS.get(f, f))  # noqa: E731
    p = d["payments"]

    # 1. Sale
    srows = "".join(f"""<tr><td>{fl(r['fuel'])}</td><td class="n">{_rs(r['rate']) if r['rate'] else '—'}</td>
<td class="n">{_l(r['liters'])}</td><td class="n">{_l(r['testing'])}</td><td class="n">{_rs(r['amount'])}</td></tr>"""
                    for r in d["sale"])
    tl = q2(sum((r["liters"] for r in d["sale"]), ZERO))
    sale_html = f"""<h2>1. Sale of the day ({d['shifts']} approved shifts)</h2>
<table><tr><th>Fuel</th><th class="n">Avg rate</th><th class="n">Litres sold</th><th class="n">Testing (L)</th><th class="n">Amount</th></tr>
{srows or '<tr><td colspan="5">No approved sale.</td></tr>'}
<tr class="total"><td colspan="2">Total</td><td class="n">{_l(tl)}</td><td class="n">{_l(d['testing_total'])}</td>
<td class="n">{_rs(p['meter_total'])}</td></tr></table>
<table style="margin-top:6px"><tr><th>Cash</th><th>Paytm / UPI</th><th>CCMS / Card</th><th>Credit sale</th>
<th>Cash advance to parties</th><th>Short / Excess</th></tr>
<tr><td class="n">{_rs(p['cash_amount'])}</td><td class="n">{_rs(p['paytm_amount'])}</td><td class="n">{_rs(p['ccms_amount'])}</td>
<td class="n">{_rs(p['credit_amount'])}</td><td class="n">{_rs(p['cash_given_to_creditor_amount'])}</td>
<td class="n">{_diff_html(p['difference'])}</td></tr></table>"""

    # 2. Stock
    strows = "".join(f"""<tr><td>{_e(r['tank'] or '')} ({fl(r['fuel'])})</td><td class="n">{_l(r['opening'])}</td>
<td class="n">{_l(r['inward'])}</td><td class="n">{_l(r['sale'])}</td><td class="n">{_l(r['dip_adjust'] + r['correction'])}</td>
<td class="n"><b>{_l(r['closing'])}</b></td><td class="n">{_l(r['dip_physical']) if r['dip_physical'] is not None else '—'}</td>
<td class="n">{_l(r['capacity'])}</td></tr>""" for r in d["stock"])
    stock_html = f"""<h2>2. Closing stock (litres)</h2>
<table><tr><th>Tank</th><th class="n">Opening</th><th class="n">Purchase</th><th class="n">Sale</th>
<th class="n">Dip / correction</th><th class="n">Closing (book)</th><th class="n">Dip (physical)</th><th class="n">Capacity</th></tr>
{strows or '<tr><td colspan="8">No tanks.</td></tr>'}</table>"""

    # 3. Money
    mrows = "".join(f"""<tr><td>{_e(r['name'])}</td><td class="n">{_rs(r['opening'])}</td>
<td class="n">{_rs(r['closing'] - r['opening'])}</td><td class="n"><b>{_rs(r['closing'])}</b></td></tr>""" for r in d["money"])
    money_html = f"""<h2>3. Cash, bank, Paytm, CCMS and oil company</h2>
<table><tr><th>Account</th><th class="n">Opening</th><th class="n">Net change today</th><th class="n">Closing</th></tr>{mrows}</table>
<p style="color:#555">Paytm / CCMS = amount not yet settled. Oil company = amount payable by the pump.</p>"""

    # 4. Credit parties
    prow = "".join(f"""<tr><td>{_e(r['party'])}{' ⚠️' if r['over'] else ''}</td><td>{_e(r['phone'])}</td>
<td class="n">{_rs(r['opening'])}</td><td class="n">{_rs(r['given']) if r['given'] else '—'}</td>
<td class="n">{_rs(r['received']) if r['received'] else '—'}</td><td class="n"><b>{_rs(r['closing'])}</b></td>
<td class="n">{_rs(r['limit']) if r['limit'] > 0 else '—'}</td></tr>""" for r in d["parties"])
    party_html = f"""<h2>4. Credit parties — balance receivable</h2>
<table><tr><th>Party</th><th>Mobile</th><th class="n">Opening</th><th class="n">Credit today</th>
<th class="n">Received today</th><th class="n">Closing</th><th class="n">Limit</th></tr>
{prow or '<tr><td colspan="7">No balances.</td></tr>'}
<tr class="total"><td colspan="3">Total ({len(d['parties'])} parties)</td><td class="n">{_rs(d['credit_given'])}</td>
<td class="n">{_rs(d['credit_received'])}</td><td class="n">{_rs(d['party_total'])}</td><td></td></tr></table>"""

    # 5. Expenses
    erows = "".join(f"""<tr><td>{_e(e['category'])}</td><td>{_e(e['description'])}</td><td>{_e(e['mode'])}</td>
<td class="n">{_rs(e['amount'])}</td></tr>""" for e in d["expenses"])
    exp_html = f"""<h2>5. Expenses of the day</h2>
<table><tr><th>Category</th><th>Description</th><th>Paid by</th><th class="n">Amount</th></tr>
{erows or '<tr><td colspan="4">No expenses.</td></tr>'}
<tr class="total"><td colspan="3">Total</td><td class="n">{_rs(d['expense_total'])}</td></tr></table>"""

    alerts = d.get("alerts") or []
    alert_html = ('<div class="warn"><b>Needs attention:</b><br>' + "<br>".join("• " + _e(a) for a in alerts) + "</div>"
                  if alerts else '<p class="ok">✔ Nothing pending for this date.</p>')

    cash = next((r["closing"] for r in d["money"] if r["account"] == "cash"), ZERO)
    bank = q2(sum((r["closing"] for r in d["money"] if r["account"] == "bank"), ZERO))
    body = f"""
<div class="meta"><div><span>Date:</span> <b>{_date(d['date'])}</b></div><div></div><div></div></div>
<div class="box">Total sale: <b>{_rs(p['meter_total'])}</b> &nbsp;·&nbsp; Cash in hand: <b>{_rs(cash)}</b>
&nbsp;·&nbsp; All banks: <b>{_rs(bank)}</b> &nbsp;·&nbsp; Credit receivable: <b>{_rs(d['party_total'])}</b></div>
{alert_html}
{sale_html}{stock_html}{money_html}{party_html}{exp_html}
<div class="end"><div class="sign"><div>Manager</div><div></div><div>Owner</div></div></div>"""
    return _page("Day Closing Report", pump, body, wide=True)


# ------------------------------------------------------------------ Oil company ledger
def oil_ledger_html(d: dict, pump: dict) -> str:
    rows_ = "".join(f"""<tr><td>{_date(x['date'])}</td><td>{_e(x['label'])}{' (reversal)' if x['reversal'] else ''}</td>
<td>{_e(x['note'])}</td><td>{_e(x['ref'] or '')}</td><td class="n">{_rs(x['debit']) if x['debit'] else ''}</td>
<td class="n">{_rs(x['credit']) if x['credit'] else ''}</td><td class="n">{_rs(x['balance'])}</td></tr>""" for x in d["lines"])
    t = d["totals"]
    body = f"""
<div class="meta"><div><span>Company:</span> <b>{_e(d['company'])}</b></div>
<div><span>Period:</span> <b>{_date(d['from'])} to {_date(d['to'])}</b></div><div></div></div>
<table><tr><th>Date</th><th>Particulars</th><th>Invoice / note</th><th>Reference</th>
<th class="n">Invoice (+)</th><th class="n">Paid / CCMS (−)</th><th class="n">Balance due</th></tr>
<tr><td colspan="6"><b>Opening balance</b></td><td class="n"><b>{_rs(d['opening'])}</b></td></tr>
{rows_}
<tr class="total"><td colspan="4">Closing balance</td><td class="n">{_rs(sum((x['debit'] for x in d['lines']), ZERO))}</td>
<td class="n">{_rs(sum((x['credit'] for x in d['lines']), ZERO))}</td><td class="n">{_rs(d['closing'])}</td></tr></table>
<div class="box">Invoices: <b>{_rs(t['invoice'])}</b> &nbsp;·&nbsp; CCMS adjusted: <b>{_rs(-t['ccms'])}</b>
&nbsp;·&nbsp; Paid from bank: <b>{_rs(-t['payment'])}</b> &nbsp;·&nbsp; Balance due: <b>{_rs(d['closing'])}</b></div>
<p style="color:#555">Match this with the oil company's account statement. Positive balance = amount payable by the pump;
negative = advance lying with the company.</p>"""
    return _page("Oil Company Ledger", pump, body)
