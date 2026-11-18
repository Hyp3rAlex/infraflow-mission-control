from datetime import date

from infraflow import capacity, config as c, finance, scoring
from tests.conftest import demand_row


def test_cells_match_ground_truth(cap, ground_truth):
    assert len(cap.cells) == len(ground_truth["capacity"]) == len(c.TEAMS) * len(c.CAPACITY_MONTHS)
    for key, exp in ground_truth["capacity"].items():
        team, month = key.split("|")
        cell = cap.cells[(team, month)]
        assert (cell["available"], cell["allocated"], cell["remaining"]) == (exp["available"], exp["allocated"], exp["remaining"])


def test_allocation_lines_reconcile_with_capacity_table(ds, cap):
    assert not [e for e in cap.exceptions if e.code == "CAPACITY_LEDGER_MISMATCH"]
    per_demand = {}
    for a in ds.allocations:
        if a["external_id"] != "RUN":
            per_demand[a["external_id"]] = per_demand.get(a["external_id"], 0) + int(a["hours"])
    for ext, hours in per_demand.items():
        d = ds.demand(ext)
        assert d.status in c.FUNDED and hours <= d.hours          # only approved work, never more than estimated


def test_overallocated_month_is_flagged(cap, ground_truth):
    assert [e.record_id.replace("/", "|") for e in cap.exceptions if e.code == "CAPACITY_OVERALLOCATED"] == ground_truth["overallocated_team_months"]


def test_hero_request_needs_more_hours_than_are_free(ds, fin, cap, ground_truth):
    hero = ground_truth["hero"]
    d = ds.demand(hero["external_id"])
    ok, note, usable = capacity.capacity_gate(cap, d.team, d.hours, d.due_at, ds.as_of)
    assert (ok, usable, d.hours) == (False, hero["hours_available_in_window"], hero["hours_requested"]) == (False, 180, 300)
    assert capacity.delivery_window(d.due_at, ds.as_of, cap.months()) == ["2026-11", "2026-12"]


def test_affordable_request_cannot_be_delivered_on_time(ds, fin, cap, ground_truth):
    """ORION-REQ-023: the cost centre can pay for it, the team cannot staff it before the due date."""
    exp = ground_truth["affordable_but_no_capacity"]
    g = scoring.evaluate(ds, ds.demand(exp["external_id"]), fin, cap)
    assert g.funding_pass is True and g.capacity_pass is False and g.security_pass and g.info_complete
    assert g.hours_available == exp["hours_available_in_window"] == 190
    assert g.failed == ["capacity"]


def test_overallocated_month_counts_as_zero_not_negative(cap):
    assert cap.remaining("NET", "2026-12") == -30
    assert cap.usable("NET", ["2026-11", "2026-12"]) == 20
    assert cap.usable("NET", ["2031-01"]) is None


def test_gate_is_unavailable_when_inputs_are_missing(ds, cap):
    assert capacity.capacity_gate(cap, "", 10, date(2026, 12, 1), ds.as_of)[0] is None
    assert capacity.capacity_gate(cap, "PLAT", None, date(2026, 12, 1), ds.as_of)[0] is None
    assert capacity.capacity_gate(cap, "NOPE", 10, date(2026, 12, 1), ds.as_of)[0] is None


def test_overdue_demand_uses_the_cutoff_month_as_window(ds, cap):
    assert capacity.delivery_window(date(2026, 11, 6), ds.as_of, cap.months()) == ["2026-11"]
    assert capacity.delivery_window(None, ds.as_of, cap.months()) == ["2026-11"]


def test_what_if_consumes_capacity_in_order(ds, cap):
    res = capacity.what_if(ds, cap, ["ORION-REQ-024", "ORION-REQ-017"])
    first, second = res["results"]
    assert first["fits"] and first["hours"] == 140
    # 024 takes the earliest free hours (60 in Nov + 80 of Dec's 120), so the hero then sees 40 instead of 180
    assert not second["fits"] and second["usable_before"] == 40 and second["shortfall"] == 260
    assert cap.remaining("PLAT", "2026-11") == 60                                               # baseline untouched


def test_what_if_with_released_hours_and_smaller_option(ds, cap):
    res = capacity.what_if(ds, cap, ["ORION-REQ-017"], extra_hours={("PLAT", "2026-12"): 120})
    assert res["results"][0]["fits"] and res["remaining"][("PLAT", "2026-11")] == 0 and res["remaining"][("PLAT", "2026-12")] == 0
    res = capacity.what_if(ds, cap, ["ORION-REQ-017"], hours_override={"ORION-REQ-017": 160})
    assert res["results"][0]["fits"] and res["remaining"][("PLAT", "2026-12")] == 20
    assert capacity.what_if(ds, cap, ["NOPE"])["results"][0]["fits"] is None


