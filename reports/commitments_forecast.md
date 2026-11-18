# Commitments and Forecast

**Organisation:** Orion Systems Engineering (fictional)  
**Reporting date (cutoff, inclusive):** 2026-11-16  
**Data mode:** OFFLINE_FIXTURE (synthetic CSV data; not a live Jira or finance-system extract)  
**Sources:** budgets.csv, actuals.csv, commitments.csv, demands.csv  
**Currency:** EUR, budget period 2026-08 to 2026-12

> **PROVISIONAL** - 6 critical data exceptions are open. Affected rows are excluded from the totals and listed in `financial_exception_register.md`. Figures may change when they are resolved.

## Forecast at completion by cost centre

| Cost centre | Name | Budget | Actual | Open commitments | Approved, not committed | Forecast EAC | Forecast variance |
|---|---|---|---|---|---|---|---|
| CC-ENG-DATA | Engineering Data Platforms | €200,000 | €95,150 | €30,900 | €50,000 | €176,050 | -€23,950 |
| CC-ENG-SIM | Simulation and Compute | €225,000 | €169,400 | €59,400 | €0 | €228,800 | €3,800 |
| CC-DIG-INFRA | Digital Infrastructure Core | €350,000 | €197,200 | €84,250 | €0 | €281,450 | -€68,550 |
| CC-SEC-OPS | Security Operations | €175,000 | €117,200 | €45,600 | €0 | €162,800 | -€12,200 |
| CC-COLLAB | Collaboration and Workplace | €100,000 | €64,500 | €18,100 | €5,000 | €87,600 | -€12,400 |
| **Total** |  | **€1,050,000** | **€643,450** | **€238,250** | **€55,000** | **€936,700** | **-€113,300** |

## Method

- **Actual**: valid, unique invoices and credit notes dated on or before the cutoff.
- **Open commitment**: for purchase orders with status `open`, `max(approved - recognised, 0)`. The invoiced part of an order is in Actual and is not counted again.
- **Approved, not committed**: period cost of approved demands that have no purchase order yet (one-time cost plus recurring cost for the months after planned go-live).
- **Forecast EAC** = Actual + Open commitments + Approved, not committed. **Forecast variance** = EAC - budget (positive = overrun).
- This is a commitment-based scenario forecast. It assumes open orders are invoiced in full inside the period and that nothing further is approved. It is not a statistical prediction.

## Forecast reliability

| PO | Cost centre | Approved | Recognised (ledger) | Linked valid invoices | Difference | Outstanding, ledger basis (used) | Outstanding, invoice basis |
|---|---|---|---|---|---|---|---|
| PO-015 | CC-DIG-INFRA | €10,200 | €3,800 | €4,800 | €1,000 | €6,400 | €5,400 |

The forecast above uses the ledger: **€936,700**. Valued from the invoices it would be **€935,700** (-€1,000). Until Finance reconciles the order, the forecast of the affected cost centre is not reliable to that amount; the difference is a critical exception and is not netted away.

## Purchase orders

| PO | Cost centre | Demand | Approved | Recognised | Status | Outstanding | Reconciliation |
|---|---|---|---|---|---|---|---|
| PO-RUN-ENG-DATA | CC-ENG-DATA | run contract | €72,500 | €58,000 | open | €14,500 | ok |
| PO-RUN-ENG-SIM | CC-ENG-SIM | run contract | €65,000 | €52,000 | open | €13,000 | ok |
| PO-RUN-DIG-INFRA | CC-DIG-INFRA | run contract | €140,000 | €112,000 | open | €28,000 | ok |
| PO-RUN-SEC-OPS | CC-SEC-OPS | run contract | €70,000 | €56,000 | open | €14,000 | ok |
| PO-RUN-COLLAB | CC-COLLAB | run contract | €45,000 | €35,200 | open | €9,800 | ok |
| PO-001 | CC-ENG-SIM | ORION-REQ-001 | €66,800 | €64,400 | open | €2,400 | ok |
| PO-002 | CC-ENG-DATA | ORION-REQ-002 | €19,800 | €18,900 | open | €900 | ok |
| PO-003 | CC-DIG-INFRA | ORION-REQ-003 | €35,200 | €34,600 | open | €600 | ok |
| PO-004 | CC-ENG-SIM | ORION-REQ-004 | €9,000 | €9,000 | closed | €0 | ok |
| PO-005 | CC-SEC-OPS | ORION-REQ-005 | €29,200 | €28,100 | open | €1,100 | ok |
| PO-006 | CC-DIG-INFRA | ORION-REQ-006 | €7,350 | €6,900 | open | €450 | ok |
| PO-007 | CC-COLLAB | ORION-REQ-007 | €21,600 | €21,300 | open | €300 | ok |
| PO-008 | CC-SEC-OPS | ORION-REQ-008 | €15,000 | €13,500 | open | €1,500 | ok |
| PO-009 | CC-DIG-INFRA | ORION-REQ-009 | €15,800 | €15,000 | open | €800 | ok |
| PO-010 | CC-SEC-OPS | ORION-REQ-010 | €22,000 | €11,000 | open | €11,000 | ok |
| PO-011 | CC-ENG-DATA | ORION-REQ-011 | €31,000 | €15,500 | open | €15,500 | ok |
| PO-012 | CC-DIG-INFRA | ORION-REQ-012 | €44,000 | €22,000 | open | €22,000 | ok |
| PO-013 | CC-ENG-SIM | ORION-REQ-013 | €88,000 | €44,000 | open | €44,000 | ok |
| PO-014 | CC-COLLAB | ORION-REQ-014 | €16,000 | €8,000 | open | €8,000 | ok |
| PO-015 | CC-DIG-INFRA | ORION-REQ-015 | €10,200 | €3,800 | open | €6,400 | NOT RECONCILED |
| PO-016 | CC-SEC-OPS | ORION-REQ-016 | €8,000 | €4,000 | open | €4,000 | ok |
| PO-019 | CC-DIG-INFRA | ORION-REQ-019 | €26,000 | €0 | open | €26,000 | ok |
| PO-020 | CC-SEC-OPS | ORION-REQ-020 | €14,000 | €0 | open | €14,000 | ok |
| PO-9010 | CC-SEC-OPS | ORION-REQ-005 | €4,000 | €4,600 | open | €0 | ok |
| PO-9012 | CC-ENG-SIM | ORION-REQ-004 | €7,500 | €0 | cancelled | €0 | ok |

## Approved demands without a purchase order

| Demand | Cost centre | Period cost |
|---|---|---|
| ORION-REQ-022 | CC-ENG-DATA | €24,000 |
| ORION-REQ-050 | CC-ENG-DATA | €26,000 |
| ORION-REQ-021 | CC-COLLAB | €5,000 |

