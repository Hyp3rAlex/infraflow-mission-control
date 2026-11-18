"""Compare live JQL results (transcribed from the Atlassian connector on 2026-11-17) with the
results expected from the dataset, and write docs/JQL_FILTERS.md + evidence/jql_verification_2026-11-17.json.

Re-run after a new live check by editing ACTUAL. Usage: .venv/bin/python scripts/record_jql_verification.py
"""
import json
from datetime import date
from pathlib import Path

from infraflow import config as c, jira_sync
from infraflow.models import load_dataset

CHECKED_ON = date(2026, 11, 17)
# filter key -> issue numbers (KAN-n) returned by Jira, in the order Jira returned them
ACTUAL = {   # second live run on 2026-11-17, after the remaining 22 demands were created (50 demands, KAN-5..KAN-54)
    "open": [30, 11, 16, 8, 21, 13, 26, 54, 41, 19, 28, 10, 27, 9, 47, 39, 25, 23, 15, 43, 18, 12, 22, 24, 20, 40, 14, 48, 42, 51, 45, 44, 53, 50, 17, 29, 46],
    "overdue": [28, 12, 22, 10], "unassigned": [24, 29, 50], "stale": [],
    "high": [30, 11, 16, 8, 21, 13, 26, 54, 41, 19, 28, 10, 27, 9, 47, 39, 25, 23, 15, 43, 18],
    "assessment": [22, 24, 25, 26, 23, 43, 46, 45, 44], "decision": [41, 21, 19, 42, 20], "needs_info": [27, 28, 47, 48],
    "finance": [21, 13, 47, 27, 53, 48, 45, 44, 42, 20, 14], "security": [30, 26, 27, 25, 23, 53, 20],
    "blocked_deferred": [10, 13, 23, 14, 51, 18, 53], "done_recent": [38, 37, 36, 35, 34, 33, 7, 6, 5],
    "team_plat": [22, 11, 9, 47, 50, 17, 13, 20, 54, 43, 41, 29, 14, 48, 42, 51, 45, 44, 18],
    "team_net": [28, 12, 10, 24, 21, 15, 46, 19], "team_sec": [30, 27, 16, 8, 39, 25, 26, 23, 40, 53],
    "attention": [21, 13, 47, 28, 27, 23, 18, 10, 53, 48, 45, 44, 42, 24, 22, 20, 14, 12, 50, 29],
}
# Additional live checks in the same run: `project = KAN` count = 54 (KAN-1..4 excluded records + 50 demands, so no duplicates);
# `labels = orion-demand AND statusCategory = Done` returned 13 issues (KAN-5, 6, 7, 31, 32, 33-38, 49, 52).

ds = load_dataset()
payloads = jira_sync.plan(ds)
mapping = jira_sync.load_mapping()
expected = jira_sync.expected_filter_ids(payloads, CHECKED_ON)
rows, ok_all = [], True
for key, (name, jql, purpose) in jira_sync.FILTERS.items():
    exp = sorted(int(mapping[e]["key"].split("-")[1]) for e in expected[key])
    act = sorted(ACTUAL[key])
    ok = exp == act
    ok_all &= ok
    rows.append(dict(key=key, name=name, jql=jql, purpose=purpose, expected=[f"KAN-{n}" for n in exp],
                     actual=[f"KAN-{n}" for n in act], match=ok))
root = Path(__file__).resolve().parents[1]
(root / "evidence" / "jql_verification_2026-11-17.json").write_text(json.dumps(dict(
    checked_on=CHECKED_ON.isoformat(), method="Each JQL executed through the Atlassian connector (searchJiraIssuesUsingJql); keys transcribed from the responses.",
    all_match=ok_all, filters=rows), indent=1) + "\n")
md = ["# Jira filters (JQL) - definition and live verification", "",
      f"Checked on {CHECKED_ON} against project `{c.JIRA_PROJECT_KEY}` with all 50 demands of the dataset (KAN-5..KAN-54). Every query was executed live through the Atlassian connector; "
      "the expected result is computed from the dataset by `jira_sync.expected_filter_ids` (independent of Jira).", "",
      f"**Result: {sum(r['match'] for r in rows)} of {len(rows)} queries returned exactly the expected issues.**", "",
      "All queries start with `project = KAN AND labels = orion-demand`, so the three onboarding issues (KAN-1..3) and the smoke-test issue (KAN-4) can never appear.", "",
      "**Saved-filter status (read live 2026-11-18):** all 16 queries are saved as Jira filters (created by hand, with the name prefix `InfraFlow |` instead of `KAN |`) "
      "and feed the dashboard `InfraFlow | Demand Operations`. One additional filter, `InfraFlow | Open demands without owner` (id 10010), holds a wrong query; "
      "the correct query is saved as `InfraFlow | Unassigned Demands`. Record: `evidence/jira_saved_filters_2026-11-18.json`.", "",
      "| Filter name | JQL | Purpose | Expected | Returned live | Match |", "|---|---|---|---|---|---|"]
for r in rows:
    md.append(f"| {r['name']} | `{r['jql']}` | {r['purpose']} | {len(r['expected'])} | {len(r['actual'])}: {', '.join(r['actual']) or '-'} | {'yes' if r['match'] else 'NO'} |")
md += ["", "Notes:", "- `KAN | No activity for 7 days` returned nothing because all issues were created on the day of the check; it becomes meaningful after a week.",
       "- `due < startOfDay()` and `updated <= -7d` are relative to the day the query runs, so live counts drift from the fixed 2026-11-16 report cutoff over time.",
       "- `resolved` is not used: `statusCategoryChangedDate` was verified to work in this team-managed project.",
       "- Ownership gaps use `assignee IS EMPTY`; the label `owner-missing` carries the same information for board quick filters."]
(root / "docs" / "JQL_FILTERS.md").write_text("\n".join(md) + "\n")
print("all match:", ok_all)
