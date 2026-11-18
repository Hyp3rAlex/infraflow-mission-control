"""Domain records and tolerant CSV loading.

Loading never drops a row: values that cannot be parsed are kept as ``None`` (or as the raw
string for finance rows) so that the validator can report them.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path

from . import config as c

CRITICAL, WARNING, INFO = "CRITICAL", "WARNING", "INFO"


def to_int(value) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def to_amount(value) -> float | None:
    """Parse a money amount; integers stay integers so that EUR totals are exact."""
    try:
        f = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return int(f) if f == int(f) else round(f, 2)


def to_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except (TypeError, ValueError):
        return None


@dataclass
class Demand:
    external_id: str
    request_type: str
    title: str
    requested_at: date | None
    department: str
    site: str
    category: str
    business_case: str
    impact: int | None
    urgency: int | None
    risk_reduction: int | None
    strategic: int | None
    due_at: date | None
    status: str
    triage_owner: str
    team: str
    delivery_lead: str
    hours: int | None
    cost_center: str
    one_time: float | None
    monthly: float | None
    security_needed: bool
    security_status: str
    blocked: bool
    blocked_reason: str
    depends_on: str
    risk_note: str
    decision_owner: str
    decision_date: date | None
    decision_outcome: str
    decision_rationale: str
    next_review_at: date | None
    routed_to: str
    handoff_ref: str
    handoff_complete: bool
    row: dict = field(default_factory=dict, repr=False)

    @property
    def is_open(self) -> bool:
        return self.status not in c.TERMINAL

    def missing_required(self) -> list[str]:
        return [f for f in c.REQUIRED_DEMAND_FIELDS if not str(self.row.get(f, "")).strip()]

    def with_changes(self, **kw) -> "Demand":
        return replace(self, **kw)

    @classmethod
    def from_row(cls, r: dict) -> "Demand":
        g = lambda k: "" if r.get(k) is None else str(r.get(k)).strip()
        return cls(
            external_id=g("external_id"), request_type=g("request_type") or "demand", title=g("title"),
            requested_at=to_date(g("requested_at")), department=g("requester_department"), site=g("site"),
            category=g("service_category"), business_case=g("business_case"),
            impact=to_int(g("business_impact_score")), urgency=to_int(g("urgency_score")),
            risk_reduction=to_int(g("risk_reduction_score")), strategic=to_int(g("strategic_alignment_score")),
            due_at=to_date(g("due_at")), status=g("demand_status"), triage_owner=g("triage_owner"),
            team=g("delivery_team"), delivery_lead=g("delivery_lead"), hours=to_int(g("estimated_hours")),
            cost_center=g("cost_center"), one_time=to_amount(g("estimated_one_time_eur")),
            monthly=to_amount(g("estimated_monthly_recurring_eur")),
            security_needed=g("security_review_needed") == "yes", security_status=g("security_review_status"),
            blocked=g("blocked") == "yes", blocked_reason=g("blocked_reason"), depends_on=g("depends_on"),
            risk_note=g("risk_note"), decision_owner=g("decision_owner"), decision_date=to_date(g("decision_date")),
            decision_outcome=g("decision_outcome"), decision_rationale=g("decision_rationale"),
            next_review_at=to_date(g("next_review_at")), routed_to=g("routed_to"), handoff_ref=g("handoff_ref"),
            handoff_complete=g("handoff_checklist_complete") == "yes", row=dict(r))


@dataclass
class Exc:
    """One entry of the exception register. Every entry carries a risk, an action, an owner and a date."""
    code: str
    severity: str
    record_id: str
    message: str
    source: str = ""
    cost_center: str = ""
    amount_eur: float | None = None      # EUR only; None when the row has no EUR value
    risk: str = ""
    proposed_action: str = ""
    decision_owner: str = ""
    due_date: str = ""
    currency: str = "EUR"                # currency of the source row
    amount_original: float | None = None  # amount in `currency` when it is not EUR (never added to EUR figures)

    @property
    def amount_text(self) -> str:
        """Amount with its own currency; a foreign amount is never shown with a euro sign."""
        if self.amount_eur is not None:
            return f"-€{abs(self.amount_eur):,.0f}" if self.amount_eur < 0 else f"€{self.amount_eur:,.0f}"
        if self.amount_original is not None:
            return f"{self.currency} {self.amount_original:,.0f} (not converted)"
        return ""

    def as_row(self) -> dict:
        return dict(code=self.code, severity=self.severity, record_id=self.record_id, source=self.source,
                    cost_center=self.cost_center, amount_eur="" if self.amount_eur is None else self.amount_eur,
                    currency=self.currency, amount_original="" if self.amount_original is None else self.amount_original,
                    message=self.message, risk=self.risk, proposed_action=self.proposed_action,
                    decision_owner=self.decision_owner, due_date=self.due_date)


@dataclass
class Dataset:
    demands: list[Demand]
    events: list[dict]
    decisions: list[dict]
    budgets: list[dict]
    actuals: list[dict]
    commitments: list[dict]
    capacity: list[dict]
    allocations: list[dict]
    options: list[dict]
    as_of: date
    data_dir: Path | None = None

    def demand(self, external_id: str) -> Demand | None:
        return next((d for d in self.demands if d.external_id == external_id), None)

    def events_for(self, external_id: str) -> list[dict]:
        """Status events up to the cutoff, oldest first."""
        cut = self.as_of.isoformat() + "T23:59:59"
        ev = [e for e in self.events if e["external_id"] == external_id and e["occurred_at"] <= cut]
        return sorted(ev, key=lambda e: (e["occurred_at"], e["event_id"]))


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return [dict(r) for r in csv.DictReader(fh)]


def load_dataset(data_dir: Path = c.DATA_DIR, as_of: date = c.AS_OF) -> Dataset:
    data_dir = Path(data_dir)
    r = lambda name: read_csv(data_dir / name)
    return Dataset(
        demands=[Demand.from_row(x) for x in r("demands.csv")], events=r("status_events.csv"),
        decisions=r("decisions.csv"), budgets=r("budgets.csv"), actuals=r("actuals.csv"),
        commitments=r("commitments.csv"), capacity=r("capacity.csv"), allocations=r("allocations.csv"),
        options=r("options.csv"), as_of=as_of, data_dir=data_dir)
