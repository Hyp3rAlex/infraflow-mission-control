import hashlib
import json

import pytest

from infraflow import reports
from infraflow.excel_export import build_workbook
from tests.conftest import demand_row


@pytest.fixture(scope="module")
def out(tmp_path_factory, ds):
    path = tmp_path_factory.mktemp("reports")
    res = reports.write_all(ds, path)
    return path, res


def test_all_reports_are_written_and_deterministic(out, ds, tmp_path):
    path, res = out
    assert len(res["files"]) == 15 and all((path / f).stat().st_size > 200 for f in res["files"])
    reports.write_all(ds, tmp_path)
    digest = lambda p: {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(p.iterdir())}
    assert digest(path) == digest(tmp_path)


def test_every_report_states_cutoff_mode_and_provisional_status(out):
    path, res = out
    for name in res["files"]:
        if name.endswith(".md") and name != "management_email.md":
            text = (path / name).read_text()
            assert "Reporting date (cutoff, inclusive):** 2026-11-16" in text, name
            assert "OFFLINE_FIXTURE" in text and "PROVISIONAL" in text and "Sources:" in text, name


def test_facts_file_matches_ground_truth(out, ground_truth):
    facts = json.loads((out[0] / "report_facts.json").read_text())
    assert facts["finance"]["totals"]["forecast_eac_eur"] == ground_truth["finance_totals"]["forecast_eac_eur"]
    for cc, exp in ground_truth["finance"].items():
        assert {k: facts["finance"]["by_cost_centre"][cc][k] for k in exp} == exp
    assert facts["kpis"]["overdue_open"]["source_ids"] == ground_truth["overdue_open_ids"]
    assert facts["provisional"] is True and facts["exception_counts"] == {"CRITICAL": 6, "WARNING": 12, "INFO": 1}
    hero = facts["hero"]
    assert hero["options"][0]["total_12_month_eur"] == ground_truth["hero"]["option_a_12_month_eur"] == 86400
    assert hero["options"][1]["total_12_month_eur"] == ground_truth["hero"]["option_b_12_month_eur"] == 21700
    assert hero["decision"]["decision"] == "deferred" and hero["decision"]["approver_role"] == "Infrastructure Demand Board Chair"


def test_weekly_report_figures_are_the_computed_ones(out, ground_truth):
    text = (out[0] / "weekly_portfolio_report.md").read_text()
    tot = ground_truth["finance_totals"]
    for amount in (tot["budget_period_eur"], tot["actual_eur"], tot["open_commitments_eur"], tot["forecast_eac_eur"]):
        assert f"€{amount:,.0f}" in text
    assert "37 open demands (50 registered); 5 await a board decision, 4 are overdue, 3 blocked and 3 have no owner" in text
    for section in ("Executive summary", "Decisions required", "Operational health", "Financial status", "Data quality caveats",
                    "Owner / action / date", "Methodology and cutoff"):
        assert f"## {section}" in text
    for ext in ground_truth["overdue_open_ids"] + ground_truth["blocked_ids"] + ground_truth["missing_owner_ids"]:
        assert ext in text


def test_weekly_report_is_short_enough_to_read_quickly(out):
    words = len((out[0] / "weekly_portfolio_report.md").read_text().split())
    assert words < 1500
    assert len((out[0] / "management_email.md").read_text().split()) < 180


def test_exception_register_csv_lists_every_finding_with_owner_and_action(out, ctx):
    import csv
    rows = list(csv.DictReader((out[0] / "exception_register.csv").open()))
    assert len(rows) == len(ctx["register"]) == 19
    assert all(r["risk"] and r["proposed_action"] and r["decision_owner"] for r in rows)


def test_decisions_required_come_from_facts(ctx):
    req = reports.decisions_required(ctx)
    topics = " | ".join(x["topic"] for x in req)
    assert req[0]["topic"].startswith("ORION-REQ-023") and "capacity" in req[0]["decision"]
    assert "CC-ENG-SIM forecast overrun" in topics and "Network and Access over-allocated in 2026-12" in topics
    assert "ORION-REQ-021" in topics and "ORION-REQ-017" in topics
    assert all(x["owner"] and x["due"] for x in req)
    assert reports.next_board_date(ctx["ds"].as_of).isoformat() == "2026-11-17"


def test_action_register_has_owner_and_date_for_every_row(ctx):
    acts = reports.action_register(ctx)
    assert len(acts) >= 15 and all(a["owner"] and a["due"] and a["action"] for a in acts)
    kinds = {a["kind"] for a in acts}
    assert {"blocked", "overdue", "needs info", "decision follow-up", "MISSING_APPROVER"} <= kinds


