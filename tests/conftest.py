"""Shared fixtures. `ground_truth` is the independent expectation file; `mini` builds tiny hand-checked datasets."""
import csv
import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from infraflow import capacity, config as c, finance
from infraflow import generator as g
from infraflow.models import load_dataset
from infraflow.reports import build_context

FIELDS = {"demands.csv": g.DEMAND_FIELDS, "status_events.csv": g.EVENT_FIELDS, "decisions.csv": g.DECISION_FIELDS,
          "budgets.csv": g.BUDGET_FIELDS, "actuals.csv": g.ACTUAL_FIELDS, "commitments.csv": g.COMMITMENT_FIELDS,
          "capacity.csv": g.CAPACITY_FIELDS, "allocations.csv": g.ALLOCATION_FIELDS, "options.csv": g.OPTION_FIELDS}


@pytest.fixture(scope="session")
def ground_truth():
    return json.loads((c.DATA_DIR / "ground_truth.json").read_text())


@pytest.fixture(scope="session")
def ds():
    return load_dataset()


@pytest.fixture(scope="session")
def fin(ds):
    return finance.reconcile(ds)


@pytest.fixture(scope="session")
def cap(ds):
    return capacity.assess(ds)


@pytest.fixture(scope="session")
def ctx(ds):
    return build_context(ds)


def write_csv(path: Path, name: str, rows: list[dict]):
    with (path / name).open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS[name], lineterminator="\n", restval="")
        w.writeheader()
        w.writerows(rows)


def demand_row(n=1, **kw):
    row = dict(external_id=f"T-{n:03d}", request_type="demand", title=f"Test demand {n}", requested_at="2026-10-01",
               requester_department="Dept", requester_role="Engineering Lead Dept", business_owner="Head of Dept", site="Munich",
               service_category="storage", business_case="Because.", business_impact_score=3, urgency_score=3,
               risk_reduction_score=3, strategic_alignment_score=3, due_at="2026-12-15", demand_status="SUBMITTED",
               triage_owner="Demand Analyst Munich", delivery_team="PLAT", estimated_hours=40, cost_center="CC-A",
               estimated_one_time_eur=1000, estimated_monthly_recurring_eur=0, security_review_needed="no",
               security_review_status="not_required", blocked="no", handoff_checklist_complete="no")
    row.update(kw)
    return row


@pytest.fixture
def mini(tmp_path):
    """Return a builder: mini(demands=[...], actuals=[...], ...) -> Dataset loaded from a temp directory."""
    def build(as_of=date(2026, 11, 16), **tables):
        defaults = {"budgets.csv": [dict(month=m, cost_center="CC-A", approved_budget_eur=10000) for m in c.PERIOD_MONTHS],
                    "capacity.csv": [dict(month=m, team="PLAT", available_hours=100, allocated_hours=40) for m in c.CAPACITY_MONTHS],
                    "allocations.csv": [dict(month=m, team="PLAT", external_id="RUN", hours=40) for m in c.CAPACITY_MONTHS]}
        for name in FIELDS:
            key = name[:-4]
            write_csv(tmp_path, name, tables.get(key, defaults.get(name, [])))
        return load_dataset(tmp_path, as_of)
    return build


@pytest.fixture
def data_copy(tmp_path):
    """A writable copy of the generated dataset."""
    dst = tmp_path / "data"
    shutil.copytree(c.DATA_DIR, dst)
    return dst


def sheet_rows(ws, first_header: str) -> tuple[list[str], list[tuple]]:
    """Header and data rows of the table on a sheet, wherever the header row is (some sheets have a title block)."""
    for row in ws.iter_rows(values_only=True):
        if row and row[0] == first_header:
            header = [h for h in row]
            break
    else:
        raise AssertionError(f"header '{first_header}' not found on {ws.title}")
    rows, started = [], False
    for row in ws.iter_rows(values_only=True):
        if started:
            if row[0] in (None, ""):
                break
            rows.append(row)
        elif row and row[0] == first_header:
            started = True
    return header, rows


# ---- neutrality guard: generated material names no real organisation -----------------------------------
import re as _re

_ENTITY = _re.compile(r"\b([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*){0,3})\s+(GmbH|AG|SE|Inc\.?|Ltd\.?|plc|LLC|S\.A\.|SAS|Corporation|Corp\.?|Group)\b")
_URL = _re.compile(r"https?://([\w.-]+)")
_ALLOWED_HOSTS = ("your-site.atlassian.net", "atlassian.net", "github.com", "example.com")


def foreign_org_mentions(text: str, org_name: str) -> list[str]:
    """Organisation-like names (legal-entity suffixes), e-mail addresses and external URLs other than the
    fictional organisation and the tools used. Empty list = the text is company-neutral."""
    found = [m.group(0) for m in _ENTITY.finditer(text) if org_name not in m.group(0)]
    found += _re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
    found += [h for h in _URL.findall(text) if not h.endswith(_ALLOWED_HOSTS)]
    return found
