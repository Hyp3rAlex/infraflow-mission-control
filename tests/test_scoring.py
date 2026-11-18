import pytest

from infraflow import config as c, scoring
from tests.conftest import demand_row
from infraflow.models import Demand


def make(i, u, r, s):
    return Demand.from_row(demand_row(1, business_impact_score=i, urgency_score=u, risk_reduction_score=r, strategic_alignment_score=s))


@pytest.mark.parametrize("scores,expected,band", [
    ((5, 4, 3, 4), 82.0, "Highest"),   # 100*(1.75+1.00+0.75+0.60)/5
    ((5, 5, 5, 5), 100.0, "Highest"), ((0, 0, 0, 0), 0.0, "Lowest"),
    ((4, 3, 3, 4), 70.0, "High"),      # 100*(1.40+0.75+0.75+0.60)/5
    ((3, 3, 3, 3), 60.0, "Medium"), ((2, 2, 1, 3), 38.0, "Low"), ((1, 1, 1, 1), 20.0, "Lowest")])
def test_score_formula_and_bands(scores, expected, band):
    d = make(*scores)
    assert scoring.priority_score(d) == expected and scoring.priority_band(expected) == band


def test_weights_sum_to_one_and_band_boundaries():
    assert sum(c.SCORE_WEIGHTS.values()) == pytest.approx(1.0)
    assert [scoring.priority_band(x) for x in (80, 79.9, 65, 45, 25, 24.9)] == ["Highest", "High", "High", "Medium", "Low", "Lowest"]


@pytest.mark.parametrize("bad", ["", "x", 6, -1])
def test_invalid_score_input_gives_unscored_not_a_guess(bad):
    d = make(bad, 3, 3, 3)
    assert scoring.priority_score(d) is None and scoring.priority_band(None) == "Unscored"


def test_hero_gates_match_ground_truth(ds, fin, cap, ground_truth):
    hero, d = ground_truth["hero"], ds.demand("ORION-REQ-017")
    a = scoring.evaluate(ds, d, fin, cap)
    assert (a.period_cost_eur, a.funding_pass, a.capacity_pass) == (hero["option_a_period_cost_eur"], hero["funding_pass_option_a"], hero["capacity_pass_option_a"])
    b = scoring.evaluate(ds, d, fin, cap, one_time=14500, monthly=600, hours=160)
    assert (b.period_cost_eur, b.funding_pass, b.capacity_pass) == (hero["option_b_period_cost_eur"], hero["funding_pass_option_b"], hero["capacity_pass_option_b"])
    assert a.band == "Highest" and d.status == c.DEFERRED and d.decision_outcome == hero["decision"]
    assert d.next_review_at.isoformat() == hero["next_review_at"]


def test_review_queue_is_ordered_by_score_and_excludes_decided_work(ds, fin, cap):
    q = scoring.review_queue(ds, fin, cap)
    scores = [r["gates"].score for r in q]
    assert scores == sorted(scores, reverse=True)
    assert all(r["demand"].status in c.PRE_DECISION or r["demand"].status == c.DEFERRED for r in q)
    assert q[0]["demand"].external_id == "ORION-REQ-023"


def test_recommendation_is_advice_and_names_failed_gates(ds, fin, cap):
    q = {r["demand"].external_id: r for r in scoring.review_queue(ds, fin, cap)}
    assert q["ORION-REQ-025"]["recommendation"].startswith("Eligible for an approval decision")
    assert "funding, capacity gates not passed" in q["ORION-REQ-027"]["recommendation"]
    assert all(r["demand"].status != c.APPROVED for r in q.values())      # evaluating never changes status


def test_missing_information_fails_the_information_and_funding_gates(ds, fin, cap):
    g = scoring.evaluate(ds, ds.demand("ORION-REQ-039"), fin, cap)        # no cost centre
    assert not g.info_complete and g.missing_fields == ["cost_center", "open clarification request"] and g.funding_pass is None
    assert "information" in g.failed and "funding" in g.failed


def test_several_high_priority_demands_are_not_approvable(ds, fin, cap):
    q = scoring.review_queue(ds, fin, cap)
    high_blocked = [r for r in q if r["gates"].band in ("High", "Highest") and not r["gates"].all_pass]
    reasons = {f for r in high_blocked for f in r["gates"].failed}
    assert len(high_blocked) >= 5 and {"funding", "capacity", "information"} <= reasons
