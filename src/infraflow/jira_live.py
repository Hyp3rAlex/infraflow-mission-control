"""Read-only reporting refresh from a recorded read of the live Jira project.

Source-of-truth design
----------------------
* Jira is the source of truth for **lifecycle** facts: status, lifecycle stage (``stage-*`` label),
  owner (assignee), due date, priority, blocked flag.
* Money and hours are **not** in Jira (Free plan, no custom fields): they stay in the finance and
  capacity ledgers. This module therefore never produces a financial or capacity figure.
* The offline pipeline (``reports.py``) is unchanged. This module adds one report that is computed
  **only from the snapshot** and one drift list that compares the snapshot with the dataset.

A snapshot is a JSON file ``{"source", "taken_at", "jql", "issues": [{key, summary, status, priority,
duedate, assignee, labels}]}``. It is produced either by ``infraflow jira pull`` (REST API, read-only,
needs an API token) or recorded from the Atlassian connector. Nothing here writes to Jira, and nothing
here invents data: if no snapshot is given, no live report is written.
"""
from __future__ import annotations

from collections import Counter
from datetime import date

from . import config as c
from .models import Dataset

STAGE_BY_LABEL = {c.stage_label(s): s for s in c.STATUS_ORDER}
JIRA_OPEN = {"Idea", "To Do", "In Review", "In Progress"}


def _ksort(keys) -> list[str]:
    return sorted(keys, key=lambda k: (k.split("-")[0], int(k.split("-")[1]) if k.split("-")[-1].isdigit() else 0))


def ext_id(issue: dict) -> str:
    return next((l.upper() for l in issue.get("labels", []) if l.startswith("orion-req-")), "")


def stage_of(issue: dict) -> str | None:
    stages = [STAGE_BY_LABEL[l] for l in issue.get("labels", []) if l in STAGE_BY_LABEL]
    return stages[0] if len(stages) == 1 else None


def live_view(snapshot: dict, today: date) -> dict:
    """Operational figures computed from the snapshot alone (portfolio issues only)."""
    issues = [i for i in snapshot["issues"] if c.PORTFOLIO_LABEL in i.get("labels", [])]
    open_issues = [i for i in issues if i.get("status") in JIRA_OPEN]
    has = lambda i, label: label in i.get("labels", [])
    overdue = [i for i in open_issues if i.get("duedate") and date.fromisoformat(i["duedate"]) < today]
    return dict(
        source=snapshot.get("source", "unknown"), taken_at=snapshot.get("taken_at", "unknown"), jql=snapshot.get("jql", ""),
        total=len(issues), open=len(open_issues),
        by_status=dict(Counter(i.get("status") for i in issues)),
        by_stage=dict(Counter(stage_of(i) or "NO SINGLE STAGE LABEL" for i in issues)),
        overdue=_ksort(i["key"] for i in overdue), unassigned=_ksort(i["key"] for i in open_issues if not i.get("assignee")),
        blocked=_ksort(i["key"] for i in open_issues if has(i, "blocked")),
        ready_for_decision=_ksort(i["key"] for i in issues if has(i, c.stage_label(c.READY_FOR_DECISION))),
        high_priority_open=_ksort(i["key"] for i in open_issues if i.get("priority") in ("Highest", "High")),
        stage_label_problems=_ksort(i["key"] for i in issues if stage_of(i) is None),
        status_stage_conflicts=_ksort(i["key"] for i in issues if stage_of(i) and c.STATUS_TO_JIRA[stage_of(i)] != i.get("status")),
        issues={i["key"]: i for i in issues})


