# Decision and Action Register

**Organisation:** Orion Systems Engineering (fictional)  
**Reporting date (cutoff, inclusive):** 2026-11-16  
**Data mode:** OFFLINE_FIXTURE (synthetic CSV data; not a live Jira or finance-system extract)  
**Sources:** decisions.csv, demands.csv, exception register  
**Currency:** EUR, budget period 2026-08 to 2026-12

> **PROVISIONAL** - 6 critical data exceptions are open. Affected rows are excluded from the totals and listed in `financial_exception_register.md`. Figures may change when they are resolved.

## Decisions required

| # | Topic | Decision needed | Decision owner | Due |
|---|---|---|---|---|
| 1 | ORION-REQ-023 VPN access modernisation for cross-site collaboration | Cannot be approved as submitted (capacity). Decide: defer with review date, reduce scope, or reallocate. | Infrastructure Demand Board Chair | 2026-11-17 |
| 2 | ORION-REQ-027 Network segmentation for the integration lab | Cannot be approved as submitted (funding, capacity). Decide: defer with review date, reduce scope, or reallocate. | Infrastructure Demand Board Chair | 2026-11-17 |
| 3 | ORION-REQ-025 DR runbook automation and failover test environment | Approve or defer; all gates pass. | Infrastructure Demand Board Chair | 2026-11-17 |
| 4 | ORION-REQ-024 Cloud-hosted analytics pilot for test-campaign data | Cannot be approved as submitted (security review). Decide: defer with review date, reduce scope, or reallocate. | Infrastructure Demand Board Chair | 2026-11-17 |
| 5 | ORION-REQ-026 Engineering desktop virtualisation pilot Bremen | Cannot be approved as submitted (funding). Decide: defer with review date, reduce scope, or reallocate. | Infrastructure Demand Board Chair | 2026-11-17 |
| 6 | CC-ENG-SIM forecast overrun | Forecast exceeds budget by €3,800. Decide: reallocate budget, defer uncommitted work, or accept the overrun. | Head of Digital Infrastructure | 2026-11-17 |
| 7 | Network and Access over-allocated in 2026-12 | 30 h more are committed than available. Decide which approved work moves. | Head of Digital Infrastructure | 2026-11-17 |
| 8 | ORION-REQ-021: missing approver | Confirm who approved and complete the decision record; until then treat the approval as unconfirmed. | Head of Digital Infrastructure | 2026-11-19 |
| 9 | INV-9003: unapproved spend | Clarify who ordered the work; bring the demand to the next board or reverse the booking. | Head of Digital Infrastructure | 2026-11-19 |
| 10 | ORION-REQ-017 Engineering Data Repository Expansion (deferred) | Re-review at the scheduled board; confirm the open follow-up items are closed before then. | Infrastructure Demand Board Chair | 2026-12-08 |

## Action register

