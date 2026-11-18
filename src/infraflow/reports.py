"""Markdown reports and the machine-readable facts file.

Reports are derived snapshots. They never feed back into the source data. Every file states its
reporting date, data mode and sources, and shows a PROVISIONAL banner when critical exceptions exist.
Output is deterministic: no wall-clock timestamps are written.
"""
from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path

from . import config as c
from .capacity import assess, what_if
from .finance import option_total_12_month, reconcile, scenario
from .kpis import compute, days_in_status
from .models import CRITICAL, INFO, WARNING, Dataset, to_date
from .scoring import evaluate, priority_band, priority_score, recommendation, review_queue
from .validator import build_register, is_provisional

HERO = "ORION-REQ-017"
MODE = "OFFLINE_FIXTURE (synthetic CSV data; not a live Jira or finance-system extract)"


def eur(x) -> str:
    if x is None:
        return "n/a"
    return f"-€{abs(x):,.0f}" if x < 0 else f"€{x:,.0f}"


def gate(v) -> str:
    return {True: "pass", False: "FAIL", None: "unavailable"}[v]


def table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join("" if v is None else str(v).replace("|", "/").replace("\n", " ") for v in r) + " |" for r in rows]
    return "\n".join(out)


def next_board_date(as_of: date) -> date:
    """The demand board meets every Tuesday."""
    d = as_of + timedelta(days=1)
    while d.weekday() != 1:
        d += timedelta(days=1)
    return d


def build_context(ds: Dataset) -> dict:
    fin, cap = reconcile(ds), assess(ds)
    register = build_register(ds, fin, cap)
    return dict(ds=ds, fin=fin, cap=cap, register=register, kpis=compute(ds, fin, cap),
                queue=review_queue(ds, fin, cap), provisional=is_provisional(register))


def header(ctx: dict, title: str, sources: str) -> str:
    ds = ctx["ds"]
    crit = [e for e in ctx["register"] if e.severity == CRITICAL]
    lines = [f"# {title}", "",
             f"**Organisation:** {c.ORG_NAME} (fictional)  ",
             f"**Reporting date (cutoff, inclusive):** {ds.as_of.isoformat()}  ",
             f"**Data mode:** {MODE}  ",
             f"**Sources:** {sources}  ",
             f"**Currency:** EUR, budget period {c.PERIOD_MONTHS[0]} to {c.PERIOD_MONTHS[-1]}", ""]
    if crit:
        lines += [f"> **PROVISIONAL** - {len(crit)} critical data exceptions are open. Affected rows are excluded from the totals "
                  f"and listed in `financial_exception_register.md`. Figures may change when they are resolved.", ""]
    return "\n".join(lines)


def signed_eur(x) -> str:
    return f"-€{abs(x):,.0f}" if x < 0 else f"€{x:,.0f}"


def money(amount, currency: str) -> str:
    """An amount in its own currency. Only EUR gets the euro sign."""
    if amount is None:
        return "amount unreadable"
    return signed_eur(amount) if currency == c.CURRENCY else f"{currency} {amount:,.0f}"


def exclusion_lines(fin) -> list[str]:
    """What is not in the EUR totals, one statement per currency and kind. Nothing is added across currencies."""
    lines = []
    for cur, b in fin.excluded_by_currency().items():
        items = ", ".join(f"{r['invoice_id']} ({money(r['amount'], cur)})" for r in b["rows"])
        if cur == c.CURRENCY:
            lines.append(f"EUR invoice rows excluded as invalid: {items}; {signed_eur(b['gross'])} gross, {signed_eur(b['net'])} net.")
        else:
            lines.append(f"{cur} invoice rows excluded, not converted (no approved {cur}/EUR rate): {items}. No EUR value is assumed.")
    if fin.unmapped_actual_eur:
        lines.append(f"Unmapped spend (valid EUR invoices on a cost centre without budget): {signed_eur(fin.unmapped_actual_eur)} ({', '.join(fin.unmapped_invoice_ids)}).")
    for p in fin.unreconciled_pos:
        lines.append(f"Unreconciled purchase order {p['po_id']}: ledger shows {signed_eur(p['ledger_recognized_eur'])} recognised, linked invoices total "
                     f"{signed_eur(p['invoiced_eur'])}. The forecast uses the ledger and would change by {signed_eur(p['forecast_effect_eur'])} on invoice basis.")
    return lines


def exclusion_short(fin) -> str:
    """One-line version for tiles and e-mail; currencies stay separate."""
    parts = []
    for cur, b in fin.excluded_by_currency().items():
        n = len(b["rows"])
        parts.append(f"{n} EUR invoice{'s' if n != 1 else ''} excluded ({signed_eur(b['gross'])} gross)" if cur == c.CURRENCY
                     else f"{cur} {b['net']:,.0f} excluded, not converted")
    if fin.unmapped_actual_eur:
        parts.append(f"{signed_eur(fin.unmapped_actual_eur)} unmapped")
    if fin.unreconciled_pos:
        parts.append(f"{signed_eur(sum(abs(p['difference_eur']) for p in fin.unreconciled_pos))} unreconciled on " + ", ".join(p["po_id"] for p in fin.unreconciled_pos))
    return "; ".join(parts)


