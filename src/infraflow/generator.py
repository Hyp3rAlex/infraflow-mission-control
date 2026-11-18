"""Deterministic synthetic data generator.

Writes the CSV datasets and `ground_truth.json`. The ground truth is built *by construction*:
the generator keeps its own tally of every clean amount it emits and of every anomaly it
injects on purpose. It does not import or call the production calculation modules
(`finance`, `capacity`, `validator`, `kpis`), so tests can compare the two independently.
"""
from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from . import config as c
from .catalog import CATALOG, OPTIONS

DEMAND_FIELDS = [
    "external_id", "jira_key", "request_type", "title", "requested_at", "requester_department", "requester_role",
    "business_owner", "site", "service_category", "business_case", "business_impact_score", "urgency_score",
    "risk_reduction_score", "strategic_alignment_score", "due_at", "demand_status", "triage_owner",
    "delivery_team", "delivery_lead", "estimated_hours", "cost_center", "estimated_one_time_eur",
    "estimated_monthly_recurring_eur", "security_review_needed", "security_review_status", "blocked",
    "blocked_reason", "depends_on", "risk_note", "decision_owner", "decision_date", "decision_outcome",
    "decision_rationale", "next_review_at", "routed_to", "handoff_ref", "handoff_checklist_complete", "handoff_url",
]
EVENT_FIELDS = ["event_id", "external_id", "occurred_at", "actor_role", "previous_status", "new_status", "reason"]
CAPACITY_FIELDS = ["month", "team", "available_hours", "allocated_hours"]
ALLOCATION_FIELDS = ["month", "team", "external_id", "hours"]
BUDGET_FIELDS = ["month", "cost_center", "approved_budget_eur"]
ACTUAL_FIELDS = ["invoice_id", "invoice_date", "month", "cost_center", "external_id", "amount", "currency",
                 "credit_note_ref", "po_id"]
COMMITMENT_FIELDS = ["po_id", "month", "cost_center", "external_id", "approved_commitment_eur",
                     "recognized_actual_eur", "status"]
DECISION_FIELDS = ["decision_id", "external_id", "decided_at", "approver_role", "decision", "rationale",
                   "budget_snapshot_ref", "capacity_snapshot_ref", "followup_owner", "followup_date"]
OPTION_FIELDS = ["external_id", "option_id", "name", "one_time_eur", "monthly_eur", "hours",
                 "security_review_needed", "delivery_risk", "benefit", "assumptions"]

LAST_EVENT_AGE = {  # days between the latest status event and the cutoff
    c.SUBMITTED: (1, 8), c.NEEDS_INFO: (3, 20), c.TRIAGED: (2, 10), c.ASSESSMENT: (3, 18),
    c.READY_FOR_DECISION: (2, 12), c.APPROVED: (2, 9), c.HANDOFF: (2, 8), c.IN_DELIVERY: (5, 30),
    c.DEFERRED: (5, 40), c.REJECTED: (5, 45), c.ROUTED_OUT: (3, 10),
}
STEP_DAYS = {
    c.NEEDS_INFO: (1, 3), c.TRIAGED: (1, 4), c.ASSESSMENT: (1, 5), c.READY_FOR_DECISION: (5, 14),
    c.APPROVED: (3, 9), c.DEFERRED: (3, 9), c.REJECTED: (3, 9), c.HANDOFF: (2, 6),
    c.IN_DELIVERY: (2, 7), c.COMPLETE: (14, 30), c.ROUTED_OUT: (0, 1),
}
REASONS = {
    c.NEEDS_INFO: "Intake check found mandatory information missing; question sent to requester.",
    c.TRIAGED: "Intake complete; classified as infrastructure demand and assigned for assessment.",
    c.ASSESSMENT: "Assessment started: impact, options, cost and effort being estimated.",
    c.READY_FOR_DECISION: "Assessment complete; finance and capacity snapshots attached for the demand board.",
    c.APPROVED: "Approved by the demand board.",
    c.DEFERRED: "Deferred by the demand board with a next review date.",
    c.REJECTED: "Rejected with documented rationale.",
    c.HANDOFF: "Handoff checklist issued to the delivery team.",
    c.IN_DELIVERY: "Delivery lead accepted the handoff; work started.",
    c.COMPLETE: "Delivery accepted by the requester; demand closed.",
    c.ROUTED_OUT: "Not an infrastructure demand; routed to the responsible queue.",
}
# Remaining hours the generator steers specific future team-months towards (drives the two capacity scenarios).
TARGET_REMAINING = {("PLAT", "2026-11"): 60, ("PLAT", "2026-12"): 120,
                    ("NET", "2026-11"): 20, ("NET", "2026-12"): -30, ("NET", "2027-01"): 90, ("NET", "2027-02"): 80}

