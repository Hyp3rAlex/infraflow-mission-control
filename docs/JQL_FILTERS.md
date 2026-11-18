# Jira filters (JQL) - definition and live verification

Checked on 2026-11-17 against project `KAN` with all 50 demands of the dataset (KAN-5..KAN-54). Every query was executed live through the Atlassian connector; the expected result is computed from the dataset by `jira_sync.expected_filter_ids` (independent of Jira).

**Result: 16 of 16 queries returned exactly the expected issues.**

All queries start with `project = KAN AND labels = orion-demand`, so the three onboarding issues (KAN-1..3) and the smoke-test issue (KAN-4) can never appear.

**Saved-filter status (read live 2026-11-18):** all 16 queries are saved as Jira filters (created by hand, with the name prefix `InfraFlow |` instead of `KAN |`) and feed the dashboard `InfraFlow | Demand Operations`. One additional filter, `InfraFlow | Open demands without owner` (id 10010), holds a wrong query; the correct query is saved as `InfraFlow | Unassigned Demands`. Record: `evidence/jira_saved_filters_2026-11-18.json`.

| Filter name | JQL | Purpose | Expected | Returned live | Match |
|---|---|---|---|---|---|
| KAN | Open demands | `project = KAN AND labels = orion-demand AND statusCategory != Done ORDER BY priority DESC, due ASC` | Working list of all open demands. | 37 | 37: KAN-8, KAN-9, KAN-10, KAN-11, KAN-12, KAN-13, KAN-14, KAN-15, KAN-16, KAN-17, KAN-18, KAN-19, KAN-20, KAN-21, KAN-22, KAN-23, KAN-24, KAN-25, KAN-26, KAN-27, KAN-28, KAN-29, KAN-30, KAN-39, KAN-40, KAN-41, KAN-42, KAN-43, KAN-44, KAN-45, KAN-46, KAN-47, KAN-48, KAN-50, KAN-51, KAN-53, KAN-54 | yes |
| KAN | Overdue open demands | `project = KAN AND labels = orion-demand AND statusCategory != Done AND due < startOfDay() ORDER BY due ASC` | Open demands past their required-by date. | 4 | 4: KAN-10, KAN-12, KAN-22, KAN-28 | yes |
| KAN | Open demands without owner | `project = KAN AND labels = orion-demand AND statusCategory != Done AND assignee IS EMPTY ORDER BY created ASC` | Ownership gaps. | 3 | 3: KAN-24, KAN-29, KAN-50 | yes |
| KAN | No activity for 7 days | `project = KAN AND labels = orion-demand AND statusCategory != Done AND updated <= -7d ORDER BY updated ASC` | Open demands nobody has touched for a week. | 0 | 0: - | yes |
| KAN | High-priority open demands | `project = KAN AND labels = orion-demand AND statusCategory != Done AND priority in (Highest, High) ORDER BY priority DESC, due ASC` | Review order for the demand board. | 21 | 21: KAN-8, KAN-9, KAN-10, KAN-11, KAN-13, KAN-15, KAN-16, KAN-18, KAN-19, KAN-21, KAN-23, KAN-25, KAN-26, KAN-27, KAN-28, KAN-30, KAN-39, KAN-41, KAN-43, KAN-47, KAN-54 | yes |
| KAN | Pending assessment | `project = KAN AND labels = orion-demand AND labels in (stage-triaged, stage-assessment) ORDER BY due ASC` | Triaged or in assessment. | 9 | 9: KAN-22, KAN-23, KAN-24, KAN-25, KAN-26, KAN-43, KAN-44, KAN-45, KAN-46 | yes |
| KAN | Ready for decision | `project = KAN AND labels = orion-demand AND labels = stage-ready-for-decision ORDER BY priority DESC` | Agenda of the next demand board. | 5 | 5: KAN-19, KAN-20, KAN-21, KAN-41, KAN-42 | yes |
| KAN | Waiting for requester | `project = KAN AND labels = orion-demand AND labels = stage-needs-info ORDER BY updated ASC` | Clarification requested from the requester. | 4 | 4: KAN-27, KAN-28, KAN-47, KAN-48 | yes |
| KAN | Needs finance review | `project = KAN AND labels = orion-demand AND statusCategory != Done AND labels = needs-finance-review ORDER BY priority DESC` | Funding gate fails or recurring cost is high. | 11 | 11: KAN-13, KAN-14, KAN-20, KAN-21, KAN-27, KAN-42, KAN-44, KAN-45, KAN-47, KAN-48, KAN-53 | yes |
| KAN | Security review pending | `project = KAN AND labels = orion-demand AND statusCategory != Done AND labels = needs-security-review ORDER BY priority DESC` | Security-sensitive demands without a passed review. | 7 | 7: KAN-20, KAN-23, KAN-25, KAN-26, KAN-27, KAN-30, KAN-53 | yes |
| KAN | Blocked or deferred | `project = KAN AND labels = orion-demand AND statusCategory != Done AND labels in (blocked, stage-deferred) ORDER BY due ASC` | Work that is not moving, with the reason in the issue. | 7 | 7: KAN-10, KAN-13, KAN-14, KAN-18, KAN-23, KAN-51, KAN-53 | yes |
| KAN | Completed in the last 30 days | `project = KAN AND labels = orion-demand AND labels = stage-complete AND statusCategoryChangedDate >= -30d ORDER BY statusCategoryChangedDate DESC` | Recently delivered demands. | 9 | 9: KAN-5, KAN-6, KAN-7, KAN-33, KAN-34, KAN-35, KAN-36, KAN-37, KAN-38 | yes |
| KAN | Team Platform and Storage | `project = KAN AND labels = orion-demand AND statusCategory != Done AND labels = team-plat ORDER BY due ASC` | Open demands of the Platform and Storage team. | 19 | 19: KAN-9, KAN-11, KAN-13, KAN-14, KAN-17, KAN-18, KAN-20, KAN-22, KAN-29, KAN-41, KAN-42, KAN-43, KAN-44, KAN-45, KAN-47, KAN-48, KAN-50, KAN-51, KAN-54 | yes |
| KAN | Team Network and Access | `project = KAN AND labels = orion-demand AND statusCategory != Done AND labels = team-net ORDER BY due ASC` | Open demands of the Network and Access team. | 8 | 8: KAN-10, KAN-12, KAN-15, KAN-19, KAN-21, KAN-24, KAN-28, KAN-46 | yes |
| KAN | Team Security Engineering | `project = KAN AND labels = orion-demand AND statusCategory != Done AND labels = team-sec ORDER BY due ASC` | Open demands of the Security Engineering team. | 10 | 10: KAN-8, KAN-16, KAN-23, KAN-25, KAN-26, KAN-27, KAN-30, KAN-39, KAN-40, KAN-53 | yes |
| KAN | Management attention | `project = KAN AND labels = orion-demand AND statusCategory != Done AND (due < startOfDay() OR assignee IS EMPTY OR labels in (blocked, needs-finance-review)) ORDER BY priority DESC` | Overdue, unowned, blocked or unfunded open demands. | 20 | 20: KAN-10, KAN-12, KAN-13, KAN-14, KAN-18, KAN-20, KAN-21, KAN-22, KAN-23, KAN-24, KAN-27, KAN-28, KAN-29, KAN-42, KAN-44, KAN-45, KAN-47, KAN-48, KAN-50, KAN-53 | yes |

Notes:
- `KAN | No activity for 7 days` returned nothing because all issues were created on the day of the check; it becomes meaningful after a week.
- `due < startOfDay()` and `updated <= -7d` are relative to the day the query runs, so live counts drift from the fixed 2026-11-16 report cutoff over time.
- `resolved` is not used: `statusCategoryChangedDate` was verified to work in this team-managed project.
- Ownership gaps use `assignee IS EMPTY`; the label `owner-missing` carries the same information for board quick filters.