# ---- decisions and actions ---------------------------------------------------
def decisions_required(ctx: dict) -> list[dict]:
    """Decisions the board has to take, most important first. Built only from computed facts."""
    ds, fin, cap = ctx["ds"], ctx["fin"], ctx["cap"]
    board = next_board_date(ds.as_of).isoformat()
    out = []
    for r in ctx["queue"]:
        d, g = r["demand"], r["gates"]
        if d.status != c.READY_FOR_DECISION:
            continue
        if g.all_pass:
            ask = "Approve or defer; all gates pass."
        else:
            ask = "Cannot be approved as submitted (" + ", ".join(g.failed) + "). Decide: defer with review date, reduce scope, or reallocate."
        out.append(dict(topic=f"{d.external_id} {d.title}", decision=ask, owner="Infrastructure Demand Board Chair", due=board,
                        evidence=f"score {g.score} ({g.band}); funding: {g.funding_note} capacity: {g.capacity_note}", rank=(0, -(g.score or 0))))
    for cc, f in fin.by_cc.items():
        if f.forecast_variance_eur > 0:
            out.append(dict(topic=f"{cc} forecast overrun", decision=f"Forecast exceeds budget by {eur(f.forecast_variance_eur)}. Decide: reallocate budget, defer uncommitted work, or accept the overrun.",
                            owner="Head of Digital Infrastructure", due=board, evidence=f"EAC {eur(f.forecast_eac_eur)} vs budget {eur(f.budget_period_eur)}", rank=(1, -f.forecast_variance_eur)))
    for (team, month), cell in sorted(cap.cells.items()):
        if cell["allocated"] > cell["available"]:
            out.append(dict(topic=f"{c.TEAMS[team][0]} over-allocated in {month}",
                            decision=f"{cell['allocated'] - cell['available']} h more are committed than available. Decide which approved work moves.",
                            owner="Head of Digital Infrastructure", due=board,
                            evidence=f"allocated {cell['allocated']} h, available {cell['available']} h; demands: {', '.join(cell['demand_ids'])}", rank=(2, 0)))
    for e in ctx["register"]:
        if e.code in ("MISSING_APPROVER", "UNAPPROVED_SPEND", "SECURITY_REVIEW_BYPASSED"):
            out.append(dict(topic=f"{e.record_id}: {e.code.replace('_', ' ').lower()}", decision=e.proposed_action, owner=e.decision_owner,
                            due=e.due_date, evidence=e.message, rank=(3, 0)))
    for d in ds.demands:
        if d.status == c.DEFERRED and d.next_review_at and d.next_review_at <= ds.as_of + timedelta(days=30):
            out.append(dict(topic=f"{d.external_id} {d.title} (deferred)", decision="Re-review at the scheduled board; confirm the open follow-up items are closed before then.",
                            owner="Infrastructure Demand Board Chair", due=d.next_review_at.isoformat(), evidence=d.decision_rationale, rank=(4, 0)))
    out.sort(key=lambda x: x["rank"])
    return out


def action_register(ctx: dict) -> list[dict]:
    """Owner / action / date list: decisions follow-ups, operational exceptions and critical data fixes."""
    ds, k = ctx["ds"], ctx["kpis"]
    rows = []
    for d in ds.demands:
        if not d.is_open:
            continue
        if d.blocked:
            rows.append(dict(ref=d.external_id, action=f"Clear blocker: {d.blocked_reason}", owner=d.delivery_lead or d.triage_owner or "Demand Manager",
                             due=(ds.as_of + timedelta(days=7)).isoformat(), kind="blocked"))
        if d.due_at and d.due_at < ds.as_of:
            rows.append(dict(ref=d.external_id, action=f"Overdue since {d.due_at}: agree a new date with the requester or escalate.",
                             owner=d.delivery_lead or d.triage_owner or "Demand Manager", due=(ds.as_of + timedelta(days=3)).isoformat(), kind="overdue"))
        if d.status == c.NEEDS_INFO:
            rows.append(dict(ref=d.external_id, action="Requester to supply the missing intake information; close the demand if no reply by the due date.",
                             owner=d.row.get("requester_role", "Requester"), due=(ds.as_of + timedelta(days=7)).isoformat(), kind="needs info"))
    for r in ds.decisions:
        d = ds.demand(r["external_id"])
        if d and d.status == c.DEFERRED and r["decision"] == "deferred":
            rows.append(dict(ref=r["external_id"], action=f"Prepare re-review ({r['decision_id']}): close the conditions named in the deferral rationale.",
                             owner=r["followup_owner"], due=r["followup_date"], kind="decision follow-up"))
    for e in ctx["register"]:
        if e.severity == CRITICAL or e.code in ("MISSING_OWNER", "UNAPPROVED_SPEND", "CAPACITY_OVERALLOCATED", "FORECAST_OVERRUN"):
            rows.append(dict(ref=e.record_id, action=e.proposed_action, owner=e.decision_owner, due=e.due_date, kind=e.code))
    rows.sort(key=lambda r: (r["due"], r["ref"], r["kind"]))
    return rows


# ---- individual reports -------------------------------------------------------
def pipeline_report(ctx: dict) -> str:
    k = ctx["kpis"]
    body = [header(ctx, "Demand Pipeline Statistics", "demands.csv, status_events.csv"),
            "## Pipeline by status", "",
            table(["Status", "Count"], [[c.STATUS_LABEL[s], n] for s, n in k["by_status"]["value"].items()]), "",
            f"Open demands: **{k['open_demands']['value']}** of {k['total_demands']['value']} registered. "
            f"Intake in the last 7 days: **{k['intake_last_7_days']['value']}** ({', '.join(k['intake_last_7_days']['source_ids'])}).", "",
            "## Open demands by priority band, site and team", "",
            table(["Priority band", "Open"], [[b, n] for b, n in k["open_by_priority"]["value"].items()]), "",
            table(["Site", "Open"], [[s, n] for s, n in k["open_by_site"]["value"].items()]), "",
            table(["Team", "Open"], [[c.TEAMS[t][0], n] for t, n in k["open_by_team"]["value"].items()]), "",
            "## Review queue (undecided and deferred demands, highest score first)", "",
            "The score orders the queue. It does not approve anything; the gates show what would stop an approval today.", "",
            table(["Demand", "Status", "Score", "Band", "Info", "Funding", "Capacity", "Security", "Advice to the board"],
                  [[f"{r['demand'].external_id} {r['demand'].title}", c.STATUS_LABEL[r["demand"].status], r["gates"].score, r["gates"].band,
                    gate(r["gates"].info_complete), gate(r["gates"].funding_pass), gate(r["gates"].capacity_pass), gate(r["gates"].security_pass),
                    r["recommendation"]] for r in ctx["queue"]]), "",
            "## Definitions", ""] + [f"- **{name}**: {v['definition']}" for name, v in k.items()
                                     if name in ("open_demands", "intake_last_7_days", "open_by_priority", "completeness_pct", "approval_pending")]
    return "\n".join(body) + "\n"


