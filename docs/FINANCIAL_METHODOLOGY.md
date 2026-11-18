# Financial methodology

How budget, actual spend, commitments and the forecast are calculated, and how invalid data is treated. Implementation: `src/infraflow/finance.py` (docstring holds the same definitions). Tests: `tests/test_finance.py`, `tests/test_currency.py`.

All amounts are synthetic. Budget period 2026-08 to 2026-12; cutoff 2026-11-16 inclusive; currency EUR.

## Definitions (per cost centre)

| Term | Definition |
|---|---|
| Budget | Approved monthly budget, summed over the period (`budgets.csv`) |
| Actual | Valid, unique invoices and credit notes dated on or before the cutoff (`actuals.csv`) |
| Open commitment | For purchase orders with status `open`: max(approved commitment - recognised actual, 0). The invoiced part of an order is actual and is not counted again. Closed and cancelled orders carry no commitment |
| Approved, not committed | Period cost of approved demands without a purchase order: one-time cost + monthly cost x months after go-live inside the period |
| Forecast at completion (EAC) | Actual + open commitments + approved, not committed |
| Variance | EAC - budget (positive = over budget, negative = headroom) |

The forecast is a commitment-based scenario: it assumes open orders are invoiced in full inside the period and nothing else is approved. It is not a statistical prediction.

## Result at the cutoff

| Cost centre | Budget | Actual | Open commitments | Approved, not committed | Forecast | Variance |
|---|---:|---:|---:|---:|---:|---:|
| CC-ENG-DATA | €200,000 | €95,150 | €30,900 | €50,000 | €176,050 | -€23,950 |
| CC-ENG-SIM | €225,000 | €169,400 | €59,400 | €0 | €228,800 | **€3,800** |
| CC-DIG-INFRA | €350,000 | €197,200 | €84,250 | €0 | €281,450 | -€68,550 |
| CC-SEC-OPS | €175,000 | €117,200 | €45,600 | €0 | €162,800 | -€12,200 |
| CC-COLLAB | €100,000 | €64,500 | €18,100 | €5,000 | €87,600 | -€12,400 |
| **Total** | **€1,050,000** | **€643,450** | **€238,250** | **€55,000** | **€936,700** | **-€113,300** |

The totals are checked against values that the data generator tallies independently of the reporting code (`data/synthetic/ground_truth.json`) and against a small ledger calculated by hand inside a test.

## Validation rules

| Finding | Treatment | Severity |
|---|---|---|
| Duplicate invoice id | Counted once | Warning |
| Invalid invoice date | Excluded, listed | Critical |
| Currency other than EUR | Excluded and reported in its own currency until Finance approves a conversion rate; never added to a EUR figure | Critical |
| Zero, non-numeric or negative amount without credit-note reference | Excluded, listed | Critical |
| Cost centre without budget | Reported as unmapped spend, outside every cost-centre total | Critical |
| Purchase order: recognised amount differs from linked invoices | Ledger value used; order marked not reconciled; forecast also shown on invoice basis | Critical |
| Approval without an authorised approver | Approval treated as unconfirmed | Critical |
| Invoice after the cutoff | Not included; listed for transparency | Information |
| Spend on a demand without approval | Counted (the money is spent) and escalated | Warning |
| Forecast above budget | Reported with amount and owner | Warning |

No row is dropped silently. Every finding has a risk, a proposed action, an owner role and a due date (`reports/financial_exception_register.md`).

## The six critical exceptions in this data set

They are injected on purpose, so the reports show how the controls behave.

| Exception | Record | Effect on the figures |
|---|---|---|
| Invalid amount (negative, no credit-note reference) | INV-9004, -€1,200 | excluded |
| Invalid date | INV-9008, €3,100 | excluded |
| Unsupported currency | INV-9006, **USD 5,000** | excluded, reported in USD, not converted |
| Unknown cost centre | INV-9002, €4,300 | unmapped spend |
| Purchase order not reconciled | PO-015: ledger €3,800, invoices €4,800 | forecast €936,700 (ledger) vs €935,700 (invoice basis) |
| Approval without approver | ORION-REQ-021 | approval unconfirmed |

Excluded EUR invoices are reported as €4,300 gross (€1,900 net) and are never added to the USD amount. While any critical exception is open, every report, the workbook and every slide are marked **PROVISIONAL**, and the €113,300 headroom is described as not confirmed free funding.

## Currency rule

Only EUR is totalled. A non-EUR row is converted only with an explicit rate in `config.APPROVED_FX_RATES` (empty in this data set); the conversion is then reported as its own informational finding. Summing a mixed-currency list raises `CurrencyMixError`. Regression tests: `tests/test_currency.py`.

Related: [architecture](ARCHITECTURE.md) · [limitations](LIMITATIONS.md) · [case study](CASE_STUDY_ORION_REQ_017.md)
