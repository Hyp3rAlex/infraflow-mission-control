"""The same reference figures in every artefact: facts JSON, workbook, slide deck, Confluence page source.

Expected values come from the independent ground truth (and the hand-listed exception design), never
from the reporting code."""
import json
import re

import pytest
from openpyxl import load_workbook
from pptx import Presentation

from infraflow import config as c
from infraflow import reports
from infraflow.confluence_pages import write_pages
from infraflow.deck import build_deck
from infraflow.excel_export import build_workbook
from infraflow.reports import eur


@pytest.fixture(scope="module")
def artefacts(tmp_path_factory, ds):
    d = tmp_path_factory.mktemp("all")
    reports.write_all(ds, d / "reports")
    build_workbook(ds, d / "wb.xlsx")
    build_deck(ds, d / "deck.pptx")
    pages = dict(write_pages(ds, d / "pages"))
    facts = json.loads((d / "reports" / "report_facts.json").read_text())
    wb = load_workbook(d / "wb.xlsx")
    deck = " ".join(sh.text_frame.text if sh.has_text_frame else " ".join(cell.text for row in sh.table.rows for cell in row.cells) if sh.has_table else ""
                    for slide in Presentation(d / "deck.pptx").slides for sh in slide.shapes)
    weekly = pages["Weekly Portfolio Review - 2026-11-16"].read_text()
    email = (d / "reports" / "management_email.md").read_text()
    return facts, wb, deck, weekly, email


def test_reference_figures_agree_everywhere(artefacts, ground_truth):
    facts, wb, deck, weekly, email = artefacts
    tot = ground_truth["finance_totals"]
    k = facts["kpis"]
    assert facts["as_of"] == ground_truth["as_of"] == "2026-11-16"
    assert (k["total_demands"]["value"], k["open_demands"]["value"]) == (ground_truth["demand_count"], ground_truth["open_count"]) == (50, 37)
    assert k["approval_pending"]["value"] == 5 and k["overdue_open"]["value"] == len(ground_truth["overdue_open_ids"]) == 4
    assert k["blocked_open"]["value"] == len(ground_truth["blocked_ids"]) == 3 and k["unassigned_open"]["value"] == len(ground_truth["missing_owner_ids"]) == 3
    assert facts["exception_counts"]["CRITICAL"] == 6 and facts["provisional"] is True
    assert facts["finance"]["totals"]["forecast_eac_eur"] == tot["forecast_eac_eur"] == 936700
    # workbook KPI sheet
    kpi = {r[1]: r[2] for r in wb["KPI Summary"].iter_rows(min_row=5, values_only=True) if r[1]}
    assert (kpi["Budget (period) EUR"], kpi["Actual to date EUR"], kpi["Open commitments EUR"], kpi["Approved, not committed EUR"],
            kpi["Forecast EAC EUR"], kpi["Forecast variance EUR"]) == (tot["budget_period_eur"], tot["actual_eur"], tot["open_commitments_eur"],
                                                                     tot["approved_not_committed_eur"], tot["forecast_eac_eur"], tot["forecast_variance_eur"])
    assert (kpi["Open demands"], kpi["Awaiting decision"], kpi["Overdue open demands"], kpi["Blocked open demands"],
            kpi["Open demands without owner"], kpi["Critical exceptions"]) == (37, 5, 4, 3, 3, 6)
    assert kpi["Unreconciled purchase orders EUR"] == ground_truth["unreconciled_po"]["difference_eur"] == 1000
    # deck, Confluence weekly review, e-mail: same money figures as text
    for text in (deck, weekly):
        for v in (tot["budget_period_eur"], tot["forecast_eac_eur"]):
            assert eur(v) in text
        assert "€3,800" in text and "USD 5,000" in text
    assert eur(tot["actual_eur"]) in deck and eur(tot["open_commitments_eur"]) in deck and eur(tot["approved_not_committed_eur"]) in deck
    assert eur(-tot["forecast_variance_eur"]) in deck                                           # 113,300 headroom
    assert "936,700" in email and "USD 5,000" in email
    # the old mixed-currency figure appears nowhere
    for text in (deck, weekly, email, json.dumps(facts)):
        assert not re.search(r"9,300\b", text.replace("€229,300", ""))


def test_capacity_and_hero_figures_agree(artefacts, ground_truth):
    facts, wb, deck, weekly, _ = artefacts
    assert facts["capacity"]["NET|2026-12"]["remaining"] == -30 and ground_truth["overallocated_team_months"] == ["NET|2026-12"]
    assert "30 engineer-hours" in deck and "Network and Access" in weekly
    hero = ground_truth["hero"]
    assert eur(hero["option_a_period_cost_eur"]) in deck and eur(hero["option_b_period_cost_eur"]) in deck
    assert f"{hero['hours_requested']} h" in deck and f"{hero['hours_available_in_window']} h free" in deck and hero["next_review_at"] in deck
    hs = {r[0]: r[1:] for r in wb["Hero Scenario"].iter_rows(min_row=2, values_only=True)}
    assert hs["Cost in budget period EUR"] == (hero["option_a_period_cost_eur"], hero["option_b_period_cost_eur"])
    assert hs["Unallocated team hours in window"] == (hero["hours_available_in_window"],) * 2
    assert hs["Funding gate"] == ("FAIL", "pass") and hs["Capacity gate"] == ("FAIL", "pass")


def test_office_files_do_not_claim_live_refresh(artefacts):
    _, wb, deck, _, _ = artefacts
    readme = " ".join(str(r[0]) for r in wb["README"].iter_rows(values_only=True) if r[0])
    assert "OFFLINE_FIXTURE" in readme and "not a live" in readme
    assert "not a live system extract" in deck
    from conftest import foreign_org_mentions
    assert "fictional" in readme and "fictional organisation" in deck
    assert foreign_org_mentions(readme + " " + deck, c.ORG_NAME) == []
