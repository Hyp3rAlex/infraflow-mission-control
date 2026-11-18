"""Regression tests: amounts in different currencies are never added without an approved conversion.

Background: INV-9006 (USD 5,000, no approved rate) was once added to two invalid EUR rows and
reported as "EUR 9,300 excluded invalid invoices". These tests pin the corrected behaviour.
"""
import json
import re

import pytest

from infraflow import config as c
from infraflow import finance, kpis, reports
from infraflow.excel_export import build_workbook
from infraflow.finance import CurrencyMixError, sum_same_currency


def _inv(i, amount, currency="EUR", cc="CC-A", day="2026-10-10", **kw):
    return dict(invoice_id=i, invoice_date=day, month=day[:7], cost_center=cc, external_id="", amount=amount,
                currency=currency, credit_note_ref="", po_id="", **kw)


# ---- the guard itself --------------------------------------------------------------------------
def test_summing_mixed_currencies_raises():
    rows = [dict(amount=3100, currency="EUR"), dict(amount=5000, currency="USD")]
    with pytest.raises(CurrencyMixError):
        sum_same_currency(rows, "EUR")
    assert sum_same_currency(rows[:1], "EUR") == 3100


def test_no_conversion_rate_is_approved_by_default():
    assert c.APPROVED_FX_RATES == {}


# ---- hand-calculated mini ledger -----------------------------------------------------------------
def test_foreign_rows_are_excluded_in_their_own_currency_and_never_reach_eur_totals(mini):
    """EUR: 1,000 valid, -200 invalid (no credit ref). USD 300 and GBP 70 without rates.
    Expected: actual 1,000 EUR; excluded EUR net -200 / gross 200; USD 300; GBP 70; no bucket mixes."""
    ds = mini(actuals=[_inv("I-1", 1000), _inv("I-2", -200), _inv("I-3", 300, "USD"), _inv("I-4", 70, "GBP")])
    fin = finance.reconcile(ds)
    assert fin.by_cc["CC-A"].actual_eur == 1000
    b = fin.excluded_by_currency()
    assert list(b) == ["EUR", "GBP", "USD"]
    assert (b["EUR"]["net"], b["EUR"]["gross"], b["EUR"]["invoice_ids"]) == (-200, 200, ["I-2"])
    assert (b["USD"]["net"], b["USD"]["invoice_ids"]) == (300, ["I-3"])
    assert (b["GBP"]["net"], b["GBP"]["invoice_ids"]) == (70, ["I-4"])
    for x in fin.excluded:
        assert (x["amount_eur"] is None) == (x["currency"] != "EUR")      # a foreign row has no EUR value
    usd = next(e for e in fin.exceptions if e.record_id == "I-3")
    assert (usd.code, usd.severity, usd.amount_eur, usd.amount_original, usd.currency) == ("UNSUPPORTED_CURRENCY", "CRITICAL", None, 300, "USD")
    assert usd.amount_text == "USD 300 (not converted)" and "€" not in usd.amount_text


def test_missing_currency_is_not_assumed_to_be_eur(mini):
    fin = finance.reconcile(mini(actuals=[_inv("I-1", 500, "")]))
    assert fin.by_cc["CC-A"].actual_eur == 0
    assert [e.code for e in fin.exceptions if e.record_id == "I-1"] == ["UNSUPPORTED_CURRENCY"]
    assert "EUR" not in fin.excluded_by_currency()


def test_conversion_happens_only_with_an_explicit_approved_rate(mini):
    ds = mini(actuals=[_inv("I-1", 1000), _inv("I-3", 300, "USD")])
    assert finance.reconcile(ds).by_cc["CC-A"].actual_eur == 1000                       # default: no rate, no conversion
    assert finance.reconcile(ds, fx_rates={"GBP": 1.2}).by_cc["CC-A"].actual_eur == 1000  # a rate for another currency does not help
    fin = finance.reconcile(ds, fx_rates={"USD": 0.9})
    assert fin.by_cc["CC-A"].actual_eur == 1270                                          # 1,000 + 300 x 0.9
    assert fin.excluded_by_currency() == {}
    conv = next(e for e in fin.exceptions if e.code == "FX_CONVERTED")                   # the conversion is itself reported
    assert (conv.record_id, conv.severity, conv.amount_eur, conv.amount_original, conv.currency) == ("I-3", "INFO", 270, 300, "USD")


# ---- the portfolio dataset -----------------------------------------------------------------------
def test_inv_9006_is_usd_5000_and_not_part_of_any_eur_figure(ds, fin, ground_truth):
    row = next(a for a in ds.actuals if a["invoice_id"] == "INV-9006")
    assert (row["amount"], row["currency"]) == ("5000", "USD")                          # injected record is preserved
    b = fin.excluded_by_currency()
    exp = ground_truth["excluded_invalid_by_currency"]
    assert {cur: (v["net"], v["gross"], v["invoice_ids"]) for cur, v in b.items()} == \
           {cur: (v["net"], v["gross"], v["invoice_ids"]) for cur, v in exp.items()}
    assert b["EUR"]["gross"] == 4300 and b["EUR"]["net"] == 1900 and b["USD"]["net"] == 5000
    assert "INV-9006" not in b["EUR"]["invoice_ids"]
    assert fin.unmapped_actual_eur == 4300 and fin.unmapped_invoice_ids == ground_truth["unmapped_invoice_ids"]
    assert all("INV-9006" not in f.invoice_ids for f in fin.by_cc.values())


