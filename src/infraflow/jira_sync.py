"""Mapping between the demand dataset and Jira project KAN.

* `issue_payload` / `plan`  - what each seeded issue must look like (single definition, used for
                              seeding, for the REST client and for reconciliation)
* `FILTERS`                 - the saved-filter catalogue with its JQL
* `expected_filter_ids`     - which demands each filter must return, computed from the dataset
* `reconcile`               - compare a Jira snapshot with the dataset and report every difference
* `seed`                    - idempotent seeding through the REST client (dry-run by default)

Stable identity: label ``orion-req-NNN`` plus the summary prefix ``ORION-REQ-NNN |``. The mapping to
Jira keys is stored in ``data/jira_mapping.json``.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from . import config as c
from .models import Dataset, Demand
from .reports import build_context, eur
from .scoring import Gates

MAPPING_FILE = c.ROOT / "data" / "jira_mapping.json"
BASE = f"project = {c.JIRA_PROJECT_KEY} AND labels = {c.PORTFOLIO_LABEL}"
OPEN = BASE + " AND statusCategory != Done"
RECURRING_REVIEW_THRESHOLD = 2500          # EUR per month; above this an undecided demand needs a finance review

# key: (name, JQL, purpose)
FILTERS: dict[str, tuple[str, str, str]] = {
    "open": ("KAN | Open demands", OPEN + " ORDER BY priority DESC, due ASC", "Working list of all open demands."),
    "overdue": ("KAN | Overdue open demands", OPEN + " AND due < startOfDay() ORDER BY due ASC", "Open demands past their required-by date."),
    "unassigned": ("KAN | Open demands without owner", OPEN + " AND assignee IS EMPTY ORDER BY created ASC", "Ownership gaps."),
    "stale": ("KAN | No activity for 7 days", OPEN + " AND updated <= -7d ORDER BY updated ASC", "Open demands nobody has touched for a week."),
    "high": ("KAN | High-priority open demands", OPEN + " AND priority in (Highest, High) ORDER BY priority DESC, due ASC", "Review order for the demand board."),
    "assessment": ("KAN | Pending assessment", BASE + " AND labels in (stage-triaged, stage-assessment) ORDER BY due ASC", "Triaged or in assessment."),
    "decision": ("KAN | Ready for decision", BASE + " AND labels = stage-ready-for-decision ORDER BY priority DESC", "Agenda of the next demand board."),
    "needs_info": ("KAN | Waiting for requester", BASE + " AND labels = stage-needs-info ORDER BY updated ASC", "Clarification requested from the requester."),
    "finance": ("KAN | Needs finance review", OPEN + " AND labels = needs-finance-review ORDER BY priority DESC", "Funding gate fails or recurring cost is high."),
    "security": ("KAN | Security review pending", OPEN + " AND labels = needs-security-review ORDER BY priority DESC", "Security-sensitive demands without a passed review."),
    "blocked_deferred": ("KAN | Blocked or deferred", OPEN + " AND labels in (blocked, stage-deferred) ORDER BY due ASC", "Work that is not moving, with the reason in the issue."),
    "done_recent": ("KAN | Completed in the last 30 days", BASE + " AND labels = stage-complete AND statusCategoryChangedDate >= -30d ORDER BY statusCategoryChangedDate DESC", "Recently delivered demands."),
    "team_plat": ("KAN | Team Platform and Storage", OPEN + " AND labels = team-plat ORDER BY due ASC", "Open demands of the Platform and Storage team."),
    "team_net": ("KAN | Team Network and Access", OPEN + " AND labels = team-net ORDER BY due ASC", "Open demands of the Network and Access team."),
    "team_sec": ("KAN | Team Security Engineering", OPEN + " AND labels = team-sec ORDER BY due ASC", "Open demands of the Security Engineering team."),
    "attention": ("KAN | Management attention", OPEN + " AND (due < startOfDay() OR assignee IS EMPTY OR labels in (blocked, needs-finance-review)) ORDER BY priority DESC",
                  "Overdue, unowned, blocked or unfunded open demands."),
}


def req_label(external_id: str) -> str:
    return external_id.lower()


def _labels(d: Demand, g: Gates | None) -> list[str]:
    labels = [c.PORTFOLIO_LABEL, req_label(d.external_id), c.stage_label(d.status), f"site-{d.site.lower()}",
              f"team-{d.team.lower()}", f"cat-{d.category}"]
    if d.cost_center:
        labels.append(d.cost_center.lower())
    if d.request_type != "demand":
        labels.append("type-" + d.request_type.replace("_", "-"))
    if d.blocked:
        labels.append("blocked")
    if d.is_open and not d.triage_owner:
        labels.append("owner-missing")
    if d.is_open and d.security_needed and d.security_status != "passed":
        labels.append("needs-security-review")
    if g is not None and d.is_open and (g.funding_pass is not True or (d.monthly or 0) >= RECURRING_REVIEW_THRESHOLD):
        labels.append("needs-finance-review")
    return sorted(labels)


def _description(ds: Dataset, d: Demand, g: Gates | None, score, band) -> str:
    opts = [o for o in ds.options if o["external_id"] == d.external_id]
    lines = [f"*Synthetic record - {c.ORG_NAME} (fictional). Source: InfraFlow dataset, cutoff {ds.as_of.isoformat()}.*", "",
             "## Business need", d.business_case, "",
             "## Request", "",
             "| Field | Value |", "|---|---|",
             f"| External ID | {d.external_id} |", f"| Request type | {d.request_type} |",
             f"| Lifecycle stage | {c.STATUS_LABEL[d.status]} |",
             f"| Requester | {d.row.get('requester_role', '')} ({d.site}) |", f"| Business owner | {d.row.get('business_owner', '')} |",
             f"| Demand analyst (owner) | {d.triage_owner or 'NOT ASSIGNED'} |",
             f"| Required by | {d.due_at} |", f"| Service category | {d.category} |",
             f"| Delivery team | {c.TEAMS[d.team][0]} |", f"| Cost centre | {d.cost_center or 'NOT PROVIDED'} |",
             f"| One-time estimate | {eur(d.one_time)} |", f"| Monthly recurring estimate | {eur(d.monthly)} |",
             f"| Effort estimate | {d.hours} h |",
             f"| Impact / urgency / risk reduction / strategic fit (0-5) | {d.impact} / {d.urgency} / {d.risk_reduction} / {d.strategic} |",
             f"| Priority score | {score} ({band}) - orders the review queue, does not approve |",
             f"| Security review | {d.security_status.replace('_', ' ')} |",
             f"| Dependencies | {d.depends_on or 'none'} |", ""]
    if d.blocked:
        lines += ["## Blocker", d.blocked_reason, ""]
    if g is not None:
        lines += ["## Gate check at the cutoff", f"- Information: {'complete' if g.info_complete else 'incomplete - ' + ', '.join(g.missing_fields)}",
                  f"- Funding: {g.funding_note}", f"- Capacity: {g.capacity_note}", f"- Security: {g.security_note}", ""]
    if opts:
        lines += ["## Options assessed", "", "| Option | One-time | Monthly | Effort | Benefit | Delivery risk |", "|---|---|---|---|---|---|"]
        lines += [f"| {o['option_id']}: {o['name']} | {eur(int(o['one_time_eur']))} | {eur(int(o['monthly_eur']))} | {o['hours']} h | {o['benefit']} | {o['delivery_risk']} |" for o in opts]
        lines.append("")
    if d.decision_outcome:
        lines += ["## Decision", f"- Outcome: **{d.decision_outcome.replace('_', ' ')}**" + (f" on {d.decision_date}" if d.decision_date else ""),
                  f"- Decided by (role): {d.decision_owner or ('triage' if d.status == c.ROUTED_OUT else 'NOT RECORDED')}",
                  f"- Rationale: {d.decision_rationale}"]
        if d.next_review_at:
            lines.append(f"- Next review: {d.next_review_at}")
        if d.routed_to:
            lines.append(f"- Routed to: {d.routed_to}")
        lines.append("")
    if d.risk_note:
        lines += ["## Risk", d.risk_note, ""]
    lines += ["## Acceptance and handoff", f"- Handoff reference: {d.handoff_ref or 'not handed off'}",
              f"- Delivery lead: {d.delivery_lead or 'not assigned yet'}",
              "- Acceptance: requester confirms the service works as described in the business need; the demand analyst closes the record."]
    return "\n".join(lines)


def issue_payload(ds: Dataset, d: Demand, g: Gates | None) -> dict:
    from .scoring import priority_band, priority_score
    score = priority_score(d)
    band = priority_band(score)
    return dict(external_id=d.external_id, summary=f"{d.external_id} | {d.title}", issue_type="Task",
                priority=band if band != "Unscored" else "Medium", duedate=d.due_at.isoformat() if d.due_at else None,
                labels=_labels(d, g), jira_status=c.STATUS_TO_JIRA[d.status], stage=d.status,
                assigned=bool(d.triage_owner) or not d.is_open, description=_description(ds, d, g, score, band))


def plan(ds: Dataset, numbers: list[int] | None = None, ctx: dict | None = None) -> list[dict]:
    """Payloads for the demands that are seeded into Jira, in id order."""
    from .scoring import evaluate
    ctx = ctx or build_context(ds)
    wanted = {f"ORION-REQ-{n:03d}" for n in (numbers or c.JIRA_SEED_NUMBERS)}
    out = []
    for d in ds.demands:
        if d.external_id in wanted:
            g = evaluate(ds, d, ctx["fin"], ctx["cap"]) if d.is_open and d.status not in c.FUNDED else None
            out.append(issue_payload(ds, d, g))
    return out


def coverage(ds: Dataset, mapping: dict, snapshot: list[dict] | None = None) -> dict:
    """Which demands of the dataset have a Jira issue. `mapped` comes from data/jira_mapping.json;
    `in_snapshot` (optional) from a recorded read of the live project."""
    all_ids = [d.external_id for d in ds.demands]
    mapped = [i for i in all_ids if i in mapping]
    out = dict(total=len(all_ids), mapped=mapped, missing=[i for i in all_ids if i not in mapping],
               unknown_in_mapping=sorted(set(mapping) - set(all_ids)))
    if snapshot is not None:
        seen = {l.upper() for issue in snapshot for l in issue.get("labels", []) if l.startswith("orion-req-")}
        out["in_snapshot"] = [i for i in all_ids if i in seen]
        out["mapped_but_not_in_snapshot"] = [i for i in mapped if i not in seen]
        out["in_snapshot_but_not_mapped"] = sorted(seen - set(mapped))
    return out


def plan_missing(ds: Dataset, mapping: dict, ctx: dict | None = None) -> list[dict]:
    """Payloads for the demands that have no Jira issue yet (by mapping). Existing mappings are never touched."""
    missing = [int(d.external_id[-3:]) for d in ds.demands if d.external_id not in mapping]
    return plan(ds, numbers=missing, ctx=ctx) if missing else []


def check_saved_filters(found: list[dict]) -> dict:
    """Compare saved Jira filters (rows with name and jql, e.g. from the filter search API) with the catalogue.

    Used to verify the manual browser step: a filter counts only if its name exists and its JQL is the
    catalogue JQL (whitespace and quoting of the same query are normalised)."""
    norm = lambda q: " ".join((q or "").replace('"', "").replace("'", "").lower().split())
    by_name = {f.get("name"): f for f in found}
    ok, wrong, missing = [], [], []
    for key, (name, jql, _) in FILTERS.items():
        f = by_name.get(name)
        if f is None:
            missing.append(name)
        elif norm(f.get("jql")) != norm(jql):
            wrong.append(dict(name=name, expected=jql, actual=f.get("jql")))
        else:
            ok.append(dict(name=name, id=f.get("id")))
    return dict(ok=ok, wrong_jql=wrong, missing=missing, complete=not wrong and not missing)


def hero_comments(ds: Dataset, external_id: str = "ORION-REQ-017") -> list[str]:
    """The hero's status history as Jira comments (one per lifecycle step after submission)."""
    return [f"**{e['occurred_at'][:10]} - {c.STATUS_LABEL[e['new_status']]}** ({e['actor_role']}): {e['reason']}"
            for e in ds.events_for(external_id)[1:]]