| Reference | Type | Action | Owner | Due |
|---|---|---|---|---|
| ORION-REQ-031 | MISSING_OWNER | Assign a demand analyst. | Demand Manager | 2026-11-18 |
| ORION-REQ-041 | MISSING_OWNER | Assign a demand analyst. | Demand Manager | 2026-11-18 |
| ORION-REQ-044 | MISSING_OWNER | Assign a demand analyst. | Demand Manager | 2026-11-18 |
| INV-9002 | UNKNOWN_COST_CENTER | Assign the invoice to a valid cost centre. | Finance Controller | 2026-11-19 |
| INV-9003 | UNAPPROVED_SPEND | Clarify who ordered the work; bring the demand to the next board or reverse the booking. | Head of Digital Infrastructure | 2026-11-19 |
| INV-9004 | INVALID_AMOUNT | Check the source document; re-enter as a credit note with reference if it is a credit. | Finance Controller | 2026-11-19 |
| INV-9006 | UNSUPPORTED_CURRENCY | Provide the EUR value booked in the ledger or an approved conversion rate. | Finance Controller | 2026-11-19 |
| INV-9008 | INVALID_DATE | Correct the invoice date in the source ledger and re-run the report. | Finance Controller | 2026-11-19 |
| ORION-REQ-012 | overdue | Overdue since 2026-11-13: agree a new date with the requester or escalate. | Delivery Lead Network and Access | 2026-11-19 |
| ORION-REQ-015 | overdue | Overdue since 2026-11-09: agree a new date with the requester or escalate. | Delivery Lead Network and Access | 2026-11-19 |
| ORION-REQ-021 | MISSING_APPROVER | Confirm who approved and complete the decision record; until then treat the approval as unconfirmed. | Head of Digital Infrastructure | 2026-11-19 |
| ORION-REQ-029 | overdue | Overdue since 2026-11-10: agree a new date with the requester or escalate. | Demand Analyst Munich | 2026-11-19 |
| ORION-REQ-040 | overdue | Overdue since 2026-11-06: agree a new date with the requester or escalate. | Demand Analyst Bremen | 2026-11-19 |
| PO-015 | PO_RECONCILIATION_MISMATCH | Reconcile the purchase order ledger with the invoices and correct the recognised amount. | Finance Controller | 2026-11-19 |
| CC-ENG-SIM | FORECAST_OVERRUN | Decide: defer uncommitted work, reallocate budget from a cost centre with headroom, or request a budget increase. | Head of Digital Infrastructure | 2026-11-23 |
| NET/2026-12 | CAPACITY_OVERALLOCATED | Re-plan with the delivery lead: move a start date, release run work, or defer one approved demand. | Head of Digital Infrastructure | 2026-11-23 |
| ORION-REQ-012 | blocked | Clear blocker: Waiting for the vendor's corrected firmware release; maintenance window cannot be booked until it is published. | Delivery Lead Network and Access | 2026-11-23 |
| ORION-REQ-022 | blocked | Clear blocker: Depends on ORION-REQ-011: the target database platform is being upgraded and cannot take new schemas until that work completes. | Demand Analyst Madrid | 2026-11-23 |
| ORION-REQ-030 | blocked | Clear blocker: Supplier contract amendment covering identity federation is not signed; legal review is pending. | Demand Analyst Toulouse | 2026-11-23 |
| ORION-REQ-037 | needs info | Requester to supply the missing intake information; close the demand if no reply by the due date. | Engineering Lead Structures Simulation | 2026-11-23 |
| ORION-REQ-038 | needs info | Requester to supply the missing intake information; close the demand if no reply by the due date. | Engineering Lead Manufacturing Engineering | 2026-11-23 |
| ORION-REQ-039 | needs info | Requester to supply the missing intake information; close the demand if no reply by the due date. | Engineering Lead Flight Test Data Engineering | 2026-11-23 |
| ORION-REQ-040 | needs info | Requester to supply the missing intake information; close the demand if no reply by the due date. | Engineering Lead Flight Test Data Engineering | 2026-11-23 |
| ORION-REQ-017 | decision follow-up | Prepare re-review (DEC-017): close the conditions named in the deferral rationale. | Demand Analyst Munich | 2026-12-08 |
| ORION-REQ-018 | decision follow-up | Prepare re-review (DEC-018): close the conditions named in the deferral rationale. | Demand Analyst Toulouse | 2027-01-12 |
| ORION-REQ-045 | decision follow-up | Prepare re-review (DEC-023): close the conditions named in the deferral rationale. | Demand Analyst Munich | 2027-01-12 |
| ORION-REQ-049 | decision follow-up | Prepare re-review (DEC-026): close the conditions named in the deferral rationale. | Demand Analyst Munich | 2027-03-09 |

## Decisions taken

