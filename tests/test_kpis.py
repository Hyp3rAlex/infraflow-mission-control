from datetime import date

from infraflow import capacity, config as c, finance, kpis
from infraflow.models import load_dataset


def test_status_counts_and_open_count_match_ground_truth(ctx, ground_truth):
    k = ctx["kpis"]
    assert {s: n for s, n in k["by_status"]["value"].items() if n} == ground_truth["status_counts"]
    assert k["open_demands"]["value"] == ground_truth["open_count"] == 37
    assert k["total_demands"]["value"] == 50


def test_exception_lists_match_ground_truth(ctx, ground_truth):
    k = ctx["kpis"]
    assert k["overdue_open"]["source_ids"] == ground_truth["overdue_open_ids"]
    assert k["blocked_open"]["source_ids"] == ground_truth["blocked_ids"]
    assert k["unassigned_open"]["source_ids"] == ground_truth["missing_owner_ids"]
    assert k["overallocated_team_months"]["source_ids"] == ground_truth["overallocated_team_months"]


def test_every_kpi_has_a_definition_and_counts_tie_to_ids(ctx):
    for name, v in ctx["kpis"].items():
        assert v["definition"], name
    for name in ("open_demands", "overdue_open", "blocked_open", "stale_open", "unassigned_open", "approval_pending",
                 "intake_last_7_days", "completed_total", "routed_out", "high_priority_not_approvable"):
        assert ctx["kpis"][name]["value"] == len(ctx["kpis"][name]["source_ids"]), name


def test_percentages_are_consistent_with_their_counts(ctx):
    k = ctx["kpis"]
    assert k["unassigned_pct"]["value"] == round(100 * 3 / 37, 1)
    assert k["completeness_pct"]["value"] == round(100 * (48 - 4) / 48, 1)       # 2 routed-out records are out of scope
    assert sum(k["open_by_priority"]["value"].values()) == sum(k["open_by_site"]["value"].values()) == sum(k["open_by_team"]["value"].values()) == 37
    assert sum(k["throughput_by_month"]["value"].values()) == k["completed_total"]["value"] == 9
    assert sum(k["intake_by_month"]["value"].values()) == 50


def test_business_days():
    assert kpis.business_days_between(date(2026, 10, 5), date(2026, 10, 14)) == 7      # Mon -> Wed of the following week
    assert kpis.business_days_between(date(2026, 11, 13), date(2026, 11, 16)) == 1     # Fri -> Mon
    assert kpis.business_days_between(date(2026, 11, 16), date(2026, 11, 16)) == 0


def test_hero_ageing_follows_the_status_history(ds):
    assert kpis.days_in_status(ds, "ORION-REQ-017", c.DEFERRED) == 6                   # deferred 2026-11-10, cutoff 2026-11-16
    assert kpis.days_in_status(ds, "ORION-REQ-017", c.COMPLETE) is None


def test_cutoff_changes_history_based_metrics(ds, ctx):
    """Events after an earlier cutoff must not count: fewer completions, hero not yet deferred."""
    early = load_dataset(as_of=date(2026, 10, 20))
    k = kpis.compute(early, finance.reconcile(early), capacity.assess(early))
    assert k["completed_total"]["value"] < ctx["kpis"]["completed_total"]["value"]
    assert set(k["throughput_by_month"]["value"]) <= {"2026-08", "2026-09", "2026-10"}
    assert [e["new_status"] for e in early.events_for("ORION-REQ-017")][-1] == c.ASSESSMENT
    assert kpis.days_in_status(early, "ORION-REQ-017", c.DEFERRED) is None
    assert k["total_demands"]["value"] < 50                                              # later requests are not registered yet


def test_a_later_event_is_ignored_until_the_cutoff_passes(data_copy):
    """Appending an event dated after the cutoff does not change today's ageing; moving the cutoff does."""
    with (data_copy / "status_events.csv").open("a", encoding="utf-8") as fh:
        fh.write("EVT-9999,ORION-REQ-017,2026-11-18T10:00:00,Infrastructure Demand Board Chair,DEFERRED,READY_FOR_DECISION,Re-review brought forward.\n")
    now = load_dataset(data_copy)
    assert kpis.days_in_status(now, "ORION-REQ-017", c.DEFERRED) == 6
    later = load_dataset(data_copy, as_of=date(2026, 11, 20))
    assert later.events_for("ORION-REQ-017")[-1]["new_status"] == c.READY_FOR_DECISION
    assert kpis.days_in_status(later, "ORION-REQ-017", c.READY_FOR_DECISION) == 2


def test_triage_and_lead_time_use_event_history(ctx, ds):
    k = ctx["kpis"]
    assert k["median_triage_business_days"]["value"] == 3.0
    assert "ORION-REQ-041" not in k["median_triage_business_days"]["source_ids"]         # never triaged, excluded
    assert k["median_lead_time_days"]["value"] == 49 and len(k["median_lead_time_days"]["source_ids"]) == 9
    assert k["decision_outcomes"]["value"] == {"approved": 21, "deferred": 4, "rejected": 2}
