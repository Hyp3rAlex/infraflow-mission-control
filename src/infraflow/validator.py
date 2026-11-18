"""Exception register: data-quality, finance, capacity and governance findings in one list.

Every entry is enriched with a risk statement, a proposed action, an owner role and a due date.
Any CRITICAL entry makes the management report provisional.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta

from . import config as c
from .capacity import CapacityResult, assess
from .finance import FinanceResult, reconcile
from .lifecycle import history_problems
from .models import CRITICAL, INFO, WARNING, Dataset, Exc, to_date

# code -> (risk, proposed action, owner role, working days to resolve)
PLAYBOOK = {
    "DUPLICATE_INVOICE": ("Spend would be overstated if both rows were counted.", "Confirm with accounts payable which row is valid and remove the duplicate from the ledger export.", "Finance Controller", 5),
    "INVALID_DATE": ("Amount cannot be assigned to a period; actuals may be understated.", "Correct the invoice date in the source ledger and re-run the report.", "Finance Controller", 3),
    "UNSUPPORTED_CURRENCY": ("Amount is excluded; actuals may be understated.", "Provide the EUR value booked in the ledger or an approved conversion rate.", "Finance Controller", 3),
    "INVALID_AMOUNT": ("Row is excluded; totals may be wrong in either direction.", "Check the source document; re-enter as a credit note with reference if it is a credit.", "Finance Controller", 3),
    "INVALID_CREDIT_NOTE": ("Credit cannot be matched to an invoice.", "Add the correct invoice reference.", "Finance Controller", 3),
    "OUT_OF_PERIOD": ("Spend outside the budget period distorts the comparison.", "Confirm the posting period.", "Finance Controller", 3),
    "PERIOD_MISMATCH": ("Monthly view may differ from the ledger.", "Align the posting month with the invoice date or document the accrual.", "Finance Controller", 5),
    "UNKNOWN_COST_CENTER": ("Spend is not allocated to any budget; cost-centre totals are incomplete.", "Assign the invoice to a valid cost centre.", "Finance Controller", 3),
    "MISSING_REFERENCE": ("Spend cannot be traced to a demand.", "Link the invoice to the correct demand or mark it as run cost.", "Demand Manager", 5),
    "UNAPPROVED_SPEND": ("Money was spent before a funding decision; the approval control was bypassed.", "Clarify who ordered the work; bring the demand to the next board or reverse the booking.", "Head of Digital Infrastructure", 3),
    "UNKNOWN_PO": ("Invoice cannot be matched to a commitment.", "Correct the purchase order reference.", "Finance Controller", 5),
    "INVALID_COMMITMENT": ("Commitment is excluded; forecast may be understated.", "Correct the purchase order record.", "Finance Controller", 3),
    "PO_RECONCILIATION_MISMATCH": ("Open commitment and forecast are wrong by the difference.", "Reconcile the purchase order ledger with the invoices and correct the recognised amount.", "Finance Controller", 3),
    "PO_OVER_RECOGNIZED": ("More was invoiced than was approved on the purchase order.", "Check for scope change; raise a purchase order amendment for approval if justified.", "Head of Digital Infrastructure", 5),
    "FORECAST_INPUT_MISSING": ("Approved cost is missing from the forecast.", "Complete the cost estimate.", "Demand Manager", 3),
    "FORECAST_OVERRUN": ("Cost centre is forecast to exceed its approved budget.", "Decide: defer uncommitted work, reallocate budget from a cost centre with headroom, or request a budget increase.", "Head of Digital Infrastructure", 5),
    "INVALID_BUDGET_ROW": ("Budget baseline is incomplete.", "Correct the budget table.", "Finance Controller", 3),
    "DUPLICATE_BUDGET_ROW": ("Budget baseline is ambiguous.", "Remove the duplicate budget row.", "Finance Controller", 3),
    "INVALID_CAPACITY_ROW": ("Capacity picture is incomplete.", "Correct the capacity table.", "Demand Manager", 3),
    "INVALID_ALLOCATION_ROW": ("Capacity picture is incomplete.", "Correct the allocation line.", "Demand Manager", 3),
    "CAPACITY_LEDGER_MISMATCH": ("Remaining capacity is unreliable; hours may be double counted.", "Reconcile capacity.csv with the allocation lines.", "Demand Manager", 3),
    "CAPACITY_OVERALLOCATED": ("Committed delivery dates are at risk; the team is promised more hours than it has.", "Re-plan with the delivery lead: move a start date, release run work, or defer one approved demand.", "Head of Digital Infrastructure", 5),
    "ALLOCATION_WITHOUT_APPROVAL": ("Team time is reserved for work that has no approval.", "Remove the allocation or bring the demand to a decision.", "Demand Manager", 5),
    "DEMAND_OVER_ALLOCATED": ("Hours may be double counted.", "Check the allocation against the estimate.", "Demand Manager", 5),
    "DUPLICATE_DEMAND_ID": ("Two records share one identifier; reporting is ambiguous.", "Merge or renumber the records.", "Demand Manager", 3),
    "INVALID_DEMAND_RECORD": ("Record cannot be reported reliably.", "Correct the status or date fields.", "Demand Manager", 3),
    "MISSING_OWNER": ("Nobody is accountable for moving the demand forward.", "Assign a demand analyst.", "Demand Manager", 2),
    "MISSING_COST_CENTER": ("Cost cannot be checked against a budget; the funding gate is unavailable.", "Ask the requester for the funding cost centre.", "Demand Manager", 5),
    "INCOMPLETE_INTAKE": ("Assessment proceeds on incomplete information.", "Return to the requester for the missing fields.", "Demand Manager", 5),
    "MISSING_APPROVER": ("An approval exists without an accountable approver; the decision is not auditable.", "Confirm who approved and complete the decision record; until then treat the approval as unconfirmed.", "Head of Digital Infrastructure", 3),
    "MISSING_DECISION_RECORD": ("Status implies a decision that is not on record.", "Record the decision or correct the status.", "Demand Manager", 3),
    "DEFERRED_WITHOUT_REVIEW_DATE": ("Deferred work may never be reviewed again.", "Set a next review date.", "Demand Manager", 5),
    "SECURITY_REVIEW_BYPASSED": ("Security-sensitive change was approved without a passed security review.", "Stop delivery until the Information Security Office has reviewed the change.", "Information Security Officer", 2),
    "HANDOFF_INCOMPLETE": ("Delivery started without a complete handoff.", "Complete the handoff checklist.", "Demand Manager", 5),
    "INVALID_TRANSITION": ("Status history skips a control step.", "Correct the history entry or repeat the skipped step.", "Demand Manager", 5),
    "STATUS_MISMATCH": ("Register and status history disagree; counts by status may be wrong.", "Confirm the true status with the owner and correct the wrong source.", "Demand Manager", 3),
    "ORPHAN_EVENT": ("History entry refers to an unknown demand.", "Correct the reference.", "Demand Manager", 5),
    "STALE_DATA": ("Report may not reflect the current situation.", "Refresh the source exports before distributing the report.", "Reporting Owner", 1),
    "AFTER_CUTOFF": ("None for this report; the amount appears in the next period.", "No action; shown for transparency.", "Reporting Owner", 0),
}
SEVERITY_RANK = {CRITICAL: 0, WARNING: 1, INFO: 2}


def add_working_days(start: date, days: int) -> date:
    d = start
    while days > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            days -= 1
    return d


def demand_exceptions(ds: Dataset, known_cost_centers: set[str]) -> list[Exc]:
    exc: list[Exc] = []
    src = "demands.csv"
    for ext, n in Counter(d.external_id for d in ds.demands).items():
        if n > 1 or not ext:
            exc.append(Exc("DUPLICATE_DEMAND_ID", CRITICAL, ext or "(blank)", f"External id is blank or used by {n} records.", source=src))
    decisions = defaultdict(list)
    for r in ds.decisions:
        decisions[r.get("external_id", "")].append(r)
    for d in ds.demands:
        if d.status not in c.STATUS_ORDER:
            exc.append(Exc("INVALID_DEMAND_RECORD", CRITICAL, d.external_id, f"Unknown status '{d.status}'.", source=src))
            continue
        if d.requested_at is None or d.due_at is None:
            exc.append(Exc("INVALID_DEMAND_RECORD", CRITICAL, d.external_id, "Requested or due date is missing or not a valid date.", source=src))
        if d.status == c.ROUTED_OUT:
            continue
        if d.is_open and not d.triage_owner:
            exc.append(Exc("MISSING_OWNER", WARNING, d.external_id, f"Open demand in status {c.STATUS_LABEL[d.status]} has no assigned owner.", source=src))
        if not d.cost_center or d.cost_center not in known_cost_centers:
            sev = CRITICAL if d.status in c.FUNDED else WARNING
            exc.append(Exc("MISSING_COST_CENTER", sev, d.external_id, f"Cost centre '{d.cost_center}' is missing or has no budget.", source=src, cost_center=d.cost_center))
        other = [f for f in d.missing_required() if f not in ("triage_owner", "cost_center")]
        if other and d.status not in (c.SUBMITTED, c.NEEDS_INFO):
            exc.append(Exc("INCOMPLETE_INTAKE", WARNING, d.external_id, f"Passed intake with missing fields: {', '.join(other)}.", source=src))
        decided = d.status in c.FUNDED or d.status in (c.DEFERRED, c.REJECTED)
        if decided:
            recs = [r for r in decisions.get(d.external_id, []) if (to_date(r.get("decided_at")) or date.max) <= ds.as_of]
            if not recs:
                exc.append(Exc("MISSING_DECISION_RECORD", CRITICAL, d.external_id, f"Status {c.STATUS_LABEL[d.status]} without a decision record.", source="decisions.csv"))
            else:
                last = recs[-1]
                approver = (last.get("approver_role") or "").strip()
                if not approver or approver not in c.AUTHORIZED_APPROVERS or (
                        d.status in c.FUNDED and approver not in c.BOARD_APPROVERS):
                    exc.append(Exc("MISSING_APPROVER", CRITICAL, d.external_id,
                                   f"Decision {last.get('decision_id')} ({last.get('decision')}) has no authorised approver role (found: '{approver or 'blank'}').",
                                   source="decisions.csv", cost_center=d.cost_center, amount_eur=d.one_time))
        if d.status == c.DEFERRED and d.next_review_at is None:
            exc.append(Exc("DEFERRED_WITHOUT_REVIEW_DATE", WARNING, d.external_id, "Deferred without a next review date.", source=src))
        if d.status in c.FUNDED and d.security_needed and d.security_status != "passed":
            exc.append(Exc("SECURITY_REVIEW_BYPASSED", CRITICAL, d.external_id, "Approved although the required security review has not passed.", source=src))
        if d.status in (c.IN_DELIVERY, c.COMPLETE) and not (d.handoff_ref and d.handoff_complete):
            exc.append(Exc("HANDOFF_INCOMPLETE", WARNING, d.external_id, "In delivery or complete without a completed handoff checklist.", source=src))
    return exc


def history_exceptions(ds: Dataset) -> list[Exc]:
    exc: list[Exc] = []
    known = {d.external_id: d for d in ds.demands}
    for ext in sorted({e["external_id"] for e in ds.events}):
        events = ds.events_for(ext)
        if ext not in known:
            exc.append(Exc("ORPHAN_EVENT", WARNING, ext, f"{len(events)} status events refer to an unknown demand.", source="status_events.csv"))
            continue
        for event_id, problem in history_problems(events):
            exc.append(Exc("INVALID_TRANSITION", WARNING, ext, f"{event_id}: {problem}.", source="status_events.csv"))
        if events and events[-1]["new_status"] != known[ext].status:
            exc.append(Exc("STATUS_MISMATCH", WARNING, ext,
                           f"Register says {known[ext].status}, latest history entry {events[-1]['event_id']} says {events[-1]['new_status']}.",
                           source="status_events.csv"))
    latest = max((to_date(e["occurred_at"]) for e in ds.events if to_date(e["occurred_at"]) and to_date(e["occurred_at"]) <= ds.as_of), default=None)
    if latest is None or (ds.as_of - latest).days > 7:
        exc.append(Exc("STALE_DATA", WARNING, "status_events.csv",
                       f"Latest status event is from {latest}; more than 7 days before the reporting date {ds.as_of}.", source="status_events.csv"))
    return exc


def build_register(ds: Dataset, fin: FinanceResult | None = None, cap: CapacityResult | None = None) -> list[Exc]:
    fin = fin or reconcile(ds)
    cap = cap or assess(ds)
    exc = demand_exceptions(ds, set(fin.by_cc)) + history_exceptions(ds) + list(fin.exceptions) + list(cap.exceptions)
    for e in exc:
        risk, action, owner, days = PLAYBOOK.get(e.code, ("Unclassified finding.", "Review.", "Demand Manager", 5))
        e.risk, e.proposed_action, e.decision_owner = risk, action, owner
        e.due_date = "" if e.severity == INFO else add_working_days(ds.as_of, days).isoformat()
    exc.sort(key=lambda e: (SEVERITY_RANK[e.severity], e.code, e.record_id))
    return exc


def is_provisional(register: list[Exc]) -> bool:
    return any(e.severity == CRITICAL for e in register)
