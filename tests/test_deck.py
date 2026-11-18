from pptx import Presentation

from infraflow.deck import build_deck
from infraflow.reports import eur


def _texts(prs):
    out = []
    for slide in prs.slides:
        parts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                parts.append(shape.text_frame.text)
            if getattr(shape, "has_table", False) and shape.has_table:
                parts += [cell.text for row in shape.table.rows for cell in row.cells]
        out.append(" ".join(parts))
    return out


def test_deck_has_five_slides_with_verified_figures(tmp_path, ds, ground_truth, ctx):
    path = tmp_path / "deck.pptx"
    build_deck(ds, path)
    prs = Presentation(path)
    texts = _texts(prs)
    assert len(texts) == 5
    tot = ground_truth["finance_totals"]
    assert eur(tot["forecast_eac_eur"]) in texts[0] and eur(tot["budget_period_eur"]) in texts[0] and "37" in texts[0]
    assert "PROVISIONAL" in texts[0] and "synthetic data" in texts[0] and "2026-11-16" in texts[0]
    for cc, f in ground_truth["finance"].items():
        assert eur(f["forecast_eac_eur"]) in texts[2] and eur(f["budget_period_eur"]) in texts[2], cc
    assert eur(tot["open_commitments_eur"]) in texts[2] and eur(tot["actual_eur"]) in texts[2] and "€3,800" in texts[2]
    # corrected currency reporting: no mixed total, USD named in its own currency, PO-015 caveat, warning kept
    assert "€9,300" not in " ".join(texts) and "USD 5,000 excluded, not converted" in texts[0] and "USD 5,000 not converted (INV-9006)" in texts[2]
    assert "PO-015 not reconciled" in texts[2] and eur(tot["forecast_eac_eur"] - 1000) in texts[2]
    assert eur(tot["approved_not_committed_eur"]) in texts[2] and "not confirmed free funding" in texts[2] and "positive = over budget" in texts[2]
    assert all("PROVISIONAL" in t for t in texts)
    hero = ground_truth["hero"]
    assert eur(hero["option_a_12_month_eur"]) in texts[3] and eur(hero["option_b_12_month_eur"]) in texts[3]
    assert "300 h" in texts[3] and "180 h free" in texts[3] and "No pending request is assumed approved" in texts[3] and "deferred" in texts[3] and hero["next_review_at"] in texts[3]
    assert "60 h (November) + 120 h (December)" in texts[3] and "FAILS: €24,050 over" in texts[3] and "FAILS: 120 h short" in texts[3] and "retention-class sign-off" in texts[3]
    assert "December 2026 over-allocation of 30 engineer-hours" in texts[3]
    assert "ORION-REQ-023" in texts[4] and "Infrastructure Demand Board Chair" in texts[4] and "Fails the funding and capacity gates" in texts[4]
    assert "Demand Analyst Munich" in texts[4] and "Close the 6 critical data exceptions" in texts[4]
    assert all("fictional organisation, synthetic data" in t for t in texts)
    from conftest import foreign_org_mentions
    from infraflow import config as c
    assert foreign_org_mentions(" ".join(texts), c.ORG_NAME) == []                 # company-neutral


def test_deck_charts_hold_the_same_numbers(tmp_path, ds, ground_truth):
    path = tmp_path / "deck.pptx"
    build_deck(ds, path)
    charts = [sh.chart for slide in Presentation(path).slides for sh in slide.shapes if getattr(sh, "has_chart", False) and sh.has_chart]
    assert len(charts) == 3
    status, finance, capacity = charts
    assert sum(status.plots[0].series[0].values) == ground_truth["demand_count"]
    by_name = {s.name: list(s.values) for s in finance.plots[0].series}
    assert by_name["Actual"] == [f["actual_eur"] for f in ground_truth["finance"].values()]
    assert by_name["Forecast at completion"] == [f["forecast_eac_eur"] for f in ground_truth["finance"].values()]
    assert by_name["Budget"] == [f["budget_period_eur"] for f in ground_truth["finance"].values()]
    plat = {s.name: list(s.values) for s in capacity.plots[0].series}["Platform and Storage"]
    assert plat[0] + plat[1] == ground_truth["hero"]["hours_available_in_window"]
    assert all(len(ch.plots[0].series) == 1 or ch.has_legend for ch in charts)


def test_deck_layout_estimate_finds_no_overflow_or_overlap(tmp_path, ds):
    """Geometry estimate (not a rendering): shapes inside the slide, text fits its box, no overlaps."""
    from infraflow.office_qa import deck_layout_findings
    path = tmp_path / "deck.pptx"
    build_deck(ds, path)
    findings = deck_layout_findings(path)
    assert len(findings) == 5 and [f["problems"] for f in findings] == [[]] * 5


def test_deck_charts_have_no_rounded_corners_or_varied_colours_and_highlight_exceptions(tmp_path, ds, ground_truth):
    import re
    import zipfile
    path = tmp_path / "deck.pptx"
    build_deck(ds, path)
    with zipfile.ZipFile(path) as z:
        charts = [z.read(n).decode() for n in sorted(z.namelist()) if re.match(r"ppt/charts/chart\d+\.xml", n)]
    assert len(charts) == 3
    for x in charts:
        assert '<c:roundedCorners val="0"/>' in x and '<c:varyColors val="0"/>' in x
        assert all(v == "0" for v in re.findall(r'<c:overlay val="(\w+)"', x))
    status, finance, capacity = charts
    assert finance.count("<c:dPt>") == 1 and capacity.count("<c:dPt>") == 1        # CC-ENG-SIM forecast bar, NET December bar
    assert "B42318" in finance and "B42318" in capacity and "<c:v>-30</c:v>" in capacity
    # a highlighted point must not be inverted: PowerPoint drew the -30 h bar white without this (owner's screenshot 16)
    for x in (finance, capacity):
        for dpt in re.findall(r"<c:dPt>.*?</c:dPt>", x, flags=re.S):
            assert '<c:invertIfNegative val="0"/>' in dpt
