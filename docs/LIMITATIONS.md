# Limitations and assumptions

## What this project is not
- Not a production system, not deployed anywhere, not used by a real team.
- Independent portfolio project using entirely synthetic data. All organizations, personnel, infrastructure demands, financial figures, and operational scenarios are fictional. This project is not affiliated with or endorsed by any real organization and has not been deployed in production. No real company data, names, logos or internal information are used.
- No claim of compliance with ITIL, FinOps, ISO 27001 or any aerospace standard. The project uses ideas that are common in demand management and cost control.
- All people are role names. All figures are invented and tuned so that the scenarios occur.

## Jira and Confluence (Free plans)
- Decision gates are not enforced in Jira: team-managed Free projects have no workflow validators. Gates are enforced in the offline model and documented as process rules.
- Five Jira statuses carry twelve lifecycle stages; the exact stage is a label.
- Saved filters and the dashboard were created by hand in the browser (the connector used for the build cannot create them). Read live on 2026-11-18: 18 saved filters, all 16 catalogue queries present. One extra filter, "InfraFlow | Open demands without owner" (id 10010), has a wrong query (`created >= -30d`); the correct query is saved as "InfraFlow | Unassigned Demands". The filter has to be corrected or removed in Jira by hand.
- Dashboard gadget settings cannot be read through the API used; screenshots 01-04 are the evidence for the eight gadgets.
- One licensed user: the Jira assignee only shows owned / not owned; role-level ownership is in the issue description.
- Jira automation rules: none configured (not available through the connector; not verified).
- Live Jira dates are relative to "today", while reports use the fixed cutoff 2026-11-16, so live counts drift over time.

## Integration
- Live Jira and Confluence operations were executed through the authenticated Atlassian MCP connector. The Python REST client (`jira_client.py`) is tested against a fake HTTP session only; it has not been run against the live site because no API token was provided.
- The Jira snapshots in `evidence/` were transcribed from connector responses (the second one by a sub-agent of the assistant; the 16 JQL result sets and the issue count were then re-checked directly).
- A live refresh needs `jira pull` (REST, API token). That call is mock-tested only; the refresh logic itself is tested on the recorded snapshot.

## Data and calculations
- All 50 demands exist in Jira. The management reports are generated from the local dataset (CSV files), not from Jira; `jira live` and `jira reconcile` compare a recorded read of Jira with that dataset. Money and hours are not stored in Jira.
- Currencies: only EUR is totalled. No conversion rate is approved, so the one USD invoice is excluded and shown in USD. The conversion path (with an explicit rate) is unit-tested but not used by the data set.
- PO-015: the purchase-order ledger and the linked invoices differ by 1,000 EUR. The forecast uses the ledger (936,700 EUR); on invoice basis it would be 935,700 EUR. Both are reported; neither is "the" correct value until Finance reconciles the order.
- The Excel-native exercise workbook contains formulas that Excel calculates on opening; PivotTables cannot be generated and are a manual step.
- The forecast is commitment-based. It does not extrapolate run rates and is not a statistical prediction.
- The current month's budget is counted in full in "budget to date".
- Capacity ignores individual skills, part-time work and task order.
- Gates evaluate one demand at a time; combinations need the what-if function.
- Scores are analyst judgements with fixed weights.
- No holiday calendar: working days are Monday to Friday.

## Outputs and evidence
- The workbook and slide deck are generated and checked programmatically. The author opened them in Microsoft Excel and PowerPoint; screenshots 14-20 show the result. Automated tests do not render them.
- The 20 screenshots were captured by the author from a private Atlassian site. Published copies cover the account holder's name, avatar initials and the Jira space name; nothing analytical is changed. There is no public demo link.
- The Confluence decision brief heading "position at the decision" shows figures computed at the 2026-11-16 cutoff; the data set has no separate finance history for the decision day (2026-11-10).
- Jira issue creation dates are the seeding date (2026-11-17); earlier lifecycle dates appear as comments and come from the synthetic status history.
- The GitHub Actions workflow runs the same steps that pass locally in a clean environment; a run on GitHub happens only after publication.