def test_ledger_mismatch_and_unapproved_allocation_are_detected(mini):
    ds = mini(demands=[demand_row(1, demand_status="ASSESSMENT")],
              capacity=[dict(month="2026-11", team="PLAT", available_hours=100, allocated_hours=70),
                        dict(month="2026-12", team="PLAT", available_hours=100, allocated_hours=-1)],
              allocations=[dict(month="2026-11", team="PLAT", external_id="RUN", hours=40),
                           dict(month="2026-11", team="PLAT", external_id="T-001", hours=20),
                           dict(month="2026-10", team="PLAT", external_id="RUN", hours=5)])
    codes = sorted(e.code for e in capacity.assess(ds).exceptions)
    assert codes == ["ALLOCATION_WITHOUT_APPROVAL", "CAPACITY_LEDGER_MISMATCH", "INVALID_ALLOCATION_ROW", "INVALID_CAPACITY_ROW"]


def test_double_counted_hours_are_detected(mini):
    ds = mini(demands=[demand_row(1, demand_status="APPROVED", estimated_hours=30)],
              capacity=[dict(month="2026-11", team="PLAT", available_hours=100, allocated_hours=50)],
              allocations=[dict(month="2026-11", team="PLAT", external_id="T-001", hours=30), dict(month="2026-11", team="PLAT", external_id="T-001", hours=20)])
    assert [e.code for e in capacity.assess(ds).exceptions] == ["DEMAND_OVER_ALLOCATED"]


# ---- what-if: hours before and after hypothetical allocations -------------------------------------
def test_what_if_separates_today_extra_and_earlier_approvals(ds, cap):
    """Hand calculation, Platform and Storage: unallocated 60 h (Nov), 120 h (Dec), 233 h (Jan).
    REQ-024 (140 h, due Jan): today 413; with +120 h in Dec 533; takes Nov 60 + Dec 80 -> 393 left.
    REQ-017 (300 h, due Dec): today 180; with +120 h 300; REQ-024 took 140 of that window -> usable 160; short by 140."""
    res = capacity.what_if(ds, cap, ["ORION-REQ-024", "ORION-REQ-017"], extra_hours={("PLAT", "2026-12"): 120})
    a, b = res["results"]
    assert (a["unallocated_today"], a["after_extra_capacity"], a["taken_by_earlier_approvals"], a["usable_for_this_demand"], a["fits"], a["remaining_after"]) == \
           (413, 533, 0, 533, True, 393)
    assert (b["unallocated_today"], b["after_extra_capacity"], b["taken_by_earlier_approvals"], b["usable_for_this_demand"], b["fits"], b["shortfall"], b["remaining_after"]) == \
           (180, 300, 140, 160, False, 140, 160)
    for r in (a, b):
        assert r["usable_for_this_demand"] == r["after_extra_capacity"] - r["taken_by_earlier_approvals"] == r["usable_before"]


def test_what_if_baseline_equals_the_capacity_gate_figure(ds, cap, ground_truth):
    """'Hours free' in the reports is the baseline: no extra hours, no other hypothetical approval."""
    hero = ds.demand("ORION-REQ-017")
    gate_hours = capacity.capacity_gate(cap, hero.team, hero.hours, hero.due_at, ds.as_of)[2]
    alone = capacity.what_if(ds, cap, ["ORION-REQ-017"])["results"][0]
    assert gate_hours == alone["unallocated_today"] == alone["usable_for_this_demand"] == ground_truth["hero"]["hours_available_in_window"] == 180
    assert alone["remaining_after"] == 180 and not alone["fits"]            # a demand that does not fit takes nothing
    # the order of hypothetical approvals changes "usable", never "today"
    later = capacity.what_if(ds, cap, ["ORION-REQ-024", "ORION-REQ-017"])["results"][1]
    assert later["unallocated_today"] == 180 and later["usable_for_this_demand"] == 40 and later["taken_by_earlier_approvals"] == 140


def test_what_if_extra_hours_first_absorb_an_over_allocation(ds, cap):
    """Network and Access is 30 h over in December. +50 h there leaves 20 h usable, not 50."""
    assert cap.remaining("NET", "2026-12") == -30
    res = capacity.what_if(ds, cap, ["ORION-REQ-023"], extra_hours={("NET", "2026-12"): 50})["results"][0]
    plain = capacity.what_if(ds, cap, ["ORION-REQ-023"])["results"][0]
    assert res["after_extra_capacity"] - plain["unallocated_today"] == (20 if "2026-12" in res["window"] else 0)


def test_what_if_does_not_change_the_capacity_table(ds, cap):
    before = {k: dict(v) for k, v in cap.cells.items()}
    capacity.what_if(ds, cap, ["ORION-REQ-024", "ORION-REQ-017", "ORION-REQ-023"], extra_hours={("PLAT", "2026-12"): 500})
    assert {k: dict(v) for k, v in cap.cells.items()} == before
    text = capacity.what_if_text(capacity.what_if(ds, cap, ["ORION-REQ-017", "NOPE"]))
    assert "short by 120 h" in text and "simulation only" in text and "unknown demand" in text
