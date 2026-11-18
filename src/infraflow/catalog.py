"""Hand-authored catalogue of the 50 synthetic infrastructure demands.

The catalogue fixes what each demand is and where it stands at the reporting cutoff.
`generator.py` derives dates, status history, finance and capacity records from it.
All content is fictional.
"""
from __future__ import annotations

from . import config as c

FTD = "Flight Test Data Engineering"
SIM = "Structures Simulation"
AVS = "Avionics Software"
SIL = "Systems Integration Lab"
MFG = "Manufacturing Engineering"
SGS = "Space Systems Ground Segment"
EIA = "Engineering IT Applications"
ISO = "Information Security Office"
PMO = "PMO and Finance"

DATA, SIMC, INFRA, SECO, COLLAB = "CC-ENG-DATA", "CC-ENG-SIM", "CC-DIG-INFRA", "CC-SEC-OPS", "CC-COLLAB"


def D(n, title, cat, site, dept, cc, team, one, mon, hrs, scores, status, due, case, **kw):
    d = dict(n=n, title=title, category=cat, site=site, dept=dept, cc=cc, team=team, one_time=one,
             monthly=mon, hours=hrs, scores=scores, status=status, due=due, case=case,
             security=False, blocked=None, depends_on="", no_owner=False, request_type="demand",
             risk="", next_review="", rationale="", ni_reason="", routed_to="", sec_passed=False)
    d.update(kw)
    return d


