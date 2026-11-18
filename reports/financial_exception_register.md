# Financial and Data Exception Register

**Organisation:** Orion Systems Engineering (fictional)  
**Reporting date (cutoff, inclusive):** 2026-11-16  
**Data mode:** OFFLINE_FIXTURE (synthetic CSV data; not a live Jira or finance-system extract)  
**Sources:** all datasets  
**Currency:** EUR, budget period 2026-08 to 2026-12

> **PROVISIONAL** - 6 critical data exceptions are open. Affected rows are excluded from the totals and listed in `financial_exception_register.md`. Figures may change when they are resolved.

**6 critical, 12 warnings, 1 informational.** Critical rows are excluded from totals or make a figure unreliable; they make the management report provisional. No row is dropped silently. The Amount column shows each amount in its own currency; non-EUR amounts are not converted.

## Critical

| Code | Record | Cost centre | Amount | Finding | Risk | Proposed action | Owner | Due |
|---|---|---|---|---|---|---|---|---|
| INVALID_AMOUNT | INV-9004 | CC-DIG-INFRA | -€1,200 | Negative amount without a credit-note reference; row excluded. | Row is excluded; totals may be wrong in either direction. | Check the source document; re-enter as a credit note with reference if it is a credit. | Finance Controller | 2026-11-19 |
| INVALID_DATE | INV-9008 | CC-ENG-SIM | €3,100 | Invoice date '2026-13-45' is not a valid date; row excluded. | Amount cannot be assigned to a period; actuals may be understated. | Correct the invoice date in the source ledger and re-run the report. | Finance Controller | 2026-11-19 |
| MISSING_APPROVER | ORION-REQ-021 | CC-COLLAB | €5,000 | Decision DEC-021 (approved) has no authorised approver role (found: 'blank'). | An approval exists without an accountable approver; the decision is not auditable. | Confirm who approved and complete the decision record; until then treat the approval as unconfirmed. | Head of Digital Infrastructure | 2026-11-19 |
| PO_RECONCILIATION_MISMATCH | PO-015 | CC-DIG-INFRA | €1,000 | Ledger shows 3,800 EUR recognised, linked valid invoices total 4,800 EUR. | Open commitment and forecast are wrong by the difference. | Reconcile the purchase order ledger with the invoices and correct the recognised amount. | Finance Controller | 2026-11-19 |
| UNKNOWN_COST_CENTER | INV-9002 | CC-UNKNOWN-99 | €4,300 | Cost centre 'CC-UNKNOWN-99' has no budget; amount is reported as unmapped spend. | Spend is not allocated to any budget; cost-centre totals are incomplete. | Assign the invoice to a valid cost centre. | Finance Controller | 2026-11-19 |
| UNSUPPORTED_CURRENCY | INV-9006 | CC-SEC-OPS | USD 5,000 (not converted) | Amount is in 'USD' and no approved conversion rate to EUR exists; row excluded and reported in USD, not added to any EUR figure. | Amount is excluded; actuals may be understated. | Provide the EUR value booked in the ledger or an approved conversion rate. | Finance Controller | 2026-11-19 |

## Warnings

| Code | Record | Cost centre | Amount | Finding | Risk | Proposed action | Owner | Due |
|---|---|---|---|---|---|---|---|---|
| CAPACITY_OVERALLOCATED | NET/2026-12 |  |  | Network and Access is allocated 390 h against 360 h available (30 h over). Approved demands in this month: ORION-REQ-019. | Committed delivery dates are at risk; the team is promised more hours than it has. | Re-plan with the delivery lead: move a start date, release run work, or defer one approved demand. | Head of Digital Infrastructure | 2026-11-23 |
| DUPLICATE_INVOICE | INV-0021 | CC-ENG-SIM | €62,000 | Invoice id INV-0021 appears more than once; counted once. | Spend would be overstated if both rows were counted. | Confirm with accounts payable which row is valid and remove the duplicate from the ledger export. | Finance Controller | 2026-11-23 |
| FORECAST_OVERRUN | CC-ENG-SIM | CC-ENG-SIM | €3,800 | Forecast at completion 228,800 EUR exceeds the period budget of 225,000 EUR. | Cost centre is forecast to exceed its approved budget. | Decide: defer uncommitted work, reallocate budget from a cost centre with headroom, or request a budget increase. | Head of Digital Infrastructure | 2026-11-23 |
| INVALID_TRANSITION | ORION-REQ-044 |  |  | EVT-0248: transition SUBMITTED -> ASSESSMENT is not allowed. | Status history skips a control step. | Correct the history entry or repeat the skipped step. | Demand Manager | 2026-11-23 |
| MISSING_COST_CENTER | ORION-REQ-039 |  |  | Cost centre '' is missing or has no budget. | Cost cannot be checked against a budget; the funding gate is unavailable. | Ask the requester for the funding cost centre. | Demand Manager | 2026-11-23 |
| MISSING_OWNER | ORION-REQ-031 |  |  | Open demand in status Assessment has no assigned owner. | Nobody is accountable for moving the demand forward. | Assign a demand analyst. | Demand Manager | 2026-11-18 |
| MISSING_OWNER | ORION-REQ-041 |  |  | Open demand in status Submitted has no assigned owner. | Nobody is accountable for moving the demand forward. | Assign a demand analyst. | Demand Manager | 2026-11-18 |
| MISSING_OWNER | ORION-REQ-044 |  |  | Open demand in status Submitted has no assigned owner. | Nobody is accountable for moving the demand forward. | Assign a demand analyst. | Demand Manager | 2026-11-18 |
| MISSING_REFERENCE | INV-9007 | CC-DIG-INFRA | €1,900 | Invoice refers to demand 'ORION-REQ-999', which does not exist. | Spend cannot be traced to a demand. | Link the invoice to the correct demand or mark it as run cost. | Demand Manager | 2026-11-23 |
| PO_OVER_RECOGNIZED | PO-9010 | CC-SEC-OPS | €600 | Recognised 4,600 EUR exceeds the approved commitment of 4,000 EUR. | More was invoiced than was approved on the purchase order. | Check for scope change; raise a purchase order amendment for approval if justified. | Head of Digital Infrastructure | 2026-11-23 |
| STATUS_MISMATCH | ORION-REQ-044 |  |  | Register says SUBMITTED, latest history entry EVT-0248 says ASSESSMENT. | Register and status history disagree; counts by status may be wrong. | Confirm the true status with the owner and correct the wrong source. | Demand Manager | 2026-11-19 |
| UNAPPROVED_SPEND | INV-9003 | CC-ENG-DATA | €2,750 | Spend booked on ORION-REQ-028 without an approval decision at the invoice date. | Money was spent before a funding decision; the approval control was bypassed. | Clarify who ordered the work; bring the demand to the next board or reverse the booking. | Head of Digital Infrastructure | 2026-11-19 |

## Informational

| Code | Record | Cost centre | Amount | Finding | Risk | Proposed action | Owner | Due |
|---|---|---|---|---|---|---|---|---|
| AFTER_CUTOFF | INV-9009 | CC-ENG-DATA | €6,400 | Invoice dated 2026-11-20 is after the cutoff and not included. | None for this report; the amount appears in the next period. | No action; shown for transparency. | Reporting Owner |  |

