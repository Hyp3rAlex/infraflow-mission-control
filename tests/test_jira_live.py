"""Read-only live view: computed from a recorded Jira snapshot only; drift against the dataset."""
import copy
import json
from datetime import date

import pytest

from infraflow import config as c, jira_live, jira_sync

SNAPSHOT = c.ROOT / "evidence" / "jira_snapshot_mcp_2026-11-17b.json"


@pytest.fixture(scope="module")
def snap():
    return json.loads(SNAPSHOT.read_text())


def test_recorded_snapshot_covers_all_demands_once(ds, snap):
    cov = jira_sync.coverage(ds, jira_sync.load_mapping(), snap["issues"])
    assert cov["total"] == 50 and len(cov["mapped"]) == 50 and cov["missing"] == [] and len(cov["in_snapshot"]) == 50
    assert cov["mapped_but_not_in_snapshot"] == [] and cov["in_snapshot_but_not_mapped"] == []
    keys = [i["key"] for i in snap["issues"]]
    assert len(keys) == len(set(keys)) == 50 and not {"KAN-1", "KAN-2", "KAN-3", "KAN-4"} & set(keys)   # onboarding and smoke-test issues excluded


def test_live_view_matches_independent_ground_truth(ds, snap, ground_truth):
    v = jira_live.live_view(snap, date(2026, 11, 17))
    mapping = jira_sync.load_mapping()
    key = lambda ext: mapping[ext]["key"]
    assert v["total"] == ground_truth["demand_count"] and v["open"] == ground_truth["open_count"]
    assert set(v["overdue"]) == {key(e) for e in ground_truth["overdue_open_ids"]}
    assert set(v["blocked"]) == {key(e) for e in ground_truth["blocked_ids"]}
    assert set(v["unassigned"]) == {key(e) for e in ground_truth["missing_owner_ids"]}
    assert {c.STATUS_ORDER[i]: n for i, n in enumerate(v["by_stage"].get(s, 0) for s in c.STATUS_ORDER) if n} == ground_truth["status_counts"]
    assert v["stage_label_problems"] == [] and v["status_stage_conflicts"] == []
    assert jira_live.drift(ds, snap) == []


def test_drift_is_reported_when_jira_changes(ds, snap):
    changed = copy.deepcopy(snap)
    issue = next(i for i in changed["issues"] if "orion-req-017" in i["labels"])
    issue["labels"] = [l for l in issue["labels"] if l != "stage-deferred"] + ["stage-approved"]
    issue["status"] = "In Progress"
    issue["duedate"] = "2027-01-31"
    changed["issues"] = [i for i in changed["issues"] if "orion-req-050" not in i["labels"]]
    found = {(x["external_id"], x["field"]): (x["dataset"], x["jira"]) for x in jira_live.drift(ds, changed)}
    assert found == {("ORION-REQ-017", "lifecycle stage"): ("Deferred", "Approved"), ("ORION-REQ-017", "due date"): ("2026-12-18", "2027-01-31"),
                     ("ORION-REQ-050", "coverage"): ("in dataset", "no issue in snapshot")}
    v = jira_live.live_view(changed, date(2026, 11, 17))
    assert v["total"] == 49 and v["by_stage"]["DEFERRED"] == jira_live.live_view(snap, date(2026, 11, 17))["by_stage"]["DEFERRED"] - 1


def test_live_report_states_its_source_and_contains_no_money(ds, snap):
    text = jira_live.live_report(ds, snap, date(2026, 11, 17))
    assert "LIVE JIRA SNAPSHOT" in text and snap["taken_at"] in text and "never writes" in text and "**No differences.**" in text
    assert "€" not in text and "EUR" not in text                      # finance is not sourced from Jira
    later = jira_live.live_view(snap, date(2026, 12, 20))               # evaluation date moves, overdue grows; nothing is cached
    assert len(later["overdue"]) > 4
