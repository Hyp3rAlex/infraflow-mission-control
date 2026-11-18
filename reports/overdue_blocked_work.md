# Overdue, Blocked and Stale Work

**Organisation:** Orion Systems Engineering (fictional)  
**Reporting date (cutoff, inclusive):** 2026-11-16  
**Data mode:** OFFLINE_FIXTURE (synthetic CSV data; not a live Jira or finance-system extract)  
**Sources:** demands.csv, status_events.csv  
**Currency:** EUR, budget period 2026-08 to 2026-12

> **PROVISIONAL** - 6 critical data exceptions are open. Affected rows are excluded from the totals and listed in `financial_exception_register.md`. Figures may change when they are resolved.

## Overdue open demands (4)

Open demands whose required-by date is before the cutoff.

| Demand | Title | Status | Due | Days overdue | Owner | Team | Blocker |
|---|---|---|---|---|---|---|---|
| ORION-REQ-012 | Core switch firmware and capacity upgrade Munich campus | In Delivery | 2026-11-13 | 3 | Demand Analyst Munich | Network and Access | Waiting for the vendor's corrected firmware release; maintenance window cannot be booked until it is published. |
| ORION-REQ-015 | Infrastructure monitoring coverage for lab networks | In Delivery | 2026-11-09 | 7 | Demand Analyst Madrid | Network and Access |  |
| ORION-REQ-029 | Time-series database for test-bench sensors | Assessment | 2026-11-10 | 6 | Demand Analyst Munich | Platform and Storage |  |
| ORION-REQ-040 | Remote access for field test teams | Needs Info | 2026-11-06 | 10 | Demand Analyst Bremen | Network and Access |  |

## Blocked open demands (3)

Open demands flagged as blocked with a recorded reason.

| Demand | Title | Status | Due | Days overdue | Owner | Team | Blocker |
|---|---|---|---|---|---|---|---|
| ORION-REQ-012 | Core switch firmware and capacity upgrade Munich campus | In Delivery | 2026-11-13 | 3 | Demand Analyst Munich | Network and Access | Waiting for the vendor's corrected firmware release; maintenance window cannot be booked until it is published. |
| ORION-REQ-022 | Oracle-to-PostgreSQL migration for the materials database | Approved | 2027-02-26 |  | Demand Analyst Madrid | Platform and Storage | Depends on ORION-REQ-011: the target database platform is being upgraded and cannot take new schemas until that work completes. |
| ORION-REQ-030 | Identity federation with a supplier tenant | Assessment | 2027-01-15 |  | Demand Analyst Toulouse | Security Engineering | Supplier contract amendment covering identity federation is not signed; legal review is pending. |

## Stale open demands (8)

Open, not deferred, and no status event for 14 days or more.

| Demand | Title | Status | Days in status | Owner |
|---|---|---|---|---|
| ORION-REQ-010 | MFA rollout for legacy engineering portals | In Delivery | 24 | Demand Analyst Munich |
| ORION-REQ-011 | Storage and performance upgrade for the test-results database | In Delivery | 20 | Demand Analyst Toulouse |
| ORION-REQ-013 | Simulation software licence renewal 2027 | In Delivery | 31 | Demand Analyst Munich |
| ORION-REQ-014 | Secure external file-exchange service for suppliers | In Delivery | 28 | Demand Analyst Bremen |
| ORION-REQ-015 | Infrastructure monitoring coverage for lab networks | In Delivery | 17 | Demand Analyst Madrid |
| ORION-REQ-031 | Wi-Fi coverage improvement hangar 3 | Assessment | 17 | UNASSIGNED |
| ORION-REQ-032 | Container platform for engineering tools | Assessment | 17 | Demand Analyst Munich |
| ORION-REQ-037 | High-memory nodes for structural optimisation jobs | Needs Info | 14 | Demand Analyst Munich |

