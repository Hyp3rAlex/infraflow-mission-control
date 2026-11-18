"""Compare the saved Jira filters (read live through the Atlassian connector on 2026-11-18 and pasted
below) with the verified JQL catalogue in jira_sync.FILTERS. Sort order is ignored; names may differ
(the owner used the prefix 'InfraFlow |'). Writes evidence/jira_saved_filters_2026-11-18.json."""
import json
import re
from pathlib import Path

from infraflow import jira_sync

LIVE = [  # id, name, jql - as returned by listJiraFilters
    ("10002", "InfraFlow | All Demands", "project = KAN AND labels = orion-demand ORDER BY priority DESC"),
    ("10004", "InfraFlow | Awaiting Decision", 'project = KAN AND labels = orion-demand AND labels = "stage-ready-for-decision" ORDER BY priority DESC'),
    ("10007", "InfraFlow | Blocked or Deferred", 'project = KAN AND labels = orion-demand AND statusCategory != Done AND labels in (blocked, "stage-deferred") ORDER BY priority DESC'),
    ("10009", "InfraFlow | Completed in the last 30 days", "project = KAN AND labels = orion-demand AND labels = stage-complete AND statusCategoryChangedDate >= -30d ORDER BY statusCategoryChangedDate DESC"),
    ("10012", "InfraFlow | High-priority open demands", "project = KAN AND labels = orion-demand AND statusCategory != Done AND priority in (Highest, High) ORDER BY priority DESC, due ASC"),
    ("10008", "InfraFlow | Management attention", "project = KAN AND labels = orion-demand AND statusCategory != Done AND (due < startOfDay() OR assignee IS EMPTY OR labels in (blocked, needs-finance-review)) ORDER BY priority DESC"),
    ("10015", "InfraFlow | Needs finance review", "project = KAN AND labels = orion-demand AND statusCategory != Done AND labels = needs-finance-review ORDER BY priority DESC"),
    ("10011", "InfraFlow | No activity for 7 days", "project = KAN AND labels = orion-demand AND statusCategory != Done AND updated <= -7d ORDER BY updated ASC"),
    ("10003", "InfraFlow | Open Demands", "project = KAN AND labels = orion-demand AND statusCategory != Done ORDER BY priority DESC, due ASC"),
    ("10010", "InfraFlow | Open demands without owner", "created >= -30d order by created DESC"),
    ("10005", "InfraFlow | Overdue Demands", "project = KAN AND labels = orion-demand AND statusCategory != Done AND due < startOfDay() ORDER BY due ASC"),
    ("10013", "InfraFlow | Pending assessment", "project = KAN AND labels = orion-demand AND labels in (stage-triaged, stage-assessment) ORDER BY due ASC"),
    ("10016", "InfraFlow | Security review pending", "project = KAN AND labels = orion-demand AND statusCategory != Done AND labels = needs-security-review ORDER BY priority DESC"),
    ("10018", "InfraFlow | Team Network and Access", "project = KAN AND labels = orion-demand AND statusCategory != Done AND labels = team-net ORDER BY due ASC"),
    ("10017", "InfraFlow | Team Platform and Storage", "project = KAN AND labels = orion-demand AND statusCategory != Done AND labels = team-plat ORDER BY due ASC"),
    ("10019", "InfraFlow | Team Security Engineering", "project = KAN AND labels = orion-demand AND statusCategory != Done AND labels = team-sec ORDER BY due ASC"),
    ("10006", "InfraFlow | Unassigned Demands", "project = KAN AND labels = orion-demand AND statusCategory != Done AND assignee IS EMPTY ORDER BY priority DESC"),
    ("10014", "InfraFlow | Waiting for requester", "project = KAN AND labels = orion-demand AND labels = stage-needs-info ORDER BY updated ASC"),
]
DASHBOARDS = [("10000", "Default dashboard"), ("10001", "InfraFlow | Demand Operations")]


def core(jql: str) -> str:
    q = re.split(r"\border by\b", jql, flags=re.I)[0]
    return " ".join(q.replace('"', "").lower().split())


catalogue = {core(jql): (key, name) for key, (name, jql, _) in jira_sync.FILTERS.items()}
rows, covered = [], set()
for fid, name, jql in LIVE:
    hit = catalogue.get(core(jql))
    if hit:
        covered.add(hit[0])
    rows.append(dict(id=fid, name=name, jql=jql, catalogue_key=hit[0] if hit else None,
                     status="matches catalogue" if hit else ("extra (all demands, not in catalogue)" if core(jql) == core(jira_sync.BASE) else "DOES NOT MATCH")))
missing = [k for k in jira_sync.FILTERS if k not in covered]
result = dict(read_on="2026-11-18", method="Atlassian connector listJiraFilters / listJiraDashboards (read-only); JQL compared without ORDER BY",
              saved_filters=len(LIVE), matching_catalogue=len(covered), catalogue_size=len(jira_sync.FILTERS), catalogue_not_saved=missing,
              mismatches=[r for r in rows if r["status"] == "DOES NOT MATCH"], filters=rows,
              dashboards=[dict(id=i, name=n) for i, n in DASHBOARDS],
              dashboard_gadgets="not readable through the connector; eight gadgets are visible in screenshots 01-04")
out = Path(__file__).resolve().parents[1] / "evidence" / "jira_saved_filters_2026-11-18.json"
out.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
print(f"{len(LIVE)} saved filters; {len(covered)}/{len(jira_sync.FILTERS)} catalogue queries saved; not saved: {missing}; mismatches: {[r['id'] + ' ' + r['name'] for r in result['mismatches']]}")