def load_mapping(path: Path = MAPPING_FILE) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def save_mapping(mapping: dict, path: Path = MAPPING_FILE) -> None:
    path.write_text(json.dumps(dict(sorted(mapping.items())), indent=2) + "\n", encoding="utf-8")


def expected_filter_ids(payloads: list[dict], today: date) -> dict[str, list[str]]:
    """External ids each filter must return for the seeded issues (independent of Jira)."""
    def is_open(p): return p["jira_status"] != "Done"
    def has(p, *labels): return any(l in p["labels"] for l in labels)
    def overdue(p): return bool(p["duedate"]) and date.fromisoformat(p["duedate"]) < today
    rules = {
        "open": is_open, "overdue": lambda p: is_open(p) and overdue(p), "unassigned": lambda p: is_open(p) and not p["assigned"],
        "stale": lambda p: False,           # nothing can be stale directly after seeding; the filter becomes useful over time
        "high": lambda p: is_open(p) and p["priority"] in ("Highest", "High"),
        "assessment": lambda p: has(p, "stage-triaged", "stage-assessment"), "decision": lambda p: has(p, "stage-ready-for-decision"),
        "needs_info": lambda p: has(p, "stage-needs-info"), "finance": lambda p: is_open(p) and has(p, "needs-finance-review"),
        "security": lambda p: is_open(p) and has(p, "needs-security-review"),
        "blocked_deferred": lambda p: is_open(p) and has(p, "blocked", "stage-deferred"),
        "done_recent": lambda p: has(p, "stage-complete"),
        "team_plat": lambda p: is_open(p) and has(p, "team-plat"), "team_net": lambda p: is_open(p) and has(p, "team-net"),
        "team_sec": lambda p: is_open(p) and has(p, "team-sec"),
        "attention": lambda p: is_open(p) and (overdue(p) or not p["assigned"] or has(p, "blocked", "needs-finance-review")),
    }
    return {key: sorted(p["external_id"] for p in payloads if rule(p)) for key, rule in rules.items()}


