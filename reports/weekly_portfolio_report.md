# Weekly IT Infrastructure Portfolio Report

**Organisation:** Orion Systems Engineering (fictional)  
**Reporting date (cutoff, inclusive):** 2026-11-16  
**Data mode:** OFFLINE_FIXTURE (synthetic CSV data; not a live Jira or finance-system extract)  
**Sources:** demands.csv, status_events.csv, decisions.csv, budgets.csv, actuals.csv, commitments.csv, capacity.csv, allocations.csv  
**Currency:** EUR, budget period 2026-08 to 2026-12

> **PROVISIONAL** - 6 critical data exceptions are open. Affected rows are excluded from the totals and listed in `financial_exception_register.md`. Figures may change when they are resolved.

## Executive summary

- **Demand:** 37 open demands (50 registered); 5 await a board decision, 4 are overdue, 3 blocked and 3 have no owner.
- **Money:** forecast at completion €936,700 against a period budget of €1,050,000 (€113,300 headroom overall). Overrun forecast in CC-ENG-SIM (€3,800).
- **Capacity:** over-allocation in Network and Access in 2026-12 (+30 h). The highest-scored undecided demand, ORION-REQ-023 (score 90.0), cannot be approved as submitted: capacity gate not passed.
- **ORION-REQ-017:** deferred on 2026-11-10 by the Infrastructure Demand Board Chair; next review 2026-12-08. Option A would take CC-ENG-DATA to €224,050 against €200,000 and needs 300 h where 180 h are free.
- **Data quality:** 6 critical exceptions: 2 EUR invoices excluded (€4,300 gross); USD 5,000 excluded, not converted; €4,300 unmapped; €1,000 unreconciled on PO-015. This report is provisional.

## Decisions required

| # | Topic | Decision needed | Owner | Due |
|---|---|---|---|---|
| 1 | ORION-REQ-023 VPN access modernisation for cross-site collaboration | Cannot be approved as submitted (capacity). Decide: defer with review date, reduce scope, or reallocate. | Infrastructure Demand Board Chair | 2026-11-17 |
| 2 | ORION-REQ-027 Network segmentation for the integration lab | Cannot be approved as submitted (funding, capacity). Decide: defer with review date, reduce scope, or reallocate. | Infrastructure Demand Board Chair | 2026-11-17 |
| 3 | ORION-REQ-025 DR runbook automation and failover test environment | Approve or defer; all gates pass. | Infrastructure Demand Board Chair | 2026-11-17 |

10 decisions are open in total; see `decision_action_register.md`.

## Operational health

| Measure | Value | Records |
|---|---|---|
| Open demands | 37 | see demand register |
| New in the last 7 days | 5 | ORION-REQ-035, ORION-REQ-036, ORION-REQ-041, ORION-REQ-042, ORION-REQ-043 |
| Awaiting decision | 5 | ORION-REQ-023, ORION-REQ-024, ORION-REQ-025, ORION-REQ-026, ORION-REQ-027 |
| Overdue | 4 | ORION-REQ-012, ORION-REQ-015, ORION-REQ-029, ORION-REQ-040 |
| Blocked | 3 | ORION-REQ-012, ORION-REQ-022, ORION-REQ-030 |
| Stale (no status change for 14+ days) | 8 | ORION-REQ-010, ORION-REQ-011, ORION-REQ-013, ORION-REQ-014, ORION-REQ-015, ORION-REQ-031, ORION-REQ-032, ORION-REQ-037 |
| Without owner | 3 (8.1%) | ORION-REQ-031, ORION-REQ-041, ORION-REQ-044 |
| Intake completeness | 91.7% | incomplete: ORION-REQ-031, ORION-REQ-039, ORION-REQ-041, ORION-REQ-044 |
| Completed to date | 9 | median lead time 49 days; on time 77.8% |
| Median triage time | 3.0 working days | 40 triaged demands |

## Financial status

| Cost centre | Name | Budget | Actual | Open commitments | Approved, not committed | Forecast EAC | Forecast variance |
|---|---|---|---|---|---|---|---|
| CC-ENG-DATA | Engineering Data Platforms | €200,000 | €95,150 | €30,900 | €50,000 | €176,050 | -€23,950 |
| CC-ENG-SIM | Simulation and Compute | €225,000 | €169,400 | €59,400 | €0 | €228,800 | €3,800 |
| CC-DIG-INFRA | Digital Infrastructure Core | €350,000 | €197,200 | €84,250 | €0 | €281,450 | -€68,550 |
| CC-SEC-OPS | Security Operations | €175,000 | €117,200 | €45,600 | €0 | €162,800 | -€12,200 |
| CC-COLLAB | Collaboration and Workplace | €100,000 | €64,500 | €18,100 | €5,000 | €87,600 | -€12,400 |
| **Total** |  | **€1,050,000** | **€643,450** | **€238,250** | **€55,000** | **€936,700** | **-€113,300** |

Positive forecast variance = overrun. Method and purchase-order detail: `commitments_forecast.md`.

## Capacity

| Team | 2026-11 | 2026-12 | 2027-01 | 2027-02 |
|---|---|---|---|---|
| Platform and Storage | 60 h free (91% allocated) | 120 h free (75% allocated) | 233 h free (64% allocated) | 287 h free (55% allocated) |
| Network and Access | 20 h free (96% allocated) | 30 h OVER (108% allocated) | 90 h free (81% allocated) | 80 h free (83% allocated) |
| Security Engineering | 10 h free (97% allocated) | 7 h free (97% allocated) | 90 h free (72% allocated) | 144 h free (55% allocated) |