CATALOG = [
    D(1, "Simulation batch compute cluster expansion", "compute", "Munich", SIM, SIMC, "PLAT", 62000, 2400, 220, (5, 4, 2, 5), c.COMPLETE, "2026-10-30",
      "Structural load simulations queue for up to four days; additional batch nodes cut turnaround before the Q4 design review."),
    D(2, "Flight-test telemetry archive tiering", "storage", "Toulouse", FTD, DATA, "PLAT", 18000, 900, 120, (4, 3, 3, 4), c.COMPLETE, "2026-10-16",
      "Move telemetry older than 18 months to a lower-cost tier to free primary storage for the autumn test campaign."),
    D(3, "Site-to-site VPN concentrator replacement Bremen", "network", "Bremen", SGS, INFRA, "NET", 34000, 600, 160, (4, 4, 4, 3), c.COMPLETE, "2026-10-23",
      "The Bremen concentrator reaches end of vendor support in December; replacement keeps the ground-segment link supported.", security=True),
    D(4, "Engineering licence server consolidation", "software-env", "Munich", EIA, SIMC, "PLAT", 9000, 0, 80, (3, 2, 2, 3), c.COMPLETE, "2026-09-30",
      "Three licence servers are consolidated onto one supported host to reduce patching effort and licence check-out failures."),
    D(5, "Privileged access workstation rollout for administrators", "security", "Madrid", ISO, SECO, "SEC", 27000, 1100, 140, (4, 4, 5, 4), c.COMPLETE, "2026-11-06",
      "Administrative access from general-purpose laptops was raised in the last internal audit; dedicated workstations close the finding.", security=True),
    D(6, "PostgreSQL test environment for avionics CI", "database", "Toulouse", AVS, INFRA, "PLAT", 6000, 450, 60, (3, 3, 1, 3), c.COMPLETE, "2026-09-25",
      "Avionics CI needs an isolated database environment so integration tests stop sharing the pre-production instance."),
    D(7, "Meeting-room collaboration endpoints refresh Madrid", "collaboration", "Madrid", MFG, COLLAB, "NET", 21000, 300, 70, (2, 2, 1, 2), c.COMPLETE, "2026-10-09",
      "Six rooms run endpoints without vendor updates; cross-site design reviews are regularly disrupted."),
    D(8, "Central log retention extension to 12 months", "monitoring", "Munich", ISO, SECO, "SEC", 12000, 1500, 90, (3, 3, 5, 4), c.COMPLETE, "2026-10-30",
      "Investigations currently lose evidence after 90 days; the security policy requires 12 months for engineering systems.", security=True),
    D(9, "Backup policy enhancement for engineering file shares", "backup-dr", "Bremen", SIL, INFRA, "PLAT", 15000, 800, 110, (4, 3, 5, 4), c.COMPLETE, "2026-11-13",
      "Lab file shares are backed up weekly only; daily incremental backups reduce potential data loss from seven days to one."),
    D(10, "MFA rollout for legacy engineering portals", "access", "Munich", ISO, SECO, "SEC", 22000, 950, 200, (5, 4, 5, 5), c.IN_DELIVERY, "2026-12-11",
      "Four legacy portals still accept password-only sign-in; MFA is required before the year-end access review.", security=True),
    D(11, "Storage and performance upgrade for the test-results database", "database", "Toulouse", FTD, DATA, "PLAT", 31000, 1200, 150, (4, 4, 3, 4), c.IN_DELIVERY, "2026-12-04",
      "Query times on the test-results database doubled this year; the upgrade restores reporting performance for certification evidence."),
    D(12, "Core switch firmware and capacity upgrade Munich campus", "network", "Munich", EIA, INFRA, "NET", 44000, 0, 180, (4, 3, 4, 3), c.IN_DELIVERY, "2026-11-13",
      "Core switches run firmware with known defects and have no free 10G ports for the new simulation cluster.",
      blocked="Waiting for the vendor's corrected firmware release; maintenance window cannot be booked until it is published."),
    D(13, "Simulation software licence renewal 2027", "software-env", "Munich", SIM, SIMC, "PLAT", 88000, 0, 30, (5, 5, 2, 5), c.IN_DELIVERY, "2026-11-30",
      "The structural simulation suite licence expires on 31 December; without renewal about 60 engineers lose access."),
    D(14, "Secure external file-exchange service for suppliers", "collaboration", "Bremen", SGS, COLLAB, "SEC", 16000, 1400, 130, (4, 3, 4, 4), c.IN_DELIVERY, "2026-12-18",
      "Suppliers currently receive design data by encrypted e-mail; a managed exchange service gives traceability and expiry control.", security=True),
    D(15, "Infrastructure monitoring coverage for lab networks", "monitoring", "Madrid", SIL, INFRA, "NET", 9500, 700, 100, (3, 3, 3, 3), c.IN_DELIVERY, "2026-11-09",
      "Lab network outages are reported by users before operations notice them; monitoring closes that gap."),
    D(16, "Legacy LDAP directory decommission phase 1", "migration", "Toulouse", EIA, SECO, "SEC", 8000, 0, 160, (3, 2, 4, 4), c.IN_DELIVERY, "2027-01-29",
      "Eleven applications still bind to the unsupported directory; phase 1 migrates the first five.", security=True, depends_on="ORION-REQ-010"),
    D(17, "Engineering Data Repository Expansion", "storage", "Munich", FTD, DATA, "PLAT", 48000, 3200, 300, (5, 4, 3, 4), c.DEFERRED, "2026-12-18",
      "The encrypted engineering data repository is at 87% of capacity. The winter test campaign is expected to add about 40 TB across Munich, Toulouse, Madrid and Bremen; without more capacity, ingest stops in January.",
      security=True, sec_passed=True, next_review="2026-12-08",
      ni_reason="Retention classification of the new data sets and the accountable business owner are missing.",
      rationale="Deferred to the 8 December board. Option A (additional managed storage) would push CC-ENG-DATA above its approved budget for the period and needs 300 engineer-hours where Platform and Storage has 180 available before the required date. Option B (archive and optimise) fits both gates but frees only part of the requested capacity and requires data-owner sign-off on archive retention classes, which is outstanding. No spend is authorised now.",
      risk="If neither option is approved by mid-December, ingest for the January campaign must be throttled."),
    D(18, "GPU nodes for CFD post-processing", "compute", "Toulouse", SIM, SIMC, "PLAT", 96000, 1800, 240, (4, 3, 1, 4), c.DEFERRED, "2027-01-29",
      "Post-processing of CFD results takes two working days per run; GPU nodes would reduce this to hours.",
      next_review="2027-01-12",
      rationale="Deferred: CC-ENG-SIM is already forecast above budget after the licence renewal; request to be resubmitted with the 2027 budget."),
    D(19, "Cross-site WAN bandwidth upgrade Madrid-Toulouse", "network", "Madrid", MFG, INFRA, "NET", 26000, 2800, 120, (4, 4, 2, 3), c.HANDOFF, "2027-01-15",
      "Nightly CAD replication between Madrid and Toulouse no longer completes inside the maintenance window."),
    D(20, "Vulnerability scanner coverage for the OT lab segment", "security", "Bremen", ISO, SECO, "SEC", 14000, 1300, 90, (4, 4, 5, 4), c.HANDOFF, "2026-12-11",
      "The operational-technology lab segment is not covered by scheduled vulnerability scans.", security=True),
    D(21, "Engineering wiki search and reporting automation", "collaboration", "Munich", PMO, COLLAB, "PLAT", 5000, 250, 60, (2, 2, 1, 3), c.APPROVED, "2026-12-18",
      "Weekly status reports are assembled by hand from four sources; automation saves about six hours per week."),
    D(22, "Oracle-to-PostgreSQL migration for the materials database", "migration", "Madrid", MFG, DATA, "PLAT", 24000, 0, 260, (4, 3, 3, 4), c.APPROVED, "2027-02-26",
      "The Oracle licence for the materials database ends in March; migration avoids a renewal.",
      depends_on="ORION-REQ-011",
      blocked="Depends on ORION-REQ-011: the target database platform is being upgraded and cannot take new schemas until that work completes."),
    D(23, "VPN access modernisation for cross-site collaboration", "access", "Bremen", SIL, INFRA, "NET", 38000, 1600, 280, (5, 4, 4, 5), c.READY_FOR_DECISION, "2027-02-12",
      "Engineers at all four sites use a VPN client that fails posture checks on current laptops; modernisation removes about 30 support calls per week.", security=True, sec_passed=True,
      risk="Affordable within CC-DIG-INFRA, but Network and Access cannot staff 280 hours before the requested date."),
    D(24, "Cloud-hosted analytics pilot for test-campaign data", "analytics", "Toulouse", FTD, DATA, "PLAT", 12000, 4200, 140, (4, 3, 1, 4), c.READY_FOR_DECISION, "2027-01-15",
      "A three-month pilot to test whether managed analytics shortens campaign reporting. Recurring cost and data classification need explicit review.", security=True),
    D(25, "DR runbook automation and failover test environment", "backup-dr", "Munich", EIA, INFRA, "PLAT", 19000, 900, 170, (4, 3, 5, 4), c.READY_FOR_DECISION, "2027-01-29",
      "The last failover test was manual and took 11 hours; automation makes a quarterly test realistic."),
    D(26, "Engineering desktop virtualisation pilot Bremen", "software-env", "Bremen", SGS, SIMC, "PLAT", 28000, 2100, 190, (3, 3, 2, 3), c.READY_FOR_DECISION, "2027-02-19",
      "Pilot for 25 engineers who need heavy CAD sessions from standard laptops."),
    D(27, "Network segmentation for the integration lab", "security", "Madrid", SIL, SECO, "NET", 17000, 400, 150, (4, 4, 5, 4), c.READY_FOR_DECISION, "2026-12-18",
      "Test benches share a flat network with office devices; segmentation is an open audit action.", security=True, sec_passed=True),
    D(28, "Object storage for satellite test imagery", "storage", "Bremen", SGS, DATA, "PLAT", 22000, 1500, 130, (4, 3, 2, 4), c.ASSESSMENT, "2027-01-22",
      "Imagery from thermal-vacuum tests is stored on project file shares that cannot scale.", depends_on="ORION-REQ-017"),
    D(29, "Time-series database for test-bench sensors", "database", "Munich", SIL, DATA, "PLAT", 13000, 950, 100, (3, 3, 2, 3), c.ASSESSMENT, "2026-11-10",
      "Sensor data is kept in spreadsheets per bench; a shared time-series database enables cross-bench analysis."),
    D(30, "Identity federation with a supplier tenant", "access", "Toulouse", AVS, SECO, "SEC", 9000, 700, 120, (4, 3, 4, 4), c.ASSESSMENT, "2027-01-15",
      "Supplier engineers use separate guest accounts; federation removes duplicate identities and manual off-boarding.", security=True,
      blocked="Supplier contract amendment covering identity federation is not signed; legal review is pending."),
    D(31, "Wi-Fi coverage improvement hangar 3", "network", "Madrid", MFG, INFRA, "NET", 31000, 200, 90, (3, 4, 1, 2), c.ASSESSMENT, "2026-12-11",
      "Tablets used for assembly instructions lose connection in the eastern half of hangar 3.", no_owner=True),
    D(32, "Container platform for engineering tools", "software-env", "Munich", AVS, INFRA, "PLAT", 36000, 2600, 320, (4, 2, 2, 5), c.ASSESSMENT, "2027-02-26",
      "Tool teams deploy on individually managed virtual machines; a shared container platform standardises releases."),
    D(33, "SIEM use-case onboarding for engineering applications", "security", "Munich", ISO, SECO, "SEC", 7000, 1900, 110, (3, 3, 5, 4), c.ASSESSMENT, "2026-12-18",
      "Engineering applications send no security events to the SIEM; onboarding the top ten closes a monitoring gap.", security=True),
    D(34, "Hosting for the model-based systems engineering tool", "software-env", "Toulouse", AVS, SIMC, "PLAT", 25000, 3100, 200, (4, 3, 1, 5), c.TRIAGED, "2027-02-26",
      "The MBSE tool selected by the programme needs a hosted environment for 80 users."),
    D(35, "Printer and plotter fleet consolidation", "collaboration", "Bremen", PMO, COLLAB, "NET", 8000, 0, 40, (1, 1, 1, 1), c.TRIAGED, "2027-01-29",
      "Fourteen devices of six models are consolidated to reduce consumables and support contracts."),
    D(36, "Automated certificate lifecycle management", "security", "Madrid", ISO, SECO, "SEC", 11000, 850, 130, (4, 3, 5, 4), c.TRIAGED, "2027-01-15",
      "Two outages this year were caused by expired certificates; automation removes manual renewal.", security=True),
    D(37, "High-memory nodes for structural optimisation jobs", "compute", "Munich", SIM, SIMC, "PLAT", 54000, 900, 110, (4, 4, 1, 4), c.NEEDS_INFO, "2026-12-11",
      "Optimisation jobs above 512 GB cannot run on the current cluster.",
      ni_reason="Expected number of jobs per month and the programme funding source are not stated."),
    D(38, "Shared CAD data exchange zone with a partner", "collaboration", "Toulouse", MFG, COLLAB, "SEC", 13000, 1100, 100, (4, 4, 3, 3), c.NEEDS_INFO, "2026-11-27",
      "A joint work package needs a controlled zone to exchange CAD data with a partner company.", security=True,
      ni_reason="Data classification of the exchanged CAD models and the partner's contact for the security assessment are missing."),
    D(39, "Engineering data lake ingestion pipeline", "analytics", "Madrid", FTD, "", "PLAT", 20000, 2400, 210, (3, 2, 1, 4), c.NEEDS_INFO, "2027-02-12",
      "Automated ingestion of test data into the engineering data lake to replace manual uploads.",
      ni_reason="No cost centre was provided and the data volume estimate is missing."),
    D(40, "Remote access for field test teams", "access", "Bremen", FTD, INFRA, "NET", 6000, 500, 60, (4, 5, 2, 3), c.NEEDS_INFO, "2026-11-06",
      "Field teams at the test range cannot reach the telemetry tools without a site visit.",
      ni_reason="List of users and the test-range network provider are missing; requester has not replied to two reminders."),
    D(41, "Archive for decommissioned programme data", "storage", "Munich", PMO, DATA, "PLAT", 9000, 400, 70, (2, 1, 3, 2), c.SUBMITTED, "2027-01-29",
      "Data of two closed programmes must be retained for ten years but still occupies primary storage.", no_owner=True),
    D(42, "Jump-host hardening for supplier maintenance access", "security", "Toulouse", ISO, SECO, "SEC", 5000, 300, 50, (4, 4, 5, 3), c.SUBMITTED, "2026-11-27",
      "Supplier maintenance sessions go through a jump host without session recording.", security=True),
    D(43, "Additional test-bench network ports in lab B", "network", "Bremen", SIL, INFRA, "NET", 4000, 0, 30, (2, 3, 1, 1), c.ROUTED_OUT, "2026-12-04",
      "Eight additional switch ports are needed for two new test benches.", request_type="service_request",
      routed_to="Service catalogue (standard change: network port activation)",
      rationale="Routed out: a standard catalogue item with a fixed price and no assessment need is not an infrastructure demand."),
    D(44, "Dashboard hosting for programme KPIs", "analytics", "Madrid", PMO, COLLAB, "PLAT", 3000, 350, 45, (2, 2, 1, 3), c.SUBMITTED, "2026-12-18",
      "Programme KPIs are distributed as slide decks; hosted dashboards would give a single current view.", no_owner=True),
    D(45, "Tape library retirement and media migration", "migration", "Munich", EIA, INFRA, "PLAT", 17000, 0, 140, (3, 2, 4, 3), c.DEFERRED, "2027-02-26",
      "The tape library is out of maintenance; remaining media must be migrated before it is retired.",
      next_review="2027-01-12",
      rationale="Deferred: Platform and Storage has no free capacity before February and the library remains usable under best-effort support."),
    D(46, "Chat-ops integration for incident bridges", "collaboration", "Toulouse", EIA, COLLAB, "PLAT", 4000, 600, 55, (2, 2, 2, 2), c.REJECTED, "2026-11-20",
      "Automatic creation of chat channels for major incidents.",
      rationale="Rejected at triage: the service-management tool already provides this function; no new infrastructure is required."),
    D(47, "Dedicated internet breakout for the Madrid lab", "network", "Madrid", SIL, INFRA, "NET", 15000, 1900, 80, (3, 3, 1, 1), c.REJECTED, "2026-12-04",
      "A separate internet line for the lab to bypass the central proxy.",
      rationale="Rejected: bypassing the central proxy conflicts with the network security policy; the requester was referred to the proxy exception process."),
    D(48, "Production file-server outage - restore service Bremen", "incident", "Bremen", SGS, INFRA, "PLAT", 0, 0, 0, (5, 5, 1, 1), c.ROUTED_OUT, "2026-11-10",
      "The Bremen project file server is unavailable; users cannot open design documents.", request_type="incident",
      routed_to="Incident management queue (priority 2 incident)",
      rationale="Routed out: restoring an existing service is an incident, not a demand for new or changed infrastructure. No budget or prioritisation decision applies."),
    D(49, "Quantum-safe VPN cryptography evaluation lab", "security", "Munich", ISO, SECO, "SEC", 30000, 0, 180, (3, 1, 4, 5), c.DEFERRED, "2027-03-26",
      "A lab to evaluate post-quantum VPN cipher suites ahead of expected customer requirements.", security=True,
      next_review="2027-03-09",
      rationale="Deferred: strategically relevant but not urgent; Security Engineering capacity is committed to MFA and directory work until March."),
    D(50, "Storage snapshot replication to the secondary site", "backup-dr", "Toulouse", FTD, DATA, "PLAT", 26000, 1300, 160, (5, 4, 5, 4), c.APPROVED, "2027-01-22",
      "Test data is held at one site only; replication protects certification evidence against a site loss."),
]

# Two technically plausible options assessed for the hero demand ORION-REQ-017.
OPTIONS = [
    dict(external_id="ORION-REQ-017", option_id="A", name="Additional managed storage",
         one_time_eur=48000, monthly_eur=3200, hours=300, security_review_needed="yes",
         delivery_risk="Medium: hardware lead time of about four weeks; new encrypted volumes need key-management onboarding.",
         benefit="Adds the full 40 TB requested; no change for users.",
         assumptions="Vendor quote valid until 31 December; rack space and power are available at Munich."),
    dict(external_id="ORION-REQ-017", option_id="B", name="Archive and optimise existing capacity",
         one_time_eur=14500, monthly_eur=600, hours=160, security_review_needed="yes",
         delivery_risk="Medium: depends on data owners confirming retention classes; archived data has slower retrieval.",
         benefit="Frees an estimated 16 TB (about 40% of the request) by moving closed-campaign data to the archive tier.",
         assumptions="Archive tier from ORION-REQ-002 has free capacity; estimate based on a sample of three campaigns."),
]
