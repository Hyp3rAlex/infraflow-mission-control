# Evidence

Records of checks against the live Atlassian site and Microsoft Office, kept so that each claim in the README can be traced.

## Records

| File | What it shows | How it was produced |
|---|---|---|
| `jira_snapshot_mcp_2026-11-17b.json` | All 50 demand issues (KAN-5..KAN-54) as stored in Jira: summary, status, priority, due date, labels, assignee | Transcribed from the Atlassian connector's JQL search response on 2026-11-17; issue count and the 16 filter result sets re-checked directly afterwards |
| `jira_snapshot_mcp_2026-11-17.json` | First seeding wave (28 issues), kept as history | Same method |
| `jql_verification_2026-11-17.json` | For each of the 16 catalogue queries: issues expected from the data set and issues returned live (16/16 match) | `scripts/record_jql_verification.py` |
| `jira_saved_filters_2026-11-18.json` | The 18 saved filters and 2 dashboards read live; comparison with the catalogue (16/16 saved, one extra filter with a wrong query) | `scripts/record_saved_filters.py` |
| `excel_desktop_native_checks_2026-11-17.json` | Values Microsoft Excel 16 calculated in the formula workbook: 27/27 check cells OK | `scripts/record_excel_calculated_checks.py` on the copy saved by Excel (the copy itself is not included) |
| `../reports/jira_consistency_report.md` | Field-by-field comparison of the snapshot with the data set: 0 differences | `python -m infraflow jira reconcile --snapshot evidence/jira_snapshot_mcp_2026-11-17b.json` |
| `../reports/jira_live_pipeline.md` | Pipeline figures computed only from the Jira snapshot, and drift against the data set: 0 | `python -m infraflow jira live --snapshot evidence/jira_snapshot_mcp_2026-11-17b.json` |

## Screenshots (`screenshots/`)

Twenty screenshots captured by the author on 2026-11-17/18: Jira dashboard (01-04), Kanban board (05), issue KAN-13 (06-07), Confluence decision brief (08-09) and weekly review (10-13), Excel workbook (14-15), and the five slides (16-20). They are presented with captions in [docs/DEMO.md](../docs/DEMO.md).

Screenshot 16 (slide 4) was recaptured by the author on 2026-11-18 after the D10 fix; it was supplied as JPEG (SHA-256 `029540e00b174ab2ae16560bc77e3c475bcc37d1e8708267ba9673ad001522e8`) and converted to PNG with identical pixels.

In the published copies, the account holder's name, avatar initials and the Jira space name are covered with flat grey blocks (27 boxes in 5 images: 02, 05, 06, 10, 13). Business content is unchanged. `screenshots/REDACTION_LOG.json` lists every box with its coordinates and the SHA-256 of each published file; the 15 other images are byte-identical to the captures.
