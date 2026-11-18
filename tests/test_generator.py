import hashlib

from infraflow import config as c
from infraflow.generator import generate
from infraflow.models import load_dataset


def _digest(path):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(path.iterdir())}


def test_generation_is_deterministic(tmp_path):
    generate(tmp_path / "a")
    generate(tmp_path / "b")
    assert _digest(tmp_path / "a") == _digest(tmp_path / "b")


def test_committed_data_matches_generator(tmp_path):
    """The dataset in the repository is exactly what the generator produces (no manual edits)."""
    generate(tmp_path / "fresh")
    assert _digest(tmp_path / "fresh") == _digest(c.DATA_DIR)


def test_dataset_shape(ds, ground_truth):
    ids = [d.external_id for d in ds.demands]
    assert len(ids) == len(set(ids)) == ground_truth["demand_count"] == 50
    assert {d.site for d in ds.demands} == set(c.SITES)
    assert len({d.cost_center for d in ds.demands if d.cost_center}) == 5
    assert {d.team for d in ds.demands} == set(c.TEAMS)
    assert all(d.status in c.STATUS_ORDER for d in ds.demands)
    assert {d.request_type for d in ds.demands} == {"demand", "incident", "service_request"}


def test_every_demand_has_a_history_starting_with_submission(ds):
    for d in ds.demands:
        ev = ds.events_for(d.external_id)
        assert ev and ev[0]["new_status"] == c.SUBMITTED and ev[0]["previous_status"] == ""
        assert ev[0]["occurred_at"][:10] == d.requested_at.isoformat()


def test_no_event_after_cutoff_and_no_weekend_events(ds):
    from datetime import date
    for e in ds.events:
        day = date.fromisoformat(e["occurred_at"][:10])
        assert day <= ds.as_of and day.weekday() < 5


def test_incident_and_service_request_are_routed_out_not_assessed(ds):
    for d in ds.demands:
        if d.request_type != "demand":
            assert d.status == c.ROUTED_OUT and d.routed_to
            assert c.ASSESSMENT not in [e["new_status"] for e in ds.events_for(d.external_id)]
            assert not [r for r in ds.decisions if r["external_id"] == d.external_id]


def test_dataset_is_synthetic_and_company_neutral():
    from conftest import foreign_org_mentions
    text = " ".join(p.read_text(encoding="utf-8") for p in c.DATA_DIR.glob("*.csv"))
    assert foreign_org_mentions(text, c.ORG_NAME) == []
    assert "@" not in text
    # the guard itself: it must flag a legal entity, an e-mail address and an external URL
    assert len(foreign_org_mentions("Example Aero GmbH, someone" + "@" + "example.org, https://intranet.example.org", c.ORG_NAME)) == 3