def reconcile(payloads: list[dict], snapshot: list[dict], mapping: dict) -> list[dict]:
    """Compare Jira (snapshot rows: key, summary, status, priority, duedate, labels, assignee) with the dataset.

    Returns one finding per difference; an empty list means the two systems agree.
    """
    findings = []
    by_ext: dict[str, list[dict]] = {}
    for issue in snapshot:
        ids = [l.upper() for l in issue.get("labels", []) if l.startswith("orion-req-")]
        if c.PORTFOLIO_LABEL in issue.get("labels", []) and not ids:
            findings.append(dict(external_id="", key=issue["key"], field="identity", expected="orion-req-NNN label", actual="missing"))
        for ext in ids:
            by_ext.setdefault(ext, []).append(issue)
    planned = {p["external_id"] for p in payloads}
    for ext, issues in sorted(by_ext.items()):
        if len(issues) > 1:
            findings.append(dict(external_id=ext, key=", ".join(i["key"] for i in issues), field="duplicate", expected="1 issue", actual=f"{len(issues)} issues"))
        if ext not in planned:
            findings.append(dict(external_id=ext, key=issues[0]["key"], field="unexpected", expected="not seeded", actual="exists in Jira"))
    for p in payloads:
        ext = p["external_id"]
        issues = by_ext.get(ext, [])
        if not issues:
            findings.append(dict(external_id=ext, key=mapping.get(ext, {}).get("key", ""), field="missing", expected="issue in Jira", actual="not found"))
            continue
        issue = issues[0]
        if mapping.get(ext, {}).get("key") != issue["key"]:
            findings.append(dict(external_id=ext, key=issue["key"], field="mapping", expected=mapping.get(ext, {}).get("key", "(unmapped)"), actual=issue["key"]))
        checks = [("summary", p["summary"], issue.get("summary")), ("status", p["jira_status"], issue.get("status")),
                  ("priority", p["priority"], issue.get("priority")), ("duedate", p["duedate"], issue.get("duedate")),
                  ("labels", p["labels"], sorted(issue.get("labels", []))),
                  ("assignment", "assigned" if p["assigned"] else "unassigned", "assigned" if issue.get("assignee") else "unassigned")]
        for field, expected, actual in checks:
            if expected != actual:
                findings.append(dict(external_id=ext, key=issue["key"], field=field, expected=expected, actual=actual))
    return findings


