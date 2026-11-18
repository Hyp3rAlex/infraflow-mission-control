"""Finance reconciliation. Expected values come from ground_truth.json (built by construction in the
generator) and from small datasets whose results are worked out by hand in the comments."""
from datetime import date

import pytest

from infraflow import config as c, finance
from infraflow.models import load_dataset
from tests.conftest import demand_row


def test_cost_centre_figures_match_ground_truth(fin, ground_truth):
    assert set(fin.by_cc) == set(ground_truth["finance"])
    for cc, expected in ground_truth["finance"].items():
        got = fin.by_cc[cc].as_dict()
        for key, value in expected.items():
            assert got[key] == value, f"{cc} {key}"


def test_totals_match_ground_truth(fin, ground_truth):
    tot = fin.totals()
    for key, value in ground_truth["finance_totals"].items():
        assert tot[key] == value, key


def test_pinned_portfolio_totals(fin):
    """Regression pins, also quoted in the reports and deck."""
    tot = fin.totals()
    assert (tot["budget_period_eur"], tot["actual_eur"], tot["open_commitments_eur"], tot["approved_not_committed_eur"],
            tot["forecast_eac_eur"], tot["forecast_variance_eur"]) == (1_050_000, 643_450, 238_250, 55_000, 936_700, -113_300)


def test_hand_calculated_mini_ledger(mini):
    """Worked example.
    Budget: 5 months x 10,000 = 50,000; to date (Aug-Nov) 40,000.
    Invoices: 1,000 + 2,000 - 500 credit = 2,500 valid. Not counted: duplicate of the 2,000, a USD row (300),
    a row after the cutoff (700).
    PO-1: approved 5,000, recognised 2,500, open -> outstanding 2,500.  PO-2 closed, PO-3 cancelled -> 0.
    T-002 approved without PO: 4,000 + 100 x 2 months after go-live 2026-10 (Nov, Dec) = 4,200.
    EAC = 2,500 + 2,500 + 4,200 = 9,200. Variance = 9,200 - 50,000 = -40,800. Uncommitted budget = 50,000 - 2,500 - 2,500 = 45,000.
    """
    inv = lambda i, day, amt, **kw: dict(invoice_id=i, invoice_date=day, month=day[:7], cost_center="CC-A", external_id="T-001",
                                         amount=amt, currency="EUR", po_id="PO-1", **kw)
    ds = mini(
        demands=[demand_row(1, demand_status="IN_DELIVERY", decision_date="2026-09-01", decision_outcome="approved"),
                 demand_row(2, demand_status="APPROVED", estimated_one_time_eur=4000, estimated_monthly_recurring_eur=100,
                            due_at="2026-10-20", decision_date="2026-10-01", decision_outcome="approved")],
        actuals=[inv("I-1", "2026-09-10", 1000), inv("I-2", "2026-10-10", 2000), inv("I-2", "2026-10-10", 2000),
                 inv("I-3", "2026-10-20", -500, credit_note_ref="I-2"),
                 dict(inv("I-4", "2026-10-21", 300), currency="USD", po_id=""), inv("I-5", "2026-11-17", 700)],
        commitments=[dict(po_id="PO-1", month="2026-09", cost_center="CC-A", external_id="T-001", approved_commitment_eur=5000, recognized_actual_eur=2500, status="open"),
                     dict(po_id="PO-2", month="2026-09", cost_center="CC-A", external_id="", approved_commitment_eur=900, recognized_actual_eur=0, status="closed"),
                     dict(po_id="PO-3", month="2026-09", cost_center="CC-A", external_id="", approved_commitment_eur=800, recognized_actual_eur=0, status="cancelled")])
    f = finance.reconcile(ds).by_cc["CC-A"]
    assert (f.budget_period_eur, f.budget_to_date_eur) == (50000, 40000)
    assert f.actual_eur == 2500
    assert f.open_commitments_eur == 2500
    assert f.approved_not_committed_eur == 4200
    assert f.forecast_eac_eur == 9200
    assert f.forecast_variance_eur == -40800
    assert f.uncommitted_budget_eur == 45000
    assert f.variance_to_date_eur == -37500