HERO_TIMELINE = [  # ORION-REQ-017, fully scripted
    ("2026-10-05", c.SUBMITTED, "Engineering Lead Flight Test Data Engineering", "Demand submitted through the intake form."),
    ("2026-10-07", c.NEEDS_INFO, "Demand Analyst Munich",
     "Retention classification of the new data sets and the accountable business owner are missing; question sent to requester."),
    ("2026-10-14", c.TRIAGED, "Demand Analyst Munich",
     "Requester confirmed retention class R3 (10 years) and named the Head of Flight Test Data Engineering as business owner. Intake complete."),
    ("2026-10-16", c.ASSESSMENT, "Demand Analyst Munich", "Assessment started; Solution Architect asked for two options."),
    ("2026-11-03", c.READY_FOR_DECISION, "Solution Architect",
     "Options A and B assessed; finance snapshot FIN-2026-11/CC-ENG-DATA and capacity snapshot CAP-2026-11/PLAT attached."),
    ("2026-11-10", c.DEFERRED, "Infrastructure Demand Board Chair",
     "Deferred to the 8 December board: Option A fails the funding and capacity gates; Option B needs data-owner sign-off."),
]


def ext_id(n: int) -> str:
    return f"ORION-REQ-{n:03d}"


def _d(s: str) -> date:
    return date.fromisoformat(s)


def _weekday(d: date) -> date:
    """Move weekend dates back to the preceding Friday (monotonic, never past the cutoff)."""
    return d - timedelta(days=max(0, d.weekday() - 4))


def _month(d: date) -> str:
    return d.strftime("%Y-%m")


def month_range(first: str, last: str) -> list[str]:
    y, m = map(int, first.split("-"))
    out = []
    while f"{y:04d}-{m:02d}" <= last:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def recurring_months(go_live: str) -> int:
    """Months of recurring charge inside the budget period: those strictly after the go-live month."""
    return sum(1 for m in c.PERIOD_MONTHS if m > go_live)


def _path(d: dict, rng: random.Random) -> list[str]:
    t = d["status"]
    if d["n"] == 46:
        return [c.REJECTED]
    if t == c.SUBMITTED:
        return []
    if t in (c.ROUTED_OUT, c.NEEDS_INFO):
        return [t]
    pre = [c.NEEDS_INFO, c.TRIAGED] if rng.random() < 0.3 else [c.TRIAGED]
    if t == c.TRIAGED:
        return pre
    if t == c.ASSESSMENT:
        return pre + [c.ASSESSMENT]
    if t == c.READY_FOR_DECISION:
        return pre + [c.ASSESSMENT, c.READY_FOR_DECISION]
    if t in (c.DEFERRED, c.REJECTED):
        return pre + [c.ASSESSMENT, c.READY_FOR_DECISION, t]
    full = [c.ASSESSMENT, c.READY_FOR_DECISION, c.APPROVED, c.HANDOFF, c.IN_DELIVERY, c.COMPLETE]
    return pre + full[: full.index(t) + 1]


def _approver(d: dict) -> str:
    if d["n"] == 46:
        return "Demand Manager"
    return "Head of Digital Infrastructure" if d["one_time"] >= 50000 else "Infrastructure Demand Board Chair"


