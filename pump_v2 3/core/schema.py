"""Tables/columns this version needs. The Diagnostics page checks every one,
so a missing column is found in one click instead of by a mysterious crash."""

FUEL_TYPES = ["petrol", "diesel", "premium_petrol", "premium_diesel"]
ROLES = ["owner", "manager", "salesman"]

REQUIRED = {
    "profiles": ["id", "name", "role", "phone", "is_active"],
    "shifts": ["id", "salesman_id", "started_by", "is_active", "started_at", "ended_at", "date"],
    "nozzles": ["id", "nozzle_name", "fuel_type", "current_reading", "is_active"],
    "fuel_rates": ["id", "fuel_type", "price_per_liter", "effective_from", "created_by", "created_at"],
    "shift_assignments": ["id", "shift_id", "salesman_id", "nozzle_id", "opening_reading",
                          "is_active", "assigned_by", "created_at", "ended_at"],
    "sale_entries": ["id", "shift_id", "nozzle_id", "salesman_id", "date", "entry_time", "fuel_type",
                     "liters", "rate", "locked_rate", "rate_date", "rate_snapshot", "amount", "status"],
    "settlements": ["id", "shift_id", "salesman_id", "date", "nozzle_readings", "meter_total",
                    "entries_total", "difference", "cash_amount", "paytm_amount", "ccms_amount",
                    "credit_amount", "cash_given_to_creditor_amount", "cash_transfer_expected",
                    "status", "manager_note", "created_at", "approved_by", "approved_at"],
}