def overdue_blocked_report(ctx: dict) -> str:
    ds, k = ctx["ds"], ctx["kpis"]
    def rows(ids):
        out = []
        for i in ids:
            d = ds.demand(i)
            out.append([i, d.title, c.STATUS_LABEL[d.status], d.due_at, (ds.as_of - d.due_at).days if d.due_at and d.due_at < ds.as_of else "",
                        d.triage_owner or "UNASSIGNED", c.TEAMS[d.team][0] if d.team in c.TEAMS else d.team, d.blocked_reason])
        return out
    heads = ["Demand", "Title", "Status", "Due", "Days overdue", "Owner", "Team", "Blocker"]
    stale_rows = [[i, ds.demand(i).title, c.STATUS_LABEL[ds.demand(i).status], days_in_status(ds, i, ds.demand(i).status), ds.demand(i).triage_owner or "UNASSIGNED"]
                  for i in k["stale_open"]["source_ids"]]
    return "\n".join([header(ctx, "Overdue, Blocked and Stale Work", "demands.csv, status_events.csv"),
                      f"## Overdue open demands ({k['overdue_open']['value']})", "", k["overdue_open"]["definition"], "", table(heads, rows(k["overdue_open"]["source_ids"])), "",
                      f"## Blocked open demands ({k['blocked_open']['value']})", "", k["blocked_open"]["definition"], "", table(heads, rows(k["blocked_open"]["source_ids"])), "",
                      f"## Stale open demands ({k['stale_open']['value']})", "", k["stale_open"]["definition"], "",
                      table(["Demand", "Title", "Status", "Days in status", "Owner"], stale_rows), ""]) + "\n"


def ownership_report(ctx: dict) -> str:
    ds, k = ctx["ds"], ctx["kpis"]
    gaps = [[i, ds.demand(i).title, c.STATUS_LABEL[ds.demand(i).status], ds.demand(i).site, ds.demand(i).requested_at]
            for i in k["unassigned_open"]["source_ids"]]
    incomplete = [[i, ds.demand(i).title, c.STATUS_LABEL[ds.demand(i).status], ", ".join(ds.demand(i).missing_required())]
                  for i in k["completeness_pct"]["source_ids"]]
    gov = [[e.record_id, e.code, e.message, e.decision_owner, e.due_date] for e in ctx["register"]
           if e.code in ("MISSING_APPROVER", "MISSING_DECISION_RECORD", "DEFERRED_WITHOUT_REVIEW_DATE", "HANDOFF_INCOMPLETE", "SECURITY_REVIEW_BYPASSED")]
    return "\n".join([header(ctx, "Ownership Gap Report", "demands.csv, decisions.csv"),
                      f"## Open demands without an owner ({k['unassigned_open']['value']}, {k['unassigned_pct']['value']}% of open)", "",
                      table(["Demand", "Title", "Status", "Site", "Requested"], gaps), "",
                      f"## Incomplete intake records (completeness {k['completeness_pct']['value']}%)", "", k["completeness_pct"]["definition"], "",
                      table(["Demand", "Title", "Status", "Missing fields"], incomplete), "",
                      "## Decision accountability gaps", "",
                      table(["Record", "Finding", "Detail", "Owner", "Due"], gov) if gov else "None.", ""]) + "\n"


def throughput_report(ctx: dict) -> str:
    k = ctx["kpis"]
    ageing = k["stage_ageing_median_days"]["value"]
    return "\n".join([header(ctx, "Status and Throughput Metrics", "demands.csv, status_events.csv, decisions.csv"),
                      "## Flow", "",
                      table(["Measure", "Value", "Definition"], [
                          ["Completed demands", k["completed_total"]["value"], k["completed_total"]["definition"]],
                          ["Median lead time (days)", k["median_lead_time_days"]["value"], k["median_lead_time_days"]["definition"]],
                          ["Median triage time (working days)", k["median_triage_business_days"]["value"], k["median_triage_business_days"]["definition"]],
                          ["On-time delivery", f"{k['on_time_delivery_pct']['value']}%", k["on_time_delivery_pct"]["definition"] + " Late: " + (", ".join(k["on_time_delivery_pct"]["source_ids"]) or "none")],
                          ["Routed out", k["routed_out"]["value"], k["routed_out"]["definition"]]]), "",
                      "## Completed per month", "", table(["Month", "Completed"], [[m, n] for m, n in k["throughput_by_month"]["value"].items()]), "",
                      "## Intake per month", "", table(["Month", "Requested"], [[m, n] for m, n in k["intake_by_month"]["value"].items()]), "",
                      "## Decision outcomes", "", table(["Outcome", "Decisions"], [[o, n] for o, n in k["decision_outcomes"]["value"].items()]), "",
                      "## Median days in current status (open demands)", "",
                      table(["Status", "Median days"], [[c.STATUS_LABEL[s], ageing[s]] for s in c.STATUS_ORDER if s in ageing]), "",
                      "History-based measures use `status_events.csv`; nothing is inferred from the current status alone.", ""]) + "\n"


def _cc_rows(fin, keys):
    rows = [[cc, c.COST_CENTERS.get(cc, (cc,))[0]] + [eur(f.as_dict()[k]) for k in keys] for cc, f in fin.by_cc.items()]
    tot = fin.totals()
    return rows + [["**Total**", ""] + [f"**{eur(tot[k])}**" for k in keys]]


def budget_report(ctx: dict) -> str:
    fin, ds = ctx["fin"], ctx["ds"]
    months = [m for m in c.PERIOD_MONTHS if m <= ds.as_of.strftime("%Y-%m")]
    monthly = [[cc] + [f"{eur(fin.monthly_actual.get((cc, m), 0))} / {eur(fin.monthly_budget.get((cc, m), 0))}" for m in months] for cc in fin.by_cc]
    return "\n".join([header(ctx, "Budget versus Actual", "budgets.csv, actuals.csv"),
                      "## Period to date by cost centre", "",
                      table(["Cost centre", "Name", "Budget to date", "Actual", "Variance to date"],
                            _cc_rows(fin, ["budget_to_date_eur", "actual_eur", "variance_to_date_eur"])), "",
                      "Variance to date = actual - budget to date (negative = under budget). The current month's budget is counted in full although the month is not finished.", "",
                      "## Actual / budget per month", "", table(["Cost centre"] + months, monthly), "",
                      f"Allocation coverage: **{ctx['kpis']['finance_allocation_coverage_pct']['value']}%** of valid EUR spend is mapped to a budgeted cost centre.", "",
                      "## Not included in the totals above", "",
                      "Each line is reported in its own currency. Amounts in different currencies are not added together.", ""]
                     + [f"- {x}" for x in exclusion_lines(fin)] + ["",
                      f"Invoices dated after the cutoff and therefore not included: {', '.join(x['invoice_id'] + ' (' + eur(x['amount_eur']) + ')' for x in fin.after_cutoff) or 'none'}.", ""]) + "\n"