def _timeline(d: dict, rng: random.Random) -> list[tuple[date, str, str, str]]:
    """Return [(date, new_status, actor_role, reason)], first entry is the submission."""
    analyst = f"Demand Analyst {d['site']}"
    lead = f"Delivery Lead {c.TEAMS[d['team']][0]}"
    requester = f"Engineering Lead {d['dept']}"
    if d["n"] == 17:
        return [(_d(day), st, actor, reason) for day, st, actor, reason in HERO_TIMELINE]
    path = _path(d, rng)
    if d["status"] == c.COMPLETE:
        last = min(_d(d["due"]) + timedelta(days=rng.randint(-10, 4)), c.AS_OF - timedelta(days=1))
    else:
        lo, hi = LAST_EVENT_AGE[d["status"]]
        last = c.AS_OF - timedelta(days=rng.randint(lo, hi))
    dates, cur = [], last
    for i in range(len(path) - 1, -1, -1):
        dates.append(cur)
        lo, hi = STEP_DAYS[path[i]]
        if path[i] == c.TRIAGED and i > 0 and path[i - 1] == c.NEEDS_INFO:
            lo, hi = 3, 8
        cur = cur - timedelta(days=max(rng.randint(lo, hi), 0))
    dates.reverse()
    out = [(_weekday(cur), c.SUBMITTED, requester, "Demand submitted through the intake form.")]
    for st, day in zip(path, dates):
        if st in (c.APPROVED, c.DEFERRED, c.REJECTED):
            actor = _approver(d)
        elif st == c.READY_FOR_DECISION:
            actor = "Solution Architect"
        elif st == c.HANDOFF:
            actor = "Demand Manager"
        elif st in (c.IN_DELIVERY, c.COMPLETE):
            actor = lead
        else:
            actor = analyst
        reason = REASONS[st]
        if st == c.NEEDS_INFO and d["ni_reason"]:
            reason = d["ni_reason"]
        if st in (c.DEFERRED, c.REJECTED, c.ROUTED_OUT) and d["rationale"]:
            reason = d["rationale"]
        out.append((_weekday(day), st, actor, reason))
    return out