def test_decision_brief_tells_the_hero_story(out):
    text = (out[0] / "decision_brief_ORION-REQ-017.md").read_text()
    for needle in ("Option A: Additional managed storage", "Option B: Archive and optimise existing capacity", "€86,400", "€21,700",
                   "€224,050", "€190,550", "300 h needed, 180 h unallocated", "DEFERRED", "Infrastructure Demand Board Chair",
                   "2026-12-08", "Needs Info", "Handoff checklist", "did not lead to approval"):
        assert needle in text, needle


def test_changing_a_source_record_changes_the_derived_report(data_copy, ctx):
    """Reports are derived: approving the hero's Option B in the source data moves the forecast and the status counts."""
    import csv
    from infraflow.models import load_dataset
    path = data_copy / "demands.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    for r in rows:
        if r["external_id"] == "ORION-REQ-017":
            r.update(demand_status="APPROVED", decision_outcome="approved", estimated_one_time_eur="14500",
                     estimated_monthly_recurring_eur="600", estimated_hours="160", next_review_at="")
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    new = reports.build_context(load_dataset(data_copy))
    assert new["fin"].by_cc["CC-ENG-DATA"].forecast_eac_eur == ctx["fin"].by_cc["CC-ENG-DATA"].forecast_eac_eur + 14500 == 190550
    assert new["kpis"]["by_status"]["value"]["DEFERRED"] == 3 and new["kpis"]["by_status"]["value"]["APPROVED"] == 4
    assert "ORION-REQ-017" in new["fin"].by_cc["CC-ENG-DATA"].uncommitted_demand_ids


def test_clean_dataset_has_no_provisional_banner(mini):
    ev = dict(event_id="E1", external_id="T-001", occurred_at="2026-11-13T09:00:00", previous_status="", new_status="SUBMITTED")
    ctx = reports.build_context(mini(demands=[demand_row(1, requested_at="2026-11-13")], status_events=[ev]))
    assert "PROVISIONAL" not in reports.header(ctx, "x", "y") and not ctx["provisional"]


def test_workbook_values_match_independent_ground_truth(tmp_path, ds, ground_truth, ctx):
    from openpyxl import load_workbook
    path = tmp_path / "wb.xlsx"
    build_workbook(ds, path)
    wb = load_workbook(path)
    assert wb.sheetnames == ["README", "KPI Summary", "Demand Register", "Budget", "Actuals", "Commitments", "Forecast", "Capacity",
                             "Exceptions", "Actions", "Hero Scenario", "Assumptions", "Data Dictionary"]
    from conftest import sheet_rows
    _, kpi_table = sheet_rows(wb["KPI Summary"], "Section")
    kpi = {r[1]: r[2] for r in kpi_table}
    tot = ground_truth["finance_totals"]
    assert kpi["Open demands"] == ground_truth["open_count"] and kpi["Overdue open demands"] == 4 and kpi["Critical exceptions"] == 6
    assert (kpi["Budget (period) EUR"], kpi["Actual to date EUR"], kpi["Open commitments EUR"], kpi["Forecast EAC EUR"], kpi["Forecast variance EUR"]) == (
        tot["budget_period_eur"], tot["actual_eur"], tot["open_commitments_eur"], tot["forecast_eac_eur"], tot["forecast_variance_eur"])
    _, rows = sheet_rows(wb["Forecast"], "Cost centre")
    for r in rows[:5]:
        exp = ground_truth["finance"][r[0]]
        assert (r[2], r[4], r[6], r[7], r[9], r[10]) == (exp["budget_period_eur"], exp["actual_eur"], exp["open_commitments_eur"],
                                                         exp["approved_not_committed_eur"], exp["forecast_eac_eur"], exp["forecast_variance_eur"])
    assert rows[5][0] == "TOTAL" and rows[5][9] == tot["forecast_eac_eur"]
    assert wb["Demand Register"].max_row == 51 and wb["Exceptions"].max_row == 20
    assert wb["Demand Register"].freeze_panes == "A2" and wb["Demand Register"].auto_filter.ref
    assert sum(len(ws._charts) for ws in wb) == 3
    included = sum(r[5] for r in wb["Actuals"].iter_rows(min_row=2, values_only=True) if r[9] == "yes")
    assert included == tot["actual_eur"]                                       # row flags reconcile with the total
    assert sum(r[7] or 0 for r in wb["Commitments"].iter_rows(min_row=2, values_only=True)) == tot["open_commitments_eur"]
    for (team_month, exp) in ground_truth["capacity"].items():
        pass
    cap_rows = {(r[0], r[1]): r[6] for r in sheet_rows(wb["Capacity"], "Team")[1]}
    assert cap_rows[("Platform and Storage", "2026-11")] + cap_rows[("Platform and Storage", "2026-12")] == 180
    assert "must be re-checked after regeneration" in " ".join(str(r[0]) for r in wb["README"].iter_rows(values_only=True))