| Decision | Demand | Title | Date | Outcome | Approver role | Rationale | Budget snapshot | Capacity snapshot | Follow-up owner | Follow-up date |
|---|---|---|---|---|---|---|---|---|---|---|
| DEC-021 | ORION-REQ-021 | Engineering wiki search and reporting automation | 2026-11-13 | approved | **MISSING** | Approved: business case accepted; funding and capacity gates passed at the decision date. | FIN-2026-11/CC-COLLAB | CAP-2026-11/PLAT | Demand Manager | 2026-11-20 |
| DEC-022 | ORION-REQ-022 | Oracle-to-PostgreSQL migration for the materials database | 2026-11-13 | approved | Infrastructure Demand Board Chair | Approved: business case accepted; funding and capacity gates passed at the decision date. | FIN-2026-11/CC-ENG-DATA | CAP-2026-11/PLAT | Demand Manager | 2026-11-20 |
| DEC-017 | ORION-REQ-017 | Engineering Data Repository Expansion | 2026-11-10 | deferred | Infrastructure Demand Board Chair | Deferred to the 8 December board. Option A (additional managed storage) would push CC-ENG-DATA above its approved budget for the period and needs 300 engineer-hours where Platform and Storage has 180 available before the required date. Option B (archive and optimise) fits both gates but frees only part of the requested capacity and requires data-owner sign-off on archive retention classes, which is outstanding. No spend is authorised now. | FIN-2026-11/CC-ENG-DATA | CAP-2026-11/PLAT | Demand Analyst Munich | 2026-12-08 |
| DEC-019 | ORION-REQ-019 | Cross-site WAN bandwidth upgrade Madrid-Toulouse | 2026-11-10 | approved | Infrastructure Demand Board Chair | Approved: business case accepted; funding and capacity gates passed at the decision date. | FIN-2026-11/CC-DIG-INFRA | CAP-2026-11/NET | Demand Manager | 2026-11-17 |
| DEC-020 | ORION-REQ-020 | Vulnerability scanner coverage for the OT lab segment | 2026-11-06 | approved | Infrastructure Demand Board Chair | Approved: business case accepted; funding and capacity gates passed at the decision date. | FIN-2026-11/CC-SEC-OPS | CAP-2026-11/SEC | Demand Manager | 2026-11-13 |
| DEC-026 | ORION-REQ-049 | Quantum-safe VPN cryptography evaluation lab | 2026-11-06 | deferred | Infrastructure Demand Board Chair | Deferred: strategically relevant but not urgent; Security Engineering capacity is committed to MFA and directory work until March. | FIN-2026-11/CC-SEC-OPS | CAP-2026-11/SEC | Demand Analyst Munich | 2027-03-09 |
| DEC-027 | ORION-REQ-050 | Storage snapshot replication to the secondary site | 2026-11-06 | approved | Infrastructure Demand Board Chair | Approved: business case accepted; funding and capacity gates passed at the decision date. | FIN-2026-11/CC-ENG-DATA | CAP-2026-11/PLAT | Demand Manager | 2026-11-13 |
| DEC-016 | ORION-REQ-016 | Legacy LDAP directory decommission phase 1 | 2026-11-02 | approved | Infrastructure Demand Board Chair | Approved: business case accepted; funding and capacity gates passed at the decision date. | FIN-2026-11/CC-SEC-OPS | CAP-2026-11/SEC | Demand Manager | 2026-11-09 |
| DEC-012 | ORION-REQ-012 | Core switch firmware and capacity upgrade Munich campus | 2026-10-30 | approved | Infrastructure Demand Board Chair | Approved: business case accepted; funding and capacity gates passed at the decision date. | FIN-2026-10/CC-DIG-INFRA | CAP-2026-10/NET | Demand Manager | 2026-11-06 |
| DEC-023 | ORION-REQ-045 | Tape library retirement and media migration | 2026-10-30 | deferred | Infrastructure Demand Board Chair | Deferred: Platform and Storage has no free capacity before February and the library remains usable under best-effort support. | FIN-2026-10/CC-DIG-INFRA | CAP-2026-10/PLAT | Demand Analyst Munich | 2027-01-12 |
| DEC-018 | ORION-REQ-018 | GPU nodes for CFD post-processing | 2026-10-27 | deferred | Head of Digital Infrastructure | Deferred: CC-ENG-SIM is already forecast above budget after the licence renewal; request to be resubmitted with the 2027 budget. | FIN-2026-10/CC-ENG-SIM | CAP-2026-10/PLAT | Demand Analyst Toulouse | 2027-01-12 |
| DEC-025 | ORION-REQ-047 | Dedicated internet breakout for the Madrid lab | 2026-10-23 | rejected | Infrastructure Demand Board Chair | Rejected: bypassing the central proxy conflicts with the network security policy; the requester was referred to the proxy exception process. | FIN-2026-10/CC-DIG-INFRA | CAP-2026-10/NET |  |  |
| DEC-015 | ORION-REQ-015 | Infrastructure monitoring coverage for lab networks | 2026-10-22 | approved | Infrastructure Demand Board Chair | Approved: business case accepted; funding and capacity gates passed at the decision date. | FIN-2026-10/CC-DIG-INFRA | CAP-2026-10/NET | Demand Manager | 2026-10-29 |
| DEC-009 | ORION-REQ-009 | Backup policy enhancement for engineering file shares | 2026-10-20 | approved | Infrastructure Demand Board Chair | Approved: business case accepted; funding and capacity gates passed at the decision date. | FIN-2026-10/CC-DIG-INFRA | CAP-2026-10/PLAT | Demand Manager | 2026-10-27 |
| DEC-011 | ORION-REQ-011 | Storage and performance upgrade for the test-results database | 2026-10-20 | approved | Infrastructure Demand Board Chair | Approved: business case accepted; funding and capacity gates passed at the decision date. | FIN-2026-10/CC-ENG-DATA | CAP-2026-10/PLAT | Demand Manager | 2026-10-27 |
| DEC-010 | ORION-REQ-010 | MFA rollout for legacy engineering portals | 2026-10-12 | approved | Infrastructure Demand Board Chair | Approved: business case accepted; funding and capacity gates passed at the decision date. | FIN-2026-10/CC-SEC-OPS | CAP-2026-10/SEC | Demand Manager | 2026-10-19 |
| DEC-008 | ORION-REQ-008 | Central log retention extension to 12 months | 2026-10-08 | approved | Infrastructure Demand Board Chair | Approved: business case accepted; funding and capacity gates passed at the decision date. | FIN-2026-10/CC-SEC-OPS | CAP-2026-10/SEC | Demand Manager | 2026-10-15 |
| DEC-014 | ORION-REQ-014 | Secure external file-exchange service for suppliers | 2026-10-06 | approved | Infrastructure Demand Board Chair | Approved: business case accepted; funding and capacity gates passed at the decision date. | FIN-2026-10/CC-COLLAB | CAP-2026-10/SEC | Demand Manager | 2026-10-13 |
| DEC-013 | ORION-REQ-013 | Simulation software licence renewal 2027 | 2026-10-05 | approved | Head of Digital Infrastructure | Approved: business case accepted; funding and capacity gates passed at the decision date. | FIN-2026-10/CC-ENG-SIM | CAP-2026-10/PLAT | Demand Manager | 2026-10-12 |
| DEC-024 | ORION-REQ-046 | Chat-ops integration for incident bridges | 2026-10-05 | rejected | Demand Manager | Rejected at triage: the service-management tool already provides this function; no new infrastructure is required. |  |  |  |  |
| DEC-001 | ORION-REQ-001 | Simulation batch compute cluster expansion | 2026-09-23 | approved | Head of Digital Infrastructure | Approved: business case accepted; funding and capacity gates passed at the decision date. | FIN-2026-09/CC-ENG-SIM | CAP-2026-09/PLAT | Demand Manager | 2026-09-30 |
| DEC-003 | ORION-REQ-003 | Site-to-site VPN concentrator replacement Bremen | 2026-09-18 | approved | Infrastructure Demand Board Chair | Approved: business case accepted; funding and capacity gates passed at the decision date. | FIN-2026-09/CC-DIG-INFRA | CAP-2026-09/NET | Demand Manager | 2026-09-25 |
| DEC-005 | ORION-REQ-005 | Privileged access workstation rollout for administrators | 2026-09-18 | approved | Infrastructure Demand Board Chair | Approved: business case accepted; funding and capacity gates passed at the decision date. | FIN-2026-09/CC-SEC-OPS | CAP-2026-09/SEC | Demand Manager | 2026-09-25 |
| DEC-007 | ORION-REQ-007 | Meeting-room collaboration endpoints refresh Madrid | 2026-09-18 | approved | Infrastructure Demand Board Chair | Approved: business case accepted; funding and capacity gates passed at the decision date. | FIN-2026-09/CC-COLLAB | CAP-2026-09/NET | Demand Manager | 2026-09-25 |
| DEC-002 | ORION-REQ-002 | Flight-test telemetry archive tiering | 2026-09-07 | approved | Infrastructure Demand Board Chair | Approved: business case accepted; funding and capacity gates passed at the decision date. | FIN-2026-09/CC-ENG-DATA | CAP-2026-09/PLAT | Demand Manager | 2026-09-14 |
| DEC-004 | ORION-REQ-004 | Engineering licence server consolidation | 2026-08-31 | approved | Infrastructure Demand Board Chair | Approved: business case accepted; funding and capacity gates passed at the decision date. | FIN-2026-08/CC-ENG-SIM | CAP-2026-08/PLAT | Demand Manager | 2026-09-07 |
| DEC-006 | ORION-REQ-006 | PostgreSQL test environment for avionics CI | 2026-08-07 | approved | Infrastructure Demand Board Chair | Approved: business case accepted; funding and capacity gates passed at the decision date. | FIN-2026-08/CC-DIG-INFRA | CAP-2026-08/PLAT | Demand Manager | 2026-08-14 |

