# Executive Management Report - Infrastructure Demand Portfolio

**Organisation:** Orion Systems Engineering (fictional)  
**Reporting date (cutoff, inclusive):** 2026-11-16  
**Data mode:** OFFLINE_FIXTURE (synthetic CSV data; not a live Jira or finance-system extract)  
**Sources:** weekly report data set  
**Currency:** EUR, budget period 2026-08 to 2026-12

> **PROVISIONAL** - 6 critical data exceptions are open. Affected rows are excluded from the totals and listed in `financial_exception_register.md`. Figures may change when they are resolved.

## Portfolio health: AMBER

37 open demands across four sites. 9 delivered so far (median lead time 49 days, 77.8% on time). Spend is forecast at €936,700, €113,300 below the period budget, but headroom is uneven between cost centres and two delivery teams have almost no free hours before year end.

## Key figures

| Area | Figure |
|---|---|
| Current demand | 37 open, 5 new this week, 5 awaiting decision |
| Attention needed | 4 overdue, 3 blocked, 3 without owner |
| Budget (period) | €1,050,000 |
| Actual to date | €643,450 |
| Open commitments | €238,250 |
| Approved, not yet committed | €55,000 |
| Forecast at completion | €936,700 (-€113,300 vs budget) |

## Forecast risks

| Cost centre | Budget | Forecast EAC | Variance | Comment |
|---|---|---|---|---|
| CC-ENG-DATA | €200,000 | €176,050 | -€23,950 | Headroom €23,950 |
| CC-ENG-SIM | €225,000 | €228,800 | €3,800 | Overrun forecast |
| CC-DIG-INFRA | €350,000 | €281,450 | -€68,550 | Headroom €68,550 |
| CC-SEC-OPS | €175,000 | €162,800 | -€12,200 | Headroom €12,200 |
| CC-COLLAB | €100,000 | €87,600 | -€12,400 | Headroom €12,400 |

## Capacity constraints (unallocated engineer-hours)

| Team | 2026-11 | 2026-12 |
|---|---|---|
| Platform and Storage | 60 h | 120 h |
| Network and Access | 20 h | -30 h |
| Security Engineering | 10 h | 7 h |

10 demands rated High or Highest cannot be approved today because the funding, capacity, information or security gate fails.

## Decisions required

| # | Topic | Decision needed | Owner | Due |
|---|---|---|---|---|
| 1 | ORION-REQ-023 VPN access modernisation for cross-site collaboration | Cannot be approved as submitted (capacity). Decide: defer with review date, reduce scope, or reallocate. | Infrastructure Demand Board Chair | 2026-11-17 |
| 2 | ORION-REQ-027 Network segmentation for the integration lab | Cannot be approved as submitted (funding, capacity). Decide: defer with review date, reduce scope, or reallocate. | Infrastructure Demand Board Chair | 2026-11-17 |
| 3 | ORION-REQ-025 DR runbook automation and failover test environment | Approve or defer; all gates pass. | Infrastructure Demand Board Chair | 2026-11-17 |
| 4 | ORION-REQ-024 Cloud-hosted analytics pilot for test-campaign data | Cannot be approved as submitted (security review). Decide: defer with review date, reduce scope, or reallocate. | Infrastructure Demand Board Chair | 2026-11-17 |
| 5 | ORION-REQ-026 Engineering desktop virtualisation pilot Bremen | Cannot be approved as submitted (funding). Decide: defer with review date, reduce scope, or reallocate. | Infrastructure Demand Board Chair | 2026-11-17 |

## Example of the trade-off: ORION-REQ-017

Engineering Data Repository Expansion scores 82.0 (Highest). The board deferred it on 2026-11-10: Option A costs €48,000 in the period against €23,950 headroom and needs 300 h against 180 h free; Option B (€14,500, 160 h) fits but covers only part of the need and awaits data-owner sign-off. Next review 2026-12-08.

## Recommended next actions

1. Decide the demands that are Ready for Decision at the next board, using the gate results rather than the score alone.
2. Resolve the cost-centre overrun and the December over-allocation before approving further work for the affected teams.
3. Close the critical data exceptions so that the next report is no longer provisional.
4. Prepare the 2026-12-08 re-review of ORION-REQ-017: retention-class sign-off for Option B, or budget and capacity for Option A.

Figures are synthetic and come from the same data set as the weekly report, workbook and slide deck.