def reconcile_report(payloads: list[dict], snapshot: list[dict], mapping: dict, snapshot_source: str) -> str:
    findings = reconcile(payloads, snapshot, mapping)
    lines = ["# Jira / dataset consistency report", "",
             f"**Snapshot:** {snapshot_source}  ", f"**Issues in snapshot:** {len(snapshot)}  ",
             f"**Demands expected in Jira:** {len(payloads)}  ", f"**Differences:** {len(findings)}", "",
             "Checked per demand: summary, Jira status (from lifecycle stage), priority, due date, full label set, assignment, mapping file entry, duplicates.", ""]
    if findings:
        lines += ["| Demand | Jira key | Field | Expected (dataset) | Actual (Jira) |", "|---|---|---|---|---|"]
        lines += [f"| {f['external_id']} | {f['key']} | {f['field']} | {f['expected']} | {f['actual']} |" for f in findings]
    else:
        lines.append("All seeded demands match the dataset.")
    lines += ["", "## Mapping", "", "| Demand | Jira key | Jira status | Lifecycle stage |", "|---|---|---|---|"]
    lines += [f"| {p['external_id']} | {mapping.get(p['external_id'], {}).get('key', '')} | {p['jira_status']} | {c.STATUS_LABEL[p['stage']]} |" for p in payloads]
    return "\n".join(lines) + "\n"


