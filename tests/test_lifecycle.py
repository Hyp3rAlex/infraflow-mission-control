from datetime import date

import pytest

from infraflow import config as c, lifecycle, scoring
from infraflow.lifecycle import LifecycleError, apply_transition, check_transition, history_problems

CHAIR = "Infrastructure Demand Board Chair"
DECISION = dict(approver_role=CHAIR, rationale="Business case accepted.", followup_date="2026-12-08")
TODAY = date(2026, 11, 17)


def gates_for(ds, fin, cap, ext):
    return scoring.evaluate(ds, ds.demand(ext), fin, cap)


def test_transition_table_is_closed_and_terminal_states_have_no_exit():
    assert set(c.ALLOWED_TRANSITIONS) == set(c.STATUS_ORDER)
    assert all(t <= set(c.STATUS_ORDER) for t in c.ALLOWED_TRANSITIONS.values())
    assert all(not c.ALLOWED_TRANSITIONS[s] for s in c.TERMINAL)


@pytest.mark.parametrize("ext,new", [("ORION-REQ-041", c.IN_DELIVERY), ("ORION-REQ-041", c.APPROVED), ("ORION-REQ-034", c.READY_FOR_DECISION),
                                     ("ORION-REQ-001", c.IN_DELIVERY), ("ORION-REQ-046", c.TRIAGED), ("ORION-REQ-048", c.ASSESSMENT)])
def test_skipping_stages_or_leaving_terminal_states_is_refused(ds, ext, new):
    with pytest.raises(LifecycleError, match="not allowed"):
        check_transition(ds.demand(ext), new, "Demand Manager")


def test_generated_histories_follow_the_transition_table(ds, ground_truth):
    bad = {d.external_id for d in ds.demands if history_problems(ds.events_for(d.external_id))}
    assert bad == set(ground_truth["invalid_transition_ids"])


def test_high_score_does_not_approve_when_a_gate_fails(ds, fin, cap):
    """ORION-REQ-023 has the highest score in the queue and still cannot be approved without an explicit exception."""
    d, g = ds.demand("ORION-REQ-023"), gates_for(ds, fin, cap, "ORION-REQ-023")
    assert g.score == 90.0 and g.band == "Highest" and g.failed == ["capacity"]
    with pytest.raises(LifecycleError, match="capacity gate not passed"):
        check_transition(d, c.APPROVED, CHAIR, DECISION, g)
    new, event = apply_transition(d, c.DEFERRED, CHAIR, TODAY, "Deferred: no network capacity before February.", DECISION, g)
    assert new.status == c.DEFERRED and new.next_review_at == date(2026, 12, 8) and new.decision_owner == CHAIR
    assert event["previous_status"] == c.READY_FOR_DECISION and event["actor_role"] == CHAIR
    assert d.status == c.READY_FOR_DECISION                      # original record is not mutated


def test_explicit_exception_is_recorded_in_the_rationale(ds, fin, cap):
    d, g = ds.demand("ORION-REQ-023"), gates_for(ds, fin, cap, "ORION-REQ-023")
    new, _ = apply_transition(d, c.APPROVED, CHAIR, TODAY, "Approved with exception.", DECISION, g,
                              exception_rationale="Contractor hours funded from the project budget.")
    assert new.status == c.APPROVED and "Exception: Contractor hours" in new.decision_rationale


def test_demand_passing_all_gates_still_needs_a_human_decision_record(ds, fin, cap):
    d, g = ds.demand("ORION-REQ-025"), gates_for(ds, fin, cap, "ORION-REQ-025")
    assert g.all_pass
    with pytest.raises(LifecycleError, match="decision record"):
        check_transition(d, c.APPROVED, CHAIR, None, g)
    with pytest.raises(LifecycleError, match="gate evaluation"):
        check_transition(d, c.APPROVED, CHAIR, DECISION, None)
    with pytest.raises(LifecycleError, match="rationale"):
        check_transition(d, c.APPROVED, CHAIR, dict(approver_role=CHAIR, rationale=" "), g)
    check_transition(d, c.APPROVED, CHAIR, DECISION, g)


@pytest.mark.parametrize("actor", ["system", "Automation rule 4", "AI assistant", "bot-weekly", "script"])
def test_no_automatic_approval(ds, fin, cap, actor):
    with pytest.raises(LifecycleError, match="human role"):
        check_transition(ds.demand("ORION-REQ-025"), c.APPROVED, actor, DECISION, gates_for(ds, fin, cap, "ORION-REQ-025"))


