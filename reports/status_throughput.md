# Status and Throughput Metrics

**Organisation:** Orion Systems Engineering (fictional)  
**Reporting date (cutoff, inclusive):** 2026-11-16  
**Data mode:** OFFLINE_FIXTURE (synthetic CSV data; not a live Jira or finance-system extract)  
**Sources:** demands.csv, status_events.csv, decisions.csv  
**Currency:** EUR, budget period 2026-08 to 2026-12

> **PROVISIONAL** - 6 critical data exceptions are open. Affected rows are excluded from the totals and listed in `financial_exception_register.md`. Figures may change when they are resolved.

## Flow

| Measure | Value | Definition |
|---|---|---|
| Completed demands | 9 | Demands with status Complete. |
| Median lead time (days) | 49 | Median calendar days from submission to completion for completed demands. |
| Median triage time (working days) | 3.0 | Median working days from submission to the first Triaged event (status history); demands never triaged are excluded. |
| On-time delivery | 77.8% | Completed demands finished on or before the required-by date / completed demands. Late: ORION-REQ-004, ORION-REQ-007 |
| Routed out | 2 | Records routed out of the demand pipeline (incidents, standard service requests). |

## Completed per month

| Month | Completed |
|---|---|
| 2026-09 | 1 |
| 2026-10 | 7 |
| 2026-11 | 1 |

## Intake per month

| Month | Requested |
|---|---|
| 2026-07 | 1 |
| 2026-08 | 5 |
| 2026-09 | 9 |
| 2026-10 | 23 |
| 2026-11 | 12 |

## Decision outcomes

| Outcome | Decisions |
|---|---|
| approved | 21 |
| deferred | 4 |
| rejected | 2 |

## Median days in current status (open demands)

| Status | Median days |
|---|---|
| Submitted | 3 |
| Needs Info | 11.0 |
| Triaged | 5 |
| Assessment | 11.0 |
| Ready for Decision | 10 |
| Deferred | 13.5 |
| Approved | 3 |
| Handoff | 4.0 |
| In Delivery | 20 |

History-based measures use `status_events.csv`; nothing is inferred from the current status alone.

