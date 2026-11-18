"""Jira client and synchronisation logic against a fake HTTP session. No network, no credentials."""
import json
from datetime import date

import pytest
import requests

from infraflow import config as c, jira_sync
from infraflow.jira_client import (JiraAuthError, JiraClient, JiraError, JiraPermissionError, JiraRateLimitError,
                                   WriteNotAllowed, simplify)


class Resp:
    def __init__(self, status=200, body=None, headers=None):
        self.status_code, self._body, self.headers = status, body, headers or {}
        self.content = b"x" if body is not None else b""
        self.text = json.dumps(body) if body is not None else ""

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def request(self, method, url, **kw):
        self.calls.append((method, url, kw))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def client(responses, **kw):
    sleeps = []
    cl = JiraClient("https://example.atlassian.net", "user@example.com", "token", session=FakeSession(responses), sleep=sleeps.append, **kw)
    return cl, sleeps


def issue(key, labels=(), status="Idea"):
    return {"key": key, "id": key[-1], "fields": {"summary": key, "status": {"name": status}, "priority": {"name": "High"},
                                                    "duedate": "2026-12-01", "labels": list(labels), "assignee": None}}


def test_search_follows_next_page_token_until_last_page():
    cl, _ = client([Resp(body={"issues": [issue("KAN-1"), issue("KAN-2")], "nextPageToken": "t1"}),
                    Resp(body={"issues": [issue("KAN-3")], "nextPageToken": "t2", "isLast": False}),
                    Resp(body={"issues": [issue("KAN-4")], "isLast": True})])
    assert [i["key"] for i in cl.search("project = KAN", page_size=2)] == ["KAN-1", "KAN-2", "KAN-3", "KAN-4"]
    bodies = [kw["json"] for _, _, kw in cl.session.calls]
    assert "nextPageToken" not in bodies[0] and bodies[1]["nextPageToken"] == "t1" and bodies[2]["nextPageToken"] == "t2"
    assert cl.session.calls[0][1].endswith("/rest/api/3/search/jql") and bodies[0]["maxResults"] == 2


def test_search_stops_if_pagination_does_not_advance():
    cl, _ = client([Resp(body={"issues": [], "nextPageToken": "same"})] * 3)
    with pytest.raises(JiraError, match="did not advance"):
        list(cl.search("project = KAN"))


def test_401_and_403_are_reported_without_retry():
    cl, sleeps = client([Resp(401, {})])
    with pytest.raises(JiraAuthError):
        list(cl.search("x"))
    cl2, _ = client([Resp(403, {})])
    with pytest.raises(JiraPermissionError):
        list(cl2.search("x"))
    assert sleeps == [] and len(cl.session.calls) == 1


def test_429_honours_retry_after_then_succeeds():
    cl, sleeps = client([Resp(429, {}, {"Retry-After": "7"}), Resp(429, {}), Resp(body={"issues": [issue("KAN-1")], "isLast": True})])
    assert [i["key"] for i in cl.search("x")] == ["KAN-1"]
    assert sleeps == [7.0, 2]


def test_429_gives_up_after_max_retries():
    cl, sleeps = client([Resp(429, {}, {"Retry-After": "1"})] * 3, max_retries=2)
    with pytest.raises(JiraRateLimitError):
        list(cl.search("x"))
    assert len(cl.session.calls) == 3 and sleeps == [1.0, 1.0]


def test_network_errors_and_5xx_are_retried_then_reported():
    cl, sleeps = client([requests.ConnectionError("boom"), Resp(503, {}), Resp(body={"issues": [], "isLast": True})])
    assert list(cl.search("x")) == [] and sleeps == [1, 2]
    cl2, _ = client([requests.Timeout("slow")] * 2, max_retries=1)
    with pytest.raises(JiraError, match="network error"):
        list(cl2.search("x"))


