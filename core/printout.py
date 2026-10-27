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
body.wide th, body.wide td { padding: 3px 5px; font-size: 11px; }
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
    return f"""<!doctype html><html lang="hi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{_e(title)}</title>
<style>{CSS}{"@page { size: A4 landscape; }" if wide else ""}</style></head><body class="{'wide' if wide else ''}">
<div class="bar"><button class="btn" onclick="window.print()">🖨️ Print</button></div>
<div class="sheet">
<div class="head"><div><h1>{name}</h1><div class="sub">{addr}</div></div>
<div><p class="title">{_e(title)}</p><div class="sub">Print: {printed}</div></div></div>
{body}
<div class="foot">Petrol Pump v2 · computer se bani report</div>
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
    rows.append(f"""<tr class="total"><td colspan="4">Kul</td><td class="n">{_l(t_t)}</td><td class="n">{_l(t_l)}</td>
<td></td><td class="n">{_rs(t_a)}</td></tr>""")

    credit_rows = d.get("credit") or []
    if credit_rows:
        cr = "".join(f"""<tr><td>{_e(c['party'])}</td><td>{'Fuel udhaar' if c['type'] == 'sale' else 'Cash diya'}</td>
<td>{_e(c.get('note'))}</td><td class="n">{_rs(c['amount'])}</td></tr>""" for c in credit_rows)
        credit_html = f"""<h2>Credit (udhaar)</h2><table><tr><th>Party</th><th>Kya</th><th>Gaadi / note</th>
<th class="n">Amount</th></tr>{cr}</table>"""
    else:
        credit_html = ""

    pay = [("Cash", s.get("cash_amount")), ("Paytm / UPI", s.get("paytm_amount")),
           ("CCMS / Card", s.get("ccms_amount")), ("Credit (fuel udhaar)", s.get("credit_amount"))]
    pay_total = q2(sum((D(v) for _, v in pay), ZERO))
    pay_rows = "".join(f'<tr><td>{k}</td><td class="n">{_rs(v)}</td></tr>' for k, v in pay)
    status = "✅ Approved" if s.get("status") == "approved" else f"⚠️ {_e(s.get('status'))} (abhi approve nahi)"

    body = f"""
<div class="meta">
<div><span>Salesman:</span> <b>{_e(d['salesman'])}</b></div>
<div><span>Duty tarikh:</span> <b>{_date(s.get('date'))}</b></div>
<div><span>Hisaab no.:</span> <b>#{_e(s.get('id'))}</b></div>
<div><span>Duty shuru:</span> {_time(d.get('started_at'))}</div>
<div><span>Approve:</span> {_time(s.get('approved_at'))}</div>
<div><span>Status:</span> {status}</div>
</div>
<h2>Nozzle reading</h2>
<table><tr><th>Nozzle</th><th>Fuel</th><th class="n">Opening</th><th class="n">Closing</th><th class="n">Testing (L)</th>
<th class="n">Sale (L)</th><th class="n">Rate</th><th class="n">Amount</th></tr>{''.join(rows)}</table>
<h2>Payment</h2>
<table><tr><th>Mode</th><th class="n">Amount</th></tr>{pay_rows}
<tr class="total"><td>Kul payment</td><td class="n">{_rs(pay_total)}</td></tr></table>
{credit_html}
<div class="box">
Meter se sale: <b>{_rs(s.get('meter_total'))}</b> &nbsp;·&nbsp; Payment: <b>{_rs(pay_total)}</b>
&nbsp;·&nbsp; Farak: <b>{_diff_html(s.get('difference'))}</b><br>
Creditor ko diya cash: {_rs(s.get('cash_given_to_creditor_amount'))} &nbsp;·&nbsp;
<b>Manager ko jama cash: {_rs(s.get('cash_transfer_expected'))}</b>
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
    body_rows.append(f"""<tr class="total"><td>Kul ({len(d['rows'])})</td>{fuel_tot}<td class="n">{_rs(t['sale'])}</td>
<td class="n">{_rs(t['cash'])}</td><td class="n">{_rs(t['paytm'])}</td><td class="n">{_rs(t['ccms'])}</td>
<td class="n">{_rs(t['credit'])}</td><td class="n">{_rs(t['cash_given'])}</td><td class="n">{_rs(t['cash_jama'])}</td>
<td class="n">{_diff_html(t['difference'])}</td></tr>""")

    pending = d.get("pending") or []
    pend_html = ""
    if pending:
        pend_html = '<div class="warn">⚠️ Abhi approve nahi hue (is summary mein nahi jode): ' + ", ".join(
            f"{_e(p['salesman'])} ({_e(p['status'])})" for p in pending) + "</div>"

    body = f"""
<div class="meta"><div><span>Tarikh:</span> <b>{_date(d['date'])}</b></div>
<div><span>Approved duty:</span> <b>{len(d['rows'])}</b></div><div></div></div>
<h2>Salesman-wise</h2>
<table><tr><th>Salesman</th>{fuel_heads}<th class="n">Sale</th><th class="n">Cash</th><th class="n">Paytm</th>
<th class="n">CCMS</th><th class="n">Credit</th><th class="n">Creditor ko cash</th><th class="n">Cash jama</th>
<th class="n">Short / Excess</th></tr>{''.join(body_rows)}</table>
{pend_html}
<div class="box">Din ki kul sale: <b>{_rs(t['sale'])}</b> &nbsp;·&nbsp; Manager ke paas cash: <b>{_rs(t['cash_jama'])}</b>
&nbsp;·&nbsp; Kul farak: <b>{_diff_html(t['difference'])}</b></div>
<div class="sign"><div>Manager</div><div></div><div>Owner</div></div>"""
    return _page("Din ka Salesman Summary", pump, body, wide=True)
