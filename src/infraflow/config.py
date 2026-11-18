"""Explicit configuration for the synthetic Orion Systems Engineering environment.

Everything here is fictional. Changing a value changes the generated dataset,
so `ground_truth.json` must be regenerated with `python -m infraflow seed`.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

ORG_NAME = "Orion Systems Engineering"
AS_OF = date(2026, 11, 16)          # reporting cutoff (inclusive)
SEED = 20261116
CURRENCY = "EUR"

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "synthetic"
REPORTS_DIR = ROOT / "reports"
PRESENTATIONS_DIR = ROOT / "presentations"

# Budget period: five months, of which the last is still in the future at AS_OF.
PERIOD_MONTHS = ["2026-08", "2026-09", "2026-10", "2026-11", "2026-12"]
# Capacity planning horizon reaches two months past the budget period.
CAPACITY_MONTHS = PERIOD_MONTHS + ["2027-01", "2027-02"]

# code: (name, approved budget per month EUR, baseline run contract per month EUR)
COST_CENTERS: dict[str, tuple[str, int, int]] = {
    "CC-ENG-DATA": ("Engineering Data Platforms", 40_000, 14_500),
    "CC-ENG-SIM": ("Simulation and Compute", 45_000, 13_000),
    "CC-DIG-INFRA": ("Digital Infrastructure Core", 70_000, 28_000),
    "CC-SEC-OPS": ("Security Operations", 35_000, 14_000),
    "CC-COLLAB": ("Collaboration and Workplace", 20_000, 9_000),
}

# code: (name, available hours in a normal month, share of hours reserved for run/operations)
TEAMS: dict[str, tuple[str, int, float]] = {
    "PLAT": ("Platform and Storage", 640, 0.45),
    "NET": ("Network and Access", 480, 0.50),
    "SEC": ("Security Engineering", 320, 0.55),
}
REDUCED_MONTHS = {"2026-12": 0.75, "2026-08": 0.85}  # holiday seasons

SITES = ["Munich", "Toulouse", "Madrid", "Bremen"]

# ---- lifecycle -----------------------------------------------------------
SUBMITTED, NEEDS_INFO, TRIAGED, ASSESSMENT = "SUBMITTED", "NEEDS_INFO", "TRIAGED", "ASSESSMENT"
READY_FOR_DECISION, APPROVED, DEFERRED, REJECTED = "READY_FOR_DECISION", "APPROVED", "DEFERRED", "REJECTED"
HANDOFF, IN_DELIVERY, COMPLETE, ROUTED_OUT = "HANDOFF", "IN_DELIVERY", "COMPLETE", "ROUTED_OUT"

STATUS_ORDER = [SUBMITTED, NEEDS_INFO, TRIAGED, ASSESSMENT, READY_FOR_DECISION, DEFERRED,
                APPROVED, HANDOFF, IN_DELIVERY, COMPLETE, REJECTED, ROUTED_OUT]
STATUS_LABEL = {
    SUBMITTED: "Submitted", NEEDS_INFO: "Needs Info", TRIAGED: "Triaged", ASSESSMENT: "Assessment",
    READY_FOR_DECISION: "Ready for Decision", DEFERRED: "Deferred", APPROVED: "Approved",
    HANDOFF: "Handoff", IN_DELIVERY: "In Delivery", COMPLETE: "Complete", REJECTED: "Rejected",
    ROUTED_OUT: "Routed Out",
}
TERMINAL = {COMPLETE, REJECTED, ROUTED_OUT}
FUNDED = {APPROVED, HANDOFF, IN_DELIVERY, COMPLETE}      # an approval decision exists
PRE_DECISION = {SUBMITTED, NEEDS_INFO, TRIAGED, ASSESSMENT, READY_FOR_DECISION}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    SUBMITTED: {NEEDS_INFO, TRIAGED, REJECTED, ROUTED_OUT},
    NEEDS_INFO: {TRIAGED, REJECTED},
    TRIAGED: {ASSESSMENT},
    ASSESSMENT: {READY_FOR_DECISION, NEEDS_INFO},
    READY_FOR_DECISION: {APPROVED, DEFERRED, REJECTED},
    DEFERRED: {READY_FOR_DECISION, REJECTED},
    APPROVED: {HANDOFF},
    HANDOFF: {IN_DELIVERY},
    IN_DELIVERY: {COMPLETE},
    COMPLETE: set(), REJECTED: set(), ROUTED_OUT: set(),
}

AUTHORIZED_APPROVERS = {
    "Infrastructure Demand Board Chair",
    "Head of Digital Infrastructure",
    "Demand Manager",          # may reject or route at triage only
}
BOARD_APPROVERS = {"Infrastructure Demand Board Chair", "Head of Digital Infrastructure"}

# ---- prioritisation --------------------------------------------------------
SCORE_WEIGHTS = {"business_impact_score": 0.35, "urgency_score": 0.25,
                 "risk_reduction_score": 0.25, "strategic_alignment_score": 0.15}
PRIORITY_BANDS = [(80, "Highest"), (65, "High"), (45, "Medium"), (25, "Low"), (0, "Lowest")]

STALE_DAYS = 14
REQUIRED_DEMAND_FIELDS = ["title", "requested_at", "requester_department", "site", "service_category",
                          "business_case", "due_at", "triage_owner", "delivery_team", "estimated_hours",
                          "cost_center", "estimated_one_time_eur"]

# ---- Jira mapping (project KAN, verified 2026-11-17) -----------------------
JIRA_PROJECT_KEY = "KAN"
PORTFOLIO_LABEL = "orion-demand"
# The Free team-managed project has five statuses; the exact lifecycle stage is carried by a
# `stage-*` label so that JQL stays precise even though several stages share a board column.
STATUS_TO_JIRA = {
    SUBMITTED: "Idea", NEEDS_INFO: "Idea", TRIAGED: "Idea",
    ASSESSMENT: "To Do",
    READY_FOR_DECISION: "In Review", DEFERRED: "In Review",
    APPROVED: "In Progress", HANDOFF: "In Progress", IN_DELIVERY: "In Progress",
    COMPLETE: "Done", REJECTED: "Done", ROUTED_OUT: "Done",
}
JIRA_TRANSITION_IDS = {"Idea": "11", "To Do": "21", "In Progress": "31", "In Review": "41", "Done": "51"}
JIRA_COLUMN_MEANING = {
    "Idea": "Intake (Submitted / Needs Info / Triaged)",
    "To Do": "Assessment",
    "In Review": "Decision board (Ready for Decision / Deferred)",
    "In Progress": "Approved, handoff and delivery",
    "Done": "Complete, rejected or routed out",
}
# Demands seeded into the live Jira project. Wave 1 (28 demands, every lifecycle stage and edge case)
# was created first; wave 2 added the remaining 22, so that all 50 demands of the dataset have an issue.
JIRA_SEED_WAVE_1 = [2, 5, 9, 10, 11, 12, 13, 15, 17, 18, 19, 20, 21, 22, 23, 24, 27, 29, 30, 31,
                    33, 36, 38, 40, 41, 42, 46, 48]
JIRA_SEED_NUMBERS = list(range(1, 51))


def stage_label(status: str) -> str:
    return "stage-" + STATUS_LABEL[status].lower().replace(" ", "-")

# Approved currency conversion rates to EUR, e.g. {"USD": 0.92}. Deliberately empty: Finance has not
# approved any rate, so non-EUR amounts are reported in their own currency and never added to EUR totals.
APPROVED_FX_RATES: dict[str, float] = {}