def forecast_report(ctx: dict) -> str:
    fin, ds = ctx["fin"], ctx["ds"]
    po_rows = []
    unrec = {p["po_id"] for p in fin.unreconciled_pos}
    for p in ds.commitments:
        if p["po_id"] in fin.po_outstanding:
            po_rows.append([p["po_id"], p["cost_center"], p["external_id"] or "run contract", eur(float(p["approved_commitment_eur"])),
                            eur(float(p["recognized_actual_eur"])), p["status"], eur(fin.po_outstanding[p["po_id"]]),
                            "NOT RECONCILED" if p["po_id"] in unrec else "ok"])
    tot = fin.totals()
    if fin.unreconciled_pos:
        reliability = ["## Forecast reliability", "",
                       table(["PO", "Cost centre", "Approved", "Recognised (ledger)", "Linked valid invoices", "Difference", "Outstanding, ledger basis (used)", "Outstanding, invoice basis"],
                             [[p["po_id"], p["cost_center"], eur(p["approved_eur"]), eur(p["ledger_recognized_eur"]), eur(p["invoiced_eur"]), signed_eur(p["difference_eur"]),
                               eur(p["outstanding_ledger_basis_eur"]), eur(p["outstanding_invoice_basis_eur"])] for p in fin.unreconciled_pos]), "",
                       f"The forecast above uses the ledger: **{eur(tot['forecast_eac_eur'])}**. Valued from the invoices it would be "
                       f"**{eur(tot['forecast_eac_eur'] + fin.forecast_uncertainty_eur)}** ({signed_eur(fin.forecast_uncertainty_eur)}). "
                       "Until Finance reconciles the order, the forecast of the affected cost centre is not reliable to that amount; the difference is a critical exception and is not netted away.", ""]
    else:
        reliability = ["## Forecast reliability", "", "All purchase orders reconcile with their linked invoices.", ""]
    unc = [[i, cc, eur(evaluate(ds, ds.demand(i), fin, ctx["cap"]).period_cost_eur)] for cc, f in fin.by_cc.items() for i in f.uncommitted_demand_ids]
    return "\n".join([header(ctx, "Commitments and Forecast", "budgets.csv, actuals.csv, commitments.csv, demands.csv"),
                      "## Forecast at completion by cost centre", "",
                      table(["Cost centre", "Name", "Budget", "Actual", "Open commitments", "Approved, not committed", "Forecast EAC", "Forecast variance"],
                            _cc_rows(fin, ["budget_period_eur", "actual_eur", "open_commitments_eur", "approved_not_committed_eur", "forecast_eac_eur", "forecast_variance_eur"])), "",
                      "## Method", "",
                      "- **Actual**: valid, unique invoices and credit notes dated on or before the cutoff.",
                      "- **Open commitment**: for purchase orders with status `open`, `max(approved - recognised, 0)`. The invoiced part of an order is in Actual and is not counted again.",
                      "- **Approved, not committed**: period cost of approved demands that have no purchase order yet (one-time cost plus recurring cost for the months after planned go-live).",
                      "- **Forecast EAC** = Actual + Open commitments + Approved, not committed. **Forecast variance** = EAC - budget (positive = overrun).",
                      "- This is a commitment-based scenario forecast. It assumes open orders are invoiced in full inside the period and that nothing further is approved. It is not a statistical prediction.", "",
                      *reliability,
                      "## Purchase orders", "", table(["PO", "Cost centre", "Demand", "Approved", "Recognised", "Status", "Outstanding", "Reconciliation"], po_rows), "",
                      "## Approved demands without a purchase order", "", table(["Demand", "Cost centre", "Period cost"], unc) if unc else "None.", ""]) + "\n"


def exception_report(ctx: dict) -> str:
    reg = ctx["register"]
    def rows(sev):
        return [[e.code, e.record_id, e.cost_center, e.amount_text, e.message, e.risk, e.proposed_action, e.decision_owner, e.due_date]
                for e in reg if e.severity == sev]
    heads = ["Code", "Record", "Cost centre", "Amount", "Finding", "Risk", "Proposed action", "Owner", "Due"]
    counts = {s: sum(1 for e in reg if e.severity == s) for s in (CRITICAL, WARNING, INFO)}
    return "\n".join([header(ctx, "Financial and Data Exception Register", "all datasets"),
                      f"**{counts[CRITICAL]} critical, {counts[WARNING]} warnings, {counts[INFO]} informational.** "
                      "Critical rows are excluded from totals or make a figure unreliable; they make the management report provisional. No row is dropped silently. "
                      "The Amount column shows each amount in its own currency; non-EUR amounts are not converted.", "",
                      "## Critical", "", table(heads, rows(CRITICAL)) if counts[CRITICAL] else "None.", "",
                      "## Warnings", "", table(heads, rows(WARNING)) if counts[WARNING] else "None.", "",
                      "## Informational", "", table(heads, rows(INFO)) if counts[INFO] else "None.", ""]) + "\n"


def capacity_report(ctx: dict) -> str:
    ds, cap, fin = ctx["ds"], ctx["cap"], ctx["fin"]
    months = [m for m in cap.months() if m >= ds.as_of.strftime("%Y-%m")]
    rows = []
    for team in c.TEAMS:
        for m in months:
            cell = cap.cells[(team, m)]
            rows.append([c.TEAMS[team][0], m, cell["available"], cell["allocated"], cell["remaining"], f"{100 * cell['allocated'] / cell['available']:.0f}%",
                         ", ".join(cell["demand_ids"])])
    pending = [r["demand"].external_id for r in ctx["queue"] if r["demand"].status == c.READY_FOR_DECISION]
    sim = what_if(ds, cap, pending)
    sim_rows = [[r["external_id"], c.TEAMS[r["team"]][0], r["hours"], f"{r['window'][0]}..{r['window'][-1]}", r["unallocated_today"],
                 r["taken_by_earlier_approvals"], r["usable_for_this_demand"], "fits" if r["fits"] else f"shortfall {r['shortfall']} h", r["remaining_after"]] for r in sim["results"] if r.get("fits") is not None]
    risk_rows = [[r["demand"].external_id, r["demand"].title, r["gates"].band, gate(r["gates"].funding_pass), r["gates"].capacity_note]
                 for r in ctx["queue"] if r["gates"].capacity_pass is False]
    return "\n".join([header(ctx, "Capacity Risk Summary", "capacity.csv, allocations.csv, demands.csv"),
                      "Capacity figures are synthetic planning data in engineer-hours per team and month.", "",
                      "## Forward capacity (cutoff month onwards)", "",
                      table(["Team", "Month", "Available h", "Allocated h", "Remaining h", "Utilisation", "Approved demands in the month"], rows), "",
                      "## Demands that cannot be staffed before their required date", "",
                      "Each demand is checked on its own against the hours that are unallocated **today** in its delivery window (cutoff month to due month). "
                      "An over-allocated month counts as zero. No other pending request is assumed to be approved.", "",
                      table(["Demand", "Title", "Band", "Funding gate", "Capacity gate"], risk_rows) if risk_rows else "None.", "",
                      "## What-if: approving every demand that is Ready for Decision, in score order", "",
                      "A simulation, not a plan: nothing is approved or written back. Each demand that fits takes the earliest unallocated hours of its team "
                      "inside its delivery window; a demand that does not fit takes nothing. Later demands see what is left.", "",
                      table(["Demand", "Team", "Hours needed", "Window", "Unallocated today", "Taken by earlier approvals in this simulation", "Usable for this demand", "Result", "Left in window afterwards"], sim_rows), "",
                      "*Unallocated today* is the figure used by the capacity gate above. *Usable for this demand* = unallocated today minus what earlier demands in this "
                      "simulation took from the same window. Extra capacity can be tested with `python -m infraflow what-if <ids> --add-hours TEAM:YYYY-MM:HOURS`.", "",
                      "The model ignores individual skills and task ordering. It supports a board discussion; it is not a schedule.", ""]) + "\n"