def test_400_carries_jira_error_messages():
    cl, _ = client([Resp(400, {"errorMessages": ["The value 'XX' does not exist for the field 'project'."], "errors": {}})])
    with pytest.raises(JiraError, match="does not exist for the field 'project'") as exc:
        list(cl.search("project = XX"))
    assert exc.value.status == 400


def test_writes_are_refused_on_a_read_only_client():
    cl, _ = client([])
    for call in (lambda: cl.create_issue({}), lambda: cl.add_comment("KAN-1", {}), lambda: cl.create_filter("n", "jql")):
        with pytest.raises(WriteNotAllowed):
            call()
    assert cl.session.calls == []                    # nothing was sent


def test_from_env_requires_all_settings_and_https():
    with pytest.raises(JiraAuthError, match="JIRA_API_TOKEN"):
        JiraClient.from_env(env={"JIRA_BASE_URL": "https://x.atlassian.net", "JIRA_EMAIL": "a@b.c"})
    with pytest.raises(JiraError, match="https"):
        JiraClient("http://x.atlassian.net", "a", "b")
    assert JiraClient.from_env(env={"JIRA_BASE_URL": "https://x.atlassian.net/", "JIRA_EMAIL": "a@b.c", "JIRA_API_TOKEN": "t"}).base_url == "https://x.atlassian.net"


def test_transition_picks_the_transition_that_leads_to_the_status():
    cl, _ = client([Resp(body={"transitions": [{"id": "11", "to": {"name": "Idea"}}, {"id": "41", "to": {"name": "In Review"}}]}), Resp(204)], allow_write=True)
    cl.transition("KAN-9", "In Review")
    assert cl.session.calls[1][2]["json"] == {"transition": {"id": "41"}}
    cl2, _ = client([Resp(body={"transitions": []})], allow_write=True)
    with pytest.raises(JiraError, match="no transition"):
        cl2.transition("KAN-9", "Nope")


# ---- plan, seeding, reconciliation --------------------------------------------
@pytest.fixture(scope="module")
def payloads(ds, ctx):
    return jira_sync.plan(ds, ctx=ctx)


def test_plan_covers_every_stage_and_has_stable_identity(payloads, ds):
    assert len(payloads) == len(c.JIRA_SEED_NUMBERS) == len(ds.demands) == 50
    assert {p["stage"] for p in payloads} == set(c.STATUS_ORDER)
    assert {p["jira_status"] for p in payloads} == {"Idea", "To Do", "In Review", "In Progress", "Done"}
    for p in payloads:
        assert p["summary"].startswith(p["external_id"] + " | ") and p["external_id"].lower() in p["labels"]
        assert c.PORTFOLIO_LABEL in p["labels"] and c.stage_label(p["stage"]) in p["labels"]
        assert all(" " not in l for l in p["labels"])
        assert "Synthetic record" in p["description"] and "## Business need" in p["description"]
    assert jira_sync.plan(ds) == payloads                      # deterministic


def test_plan_flags_follow_the_gates(payloads):
    by = {p["external_id"]: p for p in payloads}
    assert "needs-finance-review" in by["ORION-REQ-017"]["labels"] and "stage-deferred" in by["ORION-REQ-017"]["labels"]
    assert "needs-finance-review" in by["ORION-REQ-027"]["labels"] and "needs-finance-review" not in by["ORION-REQ-023"]["labels"]
    assert "needs-finance-review" in by["ORION-REQ-024"]["labels"]            # recurring cost above the review threshold
    assert "needs-security-review" in by["ORION-REQ-024"]["labels"] and "needs-security-review" not in by["ORION-REQ-023"]["labels"]
    assert "blocked" in by["ORION-REQ-012"]["labels"] and "owner-missing" in by["ORION-REQ-041"]["labels"]
    assert not by["ORION-REQ-041"]["assigned"] and by["ORION-REQ-017"]["assigned"]
    assert "type-incident" in by["ORION-REQ-048"]["labels"] and by["ORION-REQ-048"]["jira_status"] == "Done"
    assert by["ORION-REQ-017"]["priority"] == "Highest" and "Option" in by["ORION-REQ-017"]["description"]


