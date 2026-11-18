# Decision Brief - ORION-REQ-017 Engineering Data Repository Expansion

**Organisation:** Orion Systems Engineering (fictional)  
**Reporting date (cutoff, inclusive):** 2026-11-16  
**Data mode:** OFFLINE_FIXTURE (synthetic CSV data; not a live Jira or finance-system extract)  
**Sources:** demands.csv, options.csv, status_events.csv, decisions.csv, finance and capacity results  
**Currency:** EUR, budget period 2026-08 to 2026-12

> **PROVISIONAL** - 6 critical data exceptions are open. Affected rows are excluded from the totals and listed in `financial_exception_register.md`. Figures may change when they are resolved.

## Request

The encrypted engineering data repository is at 87% of capacity. The winter test campaign is expected to add about 40 TB across Munich, Toulouse, Madrid and Bremen; without more capacity, ingest stops in January.

| Field | Value |
|---|---|
| Requester | Engineering Lead Flight Test Data Engineering |
| Business owner | Head of Flight Test Data Engineering |
| Site | Munich |
| Required by | 2026-12-18 |
| Cost centre | CC-ENG-DATA |
| Delivery team | Platform and Storage |
| Priority score | 82.0 (Highest) |
| Current status | Deferred |

## History

| Date | Status | Actor (role) | Note |
|---|---|---|---|
| 2026-10-05 | Submitted | Engineering Lead Flight Test Data Engineering | Demand submitted through the intake form. |
| 2026-10-07 | Needs Info | Demand Analyst Munich | Retention classification of the new data sets and the accountable business owner are missing; question sent to requester. |
| 2026-10-14 | Triaged | Demand Analyst Munich | Requester confirmed retention class R3 (10 years) and named the Head of Flight Test Data Engineering as business owner. Intake complete. |
| 2026-10-16 | Assessment | Demand Analyst Munich | Assessment started; Solution Architect asked for two options. |
| 2026-11-03 | Ready for Decision | Solution Architect | Options A and B assessed; finance snapshot FIN-2026-11/CC-ENG-DATA and capacity snapshot CAP-2026-11/PLAT attached. |
| 2026-11-10 | Deferred | Infrastructure Demand Board Chair | Deferred to the 8 December board: Option A fails the funding and capacity gates; Option B needs data-owner sign-off. |

## Options

| Criterion | Option A: Additional managed storage | Option B: Archive and optimise existing capacity |
|---|---|---|
| One-time cost | €48,000 | €14,500 |
| Recurring cost per month | €3,200 | €600 |
| Cost inside the budget period | €48,000 | €14,500 |
| 12-month total (setup + 12 x monthly, undiscounted) | €86,400 | €21,700 |
| Delivery effort | 300 h | 160 h |
| Forecast of CC-ENG-DATA if approved | €224,050 vs budget €200,000 | €190,550 vs budget €200,000 |
| Funding gate | FAIL | pass |
| Capacity gate | FAIL - 300 h needed, 180 h unallocated for Platform and Storage in 2026-11 to 2026-12 (shortfall of 120 h). | pass - 160 h needed, 180 h unallocated for Platform and Storage in 2026-11 to 2026-12 (fits). |
| Security review | pass | pass |
| Benefit | Adds the full 40 TB requested; no change for users. | Frees an estimated 16 TB (about 40% of the request) by moving closed-campaign data to the archive tier. |
| Delivery risk | Medium: hardware lead time of about four weeks; new encrypted volumes need key-management onboarding. | Medium: depends on data owners confirming retention classes; archived data has slower retrieval. |
| Assumptions | Vendor quote valid until 31 December; rack space and power are available at Munich. | Archive tier from ORION-REQ-002 has free capacity; estimate based on a sample of three campaigns. |

Option descriptions are illustrative assumptions for a fictional environment, not statements about real infrastructure.

## Finance and capacity position at the decision

- CC-ENG-DATA forecast at completion: €176,050 against a period budget of €200,000; headroom €23,950.
- Forecast 176,050 + request 48,000 = 224,050 EUR against a budget of 200,000 EUR (overrun of 24,050 EUR).
- 300 h needed, 180 h unallocated for Platform and Storage in 2026-11 to 2026-12 (shortfall of 120 h).
- Option B: Forecast 176,050 + request 14,500 = 190,550 EUR against a budget of 200,000 EUR (within budget). 160 h needed, 180 h unallocated for Platform and Storage in 2026-11 to 2026-12 (fits).
- What-if: if 120 h of Platform and Storage run work were released in December, Option A would fit the capacity gate (300 h unallocated against 300 h); the funding gate would still fail.

## Decision

| Field | Value |
|---|---|
| Decision record | DEC-017 |
| Date | 2026-11-10 |
| Outcome | DEFERRED |
| Decided by (role) | Infrastructure Demand Board Chair |
| Rationale | Deferred to the 8 December board. Option A (additional managed storage) would push CC-ENG-DATA above its approved budget for the period and needs 300 engineer-hours where Platform and Storage has 180 available before the required date. Option B (archive and optimise) fits both gates but frees only part of the requested capacity and requires data-owner sign-off on archive retention classes, which is outstanding. No spend is authorised now. |
| Budget snapshot | FIN-2026-11/CC-ENG-DATA |
| Capacity snapshot | CAP-2026-11/PLAT |
| Follow-up owner | Demand Analyst Munich |
| Next review | 2026-12-08 |

A score of 82.0 (Highest) did not lead to approval: the score sets the order of review, the gates and a human decision determine the outcome.

## Handoff checklist (to be completed if an option is approved on re-review)

| Item | Content |
|---|---|
| Stable references | ORION-REQ-017, decision record of the approving board, Jira issue key |
| Delivery owner | Delivery Lead Platform and Storage |
| Approved option and scope | Option letter, capacity to be delivered, sites in scope |
| Cost envelope | Approved one-time and monthly amounts, cost centre, purchase order number |
| Target window | Start month, required-by date, maintenance windows |
| Prerequisites | Retention classes confirmed by data owners; security review passed; rack space or archive capacity confirmed |
| Acceptance conditions | Capacity available to users, encryption verified, backup job extended, monitoring thresholds updated |
| Risks carried into delivery | Hardware lead time (A) or slower retrieval of archived data (B) |
| Sign-off | Demand Manager (handoff complete), Delivery Lead (accepted), Business owner (acceptance at completion) |

