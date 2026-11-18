"""Confluence knowledge-base pages (space IFMC) as HTML fragments in the dialect accepted by the
Atlassian connector. Figures come from the same context as the reports; procedures are written here.

`write_pages()` stores every page under docs/confluence_pages/ so that the space can be rebuilt
(or pasted manually) without this conversation. Publishing is done through the connector.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from . import config as c
from .jira_sync import BASE, FILTERS, OPEN, load_mapping
from .reports import HERO, action_register, build_context, decisions_required, eur, exclusion_short, hero_facts
from .validator import PLAYBOOK

SITE = "https://your-site.atlassian.net"
OUT_DIR = c.ROOT / "docs" / "confluence_pages"
SYNTHETIC = ('<div data-type="panel-info"><p>All content in this space is <strong>synthetic</strong>. Orion Systems Engineering is a fictional '
             'organisation used for a portfolio demonstrator. No real company data is stored here.</p></div>')


def e(text) -> str:
    return html.escape("" if text is None else str(text), quote=False)


def table(headers: list[str], rows: list[list], raw: bool = False) -> str:
    cell = (lambda v: str(v)) if raw else e
    head = "".join(f"<th>{e(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell(v)}</td>" for v in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def ul(items: list[str], ordered: bool = False) -> str:
    tag = 'ol start="1"' if ordered else "ul"
    return f"<{tag}>" + "".join(f"<li>{i}</li>" for i in items) + f"</{tag.split()[0]}>"


def lozenge(text: str, color: str) -> str:
    return f'<span data-type="status" data-color="{color}">{e(text)}</span>'


def jira(jql: str) -> str:
    params = {"macroParams": {"jqlQuery": {"value": jql}, "showSummary": {"value": "true"}},
              "macroMetadata": {"schemaVersion": {"value": "1"}, "title": "Jira"}}
    return ('<div data-type="extension" data-extension-key="jira" data-extension-type="com.atlassian.confluence.macro.core" '
            f'data-parameters="{html.escape(json.dumps(params), quote=True)}"></div>')


def issue(ext: str, mapping: dict) -> str:
    key = mapping.get(ext, {}).get("key")
    return f'{e(ext)} (<a href="{SITE}/browse/{key}">{key}</a>)' if key else e(ext)


def start_here(ctx, mapping) -> str:
    flow = [["Submitted / Needs Info / Triaged", "Idea", "Demand analyst of the site", "Mandatory intake fields complete; classified as demand, incident or service request"],
            ["Assessment", "To Do", "Demand analyst with solution architect", "Impact, options, cost, effort and security need documented"],
            ["Ready for Decision / Deferred", "In Review", "Infrastructure Demand Board", "Recorded decision: approved, deferred with review date, or rejected"],
            ["Approved / Handoff / In Delivery", "In Progress", "Demand manager, then delivery lead", "Handoff checklist complete; delivery accepted by the requester"],
            ["Complete / Rejected / Routed Out", "Done", "Demand analyst", "Record closed with outcome label"]]
    raci = [["Business case and answers to questions", "Requester", "Business owner", "Demand analyst", "-"],
            ["Intake completeness and classification", "Demand analyst", "Demand manager", "Requester", "Delivery lead"],
            ["Technical options", "Solution architect", "Demand manager", "Delivery lead, Information Security Office", "Requester"],
            ["Funding check", "Demand analyst", "Finance controller", "Cost-centre owner", "Board"],
            ["Capacity check", "Demand analyst", "Delivery lead", "Team members", "Board"],
            ["Approval, deferral, rejection", "Board chair", "Head of Digital Infrastructure (above 50,000 EUR one-time)", "Finance controller, delivery lead", "Requester"],
            ["Handoff to delivery", "Demand manager", "Demand manager", "Delivery lead", "Requester"],
            ["Implementation", "Delivery team", "Delivery lead", "Requester", "Demand analyst"],
            ["Weekly report and data freshness", "Reporting owner", "Demand manager", "Finance controller", "Management"]]
    truth = [["Lifecycle, owner, dates, priority", "Jira project KAN", "Demand analyst"], ["Budget, invoices, purchase orders", "Finance ledgers (CSV extract)", "Finance controller"],
             ["Team hours", "Capacity table", "Delivery leads"], ["Procedures and decisions narrative", "This Confluence space", "Demand manager"],
             ["Reports, workbook, slides", "Generated snapshots; never edited by hand", "Reporting owner"]]
    cadence = [["Daily", "Triage of new requests; reminders for open questions", "Demand analysts"], ["Monday", "Refresh data, run validation, publish Weekly Portfolio Review", "Reporting owner"],
               ["Tuesday", "Infrastructure Demand Board: decisions on demands that are Ready for Decision", "Board chair"],
               ["Month end + 3 working days", "Finance reconciliation and forecast update", "Finance controller"]]
    return "".join([SYNTHETIC, "<h2>Purpose</h2>",
                    "<p>Infrastructure Demand Management is the single entry point for requests to build or change IT infrastructure at the Munich, Toulouse, Madrid and Bremen sites. "
                    "It makes sure that every request is understood, costed, checked against budget and team capacity, decided by an accountable person and handed to delivery with clear conditions.</p>",
                    "<h2>How a demand flows</h2>",
                    table(["Lifecycle stage (label stage-*)", "Jira board column", "Who acts", "Exit criterion"], flow),
                    "<p>The Jira project offers five statuses. The exact stage is carried by a <code>stage-*</code> label so that filters stay precise. Blocked is a label with a reason in the issue, not a status.</p>",
                    "<h2>Responsibilities (RACI)</h2>", table(["Activity", "Responsible", "Accountable", "Consulted", "Informed"], raci),
                    "<h2>Sources of truth</h2>", table(["Information", "System of record", "Maintained by"], truth),
                    "<p>Demand identifiers (<code>ORION-REQ-NNN</code>) are stable across all systems: Jira summary and label, finance ledgers, capacity allocations, decision register and reports.</p>",
                    "<h2>Cadence</h2>", table(["When", "What", "Owner"], cadence),
                    "<h2>Open demands (live from Jira)</h2>", jira(FILTERS["open"][1])])


def intake(ctx, mapping) -> str:
    fields = [["Business need", "What is not possible today and what changes for the users"], ["Required-by date and reason", "Date and the event that drives it"],
              ["Requester, business owner, site", "Role names; the business owner accepts the result"], ["Cost centre", "Where the cost is funded"],
              ["Impact, urgency, risk reduction, strategic fit", "Analyst rating 0-5 with one sentence each"], ["Cost estimate", "One-time and monthly recurring, in EUR"],
              ["Effort estimate and delivery team", "Engineer-hours"], ["Security consideration", "Data classification; does the change touch access, network zones or external parties?"],
              ["Dependencies", "Other demands or contracts that must complete first"], ["Acceptance criteria", "How the requester will confirm the result"]]
    kinds = [["Infrastructure demand", "New or changed infrastructure that needs assessment, funding or capacity", "Enters this pipeline", issue("ORION-REQ-017", mapping)],
             ["Incident", "An existing service is broken or degraded", "Routed to incident management on the same day; no budget or priority decision here", issue("ORION-REQ-048", mapping)],
             ["Service request", "A standard catalogue item with a fixed price and procedure", "Routed to the service catalogue", "ORION-REQ-043"]]
    labels = [["orion-demand", "Every record of this portfolio (reports and filters use it)"], ["orion-req-NNN", "Stable identifier"], ["stage-*", "Exact lifecycle stage"],
              ["site-*, team-*, cat-*, cc-*", "Site, delivery team, service category, cost centre"], ["needs-finance-review", "Funding gate not passed, or recurring cost of 2,500 EUR per month or more"],
              ["needs-security-review", "Security review required and not yet passed"], ["blocked", "Cannot proceed; reason in the issue"], ["owner-missing", "No demand analyst assigned"]]
    return "".join([SYNTHETIC, "<h2>Scope</h2><p>This procedure covers the path from a new request to a triaged demand. It applies to all four sites.</p>",
                    "<h2>Step 1 - Classify</h2>", table(["Type", "Definition", "Routing", "Example"], kinds, raw=True),
                    "<p>Demands, incidents and service requests are different processes. An incident is never held back for a prioritisation decision, and a demand is never fast-tracked by calling it an incident.</p>",
                    "<h2>Step 2 - Check the minimum entry criteria</h2>", table(["Field in the request template", "What is expected"], fields),
                    "<p>The same structure is used as the description template of every Jira issue in project KAN.</p>",
                    "<h2>Step 3 - Triage</h2>",
                    ul(["Create the Jira issue with summary <code>ORION-REQ-NNN | title</code>, due date, priority and labels.",
                        "Assign the demand analyst of the requesting site. An issue without assignee appears in the ownership-gap filter.",
                        "If a mandatory field is missing, set <code>stage-needs-info</code>, write the question as a comment and remind the requester after 3 and 7 working days. Close the request after 10 working days without an answer.",
                        "When the information is complete, set <code>stage-triaged</code>. Triage should not take longer than 3 working days."], ordered=True),
                    "<h2>Label conventions</h2>", table(["Label", "Meaning"], labels),
                    "<h2>Waiting for the requester (live from Jira)</h2>", jira(FILTERS["needs_info"][1]),
                    "<h2>Without owner (live from Jira)</h2>", jira(FILTERS["unassigned"][1])])


def assessment(ctx, mapping) -> str:
    h = hero_facts(ctx)
    top = ctx["queue"][0]
    weights = [["Business impact", "0-5", "35%"], ["Urgency", "0-5", "25%"], ["Risk reduction", "0-5", "25%"], ["Strategic alignment", "0-5", "15%"]]
    gates = [["Information", "All mandatory fields are filled and no question to the requester is open", "Return to requester"],
             ["Funding", "Cost-centre forecast + cost of the demand inside the budget period does not exceed the period budget", "Defer, reduce scope, or reallocate budget"],
             ["Capacity", "Effort fits into the unallocated hours of the delivery team between today and the required-by date", "Defer, re-plan, or release other work"],
             ["Security review", "If the demand is security-sensitive, the Information Security Office has passed the review", "No approval possible; this gate cannot be overridden"]]
    authority = [["Reject at triage or route out", "Demand manager"], ["Approve, defer or reject up to 50,000 EUR one-time cost", "Infrastructure Demand Board Chair"],
                 ["Approve above 50,000 EUR one-time cost", "Head of Digital Infrastructure"], ["Approve against a failed funding or capacity gate", "Same approver, with a written exception rationale in the decision record"]]
    return "".join([SYNTHETIC, "<h2>Priority score</h2>",
                    "<p><code>score = 100 x (0.35 x impact + 0.25 x urgency + 0.25 x risk reduction + 0.15 x strategic alignment) / 5</code></p>",
                    table(["Criterion", "Scale", "Weight"], weights),
                    "<p>Bands: 80 and above Highest, 65 High, 45 Medium, 25 Low, below 25 Lowest. The band is stored as the Jira priority.</p>",
                    '<div data-type="panel-note"><p>The score decides the <strong>order of review</strong>. It never approves a demand. Approval is a recorded decision by an authorised person after the gates have been checked.</p></div>',
                    "<h2>Decision gates</h2>", table(["Gate", "Passes when", "If it fails"], gates),
                    "<p>The gates look at one demand at a time. Before a board meeting the analyst runs the what-if comparison for the whole agenda, because hours and budget can only be used once.</p>",
                    "<h2>Decision authority</h2>", table(["Decision", "Authorised role"], authority),
                    "<p>Every decision record contains: approver role, date, outcome, rationale, the finance and capacity snapshot it was based on, a follow-up owner and a follow-up date. A deferral always has a next review date.</p>",
                    "<h2>Options</h2><p>For demands above 20,000 EUR or 150 hours the solution architect documents at least two options with one-time cost, monthly cost, 12-month total, effort, benefit, delivery risk and assumptions.</p>",
                    "<h2>Two examples from the current portfolio</h2>",
                    ul([f"{issue(top['demand'].external_id, mapping)} has the highest score in the queue ({top['gates'].score}) and is affordable, but: {e(top['gates'].capacity_note)} It cannot be approved as submitted.",
                        f"{issue(HERO, mapping)} scores {h['score']}. Option A fails funding and capacity; Option B fits but covers only part of the need. The board deferred it to {h['next_review_at']}. See the decision brief under the Decision Register."]),
                    "<h2>Agenda of the next board (live from Jira)</h2>", jira(FILTERS["decision"][1])])


def finance_method(ctx, mapping) -> str:
    rules = [["Duplicate invoice id", "Counted once", "Warning"], ["Invalid invoice date", "Excluded", "Critical"], ["Currency other than EUR", "Excluded and reported in its own currency until Finance approves a conversion rate; never added to a EUR figure", "Critical"],
             ["Zero, non-numeric or negative amount without credit-note reference", "Excluded", "Critical"], ["Credit note referring to an unknown invoice", "Excluded", "Critical"],
             ["Cost centre without budget", "Reported as unmapped spend, not in any cost-centre total", "Critical"], ["Invoice dated after the cutoff", "Not included; listed for transparency", "Information"],
             ["Invoice for a demand that is not approved", "Counted (the money is spent) and escalated", "Warning"], ["Invoice referring to an unknown demand", "Counted in the cost centre, flagged", "Warning"],
             ["Purchase order: recognised amount differs from linked invoices", "Ledger value used; the order is marked not reconciled and the difference is shown as forecast uncertainty", "Critical"],
             ["Purchase order: recognised exceeds approved", "Outstanding set to zero; flagged", "Warning"], ["Forecast above budget", "Reported with amount", "Warning"]]
    steps = ["Export budgets, invoices and purchase orders as of the cutoff date.", "Run <code>python -m infraflow validate</code>. Every rejected row appears in the exception register with a reason, an owner and a due date.",
             "Reconcile each open purchase order: recognised amount = sum of its valid invoices.", "Compute actuals, open commitments and the forecast per cost centre.",
             "If a critical exception is open, publish the report as <strong>provisional</strong> with the banner and the excluded amounts.", "Finance controller resolves the exceptions in the source ledger; nothing is corrected in the report."]
    return "".join([SYNTHETIC, "<h2>Purpose</h2><p>How budget, actual spend, commitments and forecast are consolidated every week and at month end, and how invalid data is treated.</p>",
                    "<h2>Procedure</h2>", ul(steps, ordered=True),
                    "<h2>No double counting</h2><p>When an invoice arrives for a purchase order, the amount moves from commitment to actual. Only the part that is not yet invoiced remains a commitment: "
                    "<code>outstanding = max(approved commitment - recognised actual, 0)</code>, for open purchase orders only. Closed and cancelled orders carry no commitment.</p>",
                    "<h2>Validation rules</h2>", table(["Finding", "Treatment", "Severity"], rules),
                    "<p>No row is dropped silently. Excluded amounts are shown in the report so that readers know how large the uncertainty is.</p>",
                    "<h2>Actual, committed, requested, forecast</h2>",
                    table(["Term", "Meaning"], [["Requested", "Cost estimate of a demand that is not decided; not in the forecast"], ["Approved, not committed", "Approved demand without a purchase order; in the forecast"],
                                                ["Committed", "Open purchase order, not yet invoiced"], ["Actual", "Invoiced and recognised"], ["Forecast", "Actual + committed + approved, not committed"]]),
                    f"<h2>Current data quality</h2><p>As of {ctx['ds'].as_of}: {sum(1 for x in ctx['register'] if x.severity == 'CRITICAL')} critical exceptions, "
                    f"{exclusion_short(ctx['fin'])}. Details: Risk and Issue Register.</p>"])


def definitions(ctx, mapping) -> str:
    f = ctx["fin"].by_cc["CC-ENG-DATA"]
    defs = [["Budget (period)", "Approved budget of a cost centre for the budget period " + f"{c.PERIOD_MONTHS[0]} to {c.PERIOD_MONTHS[-1]}", "sum of monthly budgets"],
            ["Budget to date", "Budget of the months up to and including the cutoff month", "sum of monthly budgets to date"],
            ["Actual", "Valid, unique invoices and credit notes dated on or before the cutoff", "sum of invoices"],
            ["Variance to date", "Negative means under budget", "actual - budget to date"],
            ["Open commitment", "Not yet invoiced part of open purchase orders", "max(approved - recognised, 0)"],
            ["Approved, not committed", "Period cost of approved demands without purchase order", "one-time + monthly x months after go-live inside the period"],
            ["Uncommitted budget", "Budget that is neither spent nor committed", "budget - actual - open commitments"],
            ["Forecast at completion (EAC)", "Expected spend at the end of the period", "actual + open commitments + approved, not committed"],
            ["Forecast variance", "Positive means overrun", "EAC - budget"], ["Headroom", "What can still be approved without an overrun", "budget - EAC"],
            ["Allocation coverage", "Share of valid spend booked to a cost centre with budget", "mapped spend / all valid spend"],
            ["12-month option total", "Used to compare options; not discounted", "setup + 12 x monthly cost"]]
    return "".join([SYNTHETIC, "<h2>Definitions</h2>", table(["Term", "Definition", "Formula"], defs),
                    f"<h2>Worked example: CC-ENG-DATA as of {ctx['ds'].as_of}</h2>",
                    table(["Line", "EUR"], [["Budget (period)", eur(f.budget_period_eur)], ["Actual", eur(f.actual_eur)], ["Open commitments", eur(f.open_commitments_eur)],
                                            ["Approved, not committed", eur(f.approved_not_committed_eur)], ["Forecast EAC", eur(f.forecast_eac_eur)],
                                            ["Forecast variance", eur(f.forecast_variance_eur)], ["Headroom", eur(f.headroom_eur)]]),
                    f"<p>{eur(f.actual_eur)} + {eur(f.open_commitments_eur)} + {eur(f.approved_not_committed_eur)} = {eur(f.forecast_eac_eur)}. A request of 48,000 EUR would exceed the headroom of {eur(f.headroom_eur)}; "
                    "a request of 14,500 EUR would not. This is the funding gate applied to ORION-REQ-017.</p>",
                    "<h2>Limits of the forecast</h2>",
                    ul(["It is a commitment-based scenario, not a statistical prediction: four months of data do not support a trend model.", "It assumes that open purchase orders are invoiced in full inside the period.",
                        "It contains only approved work. Requests that are not decided are shown separately as scenarios.", "Totals are in EUR. A non-EUR invoice is excluded and reported in its own currency until Finance approves a conversion rate; it is never added to a EUR figure."])])


def weekly(ctx, mapping) -> str:
    ds, fin, cap, k = ctx["ds"], ctx["fin"], ctx["cap"], ctx["kpis"]
    tot, h = fin.totals(), hero_facts(ctx)
    crit = [x for x in ctx["register"] if x.severity == "CRITICAL"]
    req = decisions_required(ctx)
    fwd = [m for m in cap.months() if m >= ds.as_of.strftime("%Y-%m")]
    over = [(cc, f) for cc, f in fin.by_cc.items() if f.forecast_variance_eur > 0]
    banner = (f'<div data-type="panel-warning"><p><strong>Provisional.</strong> {len(crit)} critical data exceptions are open: {exclusion_short(fin)}. '
              f'Amounts in different currencies are not added together. Figures may change when they are resolved.</p></div>') if crit else ""
    summary = [f"<strong>Demand:</strong> {k['open_demands']['value']} open ({k['total_demands']['value']} registered); {k['approval_pending']['value']} await a decision, {k['overdue_open']['value']} overdue, "
               f"{k['blocked_open']['value']} blocked, {k['unassigned_open']['value']} without owner.",
               f"<strong>Money:</strong> forecast {eur(tot['forecast_eac_eur'])} against a budget of {eur(tot['budget_period_eur'])}; " +
               ("overrun forecast in " + ", ".join(f"{cc} ({eur(f.forecast_variance_eur)})" for cc, f in over) + "." if over else "no overrun forecast."),
               f"<strong>Capacity:</strong> Network and Access is over-allocated in December; {k['high_priority_not_approvable']['value']} High or Highest demands fail at least one gate.",
               f"<strong>{HERO}:</strong> deferred on {h['decision']['decided_at']}; next review {h['next_review_at']}."]
    kpi = [["Open demands", k["open_demands"]["value"]], ["New in the last 7 days", k["intake_last_7_days"]["value"]], ["Awaiting decision", k["approval_pending"]["value"]],
           ["Overdue", f"{k['overdue_open']['value']}: {', '.join(k['overdue_open']['source_ids'])}"], ["Blocked", f"{k['blocked_open']['value']}: {', '.join(k['blocked_open']['source_ids'])}"],
           ["Without owner", f"{k['unassigned_open']['value']} ({k['unassigned_pct']['value']}%)"], ["Intake completeness", f"{k['completeness_pct']['value']}%"],
           ["Completed to date", f"{k['completed_total']['value']} (median lead time {k['median_lead_time_days']['value']} days, {k['on_time_delivery_pct']['value']}% on time)"],
           ["Median triage time", f"{k['median_triage_business_days']['value']} working days"]]
    fin_rows = [[cc, eur(f.budget_period_eur), eur(f.actual_eur), eur(f.open_commitments_eur), eur(f.approved_not_committed_eur), eur(f.forecast_eac_eur), eur(f.forecast_variance_eur)] for cc, f in fin.by_cc.items()]
    fin_rows.append(["Total"] + [eur(tot[x]) for x in ("budget_period_eur", "actual_eur", "open_commitments_eur", "approved_not_committed_eur", "forecast_eac_eur", "forecast_variance_eur")])
    cap_rows = [[c.TEAMS[t][0]] + [f"{cap.cells[(t, m)]['remaining']} h" for m in fwd] for t in c.TEAMS]
    acts = [[a["ref"], a["action"], a["owner"], a["due"]] for a in action_register(ctx) if a["kind"] in ("blocked", "overdue", "MISSING_APPROVER", "UNAPPROVED_SPEND", "CAPACITY_OVERALLOCATED", "FORECAST_OVERRUN", "MISSING_OWNER")]
    return "".join([SYNTHETIC, banner, f"<p><strong>Reporting date:</strong> {ds.as_of} (inclusive). Figures on this page are a snapshot generated from the validated data set; the Jira lists at the bottom are live.</p>",
                    "<h2>Executive summary</h2>", ul(summary),
                    "<h2>Decisions required</h2>", table(["#", "Topic", "Decision needed", "Owner", "Due"], [[i + 1, x["topic"], x["decision"], x["owner"], x["due"]] for i, x in enumerate(req[:5])]),
                    "<h2>Operational health</h2>", table(["Measure", "Value"], kpi),
                    "<h2>Financial status (EUR)</h2>", table(["Cost centre", "Budget", "Actual", "Open commitments", "Approved, not committed", "Forecast EAC", "Forecast variance"], fin_rows),
                    "<p>Positive variance = overrun. Definitions: Budget and Forecast Definitions.</p>",
                    "<h2>Unallocated team hours</h2>", table(["Team"] + fwd, cap_rows),
                    "<h2>Owner / action / date</h2>", table(["Reference", "Action", "Owner", "Due"], acts),
                    "<h2>Live from Jira: ready for decision</h2>", jira(FILTERS["decision"][1]),
                    "<h2>Live from Jira: overdue</h2>", jira(FILTERS["overdue"][1]),
                    "<h2>Live from Jira: blocked or deferred</h2>", jira(FILTERS["blocked_deferred"][1])])


def decision_register(ctx, mapping) -> str:
    ds = ctx["ds"]
    color = {"approved": "green", "deferred": "yellow", "rejected": "red"}
    rows, approved_shown = [], 0
    for r in sorted(ds.decisions, key=lambda r: (r["decided_at"], r["decision_id"]), reverse=True):
        d = ds.demand(r["external_id"])
        if r["decision"] == "approved":            # page shows every deferral and rejection, and the eight latest approvals
            approved_shown += 1
            if approved_shown > 8:
                continue
        rationale = "Gates passed at the decision date; business case accepted." if r["decision"] == "approved" else r["rationale"]
        rows.append([e(r["decision_id"]), f"{issue(r['external_id'], mapping)} {e(d.title)}", e(r["decided_at"]), lozenge(r["decision"].upper(), color[r["decision"]]),
                     e(r["approver_role"]) or lozenge("MISSING", "red"), e(rationale), e(r["budget_snapshot_ref"] + " / " + r["capacity_snapshot_ref"] if r["budget_snapshot_ref"] else "-"),
                     e((r["followup_owner"] + ", " + r["followup_date"]) if r["followup_owner"] else "-")])
    out = ctx["kpis"]["decision_outcomes"]["value"]
    routed = [[issue(d.external_id, mapping), e(d.title), e(d.routed_to), e(d.decision_rationale)] for d in ds.demands if d.status == c.ROUTED_OUT]
    return "".join([SYNTHETIC, f"<p>One row per decision of the Infrastructure Demand Board, newest first. As of {ds.as_of}: {out['approved']} approved, {out['deferred']} deferred, {out['rejected']} rejected. "
                    "This page lists every deferral and rejection and the eight most recent approvals; the complete log is decisions.csv in the repository (report decision_action_register.md). "
                    "The decision brief of ORION-REQ-017 is a child page.</p>",
                    '<div data-type="panel-warning"><p>DEC-021 (ORION-REQ-021) has no approver role on record. Until the Head of Digital Infrastructure confirms who approved, the approval is treated as unconfirmed.</p></div>',
                    "<h2>Decisions</h2>", table(["Decision", "Demand", "Date", "Outcome", "Approver (role)", "Rationale", "Snapshots (finance / capacity)", "Follow-up"], rows, raw=True),
                    "<h2>Routed out at triage (no board decision)</h2>", table(["Record", "Title", "Routed to", "Reason"], routed, raw=True)])


def risk_register(ctx, mapping) -> str:
    ds, fin, cap = ctx["ds"], ctx["fin"], ctx["cap"]
    h = hero_facts(ctx)
    top = ctx["queue"][0]
    risks = [["R-01", f"{HERO}: repository reaches capacity before an option is approved", "Ingest for the January test campaign is throttled", "High",
              f"Data owners confirm retention classes for Option B; re-review on {h['next_review_at']}", "Demand Analyst Munich", h["next_review_at"]],
             ["R-02", "CC-ENG-SIM forecast exceeds budget by " + eur(fin.by_cc["CC-ENG-SIM"].forecast_variance_eur), "Unfunded spend at period end", "Medium",
              "Reallocate from a cost centre with headroom or accept the overrun", "Head of Digital Infrastructure", decisions_required(ctx)[0]["due"]],
             ["R-03", "Network and Access is committed 30 h beyond its December capacity", "Dates of approved network work slip", "Medium", "Move one start date or release run work", "Head of Digital Infrastructure", decisions_required(ctx)[0]["due"]],
             ["R-04", f"{top['demand'].external_id}: highest-scored demand cannot be staffed ({top['gates'].hours_available} h free, {top['demand'].hours} h needed)", "About 30 VPN support calls per week continue", "High",
              "Board decides between deferral, phased delivery and external support", "Infrastructure Demand Board Chair", decisions_required(ctx)[0]["due"]],
             ["R-05", "Security Engineering has under 20 unallocated hours before January", "Security demands in assessment cannot start this year", "Medium", "Sequence security demands in the January plan", "Delivery Lead Security Engineering", "2026-12-01"]]
    issues = []
    for d in ds.demands:
        if d.is_open and d.blocked:
            issues.append([issue(d.external_id, mapping), "Blocked", e(d.blocked_reason), e(d.delivery_lead or d.triage_owner)])
        if d.is_open and d.due_at and d.due_at < ds.as_of:
            issues.append([issue(d.external_id, mapping), "Overdue", e(f"Required by {d.due_at}; {(ds.as_of - d.due_at).days} days late, status {c.STATUS_LABEL[d.status]}"), e(d.delivery_lead or d.triage_owner or "Demand Manager")])
    data = [[e(x.code), e(x.record_id), e(x.message), e(x.proposed_action), e(x.decision_owner), e(x.due_date)] for x in ctx["register"] if x.severity == "CRITICAL"]
    warn = [[e(x.code), e(x.record_id), e(x.message), e(x.decision_owner), e(x.due_date)] for x in ctx["register"] if x.severity == "WARNING"]
    return "".join([SYNTHETIC, f"<p>Status as of {ds.as_of}. Risks are reviewed at every board meeting; issues and data exceptions are generated from the validated data set.</p>",
                    "<h2>Risks</h2>", table(["ID", "Risk", "Consequence", "Rating", "Response", "Owner", "Due"], risks),
                    "<h2>Issues: blocked and overdue demands</h2>", table(["Demand", "Type", "Detail", "Owner"], issues, raw=True),
                    "<h2>Critical data exceptions</h2>", table(["Code", "Record", "Finding", "Action", "Owner", "Due"], data, raw=True),
                    "<h2>Other exceptions</h2>", table(["Code", "Record", "Finding", "Owner", "Due"], warn, raw=True),
                    "<h2>Live from Jira: management attention</h2>", jira(FILTERS["attention"][1])])


def handoff(ctx, mapping) -> str:
    ds = ctx["ds"]
    items = [["Stable references", "Demand id, Jira key, decision record", "Demand manager"], ["Approved scope", "Option approved, sites and capacity in scope, what is explicitly out of scope", "Solution architect"],
             ["Cost envelope", "Approved one-time and monthly amounts, cost centre, purchase order number", "Finance controller"],
             ["Target window", "Start month, required-by date, maintenance windows, hours allocated per month", "Delivery lead"],
             ["Prerequisites", "Security review result, contracts, dependencies on other demands", "Demand analyst"],
             ["Acceptance conditions", "How the requester confirms the result; operational readiness (monitoring, backup, documentation)", "Requester and delivery lead"],
             ["Risks carried into delivery", "Open risks with owner", "Demand analyst"], ["Sign-off", "Demand manager (complete), delivery lead (accepted)", "Both"]]
    rows = [[issue(d.external_id, mapping), e(d.title), e(c.STATUS_LABEL[d.status]), e(d.handoff_ref), e(d.delivery_lead), e(d.due_at), lozenge("BLOCKED", "red") if d.blocked else lozenge("OK", "green")]
            for d in ds.demands if d.status in (c.HANDOFF, c.IN_DELIVERY)]
    waiting = [[issue(d.external_id, mapping), e(d.title), e(d.decision_date), e(d.blocked_reason or "Purchase order and handoff checklist to be issued")] for d in ds.demands if d.status == c.APPROVED]
    return "".join([SYNTHETIC, "<h2>When it is used</h2><p>After an approval and before any delivery work starts. The demand moves to <code>stage-handoff</code> when the demand manager issues the checklist and to "
                    "<code>stage-in-delivery</code> only when the delivery lead has accepted it. Delivery without an accepted handoff is reported as an exception.</p>",
                    "<h2>Checklist</h2>", table(["Item", "Content", "Provided by"], items),
                    "<h2>Copy for a new handoff</h2>",
                    '<ul data-type="task-list">' + "".join(f'<li data-type="task-item"><input type="checkbox"> {e(i[0])}: {e(i[1])}</li>' for i in items) + "</ul>",
                    "<h2>Handoffs in progress</h2>", table(["Demand", "Title", "Stage", "Handoff ref", "Delivery lead", "Required by", "State"], rows, raw=True),
                    "<h2>Approved, handoff not yet issued</h2>", table(["Demand", "Title", "Approved on", "Open point"], waiting, raw=True)])


def runbook(ctx, mapping) -> str:
    weekly_steps = ["Export the finance ledgers and the capacity table as of Sunday evening into <code>data/</code>.", "<code>python -m infraflow validate</code> - read the exception register; critical findings make the report provisional.",
                    "<code>python -m infraflow all</code> - regenerates reports, workbook and slide deck from the same data.", "<code>python -m infraflow jira pull</code> and <code>python -m infraflow jira reconcile --snapshot ...</code> - every difference between Jira and the data set is listed.",
                    "Publish the Weekly Portfolio Review page and send the management e-mail. Do not edit numbers by hand; correct the source and regenerate."]
    failures = [["401 Unauthorized", "Token missing, wrong or expired", "Renew the API token; never paste it into a file or chat"], ["403 Forbidden", "Account lacks permission", "Ask the site administrator; do not retry"],
                ["429 Too Many Requests", "Rate limit", "The client waits for Retry-After and retries up to four times; if it still fails, run later"],
                ["Network error or 5xx", "Temporary outage", "Automatic retry with backoff; use the last snapshot and mark the report with its date"],
                ["Jira and data set differ", "Manual change in Jira or stale export", "Decide which source is right for that field (see Sources of truth), correct it, reconcile again"]]
    return "".join([SYNTHETIC, "<h2>Weekly refresh (Monday)</h2>", ul(weekly_steps, ordered=True),
                    "<h2>Rules for writing to Jira</h2>",
                    ul(["Read-only by default. Writes need <code>--apply</code> and <code>INFRAFLOW_ALLOW_WRITE=1</code>.", "Before creating an issue, search for the label <code>orion-req-NNN</code>. One demand, one issue. A second run creates nothing.",
                        "The mapping between demand ids and Jira keys is stored in <code>data/jira_mapping.json</code>.", "Nothing is deleted by automation. Records KAN-1 to KAN-4 are onboarding and test records and are excluded by the label <code>orion-demand</code>."]),
                    "<h2>When something fails</h2>", table(["Symptom", "Cause", "Action"], failures),
                    "<h2>Escalating data errors</h2><p>Each exception has an owner role and a due date in the register. Critical finance exceptions go to the Finance Controller the same day; "
                    "approvals without approver and spend without approval go to the Head of Digital Infrastructure. The reporting owner does not fix source data.</p>",
                    "<h2>Known platform limits (Jira and Confluence Free)</h2>",
                    ul(["Workflow validators and approval steps are not available: the gates are process controls documented in this space and enforced in the offline model.",
                        "The team-managed project has five statuses; the lifecycle stage is a label.", "Filters and dashboards are private to the site; nothing is shared publicly."]),
                    "<h2>Integration check (live from Jira)</h2>", jira(f"project = {c.JIRA_PROJECT_KEY} AND labels = infraflow-smoke-test")])


def improvement(ctx, mapping) -> str:
    rows = [["CI-01", "Jira cannot enforce the decision gates (no validators on the Free plan); several lifecycle stages share one board column", "A status can be changed without a decision record",
             "Rename the five columns to Intake / Assessment / Decision / Delivery / Closed; weekly reconciliation flags stage changes without decision record", "0 issues with stage-approved and no decision record", lozenge("OPEN", "yellow")],
            ["CI-02", "Saved filters and the dashboard cannot be created through the connector", "The 16 verified queries are documented but must be saved by hand once",
             "Create them in the Jira UI from the Jira Filters page, or run the REST command with an API token", "16 saved filters and one dashboard visible in Jira", lozenge("OPEN", "yellow")],
            ["CI-03", "Finance and capacity data are CSV extracts, not Jira fields", "The funding and capacity position is not visible on the board", "Publish the gate result as labels (done for needs-finance-review) and in the issue description (done)", "Every undecided issue shows its gate check", lozenge("DONE", "green")],
            ["CI-04", "The REST client is tested with mocks only; live operations so far ran through the connector", "A live REST run could reveal differences", "Run jira pull with an API token and compare with the connector snapshot", "0 differences between both snapshots", lozenge("OPEN", "yellow")],
            ["CI-05", "Relative JQL (overdue, stale) drifts from the fixed report cutoff", "Live lists and the weekly snapshot can show different counts", "State the cutoff on every report and label live lists as live (done)", "No unexplained difference raised in the board", lozenge("DONE", "green")],
            ["CI-06", "One licensed user: ownership is shown by role names in the description, the assignee only signals owned / not owned", "Per-person workload cannot be reported from Jira", "Invite the analysts as users (Free plan allows 10) or keep role-based ownership", "Each open issue has a named owner", lozenge("OPEN", "yellow")]]
    return "".join([SYNTHETIC, "<p>Limitations found while building and operating the process, with the agreed remedy and how success is measured. Reviewed monthly by the demand manager.</p>",
                    table(["ID", "Limitation", "Impact", "Remediation", "Success criterion", "Status"], rows, raw=True),
                    "<h2>Retrospective of the first reporting cycle</h2>",
                    ul(["<strong>Worked:</strong> stable identifiers made it possible to trace every figure to a record in Jira, the ledgers and the decision log.",
                        "<strong>Worked:</strong> publishing the report as provisional, with the excluded amounts, avoided a wrong total.",
                        "<strong>To improve:</strong> three open demands had no owner for more than a week; the ownership-gap filter is now part of the daily triage.",
                        "<strong>To improve:</strong> one approval was recorded without approver; the decision template now makes the role mandatory."])])


PAGES = [("Start Here - Operating Model", start_here), ("Infrastructure Demand Intake Procedure", intake), ("Demand Assessment and Prioritisation", assessment),
         ("Financial Reporting Methodology", finance_method), ("Budget and Forecast Definitions", definitions), ("Weekly Portfolio Review - 2026-11-16", weekly),
         ("Decision Register", decision_register), ("Risk and Issue Register", risk_register), ("Delivery Handoff Checklist", handoff),
         ("Operational Runbook", runbook), ("Continuous Improvement Register", improvement)]


def jira_filters_page() -> str:
    rows = [[e(name), f"<code>{e(jql)}</code>", e(purpose)] for name, jql, purpose in FILTERS.values()]
    return "".join([SYNTHETIC, "<p>Verified JQL for project KAN. Each query was executed live and returned exactly the issues expected from the data set (see the repository file docs/JQL_FILTERS.md). "
                    "To save one: Jira &gt; Filters &gt; Create filter &gt; JQL &gt; paste &gt; Save as.</p>", table(["Filter name", "JQL", "Purpose"], rows, raw=True),
                    "<h2>Operational dashboard (live)</h2><p>Until a native Jira dashboard is configured, these live lists serve as the operational view.</p>",
                    "<h3>High-priority open demands</h3>", jira(FILTERS["high"][1]), "<h3>Needs finance review</h3>", jira(FILTERS["finance"][1]),
                    "<h3>Security review pending</h3>", jira(FILTERS["security"][1]), "<h3>Completed in the last 30 days</h3>", jira(FILTERS["done_recent"][1])])


def write_pages(ds, out_dir: Path = OUT_DIR) -> list[tuple[str, Path]]:
    ctx, mapping = build_context(ds), load_mapping()
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for i, (title, fn) in enumerate(PAGES + [("Jira Filters and Operational Dashboard", lambda ctx, mapping: jira_filters_page())], 1):
        path = out_dir / f"{i:02d}_{title.lower().replace(' - ', '_').replace(' ', '_')}.html"
        path.write_text(fn(ctx, mapping) + "\n", encoding="utf-8")
        written.append((title, path))
    return written