def test_expected_filter_results_are_derived_from_the_dataset(payloads):
    exp = jira_sync.expected_filter_ids(payloads, date(2026, 11, 17))
    assert set(exp) == set(jira_sync.FILTERS)
    assert exp["overdue"] == ["ORION-REQ-012", "ORION-REQ-015", "ORION-REQ-029", "ORION-REQ-040"]
    assert exp["unassigned"] == ["ORION-REQ-031", "ORION-REQ-041", "ORION-REQ-044"]
    assert exp["decision"] == [f"ORION-REQ-{n:03d}" for n in (23, 24, 25, 26, 27)]
    # hand-listed from the catalogue: blocked 012, 022, 030; deferred 017, 018, 045, 049; complete 001-009
    assert exp["blocked_deferred"] == [f"ORION-REQ-{n:03d}" for n in (12, 17, 18, 22, 30, 45, 49)]
    assert exp["done_recent"] == [f"ORION-REQ-{n:03d}" for n in range(1, 10)] and exp["stale"] == []
    assert all("project = KAN AND labels = orion-demand" in jql for _, jql, _ in jira_sync.FILTERS.values())   # onboarding issues can never match


def as_snapshot(payloads, start=5):
    return [dict(key=f"KAN-{start + i}", summary=p["summary"], status=p["jira_status"], priority=p["priority"], duedate=p["duedate"],
                 labels=list(p["labels"]), assignee="Owner" if p["assigned"] else None) for i, p in enumerate(payloads)]


def test_reconcile_reports_no_difference_for_a_faithful_snapshot(payloads):
    snap = as_snapshot(payloads)
    mapping = {p["external_id"]: {"key": s["key"]} for p, s in zip(payloads, snap)}
    onboarding = [dict(key="KAN-1", summary="Task 1", status="To Do", priority="Medium", duedate=None, labels=[], assignee=None)]
    assert jira_sync.reconcile(payloads, snap + onboarding, mapping) == []     # unlabeled onboarding issues are ignored


def test_reconcile_reports_every_kind_of_difference(payloads):
    snap = as_snapshot(payloads)
    mapping = {p["external_id"]: {"key": s["key"]} for p, s in zip(payloads, snap)}
    snap[0]["status"] = "Idea"
    snap[1]["priority"] = "Lowest"
    snap[2]["labels"] = [l for l in snap[2]["labels"] if not l.startswith("stage-")]
    snap[3]["duedate"] = "2030-01-01"
    missing = snap.pop(4)
    snap.append(dict(snap[5], key="KAN-99"))                                   # duplicate
    snap.append(dict(key="KAN-98", summary="x", status="Idea", priority="Low", duedate=None, labels=["orion-demand"], assignee=None))
    fields = sorted({f["field"] for f in jira_sync.reconcile(payloads, snap, mapping)})
    assert fields == ["duedate", "duplicate", "identity", "labels", "missing", "priority", "status"]
    report = jira_sync.reconcile_report(payloads, snap, mapping, "test")
    assert "**Differences:** 7" in report and missing["key"] in report


class FakeJira:
    """In-memory stand-in for JiraClient used to prove idempotent seeding."""
    def __init__(self):
        self.issues, self.transitions, self.n = [], [], 100

    def find_by_label(self, project, label):
        return [i for i in self.issues if label in i["labels"]]

    def create_issue(self, fields):
        self.n += 1
        row = dict(key=f"KAN-{self.n}", id=str(self.n), labels=fields["labels"])
        self.issues.append(row)
        return row

    def transition(self, key, status):
        self.transitions.append((key, status))


def test_seed_dry_run_creates_nothing(payloads):
    jira, mapping = FakeJira(), {}
    log = jira_sync.seed(jira, payloads, mapping, apply=False)
    assert jira.issues == [] and mapping == {} and {r["action"] for r in log} == {"would create"}


