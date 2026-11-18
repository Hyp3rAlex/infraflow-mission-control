# Capacity Risk Summary

**Organisation:** Orion Systems Engineering (fictional)  
**Reporting date (cutoff, inclusive):** 2026-11-16  
**Data mode:** OFFLINE_FIXTURE (synthetic CSV data; not a live Jira or finance-system extract)  
**Sources:** capacity.csv, allocations.csv, demands.csv  
**Currency:** EUR, budget period 2026-08 to 2026-12

> **PROVISIONAL** - 6 critical data exceptions are open. Affected rows are excluded from the totals and listed in `financial_exception_register.md`. Figures may change when they are resolved.

Capacity figures are synthetic planning data in engineer-hours per team and month.

## Forward capacity (cutoff month onwards)

| Team | Month | Available h | Allocated h | Remaining h | Utilisation | Approved demands in the month |
|---|---|---|---|---|---|---|
| Platform and Storage | 2026-11 | 640 | 580 | 60 | 91% | ORION-REQ-009, ORION-REQ-011, ORION-REQ-013, ORION-REQ-021, ORION-REQ-022, ORION-REQ-050 |
| Platform and Storage | 2026-12 | 480 | 360 | 120 | 75% | ORION-REQ-011, ORION-REQ-021, ORION-REQ-022, ORION-REQ-050 |
| Platform and Storage | 2027-01 | 640 | 407 | 233 | 64% | ORION-REQ-022, ORION-REQ-050 |
| Platform and Storage | 2027-02 | 640 | 353 | 287 | 55% | ORION-REQ-022 |
| Network and Access | 2026-11 | 480 | 460 | 20 | 96% | ORION-REQ-012, ORION-REQ-015, ORION-REQ-019 |
| Network and Access | 2026-12 | 360 | 390 | -30 | 108% | ORION-REQ-019 |
| Network and Access | 2027-01 | 480 | 390 | 90 | 81% | ORION-REQ-019 |
| Network and Access | 2027-02 | 480 | 400 | 80 | 83% |  |
| Security Engineering | 2026-11 | 320 | 310 | 10 | 97% | ORION-REQ-010, ORION-REQ-014, ORION-REQ-016, ORION-REQ-020 |
| Security Engineering | 2026-12 | 240 | 233 | 7 | 97% | ORION-REQ-010, ORION-REQ-014, ORION-REQ-016, ORION-REQ-020 |
| Security Engineering | 2027-01 | 320 | 230 | 90 | 72% | ORION-REQ-016 |
| Security Engineering | 2027-02 | 320 | 176 | 144 | 55% |  |

## Demands that cannot be staffed before their required date

Each demand is checked on its own against the hours that are unallocated **today** in its delivery window (cutoff month to due month). An over-allocated month counts as zero. No other pending request is assumed to be approved.

| Demand | Title | Band | Funding gate | Capacity gate |
|---|---|---|---|---|
| ORION-REQ-023 | VPN access modernisation for cross-site collaboration | Highest | pass | 280 h needed, 190 h unallocated for Network and Access in 2026-11 to 2027-02 (shortfall of 90 h). |
| ORION-REQ-027 | Network segmentation for the integration lab | Highest | FAIL | 150 h needed, 20 h unallocated for Network and Access in 2026-11 to 2026-12 (shortfall of 130 h). |
| ORION-REQ-042 | Jump-host hardening for supplier maintenance access | Highest | pass | 50 h needed, 10 h unallocated for Security Engineering in 2026-11 (shortfall of 40 h). |
| ORION-REQ-017 | Engineering Data Repository Expansion | Highest | FAIL | 300 h needed, 180 h unallocated for Platform and Storage in 2026-11 to 2026-12 (shortfall of 120 h). |
| ORION-REQ-036 | Automated certificate lifecycle management | Highest | pass | 130 h needed, 107 h unallocated for Security Engineering in 2026-11 to 2027-01 (shortfall of 23 h). |
| ORION-REQ-030 | Identity federation with a supplier tenant | High | pass | 120 h needed, 107 h unallocated for Security Engineering in 2026-11 to 2027-01 (shortfall of 13 h). |
| ORION-REQ-033 | SIEM use-case onboarding for engineering applications | High | pass | 110 h needed, 17 h unallocated for Security Engineering in 2026-11 to 2026-12 (shortfall of 93 h). |
| ORION-REQ-040 | Remote access for field test teams | High | pass | 60 h needed, 20 h unallocated for Network and Access in 2026-11 (shortfall of 40 h). |
| ORION-REQ-038 | Shared CAD data exchange zone with a partner | High | FAIL | 100 h needed, 10 h unallocated for Security Engineering in 2026-11 (shortfall of 90 h). |
| ORION-REQ-029 | Time-series database for test-bench sensors | Medium | pass | 100 h needed, 60 h unallocated for Platform and Storage in 2026-11 (shortfall of 40 h). |
| ORION-REQ-031 | Wi-Fi coverage improvement hangar 3 | Medium | pass | 90 h needed, 20 h unallocated for Network and Access in 2026-11 to 2026-12 (shortfall of 70 h). |

## What-if: approving every demand that is Ready for Decision, in score order

A simulation, not a plan: nothing is approved or written back. Each demand that fits takes the earliest unallocated hours of its team inside its delivery window; a demand that does not fit takes nothing. Later demands see what is left.

| Demand | Team | Hours needed | Window | Unallocated today | Taken by earlier approvals in this simulation | Usable for this demand | Result | Left in window afterwards |
|---|---|---|---|---|---|---|---|---|
| ORION-REQ-023 | Network and Access | 280 | 2026-11..2027-02 | 190 | 0 | 190 | shortfall 90 h | 190 |
| ORION-REQ-027 | Network and Access | 150 | 2026-11..2026-12 | 20 | 0 | 20 | shortfall 130 h | 20 |
| ORION-REQ-025 | Platform and Storage | 170 | 2026-11..2027-01 | 413 | 0 | 413 | fits | 243 |
| ORION-REQ-024 | Platform and Storage | 140 | 2026-11..2027-01 | 413 | 170 | 243 | fits | 103 |
| ORION-REQ-026 | Platform and Storage | 190 | 2026-11..2027-02 | 700 | 310 | 390 | fits | 200 |

*Unallocated today* is the figure used by the capacity gate above. *Usable for this demand* = unallocated today minus what earlier demands in this simulation took from the same window. Extra capacity can be tested with `python -m infraflow what-if <ids> --add-hours TEAM:YYYY-MM:HOURS`.

The model ignores individual skills and task ordering. It supports a board discussion; it is not a schedule.