def decision_register_report(ctx: dict) -> str:
    ds = ctx["ds"]
    dec = [[r["decision_id"], r["external_id"], ds.demand(r["external_id"]).title, r["decided_at"], r["decision"], r["approver_role"] or "**MISSING**",
            r["rationale"], r["budget_snapshot_ref"], r["capacity_snapshot_ref"], r["followup_owner"], r["followup_date"]]
           for r in sorted(ds.decisions, key=lambda r: r["decided_at"], reverse=True)]
    req = [[i + 1, x["topic"], x["decision"], x["owner"], x["due"]] for i, x in enumerate(decisions_required(ctx))]
    act = [[a["ref"], a["kind"], a["action"], a["owner"], a["due"]] for a in action_register(ctx)]
    return "\n".join([header(ctx, "Decision and Action Register", "decisions.csv, demands.csv, exception register"),
                      "## Decisions required", "", table(["#", "Topic", "Decision needed", "Decision owner", "Due"], req), "",
                      "## Action register", "", table(["Reference", "Type", "Action", "Owner", "Due"], act), "",
                      "## Decisions taken", "",
                      table(["Decision", "Demand", "Title", "Date", "Outcome", "Approver role", "Rationale", "Budget snapshot", "Capacity snapshot", "Follow-up owner", "Follow-up date"], dec), ""]) + "\n"


def hero_facts(ctx: dict) -> dict:
    ds, fin, cap = ctx["ds"], ctx["fin"], ctx["cap"]
    d = ds.demand(HERO)
    options = []
    for o in [o for o in ds.options if o["external_id"] == HERO]:
        one, mon, hrs = int(o["one_time_eur"]), int(o["monthly_eur"]), int(o["hours"])
        g = evaluate(ds, d, fin, cap, one_time=one, monthly=mon, hours=hrs)
        options.append(dict(option_id=o["option_id"], name=o["name"], one_time_eur=one, monthly_eur=mon, hours=hrs,
                            period_cost_eur=g.period_cost_eur, total_12_month_eur=option_total_12_month(one, mon),
                            funding_pass=g.funding_pass, funding_note=g.funding_note, capacity_pass=g.capacity_pass,
                            capacity_note=g.capacity_note, hours_available=g.hours_available, security_pass=g.security_pass,
                            delivery_risk=o["delivery_risk"], benefit=o["benefit"], assumptions=o["assumptions"],
                            scenario_eac_eur=scenario(fin, {d.cost_center: g.period_cost_eur})[d.cost_center]["forecast_eac_eur"]))
    dec = [r for r in ds.decisions if r["external_id"] == HERO]
    score = priority_score(d)
    return dict(external_id=HERO, title=d.title, status=d.status, score=score, band=priority_band(score), cost_center=d.cost_center,
                team=d.team, due_at=d.due_at.isoformat(), options=options, decision=dec[-1] if dec else None,
                timeline=[dict(date=e["occurred_at"][:10], status=e["new_status"], actor=e["actor_role"], reason=e["reason"]) for e in ds.events_for(HERO)],
                cc_forecast_eac_eur=fin.by_cc[d.cost_center].forecast_eac_eur, cc_budget_eur=fin.by_cc[d.cost_center].budget_period_eur,
                cc_headroom_eur=fin.by_cc[d.cost_center].headroom_eur, next_review_at=d.next_review_at.isoformat() if d.next_review_at else None)