def test_seed_is_idempotent_and_resumes_after_interruption(payloads):
    jira, mapping = FakeJira(), {}
    jira_sync.seed(jira, payloads[:10], mapping, apply=True)                  # interrupted after 10
    assert len(jira.issues) == 10
    log = jira_sync.seed(jira, payloads, mapping, apply=True)                 # resume
    assert [r["action"] for r in log].count("exists") == 10 and [r["action"] for r in log].count("created") == 40
    again = jira_sync.seed(jira, payloads, mapping, apply=True)               # full re-run
    assert len(jira.issues) == 50 and {r["action"] for r in again} == {"exists"}
    assert len(mapping) == 50 and len({m["key"] for m in mapping.values()}) == 50
    assert len(jira.transitions) == sum(1 for p in payloads if p["jira_status"] != "Idea")


def test_seed_reports_existing_duplicates_instead_of_adding_a_third(payloads):
    jira = FakeJira()
    jira.issues = [dict(key="KAN-7", id="7", labels=["orion-req-002"]), dict(key="KAN-8", id="8", labels=["orion-req-002"])]
    log = jira_sync.seed(jira, [p for p in payloads if p["external_id"] == "ORION-REQ-002"], {}, apply=True)
    assert log[0]["action"].startswith("ERROR duplicate") and len(jira.issues) == 2


def test_markdown_to_adf_subset():
    adf = jira_sync.to_adf("## Title\nText **bold**\n\n| A | B |\n|---|---|\n| 1 | 2 |\n- one\n- two")
    kinds = [n["type"] for n in adf["content"]]
    assert kinds == ["heading", "paragraph", "table", "bulletList"] and adf["version"] == 1
    assert adf["content"][2]["content"][0]["content"][0]["type"] == "tableHeader" and len(adf["content"][3]["content"]) == 2
    assert adf["content"][1]["content"][0]["text"] == "Text bold"


def test_simplify_and_mapping_roundtrip(tmp_path):
    s = simplify(issue("KAN-5", labels=["b", "a"], status="Done"))
    assert s == dict(key="KAN-5", summary="KAN-5", status="Done", priority="High", duedate="2026-12-01", labels=["a", "b"], assignee=None, updated=None)
    path = tmp_path / "m.json"
    jira_sync.save_mapping({"ORION-REQ-002": {"key": "KAN-5"}}, path)
    assert jira_sync.load_mapping(path) == {"ORION-REQ-002": {"key": "KAN-5"}} and jira_sync.load_mapping(tmp_path / "none.json") == {}


def test_cli_reports_not_configured_without_credentials(monkeypatch, capsys):
    from infraflow.cli import main
    for k in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    assert main(["jira", "pull"]) == 3 and "NOT_CONFIGURED" in capsys.readouterr().out
    assert main(["jira", "filters"]) == 0 and "Dry run" in capsys.readouterr().out


def test_check_saved_filters_distinguishes_ok_wrong_and_missing():
    names = {k: v for k, v in jira_sync.FILTERS.items()}
    found = [dict(id="1", name=names["open"][0], jql=names["open"][1].replace("orion-demand", '"orion-demand"')),     # quoting differs only
             dict(id="2", name=names["overdue"][0], jql="project = KAN")]                                               # wrong query
    res = jira_sync.check_saved_filters(found)
    assert [x["name"] for x in res["ok"]] == [names["open"][0]] and [x["name"] for x in res["wrong_jql"]] == [names["overdue"][0]]
    assert len(res["missing"]) == len(names) - 2 and res["complete"] is False
    assert jira_sync.check_saved_filters([dict(id=str(i), name=n, jql=q) for i, (n, q, _) in enumerate(names.values())])["complete"] is True
    assert jira_sync.check_saved_filters([])["complete"] is False                # the state verified live on 2026-11-17: no saved filters