def test_invoiced_part_of_a_purchase_order_is_not_counted_twice(ds, fin):
    """For every reconciled open PO: invoices linked to it + outstanding == approved commitment."""
    flagged = {e.record_id for e in fin.exceptions if e.code in ("PO_RECONCILIATION_MISMATCH", "PO_OVER_RECOGNIZED")}
    linked, seen = {}, set()
    excluded = {x["invoice_id"] for x in fin.excluded if x["reason"] != "DUPLICATE_INVOICE"} | {x["invoice_id"] for x in fin.after_cutoff}
    for a in ds.actuals:
        if a["po_id"] and a["invoice_id"] not in excluded and a["invoice_id"] not in seen:   # a duplicate id counts once
            linked[a["po_id"]] = linked.get(a["po_id"], 0) + float(a["amount"])
        seen.add(a["invoice_id"])
    checked = 0
    for p in ds.commitments:
        if p["status"] == "open" and p["po_id"] not in flagged:
            assert linked.get(p["po_id"], 0) + fin.po_outstanding[p["po_id"]] == float(p["approved_commitment_eur"]), p["po_id"]
            checked += 1
    assert checked >= 15


def test_duplicate_invoice_counted_once(fin, ground_truth):
    dup = ground_truth["anomalies"]["DUPLICATE_INVOICE"]
    assert [e.record_id for e in fin.exceptions if e.code == "DUPLICATE_INVOICE"] == dup
    assert sum(f.invoice_ids.count(dup[0]) for f in fin.by_cc.values()) == 1


@pytest.mark.parametrize("code", ["UNKNOWN_COST_CENTER", "UNAPPROVED_SPEND", "INVALID_AMOUNT", "UNSUPPORTED_CURRENCY",
                                  "MISSING_REFERENCE", "INVALID_DATE", "PO_OVER_RECOGNIZED", "PO_RECONCILIATION_MISMATCH"])
def test_injected_anomaly_is_detected_exactly(fin, ground_truth, code):
    assert sorted(e.record_id for e in fin.exceptions if e.code == code) == sorted(ground_truth["anomalies"][code])


def test_excluded_rows_match_ground_truth_and_are_reported(fin, ground_truth):
    got = sorted((x["invoice_id"], x["reason"], x["amount"], x["currency"]) for x in fin.excluded)
    assert got == sorted((x["invoice_id"], x["reason"], x["amount"], x["currency"]) for x in ground_truth["excluded_invoices"])
    reported = {(e.record_id, e.code) for e in fin.exceptions}
    assert all((i, r) in reported for i, r, _, _ in got)         # nothing is dropped silently


def test_unmapped_spend_and_allocation_coverage(fin, ground_truth):
    assert fin.unmapped_actual_eur == ground_truth["unmapped_actual_eur"] == 4300
    mapped = ground_truth["finance_totals"]["actual_eur"]
    assert fin.allocation_coverage == pytest.approx(mapped / (mapped + 4300))


def test_cutoff_excludes_later_invoice_and_including_it_changes_actuals(ds, fin, ground_truth):
    late = ground_truth["invoice_after_cutoff"]
    assert [x["invoice_id"] for x in fin.after_cutoff] == [late["invoice_id"]]
    later = finance.reconcile(load_dataset(as_of=date(2026, 11, 20)))
    assert later.by_cc["CC-ENG-DATA"].actual_eur == fin.by_cc["CC-ENG-DATA"].actual_eur + late["amount_eur"]
    assert not later.after_cutoff


def test_monthly_actuals_and_budgets_add_up_to_cost_centre_totals(fin):
    for cc, f in fin.by_cc.items():
        assert sum(v for (k, _), v in fin.monthly_actual.items() if k == cc) == f.actual_eur
        assert sum(v for (k, _), v in fin.monthly_budget.items() if k == cc) == f.budget_period_eur
    assert sum(f.forecast_eac_eur for f in fin.by_cc.values()) == fin.totals()["forecast_eac_eur"]


def test_forecast_identity_holds_for_every_cost_centre(fin):
    for f in fin.by_cc.values():
        assert f.forecast_eac_eur == f.actual_eur + f.open_commitments_eur + f.approved_not_committed_eur
        assert f.forecast_variance_eur == f.forecast_eac_eur - f.budget_period_eur
        assert f.uncommitted_budget_eur == f.budget_period_eur - f.actual_eur - f.open_commitments_eur