def decision_brief(ctx: dict) -> str:
    ds = ctx["ds"]
    h, d = hero_facts(ctx), ctx["ds"].demand(HERO)
    opt = h["options"]
    comp = [["One-time cost"] + [eur(o["one_time_eur"]) for o in opt], ["Recurring cost per month"] + [eur(o["monthly_eur"]) for o in opt],
            ["Cost inside the budget period"] + [eur(o["period_cost_eur"]) for o in opt],
            ["12-month total (setup + 12 x monthly, undiscounted)"] + [eur(o["total_12_month_eur"]) for o in opt],
            ["Delivery effort"] + [f"{o['hours']} h" for o in opt],
            [f"Forecast of {h['cost_center']} if approved"] + [f"{eur(o['scenario_eac_eur'])} vs budget {eur(h['cc_budget_eur'])}" for o in opt],
            ["Funding gate"] + [gate(o["funding_pass"]) for o in opt], ["Capacity gate"] + [f"{gate(o['capacity_pass'])} - {o['capacity_note']}" for o in opt],
            ["Security review"] + [gate(o["security_pass"]) for o in opt],
            ["Benefit"] + [o["benefit"] for o in opt], ["Delivery risk"] + [o["delivery_risk"] for o in opt], ["Assumptions"] + [o["assumptions"] for o in opt]]
    dec = h["decision"]
    tl = [[t["date"], c.STATUS_LABEL[t["status"]], t["actor"], t["reason"]] for t in h["timeline"]]
    release = what_if(ds, ctx["cap"], [HERO], extra_hours={(d.team, "2026-12"): 120})["results"][0]
    return "\n".join([header(ctx, f"Decision Brief - {HERO} {h['title']}", "demands.csv, options.csv, status_events.csv, decisions.csv, finance and capacity results"),
                      "## Request", "", d.business_case, "",
                      table(["Field", "Value"], [["Requester", d.row["requester_role"]], ["Business owner", d.row["business_owner"]], ["Site", d.site],
                                                 ["Required by", h["due_at"]], ["Cost centre", h["cost_center"]], ["Delivery team", c.TEAMS[h["team"]][0]],
                                                 ["Priority score", f"{h['score']} ({h['band']})"], ["Current status", c.STATUS_LABEL[h["status"]]]]), "",
                      "## History", "", table(["Date", "Status", "Actor (role)", "Note"], tl), "",
                      "## Options", "", table(["Criterion"] + [f"Option {o['option_id']}: {o['name']}" for o in opt], comp), "",
                      "Option descriptions are illustrative assumptions for a fictional environment, not statements about real infrastructure.", "",
                      "## Finance and capacity position at the decision", "",
                      f"- {h['cost_center']} forecast at completion: {eur(h['cc_forecast_eac_eur'])} against a period budget of {eur(h['cc_budget_eur'])}; headroom {eur(h['cc_headroom_eur'])}.",
                      f"- {opt[0]['funding_note']}", f"- {opt[0]['capacity_note']}", f"- Option B: {opt[1]['funding_note']} {opt[1]['capacity_note']}",
                      f"- What-if: if 120 h of Platform and Storage run work were released in December, Option A would {'fit' if release['fits'] else 'still not fit'} the capacity gate "
                      f"({release['usable_before']} h unallocated against {release['hours']} h); the funding gate would still fail.", "",
                      "## Decision", "",
                      table(["Field", "Value"], [["Decision record", dec["decision_id"]], ["Date", dec["decided_at"]], ["Outcome", dec["decision"].upper()],
                                                 ["Decided by (role)", dec["approver_role"]], ["Rationale", dec["rationale"]],
                                                 ["Budget snapshot", dec["budget_snapshot_ref"]], ["Capacity snapshot", dec["capacity_snapshot_ref"]],
                                                 ["Follow-up owner", dec["followup_owner"]], ["Next review", dec["followup_date"]]]), "",
                      "A score of " + f"{h['score']} ({h['band']})" + " did not lead to approval: the score sets the order of review, the gates and a human decision determine the outcome.", "",
                      "## Handoff checklist (to be completed if an option is approved on re-review)", "",
                      table(["Item", "Content"], [["Stable references", f"{HERO}, decision record of the approving board, Jira issue key"],
                                                  ["Delivery owner", f"Delivery Lead {c.TEAMS[h['team']][0]}"], ["Approved option and scope", "Option letter, capacity to be delivered, sites in scope"],
                                                  ["Cost envelope", "Approved one-time and monthly amounts, cost centre, purchase order number"],
                                                  ["Target window", "Start month, required-by date, maintenance windows"],
                                                  ["Prerequisites", "Retention classes confirmed by data owners; security review passed; rack space or archive capacity confirmed"],
                                                  ["Acceptance conditions", "Capacity available to users, encryption verified, backup job extended, monitoring thresholds updated"],
                                                  ["Risks carried into delivery", "Hardware lead time (A) or slower retrieval of archived data (B)"],
                                                  ["Sign-off", "Demand Manager (handoff complete), Delivery Lead (accepted), Business owner (acceptance at completion)"]]), ""]) + "\n"