def drift(ds: Dataset, snapshot: dict) -> list[dict]:
    """Lifecycle differences between Jira (truth for lifecycle) and the reporting dataset."""
    out = []
    by_ext = {ext_id(i): i for i in snapshot["issues"] if ext_id(i)}
    for d in ds.demands:
        issue = by_ext.get(d.external_id)
        if issue is None:
            out.append(dict(external_id=d.external_id, key="", field="coverage", dataset="in dataset", jira="no issue in snapshot"))
            continue
        stage = stage_of(issue)
        pairs = [("lifecycle stage", c.STATUS_LABEL[d.status], c.STATUS_LABEL[stage] if stage else "no single stage label"),
                 ("due date", d.due_at.isoformat() if d.due_at else None, issue.get("duedate")),
                 ("owner", "assigned" if (d.triage_owner or not d.is_open) else "unassigned", "assigned" if issue.get("assignee") else "unassigned"),
                 ("blocked", "yes" if d.blocked else "no", "yes" if "blocked" in issue.get("labels", []) else "no")]
        out += [dict(external_id=d.external_id, key=issue["key"], field=f, dataset=a, jira=b) for f, a, b in pairs if a != b]
    known = {d.external_id for d in ds.demands}
    out += [dict(external_id=e, key=i["key"], field="coverage", dataset="not in dataset", jira="issue exists") for e, i in sorted(by_ext.items()) if e not in known]
    return out


def live_report(ds: Dataset, snapshot: dict, today: date) -> str:
    from .reports import table
    v, diffs = live_view(snapshot, today), drift(ds, snapshot)
    keys = lambda ks: ", ".join(ks) or "none"
    stage_rows = [[c.STATUS_LABEL[s], c.STATUS_TO_JIRA[s], v["by_stage"].get(s, 0)] for s in c.STATUS_ORDER]
    lines = ["# Jira live pipeline view", "",
             f"**Data mode:** LIVE JIRA SNAPSHOT - {v['source']}  ",
             f"**Snapshot taken:** {v['taken_at']}  ", f"**Query:** `{v['jql']}`  ",
             f"**Evaluated for date:** {today.isoformat()} (overdue = due date before this date)  ",
             f"**Dataset cutoff used for the drift check:** {ds.as_of.isoformat()}", "",
             "Every figure in the first three sections is computed from the Jira snapshot only. Jira holds lifecycle facts; "
             "budget, spend and capacity are not stored in Jira and are reported from the finance and capacity ledgers in the other reports. "
             "This report reads Jira; it never writes to it.", "",
             "## Portfolio in Jira", "",
             table(["Measure", "Value", "Issues"], [
                 ["Portfolio issues", v["total"], f"label {c.PORTFOLIO_LABEL}"], ["Open (status not Done)", v["open"], ""],
                 ["Overdue", len(v["overdue"]), keys(v["overdue"])], ["Open without assignee", len(v["unassigned"]), keys(v["unassigned"])],
                 ["Blocked", len(v["blocked"]), keys(v["blocked"])], ["Ready for decision", len(v["ready_for_decision"]), keys(v["ready_for_decision"])],
                 ["Open with priority High or Highest", len(v["high_priority_open"]), keys(v["high_priority_open"])]]), "",
             "## By lifecycle stage (stage label) and Jira status", "",
             table(["Lifecycle stage", "Jira status", "Issues"], stage_rows), "",
             "## Jira data-quality checks", "",
             f"- Issues without exactly one `stage-*` label: {keys(v['stage_label_problems'])}",
             f"- Issues whose Jira status does not match their stage label: {keys(v['status_stage_conflicts'])}", "",
             "## Drift between Jira and the reporting dataset", "",
             f"Compared for all {len(ds.demands)} demands of the dataset: coverage, lifecycle stage, due date, owner assigned, blocked flag. "
             "Jira wins for these fields; a difference means the dataset export is stale or Jira was edited after the export.", ""]
    if diffs:
        lines += [table(["Demand", "Jira key", "Field", "Dataset", "Jira"], [[x["external_id"], x["key"], x["field"], x["dataset"], x["jira"]] for x in diffs]), ""]
    else:
        lines += ["**No differences.** The management reports (generated from the dataset) describe the same lifecycle state as Jira at the time of the snapshot.", ""]
    lines += ["## How to refresh", "",
              "1. `python -m infraflow jira pull --output evidence/jira_snapshot_rest.json` (read-only REST call; needs `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`).",
              "2. `python -m infraflow jira live --snapshot evidence/jira_snapshot_rest.json` writes this report; `jira reconcile --snapshot ...` writes the field-by-field comparison.",
              "3. If the drift list is not empty, correct the stale side, then regenerate the management reports with `python -m infraflow all`.", ""]
    return "\n".join(lines) + "\n"
