"""LOGIC.md ke test examples. Chalayein:  python -m unittest discover -s tests -v"""
import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.calc import (  # noqa: E402
    CalcError, breakup_matches_entries, cash_transfer_expected, credit_limit_exceeded,
    is_matched, liters_by_fuel, meter_total, nozzle_closing, q2, sale_amount,
    settlement_difference, short_excess_label, stock_after_sale, vehicle_allowed,
    cost_of_sales, party_statement, profit_loss, stock_register,
)


class TestClosing(unittest.TestCase):
    def test_T1_testing_not_counted(self):
        r = nozzle_closing("1000.00", "1105.00", "5.00", "100")
        self.assertEqual(r["gross_liters"], Decimal("105.00"))
        self.assertEqual(r["net_sale_liters"], Decimal("100.00"))

    def test_T2_amount(self):
        r = nozzle_closing("1000", "1100", "0", "100.00")
        self.assertEqual(r["sale_amount"], Decimal("10000.00"))

    def test_T10_closing_less_than_opening_blocked(self):
        with self.assertRaises(CalcError):
            nozzle_closing("1105", "1100", "0", "100")

    def test_T11_testing_more_than_gross_blocked(self):
        with self.assertRaises(CalcError):
            nozzle_closing("1000", "1003", "5", "100")

    def test_zero_closing_blocked(self):
        with self.assertRaises(CalcError):
            nozzle_closing("1000", "0", "0", "100")

    def test_missing_rate_blocked(self):
        with self.assertRaises(CalcError):
            nozzle_closing("1000", "1100", "0", "0")

    def test_no_float_error(self):
        # float mein 0.1 * 3 = 0.30000000000000004
        r = nozzle_closing("0.1", "0.4", "0", "1")
        self.assertEqual(r["net_sale_liters"], Decimal("0.30"))

    def test_real_rate_rounding(self):
        # 33.33 L × 94.77 = 3158.6841 -> 3158.68
        r = nozzle_closing("500", "533.33", "0", "94.77")
        self.assertEqual(r["sale_amount"], Decimal("3158.68"))

    def test_meter_total_multi_nozzle(self):
        rows = [nozzle_closing("0", "100", "0", "100"), nozzle_closing("0", "50", "0", "90")]
        self.assertEqual(meter_total(rows), Decimal("14500.00"))


class TestSettlement(unittest.TestCase):
    def test_T6_short_not_matched(self):
        diff = settlement_difference("10000", "9950", "0", "0", "0")
        self.assertEqual(diff, Decimal("50.00"))
        self.assertFalse(is_matched(diff))
        self.assertEqual(short_excess_label(diff), "Short ₹50.00")

    def test_T7_within_two_rupees(self):
        diff = settlement_difference("10000", "5000", "2998.50", "1000", "1000")
        self.assertEqual(diff, Decimal("1.50"))
        self.assertTrue(is_matched(diff))

    def test_exactly_two_rupees_matched(self):
        self.assertTrue(is_matched(settlement_difference("100", "98", 0, 0, 0)))
        self.assertTrue(is_matched(settlement_difference("100", "102", 0, 0, 0)))

    def test_just_over_two_not_matched(self):
        self.assertFalse(is_matched(settlement_difference("100", "97.99", 0, 0, 0)))

    def test_excess_label(self):
        self.assertEqual(short_excess_label(Decimal("-20")), "Excess ₹20.00")

    def test_breakup_must_match_entries_exactly(self):
        ok, diff = breakup_matches_entries("10000", "6000", "2000", "1000", "1000")
        self.assertTrue(ok)
        ok, diff = breakup_matches_entries("10000", "6000", "2000", "1000", "999.99")
        self.assertFalse(ok)
        self.assertEqual(diff, Decimal("0.01"))

    def test_negative_payment_blocked(self):
        with self.assertRaises(CalcError):
            settlement_difference("100", "-5", 0, 0, 0)

    def test_T9_cash_given_to_creditor(self):
        self.assertEqual(cash_transfer_expected("5000", "500"), Decimal("4500.00"))

    def test_cash_given_more_than_cash_blocked(self):
        with self.assertRaises(CalcError):
            cash_transfer_expected("100", "200")


class TestSale(unittest.TestCase):
    def test_sale_amount(self):
        self.assertEqual(sale_amount("10.5", "94.72"), Decimal("994.56"))

    def test_zero_liters_blocked(self):
        with self.assertRaises(CalcError):
            sale_amount("0", "94")


