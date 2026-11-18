# Demand Pipeline Statistics

**Organisation:** Orion Systems Engineering (fictional)  
**Reporting date (cutoff, inclusive):** 2026-11-16  
**Data mode:** OFFLINE_FIXTURE (synthetic CSV data; not a live Jira or finance-system extract)  
**Sources:** demands.csv, status_events.csv  
**Currency:** EUR, budget period 2026-08 to 2026-12

> **PROVISIONAL** - 6 critical data exceptions are open. Affected rows are excluded from the totals and listed in `financial_exception_register.md`. Figures may change when they are resolved.

## Pipeline by status

| Status | Count |
|---|---|
| Submitted | 3 |
| Needs Info | 4 |
| Triaged | 3 |
| Assessment | 6 |
| Ready for Decision | 5 |
| Deferred | 4 |
| Approved | 3 |
| Handoff | 2 |
| In Delivery | 7 |
| Complete | 9 |
| Rejected | 2 |
| Routed Out | 2 |

Open demands: **37** of 50 registered. Intake in the last 7 days: **5** (ORION-REQ-035, ORION-REQ-036, ORION-REQ-041, ORION-REQ-042, ORION-REQ-043).

## Open demands by priority band, site and team

| Priority band | Open |
|---|---|
| Highest | 10 |
| High | 11 |
| Medium | 12 |
| Low | 3 |
| Lowest | 1 |

| Site | Open |
|---|---|
| Bremen | 7 |
| Madrid | 8 |
| Munich | 13 |
| Toulouse | 9 |

| Team | Open |
|---|---|
| Platform and Storage | 19 |
| Network and Access | 8 |
| Security Engineering | 10 |

## Review queue (undecided and deferred demands, highest score first)

The score orders the queue. It does not approve anything; the gates show what would stop an approval today.

