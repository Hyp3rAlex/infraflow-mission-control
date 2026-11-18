# Budget versus Actual

**Organisation:** Orion Systems Engineering (fictional)  
**Reporting date (cutoff, inclusive):** 2026-11-16  
**Data mode:** OFFLINE_FIXTURE (synthetic CSV data; not a live Jira or finance-system extract)  
**Sources:** budgets.csv, actuals.csv  
**Currency:** EUR, budget period 2026-08 to 2026-12

> **PROVISIONAL** - 6 critical data exceptions are open. Affected rows are excluded from the totals and listed in `financial_exception_register.md`. Figures may change when they are resolved.

## Period to date by cost centre

| Cost centre | Name | Budget to date | Actual | Variance to date |
|---|---|---|---|---|
| CC-ENG-DATA | Engineering Data Platforms | €160,000 | €95,150 | -€64,850 |
| CC-ENG-SIM | Simulation and Compute | €180,000 | €169,400 | -€10,600 |
| CC-DIG-INFRA | Digital Infrastructure Core | €280,000 | €197,200 | -€82,800 |
| CC-SEC-OPS | Security Operations | €140,000 | €117,200 | -€22,800 |
| CC-COLLAB | Collaboration and Workplace | €80,000 | €64,500 | -€15,500 |
| **Total** |  | **€840,000** | **€643,450** | **-€196,550** |

Variance to date = actual - budget to date (negative = under budget). The current month's budget is counted in full although the month is not finished.

## Actual / budget per month

| Cost centre | 2026-08 | 2026-09 | 2026-10 | 2026-11 |
|---|---|---|---|---|
| CC-ENG-DATA | €14,500 / €40,000 | €14,500 / €40,000 | €32,500 / €40,000 | €33,650 / €40,000 |
| CC-ENG-SIM | €13,000 / €45,000 | €13,000 / €45,000 | €128,000 / €45,000 | €15,400 / €45,000 |
| CC-DIG-INFRA | €28,000 / €70,000 | €34,000 / €70,000 | €64,350 / €70,000 | €70,850 / €70,000 |
| CC-SEC-OPS | €14,000 / €35,000 | €14,000 / €35,000 | €68,600 / €35,000 | €20,600 / €35,000 |
| CC-COLLAB | €9,000 / €20,000 | €9,000 / €20,000 | €38,000 / €20,000 | €8,500 / €20,000 |

Allocation coverage: **99.34%** of valid EUR spend is mapped to a budgeted cost centre.

## Not included in the totals above

Each line is reported in its own currency. Amounts in different currencies are not added together.

- EUR invoice rows excluded as invalid: INV-9004 (-€1,200), INV-9008 (€3,100); €4,300 gross, €1,900 net.
- USD invoice rows excluded, not converted (no approved USD/EUR rate): INV-9006 (USD 5,000). No EUR value is assumed.
- Unmapped spend (valid EUR invoices on a cost centre without budget): €4,300 (INV-9002).
- Unreconciled purchase order PO-015: ledger shows €3,800 recognised, linked invoices total €4,800. The forecast uses the ledger and would change by -€1,000 on invoice basis.

Invoices dated after the cutoff and therefore not included: INV-9009 (€6,400).

