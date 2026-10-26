"""Pure money / meter maths. No database, no Streamlit: easy to test."""


def f(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def payment_match(total_sale, cash, paytm, ccms, credit=0.0) -> dict:
    total_sale, cash, paytm, ccms, credit = (round(f(x), 2) for x in (total_sale, cash, paytm, ccms, credit))
    paid = round(cash + paytm + ccms + credit, 2)
    diff = round(total_sale - paid, 2)
    return {"total_sale": total_sale, "cash": cash, "paytm": paytm, "ccms": ccms, "credit": credit,
            "payment_total": paid, "difference": diff, "is_matched": abs(diff) < 0.01}


def meter_rows(assignments, sales, closing_inputs):
    """
    assignments: active shift assignments (need id, nozzle_id, nozzle_name, opening_reading)
    sales: live sale entries of the shift
    closing_inputs: {assignment_id: closing reading}
    Returns (rows, total_meter_amount, errors).
    """
    rows, errors, total = [], [], 0.0
    for a in assignments:
        aid = a["id"]
        name = a.get("nozzle_name") or f"Nozzle {a['nozzle_id']}"
        mine = [s for s in sales if s.get("nozzle_id") == a["nozzle_id"]]
        entered_l = round(sum(f(s.get("liters")) for s in mine), 3)
        entered_amt = round(sum(f(s.get("amount")) for s in mine), 2)
        opening = f(a.get("opening_reading"))

        raw = closing_inputs.get(aid, closing_inputs.get(str(aid)))
        if raw is None or raw == "":
            errors.append(f"{name}: closing reading missing.")
            continue
        closing = f(raw)
        if closing < opening:
            errors.append(f"{name}: closing {closing} is less than opening {opening}.")
            continue

        meter_l = round(closing - opening, 3)
        if abs(meter_l - entered_l) < 0.0005:
            meter_amt = entered_amt
        elif entered_l > 0:
            meter_amt = round(meter_l * (entered_amt / entered_l), 2)
        elif meter_l > 0:
            errors.append(f"{name}: meter shows {meter_l} L but no sale entry exists, so no rate to use.")
            continue
        else:
            meter_amt = 0.0

        total += meter_amt
        rows.append({
            "assignment_id": aid, "nozzle_id": a["nozzle_id"], "nozzle": name,
            "opening": opening, "closing": closing, "meter_liters": meter_l,
            "entered_liters": entered_l, "liters_difference": round(meter_l - entered_l, 3),
            "meter_amount": meter_amt,
        })
    return rows, round(total, 2), errors
