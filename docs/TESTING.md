# Testing and verification

## Reproduce

Python 3.12 or newer; no credentials, no network.

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q                         # full suite
.venv/bin/python -m infraflow seed                    # regenerate data/synthetic
git diff --exit-code data/synthetic                   # must print nothing: generation is byte-identical
.venv/bin/python -m infraflow all                     # reports, both workbooks, slide deck
.venv/bin/python -m infraflow jira reconcile --snapshot evidence/jira_snapshot_mcp_2026-11-17b.json   # 0 differences
.venv/bin/python -m infraflow jira live --snapshot evidence/jira_snapshot_mcp_2026-11-17b.json        # 0 drift
```

The GitHub Actions workflow `.github/workflows/python-validation.yml` runs the same install, seed, data comparison, test and build steps on every push and pull request (read-only permissions).

## Current result

**179 passed** (local run on 2026-11-18, Python 3.12, Ubuntu under WSL2). The same suite passed in a clean virtual environment built from the release candidate. A GitHub Actions run will be linked here once the repository is published; until then no CI badge is shown.

## What the tests cover

| Area | Test file | Tests | Examples of what is asserted |
|---|---|---:|---|
| Data generation | `test_generator.py` | 7 | deterministic output; anomalies present by design; no real names or e-mail addresses |
| Lifecycle controls | `test_lifecycle.py` | 23 | only allowed transitions; decisions need an authorised role and rationale; deferral needs a review date; failed security gate cannot be overridden |
| Scoring and gates | `test_scoring.py` | 17 | score formula and bands; score never approves; funding, capacity, information, security gates |
| Finance | `test_finance.py` | 31 | totals equal the independent ground truth; hand-calculated mini ledger; invoiced part of a purchase order not counted twice; invalid rows excluded and reported |
| Currency and reconciliation | `test_currency.py` | 10 | mixed-currency sums raise; USD reported in USD only; conversion only with an explicit rate; PO-015 shown as forecast uncertainty |
| Capacity | `test_capacity.py` | 16 | remaining hours; delivery window; what-if separates hours today, extra capacity and earlier hypothetical approvals |
| Data quality and KPIs | `test_quality.py`, `test_kpis.py` | 18 | exception register (6 critical, 12 warnings, 1 info); KPI values and their source record ids |
| Reports | `test_reporting.py` | 12 | provisional banner; figures in reports, facts JSON and workbook equal the ground truth |
| Office files | `test_office_charts.py`, `test_deck.py`, `test_excel_native.py` | 16 | chart XML that Excel draws without overlapping labels; chart data references; slide figures; slide layout estimate; formula checks; byte-reproducible files |
| Cross-artefact consistency | `test_cross_artifact_consistency.py` | 3 | same reference figures in facts JSON, workbook, deck, Confluence page source and e-mail; the old mixed-currency figure appears nowhere |
| Jira integration | `test_jira_client_mock.py`, `test_jira_live.py` | 26 | pagination, 401/403/429/5xx handling, dry-run by default, idempotent seeding against a fake Jira; reconciliation and drift on the recorded snapshot |

Test oracles are independent of the reporting code: `data/synthetic/ground_truth.json` is tallied inside the generator, which never imports the calculation modules, and some expectations are hand-calculated in the test itself.

## Evidence beyond the test suite

| Check | Result | Record |
|---|---|---|
| 50 Jira issues read back and compared field by field | 0 differences | `evidence/jira_snapshot_mcp_2026-11-17b.json`, `reports/jira_consistency_report.md` |
| 16 JQL queries run live | 16/16 returned exactly the expected issues | `evidence/jql_verification_2026-11-17.json`, `docs/JQL_FILTERS.md` |
| Saved filters and dashboard read live (2026-11-18) | 18 filters, all 16 catalogue queries saved; one extra filter with a wrong query | `evidence/jira_saved_filters_2026-11-18.json` |
| Excel formulas calculated by Microsoft Excel | 27/27 check cells OK | `evidence/excel_desktop_native_checks_2026-11-17.json` |
| Workbook and deck viewed in Microsoft Office | charts and slides render as intended | screenshots 14-20 in `evidence/screenshots/` |

## Not covered

- The Python REST client against the live Jira site: tested with a fake HTTP session only.
- Rendering of the Office files is not tested automatically. The author checked it in Microsoft Office, and the slide layout test is a geometric estimate.
- Jira dashboard gadgets cannot be read through the API used; the screenshots are the evidence.