class TestCredit(unittest.TestCase):
    def test_limit(self):
        self.assertFalse(credit_limit_exceeded("4000", "500", "500", "5000"))
        self.assertTrue(credit_limit_exceeded("4000", "500", "500.01", "5000"))

    def test_no_limit(self):
        self.assertFalse(credit_limit_exceeded("999999", "0", "1", "0"))

    def test_vehicle_list(self):
        self.assertTrue(vehicle_allowed("mh 12 ab 1234", ["MH12AB1234"]))
        self.assertFalse(vehicle_allowed("MH12AB9999", ["MH12AB1234"]))
        self.assertTrue(vehicle_allowed("ANY", []))


class TestStock(unittest.TestCase):
    def test_T12_stock_minus(self):
        self.assertEqual(stock_after_sale("5000", "100"), Decimal("4900.00"))

    def test_stock_cannot_go_negative(self):
        with self.assertRaises(CalcError):
            stock_after_sale("50", "100", "petrol")

    def test_liters_by_fuel(self):
        rows = [
            {"fuel_type": "petrol", "net_sale_liters": "10.10"},
            {"fuel_type": "petrol", "net_sale_liters": "0.20"},
            {"fuel_type": "diesel", "net_sale_liters": "5"},
        ]
        self.assertEqual(liters_by_fuel(rows), {"petrol": Decimal("10.30"), "diesel": Decimal("5.00")})


class TestRounding(unittest.TestCase):
    def test_half_up(self):
        self.assertEqual(q2("2.675"), Decimal("2.68"))   # float round(2.675, 2) = 2.67 (galat)
        self.assertEqual(q2(2.675), Decimal("2.68"))


class TestRegister(unittest.TestCase):
    def test_R6_daily_opening_is_previous_closing(self):
        moves = [
            {"date": "2026-10-01", "kind": "opening", "delta": "5000"},
            {"date": "2026-10-01", "kind": "sale", "delta": "-100"},
            {"date": "2026-10-02", "kind": "inward", "delta": "4000"},
            {"date": "2026-10-02", "kind": "sale", "delta": "-250.50"},
            {"date": "2026-10-03", "kind": "dip_adjust", "delta": "-12"},
        ]
        r = stock_register(Decimal("0"), moves)
        self.assertEqual(r[0]["closing"], Decimal("4900.00"))
        self.assertEqual(r[1]["opening_balance"], Decimal("4900.00"))   # kal ki closing
        self.assertEqual(r[1]["closing"], Decimal("8649.50"))
        self.assertEqual(r[2]["opening_balance"], Decimal("8649.50"))
        self.assertEqual(r[2]["closing"], Decimal("8637.50"))
        self.assertEqual(r[0]["new_tank"], Decimal("5000.00"))

    def test_register_with_previous_balance(self):
        r = stock_register(Decimal("1000"), [{"date": "2026-10-05", "kind": "sale", "delta": "-10"}])
        self.assertEqual(r[0]["opening_balance"], Decimal("1000.00"))
        self.assertEqual(r[0]["closing"], Decimal("990.00"))


class TestParty(unittest.TestCase):
    def test_statement(self):
        tx = [
            {"date": "2026-09-30", "type": "opening", "amount": "2000"},
            {"date": "2026-10-01", "type": "sale", "amount": "1500"},
            {"date": "2026-10-02", "type": "cash_given", "amount": "200"},
            {"date": "2026-10-03", "type": "payment_received", "amount": "3000"},
        ]
        s = party_statement(tx, "2026-10-01")
        self.assertEqual(s["opening"], Decimal("2000.00"))
        self.assertEqual([x["balance"] for x in s["lines"]], [Decimal("3500.00"), Decimal("3700.00"), Decimal("700.00")])
        self.assertEqual(s["closing"], Decimal("700.00"))


class TestProfit(unittest.TestCase):
    def test_R9_cost_by_liters_not_full_tanker(self):
        # 100 L petrol bika, tanker rate 92.50/L -> laagat 9250 (poora tanker bill nahi)
        cost, missing = cost_of_sales({"petrol": Decimal("100"), "diesel": Decimal("50")},
                                      {"petrol": Decimal("92.50")})
        self.assertEqual(cost, Decimal("9250.00"))
        self.assertEqual(missing, ["diesel"])
        p = profit_loss("14500", cost, "1000")
        self.assertEqual(p["gross_margin"], Decimal("5250.00"))
        self.assertEqual(p["net_profit"], Decimal("4250.00"))


if __name__ == "__main__":
    unittest.main()