def test_overrun_is_flagged_only_where_forecast_exceeds_budget(fin):
    assert [e.record_id for e in fin.exceptions if e.code == "FORECAST_OVERRUN"] == ["CC-ENG-SIM"]
    assert fin.by_cc["CC-ENG-SIM"].forecast_variance_eur == 3800


@pytest.mark.parametrize("amount,credit,code", [("-50", "", "INVALID_AMOUNT"), ("0", "", "INVALID_AMOUNT"), ("abc", "", "INVALID_AMOUNT"),
                                                 ("", "", "INVALID_AMOUNT"), ("-50", "NOPE", "INVALID_CREDIT_NOTE")])
def test_invalid_amounts_are_excluded_and_flagged(mini, amount, credit, code):
    ds = mini(actuals=[dict(invoice_id="I-1", invoice_date="2026-10-01", month="2026-10", cost_center="CC-A", amount=amount,
                            currency="EUR", credit_note_ref=credit)])
    res = finance.reconcile(ds)
    assert res.by_cc["CC-A"].actual_eur == 0
    assert [e.code for e in res.exceptions] == [code] and res.exceptions[0].severity == "CRITICAL"


def test_wrong_period_and_unknown_po_are_flagged(mini):
    ds = mini(actuals=[dict(invoice_id="I-1", invoice_date="2026-03-01", month="2026-03", cost_center="CC-A", amount=10, currency="EUR"),
                       dict(invoice_id="I-2", invoice_date="2026-10-01", month="2026-09", cost_center="CC-A", amount=20, currency="EUR", po_id="PO-X")])
    res = finance.reconcile(ds)
    assert sorted(e.code for e in res.exceptions) == ["OUT_OF_PERIOD", "PERIOD_MISMATCH", "UNKNOWN_PO"]
    assert res.by_cc["CC-A"].actual_eur == 20


def test_invalid_commitments_are_excluded_and_flagged(mini):
    po = lambda i, **kw: dict(dict(po_id=i, month="2026-09", cost_center="CC-A", approved_commitment_eur=100, recognized_actual_eur=0, status="open"), **kw)
    ds = mini(commitments=[po("P-1"), po("P-1"), po("P-2", approved_commitment_eur=-5), po("P-3", status="pending"),
                           po("P-4", cost_center="CC-NONE"), po("P-5", month="2025-01")])
    res = finance.reconcile(ds)
    assert res.by_cc["CC-A"].open_commitments_eur == 100
    assert sorted(e.record_id for e in res.exceptions if e.code == "INVALID_COMMITMENT") == ["P-1", "P-2", "P-3", "P-4", "P-5"]


def test_forecast_input_missing_is_disclosed_not_invented(mini):
    ds = mini(demands=[demand_row(1, demand_status="APPROVED", estimated_one_time_eur="", decision_outcome="approved")])
    res = finance.reconcile(ds)
    assert res.by_cc["CC-A"].approved_not_committed_eur == 0
    assert [e.code for e in res.exceptions] == ["FORECAST_INPUT_MISSING"]


def test_period_cost_and_option_total():
    assert finance.recurring_months("2026-10") == 2 and finance.recurring_months("2026-12") == 0 and finance.recurring_months("2027-02") == 0
    assert finance.period_cost(18000, 900, "2026-10") == 19800
    assert finance.period_cost(None, 900, "2026-10") is None
    assert finance.option_total_12_month(48000, 3200) == 86400
    assert finance.option_total_12_month(14500, 600) == 21700


def test_funding_gate_unavailable_without_budget_or_estimate(fin):
    assert finance.funding_gate(fin, "", 100)[0] is None
    assert finance.funding_gate(fin, "CC-ENG-DATA", None)[0] is None
    assert finance.funding_gate(fin, "CC-ENG-DATA", 23950)[0] is True       # exactly the headroom
    assert finance.funding_gate(fin, "CC-ENG-DATA", 23951)[0] is False


def test_scenario_adds_cost_without_changing_the_baseline(fin):
    before = fin.by_cc["CC-ENG-DATA"].forecast_eac_eur
    s = finance.scenario(fin, {"CC-ENG-DATA": 48000})
    assert s["CC-ENG-DATA"] == dict(forecast_eac_eur=224050, forecast_variance_eur=24050)
    assert fin.by_cc["CC-ENG-DATA"].forecast_eac_eur == before