# ---- Markdown -> Atlassian Document Format (subset used by the descriptions) ----
def to_adf(markdown: str) -> dict:
    content, bullets, rows = [], [], []
    text = lambda s: {"type": "text", "text": s.replace("**", "").replace("*", "")}
    para = lambda s: {"type": "paragraph", "content": [text(s)]}

    def flush():
        nonlocal bullets, rows
        if bullets:
            content.append({"type": "bulletList", "content": [{"type": "listItem", "content": [para(b)]} for b in bullets]})
            bullets = []
        if rows:
            content.append({"type": "table", "content": [
                {"type": "tableRow", "content": [{"type": "tableHeader" if i == 0 else "tableCell", "content": [para(cell or " ")]} for cell in r]}
                for i, r in enumerate(rows)]})
            rows = []
    for line in markdown.splitlines():
        s = line.strip()
        if s.startswith("|"):
            if bullets:
                flush()
            cells = [x.strip() for x in s.strip("|").split("|")]
            if not all(set(x) <= set("-: ") for x in cells):
                rows.append(cells)
            continue
        if s.startswith("- "):
            if rows:
                flush()
            bullets.append(s[2:])
            continue
        flush()
        if s.startswith("## "):
            content.append({"type": "heading", "attrs": {"level": 2}, "content": [text(s[3:])]})
        elif s:
            content.append(para(s))
    flush()
    return {"type": "doc", "version": 1, "content": content}


def seed(client, payloads: list[dict], mapping: dict, apply: bool = False, project: str = c.JIRA_PROJECT_KEY) -> list[dict]:
    """Create missing issues; never create a second issue for an external id. Returns the action log."""
    log = []
    for p in payloads:
        existing = client.find_by_label(project, req_label(p["external_id"]))
        if len(existing) > 1:
            log.append(dict(external_id=p["external_id"], action="ERROR duplicate in Jira", key=", ".join(i["key"] for i in existing)))
            continue
        if existing:
            key = existing[0]["key"]
            mapping[p["external_id"]] = dict(key=key, id=existing[0].get("id", ""))
            log.append(dict(external_id=p["external_id"], action="exists", key=key))
            continue
        if not apply:
            log.append(dict(external_id=p["external_id"], action="would create", key=""))
            continue
        fields = dict(project={"key": project}, summary=p["summary"], issuetype={"name": p["issue_type"]}, labels=p["labels"],
                      priority={"name": p["priority"]}, description=to_adf(p["description"]))
        if p["duedate"]:
            fields["duedate"] = p["duedate"]
        created = client.create_issue(fields)
        mapping[p["external_id"]] = dict(key=created["key"], id=created.get("id", ""))
        if p["jira_status"] != "Idea":
            client.transition(created["key"], p["jira_status"])
        log.append(dict(external_id=p["external_id"], action="created", key=created["key"]))
    return log