def weekly_report(ctx: dict) -> str:
    ds, fin, cap, k = ctx["ds"], ctx["fin"], ctx["cap"], ctx["kpis"]
    tot, h = fin.totals(), hero_facts(ctx)
    over_cc = [(cc, f) for cc, f in fin.by_cc.items() if f.forecast_variance_eur > 0]
    crit = [e for e in ctx["register"] if e.severity == CRITICAL]
    req = decisions_required(ctx)
    top = ctx["queue"][0]
    overalloc = [f"{c.TEAMS[t][0]} in {m} (+{cell['allocated'] - cell['available']} h)" for (t, m), cell in sorted(cap.cells.items()) if cell["allocated"] > cell["available"]]
    summary = [
        f"- **Demand:** {k['open_demands']['value']} open demands ({k['total_demands']['value']} registered); {k['approval_pending']['value']} await a board decision, "
        f"{k['overdue_open']['value']} are overdue, {k['blocked_open']['value']} blocked and {k['unassigned_open']['value']} have no owner.",
        f"- **Money:** forecast at completion {eur(tot['forecast_eac_eur'])} against a period budget of {eur(tot['budget_period_eur'])} "
        f"({eur(-tot['forecast_variance_eur'])} headroom overall)." + (" Overrun forecast in " + ", ".join(f"{cc} ({eur(f.forecast_variance_eur)})" for cc, f in over_cc) + "." if over_cc else " No cost centre is forecast to overrun."),
        f"- **Capacity:** " + ("over-allocation in " + "; ".join(overalloc) + ". " if overalloc else "no team is over-allocated. ") +
        f"The highest-scored undecided demand, {top['demand'].external_id} (score {top['gates'].score}), " +
        ("passes all gates." if top["gates"].all_pass else f"cannot be approved as submitted: {', '.join(top['gates'].failed)} gate not passed."),
        f"- **{HERO}:** {c.STATUS_LABEL[h['status']].lower()} on {h['decision']['decided_at']} by the {h['decision']['approver_role']}; next review {h['next_review_at']}. "
        f"Option A would take {h['cost_center']} to {eur(h['options'][0]['scenario_eac_eur'])} against {eur(h['cc_budget_eur'])} and needs {h['options'][0]['hours']} h where {h['options'][0]['hours_available']} h are free.",
        f"- **Data quality:** {len(crit)} critical exceptions: {exclusion_short(fin)}. "
        + ("This report is provisional." if crit else "No critical exceptions."),
    ]
    actions = action_register(ctx)
    lines = [header(ctx, "Weekly IT Infrastructure Portfolio Report", "demands.csv, status_events.csv, decisions.csv, budgets.csv, actuals.csv, commitments.csv, capacity.csv, allocations.csv"),
             "## Executive summary", ""] + summary + ["",
             "## Decisions required", "",
             table(["#", "Topic", "Decision needed", "Owner", "Due"], [[i + 1, x["topic"], x["decision"], x["owner"], x["due"]] for i, x in enumerate(req[:3])]), "",
             f"{len(req)} decisions are open in total; see `decision_action_register.md`.", "",
             "## Operational health", "",
             table(["Measure", "Value", "Records"], [
                 ["Open demands", k["open_demands"]["value"], "see demand register"],
                 ["New in the last 7 days", k["intake_last_7_days"]["value"], ", ".join(k["intake_last_7_days"]["source_ids"])],
                 ["Awaiting decision", k["approval_pending"]["value"], ", ".join(k["approval_pending"]["source_ids"])],
                 ["Overdue", k["overdue_open"]["value"], ", ".join(k["overdue_open"]["source_ids"])],
                 ["Blocked", k["blocked_open"]["value"], ", ".join(k["blocked_open"]["source_ids"])],
                 ["Stale (no status change for 14+ days)", k["stale_open"]["value"], ", ".join(k["stale_open"]["source_ids"])],
                 ["Without owner", f"{k['unassigned_open']['value']} ({k['unassigned_pct']['value']}%)", ", ".join(k["unassigned_open"]["source_ids"])],
                 ["Intake completeness", f"{k['completeness_pct']['value']}%", "incomplete: " + ", ".join(k["completeness_pct"]["source_ids"])],
                 ["Completed to date", k["completed_total"]["value"], f"median lead time {k['median_lead_time_days']['value']} days; on time {k['on_time_delivery_pct']['value']}%"],
                 ["Median triage time", f"{k['median_triage_business_days']['value']} working days", f"{len(k['median_triage_business_days']['source_ids'])} triaged demands"]]), "",
             "## Financial status", "",
             table(["Cost centre", "Name", "Budget", "Actual", "Open commitments", "Approved, not committed", "Forecast EAC", "Forecast variance"],
                   _cc_rows(fin, ["budget_period_eur", "actual_eur", "open_commitments_eur", "approved_not_committed_eur", "forecast_eac_eur", "forecast_variance_eur"])), "",
             "Positive forecast variance = overrun. Method and purchase-order detail: `commitments_forecast.md`.", "",
             "## Capacity", "",
             table(["Team"] + [m for m in cap.months() if m >= ds.as_of.strftime("%Y-%m")],
                   [[c.TEAMS[t][0]] + [(f"{cap.cells[(t, m)]['remaining']} h free" if cap.cells[(t, m)]['remaining'] >= 0 else f"{-cap.cells[(t, m)]['remaining']} h OVER") +
                                       f" ({100 * cap.cells[(t, m)]['allocated'] / cap.cells[(t, m)]['available']:.0f}% allocated)"
                                       for m in cap.months() if m >= ds.as_of.strftime("%Y-%m")] for t in c.TEAMS]), "",
             f"{k['high_priority_not_approvable']['value']} High or Highest demands cannot be approved today because a gate fails; see `capacity_risk_summary.md` and `demand_pipeline.md`.", "",
             "## Data quality caveats", ""] + [f"- **{e.code}** {e.record_id}: {e.message}" for e in crit] + ["",
             "Amounts outside the EUR totals are itemised per currency in `budget_vs_actual.md`; currencies are never added together.", "",
             "Known: everything computed from valid rows. Unknown: the correct value of the excluded rows. Assumed: open purchase orders are invoiced in full inside the period.", "",
             "## Owner / action / date (next 7 days)", "",
             table(["Reference", "Action", "Owner", "Due"], [[a["ref"], a["action"], a["owner"], a["due"]] for a in actions if a["due"] and a["due"] <= (ds.as_of + timedelta(days=7)).isoformat()]), "",
             "## Methodology and cutoff", "",
             f"- Cutoff {ds.as_of.isoformat()} inclusive; later records are ignored and listed where relevant.",
             "- Sources of truth: demand register and status history (lifecycle), finance ledgers (money), capacity table (hours), decision log (decisions). This report is a derived snapshot.",
             "- KPI definitions are listed in `report_facts.json` together with the record ids behind each value.",
             "- All data is synthetic.", ""]
    return "\n".join(lines) + "\n"


def management_email(ctx: dict) -> str:
    k, fin, req = ctx["kpis"], ctx["fin"], decisions_required(ctx)
    tot = fin.totals()
    over = [(cc, f) for cc, f in fin.by_cc.items() if f.forecast_variance_eur > 0]
    issues = [f"{k['overdue_open']['value']} demands are overdue and {k['blocked_open']['value']} are blocked.",
              (f"{over[0][0]} is forecast {eur(over[0][1].forecast_variance_eur)} over budget." if over else "No cost centre is forecast over budget."),
              f"Figures are provisional: {exclusion_short(fin)}."]
    body = [f"**Subject:** Infrastructure demand portfolio - status as of {ctx['ds'].as_of.isoformat()}", "",
            "Dear all,", "",
            f"{k['open_demands']['value']} demands are open; {k['approval_pending']['value']} are ready for a board decision. "
            f"Forecast spend is {eur(tot['forecast_eac_eur'])} against a budget of {eur(tot['budget_period_eur'])}.", "",
            "Issues:"] + [f"{i + 1}. {x}" for i, x in enumerate(issues)] + ["", "Decisions needed:"] + \
           [f"{i + 1}. {x['topic']} - owner: {x['owner']}, due {x['due']}." for i, x in enumerate(req[:3])] + \
           ["", "The full report, exception register and workbook are on the Weekly Portfolio Review page.", "", "Kind regards,", "Infrastructure Demand Management (synthetic demonstration data)"]
    return "\n".join(body) + "\n"