def test_unauthorised_or_limited_approvers_are_refused(ds, fin, cap):
    d, g = ds.demand("ORION-REQ-025"), gates_for(ds, fin, cap, "ORION-REQ-025")
    with pytest.raises(LifecycleError, match="not an authorised approver"):
        check_transition(d, c.APPROVED, "Delivery Lead", dict(DECISION, approver_role="Delivery Lead"), g)
    with pytest.raises(LifecycleError, match="not approve spend"):
        check_transition(d, c.APPROVED, "Demand Manager", dict(DECISION, approver_role="Demand Manager"), g)
    check_transition(d, c.REJECTED, "Demand Manager", dict(DECISION, approver_role="Demand Manager"), g)


def test_security_gate_cannot_be_overridden(ds, fin, cap):
    d, g = ds.demand("ORION-REQ-024"), gates_for(ds, fin, cap, "ORION-REQ-024")
    assert d.security_needed and not g.security_pass
    with pytest.raises(LifecycleError, match="security review"):
        check_transition(d, c.APPROVED, CHAIR, DECISION, g, exception_rationale="urgent")


def test_deferral_needs_a_review_date(ds, fin, cap):
    with pytest.raises(LifecycleError, match="next review date"):
        check_transition(ds.demand("ORION-REQ-023"), c.DEFERRED, CHAIR, dict(approver_role=CHAIR, rationale="No capacity."))


def test_triage_requires_complete_intake_and_routing_requires_a_target(ds):
    incomplete = ds.demand("ORION-REQ-039")            # no cost centre
    with pytest.raises(LifecycleError, match="intake incomplete, missing cost_center"):
        check_transition(incomplete, c.TRIAGED, "Demand Analyst Madrid")
    with pytest.raises(LifecycleError, match="receiving queue"):
        check_transition(ds.demand("ORION-REQ-042"), c.ROUTED_OUT, "Demand Analyst Toulouse")
    with pytest.raises(LifecycleError, match="actor role"):
        check_transition(ds.demand("ORION-REQ-042"), c.TRIAGED, " ")


def test_handoff_and_delivery_controls(ds):
    approved = ds.demand("ORION-REQ-050")
    check_transition(approved, c.HANDOFF, "Demand Manager")
    with pytest.raises(LifecycleError, match="recorded approval"):
        check_transition(approved.with_changes(decision_outcome=""), c.HANDOFF, "Demand Manager")
    handoff = ds.demand("ORION-REQ-019")
    check_transition(handoff, c.IN_DELIVERY, "Delivery Lead Network and Access")
    for change in (dict(handoff_ref=""), dict(handoff_complete=False), dict(delivery_lead="")):
        with pytest.raises(LifecycleError, match="handoff checklist"):
            check_transition(handoff.with_changes(**change), c.IN_DELIVERY, "Delivery Lead Network and Access")


def test_completion_controls(ds):
    running = ds.demand("ORION-REQ-010")
    check_transition(running, c.COMPLETE, "Delivery Lead Security Engineering")
    with pytest.raises(LifecycleError, match="blocked"):
        check_transition(ds.demand("ORION-REQ-012"), c.COMPLETE, "Delivery Lead Network and Access")
    row = dict(running.row, cost_center="")
    with pytest.raises(LifecycleError, match="unfilled required fields"):
        check_transition(running.with_changes(row=row), c.COMPLETE, "Delivery Lead Security Engineering")


def test_history_problems_detects_bad_start_gap_and_jump():
    ev = lambda i, prev, new: dict(event_id=f"E{i}", previous_status=prev, new_status=new)
    assert history_problems([ev(1, "", c.SUBMITTED), ev(2, c.SUBMITTED, c.TRIAGED), ev(3, c.TRIAGED, c.ASSESSMENT)]) == []
    assert [p[0] for p in history_problems([ev(1, "", c.TRIAGED)])] == ["E1"]
    assert [p[0] for p in history_problems([ev(1, "", c.SUBMITTED), ev(2, c.TRIAGED, c.ASSESSMENT)])] == ["E2"]
    assert [p[0] for p in history_problems([ev(1, "", c.SUBMITTED), ev(2, c.SUBMITTED, c.COMPLETE)])] == ["E2"]