def main(args) -> int:
    """CLI entry: plan | pull | seed | reconcile | filters."""
    from .jira_client import JiraAuthError, JiraClient, simplify
    from .models import load_dataset
    ds = load_dataset(Path(args.data), date.fromisoformat(args.as_of))
    payloads = plan(ds)
    if args.action == "coverage":
        snap = json.loads(Path(args.snapshot).read_text())["issues"] if args.snapshot else None
        cov = coverage(ds, load_mapping(), snap)
        print(f"Dataset demands: {cov['total']}\nWith a Jira issue (data/jira_mapping.json): {len(cov['mapped'])}\nWithout a Jira issue: {len(cov['missing'])}")
        if cov["missing"]:
            print("  " + ", ".join(cov["missing"]))
        if snap is not None:
            print(f"Found in snapshot {args.snapshot}: {len(cov['in_snapshot'])}")
            for label in ("mapped_but_not_in_snapshot", "in_snapshot_but_not_mapped"):
                if cov[label]:
                    print(f"  {label}: {', '.join(cov[label])}")
        return 0
    if args.action == "plan" and getattr(args, "missing", False):
        payloads = plan_missing(ds, load_mapping())
    if args.action == "plan":
        text = json.dumps(payloads, indent=2)
        Path(args.output).write_text(text + "\n", encoding="utf-8") if args.output else print(text)
        return 0
    if args.action == "filters" and not args.apply:
        for key, (name, jql, purpose) in FILTERS.items():
            print(f"{name}\n  {jql}\n  {purpose}\n")
        print("Dry run: no filter was created. Use --apply with INFRAFLOW_ALLOW_WRITE=1 and Jira credentials to create them.")
        return 0
    if args.action == "live":
        if not args.snapshot:
            print("live needs --snapshot <file>: a recorded read of Jira ('jira pull --output <file>'). Without one no live report is written.")
            return 2
        from .jira_live import drift, live_report
        snap = json.loads(Path(args.snapshot).read_text())
        today = date.fromisoformat(args.today) if getattr(args, "today", None) else date.fromisoformat(snap.get("taken_at", date.today().isoformat()))
        out = Path(args.output) if args.output else c.REPORTS_DIR / "jira_live_pipeline.md"
        out.write_text(live_report(ds, snap, today), encoding="utf-8")
        print(f"Wrote {out} from {args.snapshot}: {len(snap['issues'])} issues, {len(drift(ds, snap))} drift findings")
        return 0
    if args.action == "reconcile":
        if not args.snapshot:
            print("reconcile needs --snapshot <file> (create one with 'jira pull --output <file>').")
            return 2
        snap = json.loads(Path(args.snapshot).read_text())
        report = reconcile_report(payloads, snap["issues"], load_mapping(), f"{args.snapshot} ({snap.get('source', 'unknown source')}, taken {snap.get('taken_at', '?')})")
        out = Path(args.output) if args.output else c.REPORTS_DIR / "jira_consistency_report.md"
        out.write_text(report, encoding="utf-8")
        n = len(reconcile(payloads, snap["issues"], load_mapping()))
        print(f"Wrote {out}: {n} differences")
        return 1 if n else 0
    allow = bool(args.apply) and os.environ.get("INFRAFLOW_ALLOW_WRITE") == "1"
    if args.apply and not allow:
        print("--apply ignored: set INFRAFLOW_ALLOW_WRITE=1 to permit writes. Continuing as dry run.")
    try:
        client = JiraClient.from_env(allow_write=allow)
    except JiraAuthError as exc:
        print(f"NOT_CONFIGURED: {exc}")
        return 3
    if args.action == "pull":
        issues = [simplify(i) for i in client.search(BASE + " ORDER BY key ASC")]
        snap = dict(source="Jira REST API (infraflow jira pull)", taken_at=date.today().isoformat(), jql=BASE, issues=issues)
        out = Path(args.output or args.snapshot or c.ROOT / "evidence" / "jira_snapshot_rest.json")
        out.write_text(json.dumps(snap, indent=2) + "\n", encoding="utf-8")
        print(f"Read {len(issues)} issues (read-only) -> {out}")
        return 0
    if args.action == "seed":
        mapping = load_mapping()
        for row in seed(client, payloads, mapping, apply=allow):
            print(f"{row['external_id']}: {row['action']} {row['key']}")
        if allow:
            save_mapping(mapping)
        else:
            print("Dry run: nothing was written.")
        return 0
    if args.action == "filters":
        have = {f["name"] for f in client.list_filters("KAN |")}
        for key, (name, jql, purpose) in FILTERS.items():
            if name in have:
                print(f"exists: {name}")
            else:
                print(f"created: {name} (id {client.create_filter(name, jql, purpose).get('id')})")
        return 0
    return 2