| Demand | Status | Score | Band | Info | Funding | Capacity | Security | Advice to the board |
|---|---|---|---|---|---|---|---|---|
| ORION-REQ-023 VPN access modernisation for cross-site collaboration | Ready for Decision | 90.0 | Highest | pass | pass | FAIL | pass | Not approvable as submitted: capacity gate not passed. Options: defer, reduce scope, reallocate, or record an explicit exception. |
| ORION-REQ-027 Network segmentation for the integration lab | Ready for Decision | 85.0 | Highest | pass | FAIL | FAIL | pass | Not approvable as submitted: funding, capacity gates not passed. Options: defer, reduce scope, reallocate, or record an explicit exception. |
| ORION-REQ-042 Jump-host hardening for supplier maintenance access | Submitted | 82.0 | Highest | pass | pass | FAIL | FAIL | Not approvable as submitted: capacity, security review gates not passed. Options: defer, reduce scope, reallocate, or record an explicit exception. |
| ORION-REQ-017 Engineering Data Repository Expansion | Deferred | 82.0 | Highest | pass | FAIL | FAIL | pass | Not approvable as submitted: funding, capacity gates not passed. Options: defer, reduce scope, reallocate, or record an explicit exception. |
| ORION-REQ-036 Automated certificate lifecycle management | Triaged | 80.0 | Highest | pass | pass | FAIL | FAIL | Not approvable as submitted: capacity, security review gates not passed. Options: defer, reduce scope, reallocate, or record an explicit exception. |
| ORION-REQ-025 DR runbook automation and failover test environment | Ready for Decision | 80.0 | Highest | pass | pass | pass | pass | Eligible for an approval decision: all gates pass. |
| ORION-REQ-030 Identity federation with a supplier tenant | Assessment | 75.0 | High | pass | pass | FAIL | FAIL | Not approvable as submitted: capacity, security review gates not passed. Options: defer, reduce scope, reallocate, or record an explicit exception. |
| ORION-REQ-033 SIEM use-case onboarding for engineering applications | Assessment | 73.0 | High | pass | pass | FAIL | FAIL | Not approvable as submitted: capacity, security review gates not passed. Options: defer, reduce scope, reallocate, or record an explicit exception. |
| ORION-REQ-040 Remote access for field test teams | Needs Info | 72.0 | High | FAIL | pass | FAIL | pass | Not approvable as submitted: information, capacity gates not passed. Options: defer, reduce scope, reallocate, or record an explicit exception. |
| ORION-REQ-038 Shared CAD data exchange zone with a partner | Needs Info | 72.0 | High | FAIL | FAIL | FAIL | FAIL | Not approvable as submitted: information, funding, capacity, security review gates not passed. Options: defer, reduce scope, reallocate, or record an explicit exception. |
| ORION-REQ-037 High-memory nodes for structural optimisation jobs | Needs Info | 65.0 | High | FAIL | FAIL | pass | pass | Not approvable as submitted: information, funding gates not passed. Options: defer, reduce scope, reallocate, or record an explicit exception. |
| ORION-REQ-028 Object storage for satellite test imagery | Assessment | 65.0 | High | pass | pass | pass | pass | Eligible for an approval decision: all gates pass. |
| ORION-REQ-032 Container platform for engineering tools | Assessment | 63.0 | Medium | pass | pass | pass | pass | Eligible for an approval decision: all gates pass. |
| ORION-REQ-034 Hosting for the model-based systems engineering tool | Triaged | 63.0 | Medium | pass | FAIL | pass | pass | Not approvable as submitted: funding gate not passed. Options: defer, reduce scope, reallocate, or record an explicit exception. |
| ORION-REQ-049 Quantum-safe VPN cryptography evaluation lab | Deferred | 61.0 | Medium | pass | FAIL | pass | FAIL | Not approvable as submitted: funding, security review gates not passed. Options: defer, reduce scope, reallocate, or record an explicit exception. |
| ORION-REQ-024 Cloud-hosted analytics pilot for test-campaign data | Ready for Decision | 60.0 | Medium | pass | pass | pass | FAIL | Not approvable as submitted: security review gate not passed. Options: defer, reduce scope, reallocate, or record an explicit exception. |
| ORION-REQ-018 GPU nodes for CFD post-processing | Deferred | 60.0 | Medium | pass | FAIL | pass | pass | Not approvable as submitted: funding gate not passed. Options: defer, reduce scope, reallocate, or record an explicit exception. |
| ORION-REQ-045 Tape library retirement and media migration | Deferred | 60.0 | Medium | pass | pass | pass | pass | Eligible for an approval decision: all gates pass. |
| ORION-REQ-029 Time-series database for test-bench sensors | Assessment | 55.0 | Medium | pass | pass | FAIL | pass | Not approvable as submitted: capacity gate not passed. Options: defer, reduce scope, reallocate, or record an explicit exception. |
| ORION-REQ-026 Engineering desktop virtualisation pilot Bremen | Ready for Decision | 55.0 | Medium | pass | FAIL | pass | pass | Not approvable as submitted: funding gate not passed. Options: defer, reduce scope, reallocate, or record an explicit exception. |
| ORION-REQ-031 Wi-Fi coverage improvement hangar 3 | Assessment | 52.0 | Medium | FAIL | pass | FAIL | pass | Not approvable as submitted: information, capacity gates not passed. Options: defer, reduce scope, reallocate, or record an explicit exception. |
| ORION-REQ-039 Engineering data lake ingestion pipeline | Needs Info | 48.0 | Medium | FAIL | unavailable | pass | pass | Not approvable as submitted: information, funding gates not passed. Options: defer, reduce scope, reallocate, or record an explicit exception. |
| ORION-REQ-041 Archive for decommissioned programme data | Submitted | 40.0 | Low | FAIL | pass | pass | pass | Not approvable as submitted: information gate not passed. Options: defer, reduce scope, reallocate, or record an explicit exception. |
| ORION-REQ-044 Dashboard hosting for programme KPIs | Submitted | 38.0 | Low | FAIL | pass | pass | pass | Not approvable as submitted: information gate not passed. Options: defer, reduce scope, reallocate, or record an explicit exception. |
| ORION-REQ-035 Printer and plotter fleet consolidation | Triaged | 20.0 | Lowest | pass | pass | pass | pass | Eligible for an approval decision: all gates pass. |

## Definitions

- **open_demands**: Records whose status is not Complete, Rejected or Routed Out.
- **open_by_priority**: Open demands per priority band derived from the weighted score.
- **intake_last_7_days**: Records requested from 2026-11-10 to 2026-11-16 inclusive.
- **completeness_pct**: Demands (excluding routed-out records) with every mandatory intake field filled / all such demands.
- **approval_pending**: Demands in Ready for Decision.
