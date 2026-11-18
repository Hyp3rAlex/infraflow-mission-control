# Jira live pipeline view

**Data mode:** LIVE JIRA SNAPSHOT - Atlassian MCP connector read-back (searchJiraIssuesUsingJql), transcribed by the assistant  
**Snapshot taken:** 2026-11-17  
**Query:** `project = KAN AND labels = orion-demand`  
**Evaluated for date:** 2026-11-17 (overdue = due date before this date)  
**Dataset cutoff used for the drift check:** 2026-11-16

Every figure in the first three sections is computed from the Jira snapshot only. Jira holds lifecycle facts; budget, spend and capacity are not stored in Jira and are reported from the finance and capacity ledgers in the other reports. This report reads Jira; it never writes to it.

## Portfolio in Jira

| Measure | Value | Issues |
|---|---|---|
| Portfolio issues | 50 | label orion-demand |
| Open (status not Done) | 37 |  |
| Overdue | 4 | KAN-10, KAN-12, KAN-22, KAN-28 |
| Open without assignee | 3 | KAN-24, KAN-29, KAN-50 |
| Blocked | 3 | KAN-10, KAN-18, KAN-23 |
| Ready for decision | 5 | KAN-19, KAN-20, KAN-21, KAN-41, KAN-42 |
| Open with priority High or Highest | 21 | KAN-8, KAN-9, KAN-10, KAN-11, KAN-13, KAN-15, KAN-16, KAN-18, KAN-19, KAN-21, KAN-23, KAN-25, KAN-26, KAN-27, KAN-28, KAN-30, KAN-39, KAN-41, KAN-43, KAN-47, KAN-54 |

## By lifecycle stage (stage label) and Jira status

| Lifecycle stage | Jira status | Issues |
|---|---|---|
| Submitted | Idea | 3 |
| Needs Info | Idea | 4 |
| Triaged | Idea | 3 |
| Assessment | To Do | 6 |
| Ready for Decision | In Review | 5 |
| Deferred | In Review | 4 |
| Approved | In Progress | 3 |
| Handoff | In Progress | 2 |
| In Delivery | In Progress | 7 |
| Complete | Done | 9 |
| Rejected | Done | 2 |
| Routed Out | Done | 2 |

## Jira data-quality checks

- Issues without exactly one `stage-*` label: none
- Issues whose Jira status does not match their stage label: none

## Drift between Jira and the reporting dataset

Compared for all 50 demands of the dataset: coverage, lifecycle stage, due date, owner assigned, blocked flag. Jira wins for these fields; a difference means the dataset export is stale or Jira was edited after the export.

**No differences.** The management reports (generated from the dataset) describe the same lifecycle state as Jira at the time of the snapshot.

## How to refresh

1. `python -m infraflow jira pull --output evidence/jira_snapshot_rest.json` (read-only REST call; needs `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`).
2. `python -m infraflow jira live --snapshot evidence/jira_snapshot_rest.json` writes this report; `jira reconcile --snapshot ...` writes the field-by-field comparison.
3. If the drift list is not empty, correct the stale side, then regenerate the management reports with `python -m infraflow all`.

