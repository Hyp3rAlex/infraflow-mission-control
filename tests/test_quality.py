"""Data-quality and governance findings (exception register)."""
from datetime import date

from infraflow import validator
from infraflow.models import load_dataset
from tests.conftest import demand_row


def ids(reg, code):
    return sorted(e.record_id for e in reg if e.code == code)


def test_register_finds_the_injected_demand_anomalies(ctx, ground_truth):
    reg = ctx["register"]
    assert ids(reg, "MISSING_OWNER") == ground_truth["missing_owner_ids"]
    assert ids(reg, "MISSING_COST_CENTER") == ground_truth["missing_cost_center_ids"]
    assert ids(reg, "MISSING_APPROVER") == ground_truth["missing_approver_ids"]
    assert ids(reg, "INVALID_TRANSITION") == ground_truth["invalid_transition_ids"]
    assert ids(reg, "STATUS_MISMATCH") == ground_truth["invalid_transition_ids"]


def test_register_contains_exactly_the_known_findings(ctx, ground_truth):
    """No unexpected finding types: guards against false positives on the clean part of the data."""
    expected = set(ground_truth["anomalies"]) | {"MISSING_OWNER", "MISSING_COST_CENTER", "MISSING_APPROVER", "INVALID_TRANSITION",
                                                 "STATUS_MISMATCH", "FORECAST_OVERRUN", "CAPACITY_OVERALLOCATED", "AFTER_CUTOFF"}
    assert {e.code for e in ctx["register"]} == expected
    assert len(ctx["register"]) == 19


def test_every_entry_has_risk_action_owner_and_due_date(ctx):
    for e in ctx["register"]:
        assert e.risk and e.proposed_action and e.decision_owner and e.code in validator.PLAYBOOK
        assert e.due_date or e.severity == "INFO"
        if e.due_date:
            assert date.fromisoformat(e.due_date) > ctx["ds"].as_of and date.fromisoformat(e.due_date).weekday() < 5


def test_critical_findings_make_the_report_provisional(ctx):
    crit = [e.code for e in ctx["register"] if e.severity == "CRITICAL"]
    assert sorted(crit) == ["INVALID_AMOUNT", "INVALID_DATE", "MISSING_APPROVER", "PO_RECONCILIATION_MISMATCH", "UNKNOWN_COST_CENTER", "UNSUPPORTED_CURRENCY"]
    assert validator.is_provisional(ctx["register"]) and ctx["provisional"]


def test_clean_data_is_not_provisional(mini):
    ev = dict(event_id="E1", external_id="T-001", occurred_at="2026-11-13T09:00:00", previous_status="", new_status="SUBMITTED")
    reg = validator.build_register(mini(demands=[demand_row(1, requested_at="2026-11-13")], status_events=[ev]))
    assert reg == [] and not validator.is_provisional(reg)


def test_malformed_demand_records_are_reported(mini):
    ds = mini(demands=[demand_row(1, due_at="31.12.2026"), demand_row(1), demand_row(2, demand_status="PARKED"), demand_row(3, external_id="")],
              status_events=[dict(event_id="E1", external_id="T-001", occurred_at="2026-11-14T09:00:00", previous_status="", new_status="SUBMITTED"),
                             dict(event_id="E2", external_id="T-404", occurred_at="2026-11-14T09:00:00", previous_status="", new_status="SUBMITTED")])
    reg = validator.build_register(ds)
    assert ids(reg, "DUPLICATE_DEMAND_ID") == ["(blank)", "T-001"]
    assert "T-001" in ids(reg, "INVALID_DEMAND_RECORD") and "T-002" in ids(reg, "INVALID_DEMAND_RECORD")
    assert ids(reg, "ORPHAN_EVENT") == ["T-404"]


def test_governance_gaps_are_reported(mini):
    ds = mini(demands=[demand_row(1, demand_status="APPROVED", decision_outcome="approved"),
                       demand_row(2, demand_status="DEFERRED"),
                       demand_row(3, demand_status="IN_DELIVERY", security_review_needed="yes", security_review_status="pending"),
                       demand_row(4, demand_status="ASSESSMENT", business_case=""),
                       demand_row(5, demand_status="APPROVED")],
              decisions=[dict(decision_id="D2", external_id="T-002", decided_at="2026-11-10", approver_role="Infrastructure Demand Board Chair", decision="deferred", rationale="x"),
                         dict(decision_id="D3", external_id="T-003", decided_at="2026-11-10", approver_role="Infrastructure Demand Board Chair", decision="approved", rationale="x"),
                         dict(decision_id="D5", external_id="T-005", decided_at="2026-11-10", approver_role="Demand Manager", decision="approved", rationale="x")])
    reg = validator.build_register(ds)
    assert ids(reg, "MISSING_DECISION_RECORD") == ["T-001"]
    assert ids(reg, "DEFERRED_WITHOUT_REVIEW_DATE") == ["T-002"]
    assert ids(reg, "SECURITY_REVIEW_BYPASSED") == ["T-003"] and ids(reg, "HANDOFF_INCOMPLETE") == ["T-003"]
    assert ids(reg, "INCOMPLETE_INTAKE") == ["T-004"]
    assert ids(reg, "MISSING_APPROVER") == ["T-005"]          # a role that may not approve spend


def test_stale_source_data_is_flagged(ds):
    fresh = validator.history_exceptions(ds)
    assert "STALE_DATA" not in {e.code for e in fresh}
    old = validator.history_exceptions(load_dataset(as_of=date(2026, 12, 15)))
    assert "STALE_DATA" in {e.code for e in old}


def test_working_day_arithmetic():
    assert validator.add_working_days(date(2026, 11, 16), 3) == date(2026, 11, 19)
    assert validator.add_working_days(date(2026, 11, 19), 3) == date(2026, 11, 24)      # skips the weekend