def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def generate(out_dir: Path = c.DATA_DIR) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    demands, events, decisions = [], [], []
    timelines: dict[int, list] = {}
    status_dates: dict[int, dict[str, date]] = {}

    # ---- demands, status history, decisions --------------------------------
    raw_events = []
    for d in CATALOG:
        rng = random.Random(f"{c.SEED}-{d['n']}")
        tl = _timeline(d, rng)
        timelines[d["n"]] = tl
        status_dates[d["n"]] = {st: day for day, st, _, _ in tl}
        prev = ""
        for i, (day, st, actor, reason) in enumerate(tl):
            raw_events.append((f"{day.isoformat()}T{9 + i:02d}:00:00", d["n"], actor, prev, st, reason))
            prev = st
    # one deliberately invalid history record: assessment logged without triage, register never updated
    raw_events.append(("2026-11-13T15:00:00", 44, "Demand Analyst Madrid", c.SUBMITTED, c.ASSESSMENT,
                       "Status changed in bulk edit (no triage recorded)."))
    raw_events.sort(key=lambda e: (e[0], e[1]))
    for i, (ts, n, actor, prev, st, reason) in enumerate(raw_events, 1):
        events.append(dict(event_id=f"EVT-{i:04d}", external_id=ext_id(n), occurred_at=ts, actor_role=actor,
                           previous_status=prev, new_status=st, reason=reason))

    dec_seq = 0
    for d in CATALOG:
        n, sd = d["n"], status_dates[d["n"]]
        outcome = next((s for s in (c.APPROVED, c.DEFERRED, c.REJECTED) if s in sd), "")
        dec_date = sd[outcome].isoformat() if outcome else ""
        approver = _approver(d) if outcome else ""
        rationale = d["rationale"] if outcome in (c.DEFERRED, c.REJECTED) else (
            "Approved: business case accepted; funding and capacity gates passed at the decision date." if outcome else "")
        if d["status"] == c.ROUTED_OUT:
            rationale = d["rationale"]
        if n == 21:
            approver = ""          # injected anomaly: approval recorded without an approver role
        funded = d["status"] in c.FUNDED
        handed = d["status"] in (c.HANDOFF, c.IN_DELIVERY, c.COMPLETE)
        team_name = c.TEAMS[d["team"]][0]
        if outcome:
            dec_seq += 1
            followup_date = d["next_review"] or (sd[c.APPROVED] + timedelta(days=7)).isoformat() if outcome != c.REJECTED else ""
            decisions.append(dict(
                decision_id=f"DEC-{dec_seq:03d}", external_id=ext_id(n), decided_at=dec_date, approver_role=approver,
                decision=outcome.lower(), rationale=rationale,
                budget_snapshot_ref=f"FIN-{dec_date[:7]}/{d['cc']}" if n != 46 else "",
                capacity_snapshot_ref=f"CAP-{dec_date[:7]}/{d['team']}" if n != 46 else "",
                followup_owner={c.APPROVED: "Demand Manager", c.DEFERRED: f"Demand Analyst {d['site']}",
                                c.REJECTED: ""}[outcome],
                followup_date=followup_date))
        demands.append(dict(
            external_id=ext_id(n), jira_key="", request_type=d["request_type"], title=d["title"],
            requested_at=timelines[n][0][0].isoformat(), requester_department=d["dept"],
            requester_role=f"Engineering Lead {d['dept']}", business_owner=f"Head of {d['dept']}",
            site=d["site"], service_category=d["category"], business_case=d["case"],
            business_impact_score=d["scores"][0], urgency_score=d["scores"][1],
            risk_reduction_score=d["scores"][2], strategic_alignment_score=d["scores"][3],
            due_at=d["due"], demand_status=d["status"],
            triage_owner="" if d["no_owner"] else f"Demand Analyst {d['site']}",
            delivery_team=d["team"], delivery_lead=f"Delivery Lead {team_name}" if handed else "",
            estimated_hours=d["hours"], cost_center=d["cc"], estimated_one_time_eur=d["one_time"],
            estimated_monthly_recurring_eur=d["monthly"],
            security_review_needed="yes" if d["security"] else "no",
            security_review_status=("passed" if funded or d["sec_passed"] else "pending") if d["security"] else "not_required",
            blocked="yes" if d["blocked"] else "no", blocked_reason=d["blocked"] or "",
            depends_on=d["depends_on"], risk_note=d["risk"],
            decision_owner=approver, decision_date=dec_date,
            decision_outcome=outcome.lower() if outcome else ("routed_out" if d["status"] == c.ROUTED_OUT else ""),
            decision_rationale=rationale, next_review_at=d["next_review"], routed_to=d["routed_to"],
            handoff_ref=f"HO-{n:03d}" if handed else "", handoff_checklist_complete="yes" if handed else "no",
            handoff_url=""))

    # ---- finance -------------------------------------------------------------
    inv_rows: list[dict] = []
    gt_actual: dict[str, int] = defaultdict(int)
    po_reg: dict[str, dict] = {}
    po_recognized: dict[str, int] = defaultdict(int)
    seq = [0]

    def invoice(day: str, cc: str, ext: str, amount, po: str = "", counted: bool = True, inv_id: str = "",
                currency: str = "EUR", credit_ref: str = "", month: str = "") -> str:
        if not inv_id:
            seq[0] += 1
            inv_id = f"INV-{seq[0]:04d}"
        inv_rows.append(dict(invoice_id=inv_id, invoice_date=day, month=month or day[:7], cost_center=cc,
                             external_id=ext, amount=amount, currency=currency, credit_note_ref=credit_ref,
                             po_id=po))
        if counted:
            gt_actual[cc] += amount
            if po:
                po_recognized[po] += amount
        return inv_id

    gt_uncommitted: dict[str, int] = defaultdict(int)
    period_cost: dict[int, int] = {}
    run_first_invoice: dict[str, str] = {}
    for cc, (_, _, run) in c.COST_CENTERS.items():
        po = f"PO-RUN-{cc[3:]}"
        po_reg[po] = dict(month=c.PERIOD_MONTHS[0], cc=cc, ext="", approved=run * len(c.PERIOD_MONTHS), status="open")
        for m in c.PERIOD_MONTHS:
            if _d(f"{m}-03") <= c.AS_OF:
                iid = invoice(f"{m}-03", cc, "", run, po)
                run_first_invoice.setdefault(cc, iid)

    for d in CATALOG:
        n, sd = d["n"], status_dates[d["n"]]
        if d["status"] not in c.FUNDED:
            continue
        go_live = _month(sd[c.COMPLETE]) if c.COMPLETE in sd else d["due"][:7]
        rec_months = [m for m in c.PERIOD_MONTHS if m > go_live]
        cost = d["one_time"] + d["monthly"] * len(rec_months)
        period_cost[n] = cost
        if c.HANDOFF not in sd:
            gt_uncommitted[d["cc"]] += cost          # approved, purchase order not raised yet
            continue
        po = f"PO-{n:03d}"
        po_reg[po] = dict(month=max(_month(sd[c.HANDOFF]), c.PERIOD_MONTHS[0]), cc=d["cc"], ext=ext_id(n),
                          approved=cost, status="open")
        if c.COMPLETE in sd:
            invoice(sd[c.COMPLETE].isoformat(), d["cc"], ext_id(n), d["one_time"], po)
            for m in rec_months:
                if d["monthly"] and _d(f"{m}-05") <= c.AS_OF:
                    invoice(f"{m}-05", d["cc"], ext_id(n), d["monthly"], po)
        elif c.IN_DELIVERY in sd:
            day = sd[c.IN_DELIVERY] + timedelta(days=5)
            if day <= c.AS_OF:
                invoice(day.isoformat(), d["cc"], ext_id(n), round(d["one_time"] * 0.5 / 100) * 100, po)

    # ---- injected finance anomalies (each one is listed in the ground truth) ---
    anomalies: dict[str, list[str]] = defaultdict(list)
    excluded: list[dict] = []
    first = dict(inv_rows[len(c.COST_CENTERS) * 4])          # first demand invoice
    inv_rows.append(dict(first))                             # A1 exact duplicate, must be counted once
    anomalies["DUPLICATE_INVOICE"].append(first["invoice_id"])
    excluded.append(dict(invoice_id=first["invoice_id"], reason="DUPLICATE_INVOICE", amount=first["amount"], currency="EUR"))
    invoice("2026-10-12", "CC-UNKNOWN-99", "", 4300, counted=False, inv_id="INV-9002")
    anomalies["UNKNOWN_COST_CENTER"].append("INV-9002")
    invoice("2026-11-04", "CC-ENG-DATA", ext_id(28), 2750, inv_id="INV-9003")           # spend before approval
    anomalies["UNAPPROVED_SPEND"].append("INV-9003")
    invoice("2026-10-20", "CC-DIG-INFRA", ext_id(9), -1200, counted=False, inv_id="INV-9004")
    anomalies["INVALID_AMOUNT"].append("INV-9004")
    excluded.append(dict(invoice_id="INV-9004", reason="INVALID_AMOUNT", amount=-1200, currency="EUR"))
    invoice("2026-11-06", "CC-COLLAB", "", -800, po="PO-RUN-COLLAB", inv_id="INV-9005",
            credit_ref=run_first_invoice["CC-COLLAB"])                                   # valid credit note
    invoice("2026-10-28", "CC-SEC-OPS", ext_id(8), 5000, counted=False, inv_id="INV-9006", currency="USD")
    anomalies["UNSUPPORTED_CURRENCY"].append("INV-9006")
    excluded.append(dict(invoice_id="INV-9006", reason="UNSUPPORTED_CURRENCY", amount=5000, currency="USD"))
    invoice("2026-10-15", "CC-DIG-INFRA", "ORION-REQ-999", 1900, inv_id="INV-9007")
    anomalies["MISSING_REFERENCE"].append("INV-9007")
    invoice("2026-13-45", "CC-ENG-SIM", ext_id(1), 3100, counted=False, inv_id="INV-9008", month="2026-13")
    anomalies["INVALID_DATE"].append("INV-9008")
    excluded.append(dict(invoice_id="INV-9008", reason="INVALID_DATE", amount=3100, currency="EUR"))
    invoice("2026-11-20", "CC-ENG-DATA", ext_id(11), 6400, po="PO-011", counted=False, inv_id="INV-9009")
    po_reg["PO-9010"] = dict(month="2026-10", cc="CC-SEC-OPS", ext=ext_id(5), approved=4000, status="open")
    invoice("2026-10-22", "CC-SEC-OPS", ext_id(5), 4600, po="PO-9010", inv_id="INV-9010")
    anomalies["PO_OVER_RECOGNIZED"].append("PO-9010")
    po_reg["PO-9012"] = dict(month="2026-09", cc="CC-ENG-SIM", ext=ext_id(4), approved=7500, status="cancelled")

    po_rows, gt_outstanding = [], defaultdict(int)
    for po, r in po_reg.items():
        stated = po_recognized[po]
        if po == "PO-015":
            stated -= 1000                           # ledger understates what was invoiced
            anomalies["PO_RECONCILIATION_MISMATCH"].append(po)
        status = r["status"]
        if status == "open" and stated >= r["approved"] and po != "PO-9010":
            status = "closed"
        if status == "open":
            gt_outstanding[r["cc"]] += max(r["approved"] - stated, 0)
        po_rows.append(dict(po_id=po, month=r["month"], cost_center=r["cc"], external_id=r["ext"],
                            approved_commitment_eur=r["approved"], recognized_actual_eur=stated, status=status))

    budget_rows = [dict(month=m, cost_center=cc, approved_budget_eur=b)
                   for cc, (_, b, _) in c.COST_CENTERS.items() for m in c.PERIOD_MONTHS]

    # ---- capacity ----------------------------------------------------------------
    alloc: dict[tuple[str, str], dict[str, int]] = defaultdict(dict)
    for d in CATALOG:
        n, sd = d["n"], status_dates[d["n"]]
        if d["status"] not in c.FUNDED or not d["hours"]:
            continue
        start = _month(sd[c.APPROVED])
        end = _month(sd[c.COMPLETE]) if c.COMPLETE in sd else max(d["due"][:7], _month(c.AS_OF))
        months = month_range(start, max(end, start))
        base, extra = divmod(d["hours"], len(months))
        for i, m in enumerate(months):
            hrs = base + (extra if i == len(months) - 1 else 0)
            if m in c.CAPACITY_MONTHS and hrs:
                alloc[(d["team"], m)][ext_id(n)] = hrs
    cap_rows, alloc_rows, gt_capacity = [], [], {}
    for team, (_, hours, run_share) in c.TEAMS.items():
        for m in c.CAPACITY_MONTHS:
            available = round(hours * c.REDUCED_MONTHS.get(m, 1.0))
            demand_hours = sum(alloc[(team, m)].values())
            if (team, m) in TARGET_REMAINING:
                run = available - demand_hours - TARGET_REMAINING[(team, m)]
            else:
                run = min(round(available * run_share), round(available * 0.97) - demand_hours)
            if run < 0:
                raise ValueError(f"capacity design error for {team} {m}: run hours {run}")
            alloc_rows.append(dict(month=m, team=team, external_id="RUN", hours=run))
            for ext, hrs in sorted(alloc[(team, m)].items()):
                alloc_rows.append(dict(month=m, team=team, external_id=ext, hours=hrs))
            allocated = run + demand_hours
            cap_rows.append(dict(month=m, team=team, available_hours=available, allocated_hours=allocated))
            gt_capacity[f"{team}|{m}"] = dict(available=available, allocated=allocated, remaining=available - allocated)

    # ---- write datasets -------------------------------------------------------------
    _write(out_dir / "demands.csv", DEMAND_FIELDS, demands)
    _write(out_dir / "status_events.csv", EVENT_FIELDS, events)
    _write(out_dir / "decisions.csv", DECISION_FIELDS, decisions)
    _write(out_dir / "budgets.csv", BUDGET_FIELDS, budget_rows)
    _write(out_dir / "actuals.csv", ACTUAL_FIELDS, inv_rows)
    _write(out_dir / "commitments.csv", COMMITMENT_FIELDS, po_rows)
    _write(out_dir / "capacity.csv", CAPACITY_FIELDS, cap_rows)
    _write(out_dir / "allocations.csv", ALLOCATION_FIELDS, alloc_rows)
    _write(out_dir / "options.csv", OPTION_FIELDS, OPTIONS)

    # ---- ground truth (by construction; see module docstring) ------------------------
    to_date = [m for m in c.PERIOD_MONTHS if m <= _month(c.AS_OF)]
    finance = {}
    for cc, (_, budget, _) in c.COST_CENTERS.items():
        eac = gt_actual[cc] + gt_outstanding[cc] + gt_uncommitted[cc]
        finance[cc] = dict(budget_period_eur=budget * len(c.PERIOD_MONTHS), budget_to_date_eur=budget * len(to_date),
                           actual_eur=gt_actual[cc], open_commitments_eur=gt_outstanding[cc],
                           approved_not_committed_eur=gt_uncommitted[cc], forecast_eac_eur=eac,
                           forecast_variance_eur=eac - budget * len(c.PERIOD_MONTHS))
    by_status: dict[str, int] = defaultdict(int)
    for d in CATALOG:
        by_status[d["status"]] += 1
    truth = dict(
        as_of=c.AS_OF.isoformat(), seed=c.SEED,
        note="Built by construction inside generator.py and from hand-listed expectations; never by calling "
             "the reporting code.",
        demand_count=len(CATALOG), status_counts=dict(sorted(by_status.items())),
        open_count=sum(1 for d in CATALOG if d["status"] not in c.TERMINAL),
        # hand-listed from the catalogue: open demands whose due date is before the cutoff
        overdue_open_ids=[ext_id(n) for n in (12, 15, 29, 40)],
        blocked_ids=[ext_id(d["n"]) for d in CATALOG if d["blocked"]],
        missing_owner_ids=[ext_id(d["n"]) for d in CATALOG if d["no_owner"]],
        missing_cost_center_ids=[ext_id(39)],
        missing_approver_ids=[ext_id(21)],
        invalid_transition_ids=[ext_id(44)],
        finance=finance,
        finance_totals={k: sum(v[k] for v in finance.values()) for k in next(iter(finance.values()))},
        unmapped_actual_eur=4300,
        excluded_invoices=excluded,
        # hand-stated, one bucket per currency (duplicates left out); the USD amount has no EUR value
        excluded_invalid_by_currency=dict(EUR=dict(net=1900, gross=4300, invoice_ids=["INV-9004", "INV-9008"]),
                                          USD=dict(net=5000, gross=5000, invoice_ids=["INV-9006"])),
        unmapped_invoice_ids=["INV-9002"],
        unreconciled_po=dict(po_id="PO-015", ledger_recognized_eur=3800, invoiced_eur=4800, difference_eur=1000,
                             forecast_effect_eur=-1000),
        invoice_after_cutoff=dict(invoice_id="INV-9009", amount_eur=6400),
        anomalies={k: v for k, v in sorted(anomalies.items())},
        capacity=gt_capacity,
        overallocated_team_months=["NET|2026-12"],
        hero=dict(external_id=ext_id(17), option_a_period_cost_eur=48000, option_b_period_cost_eur=14500,
                  option_a_12_month_eur=48000 + 12 * 3200, option_b_12_month_eur=14500 + 12 * 600,
                  hours_requested=300, hours_available_in_window=180, funding_pass_option_a=False,
                  capacity_pass_option_a=False, funding_pass_option_b=True, capacity_pass_option_b=True,
                  decision="deferred", next_review_at="2026-12-08"),
        affordable_but_no_capacity=dict(external_id=ext_id(23), funding_pass=True, capacity_pass=False,
                                        hours_requested=280, hours_available_in_window=190),
    )
    (out_dir / "ground_truth.json").write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8")
    return truth
