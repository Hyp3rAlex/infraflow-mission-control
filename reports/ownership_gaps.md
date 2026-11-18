# Ownership Gap Report

**Organisation:** Orion Systems Engineering (fictional)  
**Reporting date (cutoff, inclusive):** 2026-11-16  
**Data mode:** OFFLINE_FIXTURE (synthetic CSV data; not a live Jira or finance-system extract)  
**Sources:** demands.csv, decisions.csv  
**Currency:** EUR, budget period 2026-08 to 2026-12

> **PROVISIONAL** - 6 critical data exceptions are open. Affected rows are excluded from the totals and listed in `financial_exception_register.md`. Figures may change when they are resolved.

## Open demands without an owner (3, 8.1% of open)

| Demand | Title | Status | Site | Requested |
|---|---|---|---|---|
| ORION-REQ-031 | Wi-Fi coverage improvement hangar 3 | Assessment | Madrid | 2026-10-21 |
| ORION-REQ-041 | Archive for decommissioned programme data | Submitted | Munich | 2026-11-13 |
| ORION-REQ-044 | Dashboard hosting for programme KPIs | Submitted | Madrid | 2026-11-09 |

## Incomplete intake records (completeness 91.7%)

Demands (excluding routed-out records) with every mandatory intake field filled / all such demands.

| Demand | Title | Status | Missing fields |
|---|---|---|---|
| ORION-REQ-031 | Wi-Fi coverage improvement hangar 3 | Assessment | triage_owner |
| ORION-REQ-039 | Engineering data lake ingestion pipeline | Needs Info | cost_center |
| ORION-REQ-041 | Archive for decommissioned programme data | Submitted | triage_owner |
| ORION-REQ-044 | Dashboard hosting for programme KPIs | Submitted | triage_owner |

## Decision accountability gaps

| Record | Finding | Detail | Owner | Due |
|---|---|---|---|---|
| ORION-REQ-021 | MISSING_APPROVER | Decision DEC-021 (approved) has no authorised approver role (found: 'blank'). | Head of Digital Infrastructure | 2026-11-19 |