def test_kpis_keep_one_figure_per_currency(ctx):
    k = ctx["kpis"]
    assert "finance_excluded_eur" not in k                                               # the old mixed KPI is gone
    assert (k["finance_excluded_eur_gross"]["value"], k["finance_excluded_eur_net"]["value"]) == (4300, 1900)
    assert k["finance_excluded_eur_gross"]["source_ids"] == ["INV-9004", "INV-9008"]
    assert k["finance_excluded_foreign"]["value"] == {"USD": 5000} and k["finance_excluded_foreign"]["source_ids"] == ["INV-9006"]
    assert k["finance_unmapped_actual_eur"]["value"] == 4300 and k["finance_unmapped_actual_eur"]["source_ids"] == ["INV-9002"]


def test_no_output_shows_the_mixed_total_or_a_euro_sign_on_the_usd_amount(tmp_path, ds, ctx):
    out = tmp_path / "reports"
    reports.write_all(ds, out)
    for path in out.iterdir():
        if path.suffix not in (".md", ".json", ".csv"):
            continue
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"9[,.]?300", text), f"mixed-currency total in {path.name}"
        for line in text.splitlines():
            if "INV-9006" in line and "INV-9004" not in line:
                assert "€" not in line, f"USD amount of INV-9006 shown next to a euro sign in {path.name}: {line}"
    weekly = (out / "weekly_portfolio_report.md").read_text(encoding="utf-8")
    assert "USD 5,000 excluded, not converted" in weekly and "PROVISIONAL" in weekly
    budget = (out / "budget_vs_actual.md").read_text(encoding="utf-8")
    assert "INV-9006 (USD 5,000)" in budget and "INV-9004 (-€1,200), INV-9008 (€3,100)" in budget
    register = (out / "financial_exception_register.md").read_text(encoding="utf-8")
    assert "| UNSUPPORTED_CURRENCY | INV-9006 | CC-SEC-OPS | USD 5,000 (not converted) |" in register
    facts = json.loads((out / "report_facts.json").read_text(encoding="utf-8"))
    assert facts["finance"]["excluded_by_currency"]["USD"] == dict(net=5000, gross=5000, invoice_ids=["INV-9006"])
    assert facts["provisional"] is True


def test_workbook_shows_usd_in_its_own_row_and_format(tmp_path, ds):
    from openpyxl import load_workbook
    path = tmp_path / "wb.xlsx"
    build_workbook(ds, path)
    wb = load_workbook(path)
    ws = wb["KPI Summary"]
    rows = {r[1].value: r for r in ws.iter_rows(min_row=5) if r[1].value}
    assert rows["Excluded invalid invoices, gross EUR"][2].value == 4300
    assert rows["Excluded invalid invoices, net EUR"][2].value == 1900
    usd = rows["Excluded, not converted: USD"][2]
    assert usd.value == 5000 and "USD" in usd.number_format and "€" not in usd.number_format and rows["Excluded, not converted: USD"][3].value == "USD"
    assert not any(isinstance(r[2].value, (int, float)) and r[2].value == 9300 for r in rows.values())
    exc = {r[2]: r for r in wb["Exceptions"].iter_rows(min_row=2, values_only=True)}
    assert exc["INV-9006"][5] is None and exc["INV-9006"][6] == 5000 and exc["INV-9006"][7] == "USD"


# ---- PO-015 --------------------------------------------------------------------------------------
def test_po_015_mismatch_is_reported_as_forecast_uncertainty(tmp_path, ds, fin, ctx, ground_truth):
    exp = ground_truth["unreconciled_po"]
    assert len(fin.unreconciled_pos) == 1
    p = fin.unreconciled_pos[0]
    assert (p["po_id"], p["ledger_recognized_eur"], p["invoiced_eur"], p["difference_eur"], p["forecast_effect_eur"]) == \
           (exp["po_id"], exp["ledger_recognized_eur"], exp["invoiced_eur"], exp["difference_eur"], exp["forecast_effect_eur"])
    e = next(e for e in ctx["register"] if e.record_id == "PO-015")
    assert (e.code, e.severity, e.amount_eur) == ("PO_RECONCILIATION_MISMATCH", "CRITICAL", 1000)
    k = ctx["kpis"]
    assert k["finance_unreconciled_po_eur"]["value"] == 1000
    assert k["finance_forecast_eac_invoice_basis_eur"]["value"] == ground_truth["finance_totals"]["forecast_eac_eur"] - 1000
    text = reports.forecast_report(ctx)
    assert "## Forecast reliability" in text and "NOT RECONCILED" in text and "PO-015" in text
    assert ctx["provisional"] is True
