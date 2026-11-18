"""Demand lifecycle: allowed transitions and the controls attached to them.

Submitted -> Needs Info / Triaged -> Assessment -> Ready for Decision -> Approved / Deferred / Rejected
-> Handoff -> In Delivery -> Complete.  Incidents and routine service requests are routed out at
triage and never enter assessment. "Blocked" is a flag with a reason, not a status.

The controls below are enforced in this offline model. The live Jira Free project cannot enforce
them (no workflow validators), so there they are process rules documented in Confluence.
"""
from __future__ import annotations

from datetime import date

from . import config as c
from .models import Demand
from .scoring import Gates


class LifecycleError(ValueError):
    """A transition was refused. The message says which control failed."""


AUTOMATION_PREFIXES = ("system", "automation", "bot", "script", "ai")


def _is_human_role(role: str) -> bool:
    return bool(role.strip()) and not role.strip().lower().startswith(AUTOMATION_PREFIXES)


def check_transition(d: Demand, new_status: str, actor_role: str, decision: dict | None = None,
                     gates: Gates | None = None, exception_rationale: str = "") -> None:
    """Raise LifecycleError unless `d` may move to `new_status`.

    `decision` is the decision record (approver_role, rationale, followup_date) and is mandatory for
    Approved / Deferred / Rejected. `gates` is the gate evaluation at decision time and is mandatory
    for Approved. Approving against a failed funding or capacity gate requires `exception_rationale`
    so that the override is a visible, attributable choice. A failed security gate cannot be overridden.
    """
    if new_status not in c.ALLOWED_TRANSITIONS.get(d.status, set()):
        raise LifecycleError(f"{d.external_id}: transition {d.status} -> {new_status} is not allowed.")
    if not actor_role.strip():
        raise LifecycleError(f"{d.external_id}: every status change needs an actor role.")
    if new_status == c.TRIAGED and d.missing_required():
        raise LifecycleError(f"{d.external_id}: intake incomplete, missing {', '.join(d.missing_required())}.")
    if new_status == c.ROUTED_OUT and not d.routed_to:
        raise LifecycleError(f"{d.external_id}: routing out requires the receiving queue.")
    if new_status in (c.APPROVED, c.DEFERRED, c.REJECTED):
        if not _is_human_role(actor_role):
            raise LifecycleError(f"{d.external_id}: decisions are taken by a human role, not by '{actor_role}'.")
        if not decision or not (decision.get("approver_role") or "").strip():
            raise LifecycleError(f"{d.external_id}: a decision record with an approver role is required.")
        approver = decision["approver_role"].strip()
        if approver not in c.AUTHORIZED_APPROVERS:
            raise LifecycleError(f"{d.external_id}: '{approver}' is not an authorised approver.")
        if not (decision.get("rationale") or "").strip():
            raise LifecycleError(f"{d.external_id}: a decision needs a recorded rationale.")
        if new_status == c.APPROVED:
            if approver not in c.BOARD_APPROVERS:
                raise LifecycleError(f"{d.external_id}: '{approver}' may reject or route, but not approve spend.")
            if gates is None:
                raise LifecycleError(f"{d.external_id}: approval requires a gate evaluation (funding, capacity, security).")
            if not gates.security_pass:
                raise LifecycleError(f"{d.external_id}: security review is required and has not passed; approval is not possible.")
            if not gates.info_complete:
                raise LifecycleError(f"{d.external_id}: mandatory information missing ({', '.join(gates.missing_fields)}).")
            failed = [g for g in ("funding", "capacity") if g in gates.failed]
            if failed and not exception_rationale.strip():
                raise LifecycleError(f"{d.external_id}: {' and '.join(failed)} gate not passed. Defer, change scope, or record an explicit exception rationale.")
        if new_status == c.DEFERRED and not (decision.get("followup_date") or "").strip():
            raise LifecycleError(f"{d.external_id}: a deferral needs a next review date.")
    if new_status == c.HANDOFF and d.decision_outcome != "approved":
        raise LifecycleError(f"{d.external_id}: handoff requires a recorded approval.")
    if new_status == c.IN_DELIVERY and not (d.handoff_ref and d.handoff_complete and d.delivery_lead):
        raise LifecycleError(f"{d.external_id}: delivery cannot start before the handoff checklist is complete and a delivery lead is named.")
    if new_status == c.COMPLETE:
        if d.blocked:
            raise LifecycleError(f"{d.external_id}: a blocked demand cannot be completed; clear the blocker first.")
        if d.missing_required() or not d.handoff_ref:
            raise LifecycleError(f"{d.external_id}: cannot close with unfilled required fields.")


def apply_transition(d: Demand, new_status: str, actor_role: str, on: date, reason: str, decision: dict | None = None,
                     gates: Gates | None = None, exception_rationale: str = "") -> tuple[Demand, dict]:
    """Return the changed demand and the status event to append. Raises LifecycleError if refused."""
    check_transition(d, new_status, actor_role, decision, gates, exception_rationale)
    changes: dict = dict(status=new_status)
    if new_status in (c.APPROVED, c.DEFERRED, c.REJECTED):
        changes.update(decision_owner=decision["approver_role"], decision_date=on, decision_outcome=new_status.lower(),
                       decision_rationale=decision["rationale"] + (f" Exception: {exception_rationale}" if exception_rationale else ""))
        if new_status == c.DEFERRED:
            changes["next_review_at"] = date.fromisoformat(decision["followup_date"])
    event = dict(external_id=d.external_id, occurred_at=f"{on.isoformat()}T12:00:00", actor_role=actor_role,
                 previous_status=d.status, new_status=new_status, reason=reason)
    return d.with_changes(**changes), event


def history_problems(events: list[dict]) -> list[tuple[str, str]]:
    """Check one demand's ordered status history. Returns (event_id, problem) pairs."""
    problems, current = [], ""
    for e in events:
        prev, new = e.get("previous_status", ""), e.get("new_status", "")
        if not current:
            if prev or new != c.SUBMITTED:
                problems.append((e["event_id"], "history does not start with a submission"))
        elif prev != current:
            problems.append((e["event_id"], f"previous status '{prev}' does not match the recorded status '{current}'"))
        elif new not in c.ALLOWED_TRANSITIONS.get(prev, set()):
            problems.append((e["event_id"], f"transition {prev} -> {new} is not allowed"))
        current = new
    return problems
