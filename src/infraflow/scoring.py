"""Prioritisation score and decision gates.

The score orders the review queue. It never approves anything: approval is a recorded decision
by an authorised human role (see lifecycle.py). The gates describe whether a demand *could* be
approved today without breaking a budget, over-committing a team or skipping a security review.

score = 100 * (0.35*impact + 0.25*urgency + 0.25*risk_reduction + 0.15*strategic) / 5, each input 0-5.

Limitations: weights are a policy choice, not derived from data; inputs are analyst judgements;
the funding and capacity gates look at one demand at a time (use the what-if functions to test
combinations).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import config as c
from .capacity import CapacityResult, capacity_gate
from .finance import FinanceResult, demand_period_cost, funding_gate
from .models import Dataset, Demand


def priority_score(d: Demand) -> float | None:
    vals = dict(business_impact_score=d.impact, urgency_score=d.urgency,
                risk_reduction_score=d.risk_reduction, strategic_alignment_score=d.strategic)
    if any(v is None or not 0 <= v <= 5 for v in vals.values()):
        return None
    return round(100 * sum(c.SCORE_WEIGHTS[k] * v for k, v in vals.items()) / 5, 1)


def priority_band(score: float | None) -> str:
    if score is None:
        return "Unscored"
    return next(name for floor, name in c.PRIORITY_BANDS if score >= floor)


@dataclass
class Gates:
    external_id: str
    score: float | None
    band: str
    info_complete: bool
    missing_fields: list[str]
    funding_pass: bool | None
    funding_note: str
    capacity_pass: bool | None
    capacity_note: str
    hours_available: int | None
    security_pass: bool
    security_note: str
    period_cost_eur: float | None
    failed: list[str] = field(default_factory=list)

    @property
    def all_pass(self) -> bool:
        return not self.failed


def evaluate(ds: Dataset, d: Demand, fin: FinanceResult, cap: CapacityResult,
             one_time: float | None = None, monthly: float | None = None, hours: int | None = None) -> Gates:
    """Evaluate the gates for a demand. The optional arguments evaluate an alternative option."""
    probe = d.with_changes(one_time=d.one_time if one_time is None else one_time,
                           monthly=d.monthly if monthly is None else monthly,
                           hours=d.hours if hours is None else hours)
    cost = demand_period_cost(ds, probe)
    if d.status in c.FUNDED:
        f = fin.by_cc.get(d.cost_center)
        fund_ok = None if f is None else f.forecast_variance_eur <= 0
        fund_note = "Already in the forecast." if f else "Unavailable: no budget is defined for this cost centre."
        cap_ok, cap_note, usable = True, "Hours are already allocated.", None
    else:
        fund_ok, fund_note = funding_gate(fin, d.cost_center, cost)
        cap_ok, cap_note, usable = capacity_gate(cap, probe.team, probe.hours, d.due_at, ds.as_of)
    missing = d.missing_required()
    if d.status == c.NEEDS_INFO:
        missing = missing + ["open clarification request"]      # the requester still owes an answer
    sec_ok = (not d.security_needed) or d.security_status == "passed"
    sec_note = ("No security review required." if not d.security_needed else
                "Security review passed." if sec_ok else "Security review required and not yet passed.")
    failed = []
    if missing:
        failed.append("information")
    if fund_ok is not True:
        failed.append("funding")
    if cap_ok is not True:
        failed.append("capacity")
    if not sec_ok:
        failed.append("security review")
    score = priority_score(d)
    return Gates(d.external_id, score, priority_band(score), not missing, missing, fund_ok, fund_note, cap_ok, cap_note,
                 usable, sec_ok, sec_note, cost, failed)


def recommendation(g: Gates) -> str:
    """Advisory text for the demand board. It is input to a human decision, not a decision."""
    if g.all_pass:
        return "Eligible for an approval decision: all gates pass."
    return "Not approvable as submitted: " + ", ".join(g.failed) + " gate" + ("s" if len(g.failed) > 1 else "") + " not passed. Options: defer, reduce scope, reallocate, or record an explicit exception."


def review_queue(ds: Dataset, fin: FinanceResult, cap: CapacityResult) -> list[dict]:
    """Demands awaiting a decision or still before it, highest score first (ties: earlier due date, then id)."""
    rows = []
    for d in ds.demands:
        if d.status not in c.PRE_DECISION and d.status != c.DEFERRED:
            continue
        g = evaluate(ds, d, fin, cap)
        rows.append(dict(demand=d, gates=g, recommendation=recommendation(g)))
    rows.sort(key=lambda r: (-(r["gates"].score or -1), r["demand"].due_at.isoformat() if r["demand"].due_at else "9999",
                             r["demand"].external_id))
    return rows