def executive_report(ctx: dict) -> str:
    """One-page management report for business stakeholders (M2)."""
    ds, fin, cap, k = ctx["ds"], ctx["fin"], ctx["cap"], ctx["kpis"]
    tot, h, req = fin.totals(), hero_facts(ctx), decisions_required(ctx)
    health = "AMBER" if (k["overdue_open"]["value"] or ctx["provisional"] or any(f.forecast_variance_eur > 0 for f in fin.by_cc.values())) else "GREEN"
    fwd = [m for m in cap.months() if m >= ds.as_of.strftime("%Y-%m")][:2]
    cap_rows = [[c.TEAMS[t][0]] + [f"{cap.cells[(t, m)]['remaining']} h" for m in fwd] for t in c.TEAMS]
    return "\n".join([header(ctx, "Executive Management Report - Infrastructure Demand Portfolio", "weekly report data set"),
                      f"## Portfolio health: {health}", "",
                      f"{k['open_demands']['value']} open demands across four sites. {k['completed_total']['value']} delivered so far (median lead time {k['median_lead_time_days']['value']} days, "
                      f"{k['on_time_delivery_pct']['value']}% on time). Spend is forecast at {eur(tot['forecast_eac_eur'])}, {eur(-tot['forecast_variance_eur'])} below the period budget, "
                      "but headroom is uneven between cost centres and two delivery teams have almost no free hours before year end.", "",
                      "## Key figures", "",
                      table(["Area", "Figure"], [
                          ["Current demand", f"{k['open_demands']['value']} open, {k['intake_last_7_days']['value']} new this week, {k['approval_pending']['value']} awaiting decision"],
                          ["Attention needed", f"{k['overdue_open']['value']} overdue, {k['blocked_open']['value']} blocked, {k['unassigned_open']['value']} without owner"],
                          ["Budget (period)", eur(tot["budget_period_eur"])], ["Actual to date", eur(tot["actual_eur"])],
                          ["Open commitments", eur(tot["open_commitments_eur"])], ["Approved, not yet committed", eur(tot["approved_not_committed_eur"])],
                          ["Forecast at completion", f"{eur(tot['forecast_eac_eur'])} ({eur(tot['forecast_variance_eur'])} vs budget)"]]), "",
                      "## Forecast risks", "",
                      table(["Cost centre", "Budget", "Forecast EAC", "Variance", "Comment"],
                            [[cc, eur(f.budget_period_eur), eur(f.forecast_eac_eur), eur(f.forecast_variance_eur),
                              "Overrun forecast" if f.forecast_variance_eur > 0 else f"Headroom {eur(f.headroom_eur)}"] for cc, f in fin.by_cc.items()]), "",
                      "## Capacity constraints (unallocated engineer-hours)", "", table(["Team"] + fwd, cap_rows), "",
                      f"{k['high_priority_not_approvable']['value']} demands rated High or Highest cannot be approved today because the funding, capacity, information or security gate fails.", "",
                      "## Decisions required", "",
                      table(["#", "Topic", "Decision needed", "Owner", "Due"], [[i + 1, x["topic"], x["decision"], x["owner"], x["due"]] for i, x in enumerate(req[:5])]), "",
                      "## Example of the trade-off: " + HERO, "",
                      f"{h['title']} scores {h['score']} ({h['band']}). The board deferred it on {h['decision']['decided_at']}: Option A costs {eur(h['options'][0]['period_cost_eur'])} in the period against "
                      f"{eur(h['cc_headroom_eur'])} headroom and needs {h['options'][0]['hours']} h against {h['options'][0]['hours_available']} h free; Option B ({eur(h['options'][1]['period_cost_eur'])}, "
                      f"{h['options'][1]['hours']} h) fits but covers only part of the need and awaits data-owner sign-off. Next review {h['next_review_at']}.", "",
                      "## Recommended next actions", "",
                      "1. Decide the demands that are Ready for Decision at the next board, using the gate results rather than the score alone.",
                      "2. Resolve the cost-centre overrun and the December over-allocation before approving further work for the affected teams.",
                      "3. Close the critical data exceptions so that the next report is no longer provisional.",
                      f"4. Prepare the {h['next_review_at']} re-review of {HERO}: retention-class sign-off for Option B, or budget and capacity for Option A.", "",
                      "Figures are synthetic and come from the same data set as the weekly report, workbook and slide deck.", ""]) + "\n"


def facts(ctx: dict) -> dict:
    """Everything the workbook, deck, Confluence pages and tests need, in one JSON-serialisable dict."""
    fin, cap = ctx["fin"], ctx["cap"]
    return dict(
        as_of=ctx["ds"].as_of.isoformat(), data_mode=MODE, provisional=ctx["provisional"], organisation=c.ORG_NAME,
        kpis=ctx["kpis"], finance=dict(by_cost_centre={cc: f.as_dict() for cc, f in fin.by_cc.items()}, totals=fin.totals(),
                                       unmapped_actual_eur=fin.unmapped_actual_eur, unmapped_invoice_ids=fin.unmapped_invoice_ids,
                                       excluded=fin.excluded,
                                       excluded_by_currency={cur: dict(net=b["net"], gross=b["gross"], invoice_ids=b["invoice_ids"]) for cur, b in fin.excluded_by_currency().items()},
                                       unreconciled_pos=fin.unreconciled_pos, forecast_uncertainty_eur=fin.forecast_uncertainty_eur,
                                       after_cutoff=fin.after_cutoff),
        capacity={f"{t}|{m}": dict(available=v["available"], allocated=v["allocated"], remaining=v["remaining"], demand_ids=v["demand_ids"]) for (t, m), v in sorted(cap.cells.items())},
        exceptions=[e.as_row() for e in ctx["register"]],
        exception_counts={s: sum(1 for e in ctx["register"] if e.severity == s) for s in (CRITICAL, WARNING, INFO)},
        review_queue=[dict(external_id=r["demand"].external_id, status=r["demand"].status, score=r["gates"].score, band=r["gates"].band,
                           funding_pass=r["gates"].funding_pass, capacity_pass=r["gates"].capacity_pass, security_pass=r["gates"].security_pass,
                           info_complete=r["gates"].info_complete, failed=r["gates"].failed, recommendation=r["recommendation"]) for r in ctx["queue"]],
        decisions_required=[{k: v for k, v in x.items() if k != "rank"} for x in decisions_required(ctx)],
        actions=action_register(ctx), hero=hero_facts(ctx))


REPORTS = {
    "weekly_portfolio_report.md": weekly_report, "demand_pipeline.md": pipeline_report, "overdue_blocked_work.md": overdue_blocked_report,
    "ownership_gaps.md": ownership_report, "status_throughput.md": throughput_report, "budget_vs_actual.md": budget_report,
    "commitments_forecast.md": forecast_report, "financial_exception_register.md": exception_report,
    "capacity_risk_summary.md": capacity_report, "decision_action_register.md": decision_register_report,
    f"decision_brief_{HERO}.md": decision_brief, "management_email.md": management_email, "executive_management_report.md": executive_report,
}


def write_all(ds: Dataset, out_dir: Path = c.REPORTS_DIR) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ctx = build_context(ds)
    for name, fn in REPORTS.items():
        (out_dir / name).write_text(fn(ctx), encoding="utf-8")
    f = facts(ctx)
    (out_dir / "report_facts.json").write_text(json.dumps(f, indent=2, default=str) + "\n", encoding="utf-8")
    with (out_dir / "exception_register.csv").open("w", newline="", encoding="utf-8") as fh:
        rows = [e.as_row() for e in ctx["register"]]
        w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["code"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return dict(ctx=ctx, facts=f, files=sorted(list(REPORTS) + ["report_facts.json", "exception_register.csv"]))
