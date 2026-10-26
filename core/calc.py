"""
Saara paisa/litre ka hisaab yahan. Koi database ya Streamlit nahi — sirf pure logic,
taaki har rule ka test ho sake (tests/test_calc.py).

Har jagah Decimal: float ki 0.1 + 0.2 = 0.30000000000000004 jaisi galti nahi hogi.
Rounding: litre aur rupaye 2 decimal, ROUND_HALF_UP (0.005 -> 0.01).
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

TWO = Decimal("0.01")
ZERO = Decimal("0")
SETTLEMENT_TOLERANCE = Decimal("2.00")   # ±₹2 tak "matched"


class CalcError(ValueError):
    """Hisaab mein aisi galti jo user ko dikhani hai."""


def D(value) -> Decimal:
    """Kisi bhi value ko Decimal banao. None / '' -> 0. float ko str se, taaki binary galti na aaye."""
    if value is None or value == "":
        return ZERO
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise CalcError(f"Galat number: {value!r}")


def q2(value) -> Decimal:
    return D(value).quantize(TWO, rounding=ROUND_HALF_UP)


def to_json(value) -> float:
    """Database/JSON ke liye: pehle 2 decimal par round, phir number."""
    return float(q2(value))


# ---------------- Sale ----------------
def sale_amount(liters, rate) -> Decimal:
    liters, rate = D(liters), D(rate)
    if liters <= 0:
        raise CalcError("Litre 0 se zyada hone chahiye.")
    if rate <= 0:
        raise CalcError("Rate 0 se zyada hona chahiye.")
    return q2(liters * rate)


# ---------------- Closing (ek nozzle) ----------------
def nozzle_closing(opening, closing, testing, rate, nozzle_name="Nozzle") -> dict:
    """
    Gross = closing - opening
    Net sale = gross - testing        (testing sale mein count nahi)
    Amount = net sale × rate
    """
    opening, closing, testing, rate = D(opening), D(closing), D(testing), D(rate)

    if closing <= 0:
        raise CalcError(f"{nozzle_name}: closing reading daalein.")
    if closing < opening:
        raise CalcError(f"{nozzle_name}: closing ({closing}) opening ({opening}) se kam nahi ho sakti.")
    if testing < 0:
        raise CalcError(f"{nozzle_name}: testing minus mein nahi ho sakti.")
    if rate <= 0:
        raise CalcError(f"{nozzle_name}: is fuel ka rate set nahi hai.")

    gross = q2(closing - opening)
    testing = q2(testing)
    if testing > gross:
        raise CalcError(f"{nozzle_name}: testing ({testing} L) gross sale ({gross} L) se zyada hai.")

    net = q2(gross - testing)
    return {
        "opening": q2(opening),
        "closing": q2(closing),
        "gross_liters": gross,
        "testing_liters": testing,
        "net_sale_liters": net,
        "rate": q2(rate),
        "sale_amount": q2(net * rate),
    }


def meter_total(rows) -> Decimal:
    return q2(sum((D(r["sale_amount"]) for r in rows), ZERO))


# ---------------- Payment ----------------
def payment_total(cash, paytm, ccms, credit) -> Decimal:
    parts = [D(cash), D(paytm), D(ccms), D(credit)]
    if any(p < 0 for p in parts):
        raise CalcError("Payment amount minus mein nahi ho sakta.")
    return q2(sum(parts, ZERO))


def breakup_matches_entries(entries_total, cash, paytm, ccms, credit) -> tuple[bool, Decimal]:
    """Salesman ka breakup uski entries ke total ke bilkul barabar hona chahiye."""
    diff = q2(D(entries_total) - payment_total(cash, paytm, ccms, credit))
    return diff == ZERO, diff


def settlement_difference(meter, cash, paytm, ccms, credit) -> Decimal:
    """+ = short (kam paisa aaya), - = excess (zyada aaya)."""
    return q2(D(meter) - payment_total(cash, paytm, ccms, credit))


def is_matched(difference, tolerance=SETTLEMENT_TOLERANCE) -> bool:
    return abs(D(difference)) <= D(tolerance)


def short_excess_label(difference) -> str:
    d = q2(difference)
    if d > 0:
        return f"Short ₹{d}"
    if d < 0:
        return f"Excess ₹{-d}"
    return "Barabar"


def cash_transfer_expected(cash, cash_given_to_creditors) -> Decimal:
    """Manager ko jama hone wala cash = cash - creditors ko diya cash."""
    cash, given = D(cash), D(cash_given_to_creditors)
    if given > cash:
        raise CalcError("Creditor ko diya cash, kul cash se zyada nahi ho sakta.")
    return q2(cash - given)


# ---------------- Credit ----------------
def credit_limit_exceeded(current_balance, pending, new_amount, limit) -> bool:
    """limit 0 ya khali = koi limit nahi."""
    limit = D(limit)
    if limit <= 0:
        return False
    return q2(D(current_balance) + D(pending) + D(new_amount)) > q2(limit)


def normalize_vehicle(vehicle) -> str:
    return "".join(ch for ch in str(vehicle or "").upper() if ch.isalnum())


def vehicle_allowed(vehicle, allowed_list) -> bool:
    """Party ki gaadi list khali ho to koi bhi gaadi chalegi; warna sirf list wali."""
    allowed = {normalize_vehicle(v) for v in (allowed_list or []) if normalize_vehicle(v)}
    if not allowed:
        return True
    return normalize_vehicle(vehicle) in allowed


# ---------------- Stock ----------------
def stock_after_sale(current_stock, sale_liters, fuel_type="fuel") -> Decimal:
    new = q2(D(current_stock) - D(sale_liters))
    if new < 0:
        raise CalcError(f"{fuel_type} stock kam hai: tank {q2(current_stock)} L, sale {q2(sale_liters)} L.")
    return new


def liters_by_fuel(rows) -> dict:
    out = {}
    for r in rows:
        ft = r["fuel_type"]
        out[ft] = q2(out.get(ft, ZERO) + D(r["net_sale_liters"]))
    return out


# ---------------- Stock register ----------------
STOCK_KINDS = ("opening", "inward", "sale", "dip_adjust", "correction")


def stock_register(opening_before, moves) -> list:
    """moves: date-wise sorted stock_moves. Har din ek row."""
    out, bal = [], q2(opening_before)
    days = {}
    for m in moves:
        days.setdefault(m["date"], []).append(m)
    for day in sorted(days):
        row = {"date": day, "opening_balance": bal}
        for k in STOCK_KINDS:
            row[k] = q2(sum((D(m["delta"]) for m in days[day] if m["kind"] == k), ZERO))
        bal = q2(bal + sum((row[k] for k in STOCK_KINDS), ZERO))
        row["closing"] = bal
        row["new_tank"] = row.pop("opening")   # tank banate waqt ka shuru ka stock
        out.append(row)
    return out


# ---------------- Credit statement ----------------
CREDIT_SIGN = {"opening": 1, "sale": 1, "cash_given": 1, "payment_received": -1}


def party_statement(txns, from_date) -> dict:
    opening, lines = ZERO, []
    for t in txns:
        delta = q2(D(t["amount"]) * CREDIT_SIGN.get(t["type"], 0))
        if str(t["date"]) < str(from_date):
            opening = q2(opening + delta)
        else:
            lines.append((t, delta))
    bal, out = opening, []
    for t, delta in lines:
        bal = q2(bal + delta)
        out.append({**t, "delta": delta, "balance": bal})
    return {"opening": opening, "lines": out, "closing": bal}


# ---------------- Profit / Loss (R9) ----------------
def cost_of_sales(liters_by_fuel_: dict, cost_rate_by_fuel: dict) -> tuple[Decimal, list]:
    """Laagat = bika litre × kharid rate (aakhri tanker). Rate na ho to fuel 'missing' mein."""
    total, missing = ZERO, []
    for ft, liters in liters_by_fuel_.items():
        rate = cost_rate_by_fuel.get(ft)
        if rate is None:
            if D(liters) > 0:
                missing.append(ft)
            continue
        total += D(liters) * D(rate)
    return q2(total), missing


def profit_loss(sales_amount, cost, expenses) -> dict:
    gross = q2(D(sales_amount) - D(cost))
    return {"sales": q2(sales_amount), "cost": q2(cost), "gross_margin": gross,
            "expenses": q2(expenses), "net_profit": q2(gross - D(expenses))}