10 High or Highest demands cannot be approved today because a gate fails; see `capacity_risk_summary.md` and `demand_pipeline.md`.

## Data quality caveats

- **INVALID_AMOUNT** INV-9004: Negative amount without a credit-note reference; row excluded.
- **INVALID_DATE** INV-9008: Invoice date '2026-13-45' is not a valid date; row excluded.
- **MISSING_APPROVER** ORION-REQ-021: Decision DEC-021 (approved) has no authorised approver role (found: 'blank').
- **PO_RECONCILIATION_MISMATCH** PO-015: Ledger shows 3,800 EUR recognised, linked valid invoices total 4,800 EUR.
- **UNKNOWN_COST_CENTER** INV-9002: Cost centre 'CC-UNKNOWN-99' has no budget; amount is reported as unmapped spend.
- **UNSUPPORTED_CURRENCY** INV-9006: Amount is in 'USD' and no approved conversion rate to EUR exists; row excluded and reported in USD, not added to any EUR figure.

Amounts outside the EUR totals are itemised per currency in `budget_vs_actual.md`; currencies are never added together.

Known: everything computed from valid rows. Unknown: the correct value of the excluded rows. Assumed: open purchase orders are invoiced in full inside the period.

## Owner / action / date (next 7 days)

| Reference | Action | Owner | Due |
|---|---|---|---|
| ORION-REQ-031 | Assign a demand analyst. | Demand Manager | 2026-11-18 |
| ORION-REQ-041 | Assign a demand analyst. | Demand Manager | 2026-11-18 |
| ORION-REQ-044 | Assign a demand analyst. | Demand Manager | 2026-11-18 |
| INV-9002 | Assign the invoice to a valid cost centre. | Finance Controller | 2026-11-19 |
| INV-9003 | Clarify who ordered the work; bring the demand to the next board or reverse the booking. | Head of Digital Infrastructure | 2026-11-19 |
| INV-9004 | Check the source document; re-enter as a credit note with reference if it is a credit. | Finance Controller | 2026-11-19 |
| INV-9006 | Provide the EUR value booked in the ledger or an approved conversion rate. | Finance Controller | 2026-11-19 |
| INV-9008 | Correct the invoice date in the source ledger and re-run the report. | Finance Controller | 2026-11-19 |
| ORION-REQ-012 | Overdue since 2026-11-13: agree a new date with the requester or escalate. | Delivery Lead Network and Access | 2026-11-19 |
| ORION-REQ-015 | Overdue since 2026-11-09: agree a new date with the requester or escalate. | Delivery Lead Network and Access | 2026-11-19 |
| ORION-REQ-021 | Confirm who approved and complete the decision record; until then treat the approval as unconfirmed. | Head of Digital Infrastructure | 2026-11-19 |
| ORION-REQ-029 | Overdue since 2026-11-10: agree a new date with the requester or escalate. | Demand Analyst Munich | 2026-11-19 |
| ORION-REQ-040 | Overdue since 2026-11-06: agree a new date with the requester or escalate. | Demand Analyst Bremen | 2026-11-19 |
| PO-015 | Reconcile the purchase order ledger with the invoices and correct the recognised amount. | Finance Controller | 2026-11-19 |
| CC-ENG-SIM | Decide: defer uncommitted work, reallocate budget from a cost centre with headroom, or request a budget increase. | Head of Digital Infrastructure | 2026-11-23 |
| NET/2026-12 | Re-plan with the delivery lead: move a start date, release run work, or defer one approved demand. | Head of Digital Infrastructure | 2026-11-23 |
| ORION-REQ-012 | Clear blocker: Waiting for the vendor's corrected firmware release; maintenance window cannot be booked until it is published. | Delivery Lead Network and Access | 2026-11-23 |
| ORION-REQ-022 | Clear blocker: Depends on ORION-REQ-011: the target database platform is being upgraded and cannot take new schemas until that work completes. | Demand Analyst Madrid | 2026-11-23 |
| ORION-REQ-030 | Clear blocker: Supplier contract amendment covering identity federation is not signed; legal review is pending. | Demand Analyst Toulouse | 2026-11-23 |
| ORION-REQ-037 | Requester to supply the missing intake information; close the demand if no reply by the due date. | Engineering Lead Structures Simulation | 2026-11-23 |
| ORION-REQ-038 | Requester to supply the missing intake information; close the demand if no reply by the due date. | Engineering Lead Manufacturing Engineering | 2026-11-23 |
| ORION-REQ-039 | Requester to supply the missing intake information; close the demand if no reply by the due date. | Engineering Lead Flight Test Data Engineering | 2026-11-23 |
| ORION-REQ-040 | Requester to supply the missing intake information; close the demand if no reply by the due date. | Engineering Lead Flight Test Data Engineering | 2026-11-23 |

## Methodology and cutoff

- Cutoff 2026-11-16 inclusive; later records are ignored and listed where relevant.
- Sources of truth: demand register and status history (lifecycle), finance ledgers (money), capacity table (hours), decision log (decisions). This report is a derived snapshot.
- KPI definitions are listed in `report_facts.json` together with the record ids behind each value.
- All data is synthetic.

