"""Workbook charts: the structure desktop Excel needs to draw them without overlapping text.

Root cause of the defect seen in Excel: openpyxl omits <c:overlay>, which Excel reads as overlay=true
(legend over the category labels, axis titles over the tick labels). These tests pin the fix and the
data each chart points to. They do not replace looking at the charts in Excel.
"""
import re
import zipfile

import pytest
from openpyxl import Workbook, load_workbook
from openpyxl.chart import BarChart, Reference

from infraflow.excel_export import build_workbook
from infraflow.office_qa import workbook_chart_findings


@pytest.fixture(scope="module")
def built(tmp_path_factory, ds):
    path = tmp_path_factory.mktemp("wb") / "wb.xlsx"
    build_workbook(ds, path)
    return path, workbook_chart_findings(path)


def _chart_xml(path, n):
    with zipfile.ZipFile(path) as z:
        return z.read(f"xl/charts/chart{n}.xml").decode()


def test_plain_openpyxl_chart_reproduces_the_overlay_defect(tmp_path):
    """Control: an unstyled openpyxl chart has no overlay element, i.e. Excel draws legend and titles over the plot."""
    wb = Workbook()
    ws = wb.active
    for r in [["x", "a", "b"], ["p", 1, 2], ["q", 3, 4]]:
        ws.append(r)
    ch = BarChart()
    ch.title = "t"
    ch.x_axis.title = "x axis"
    ch.add_data(Reference(ws, min_col=2, max_col=3, min_row=1, max_row=3), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=1, min_row=2, max_row=3))
    ws.add_chart(ch, "E1")
    wb.save(tmp_path / "plain.xlsx")
    problems = workbook_chart_findings(tmp_path / "plain.xlsx")["xl/charts/chart1.xml"]["problems"]
    assert any("overlay" in p for p in problems) and "axis titles present" in problems


def test_all_workbook_charts_pass_the_structure_checks(built):
    path, findings = built
    assert sorted(findings) == ["xl/charts/chart1.xml", "xl/charts/chart2.xml", "xl/charts/chart3.xml"]
    assert {name: f["problems"] for name, f in findings.items()} == {name: [] for name in findings}


def test_forecast_chart_points_to_the_right_data_and_flags_the_overrun(built, ground_truth):
    path, findings = built
    chk = findings["xl/charts/chart2.xml"]["checks"]
    assert chk["anchor"]["sheet"] == "Forecast"
    assert chk["categories"] == list(ground_truth["finance"])                       # five cost-centre codes, not 1..5
    assert chk["series_titles"] == ["Budget (period)", "Actual", "Forecast EAC"]
    assert chk["value_min"] == ["0"]                                                 # no truncated value axis
    xml = _chart_xml(path, 2)
    wb = load_workbook(path)
    ws = wb["Forecast"]
    refs = re.findall(r"<val><numRef><f>'Forecast'!\$(\w)\$(\d+):\$\w\$(\d+)</f>", xml)
    got = {col: [ws[f"{col}{r}"].value for r in range(int(a), int(b) + 1)] for col, a, b in refs}
    gt = ground_truth["finance"]
    assert got == {"C": [v["budget_period_eur"] for v in gt.values()], "E": [v["actual_eur"] for v in gt.values()],
                   "J": [v["forecast_eac_eur"] for v in gt.values()]}
    over = [i for i, v in enumerate(gt.values()) if v["forecast_variance_eur"] > 0]
    assert over == [list(gt).index("CC-ENG-SIM")]
    assert re.findall(r"<dPt><idx val=\"(\d+)\"/>", xml) == [str(i) for i in over]
    texts = [str(c.value) for row in ws.iter_rows() for c in row if c.value]
    assert any("CC-ENG-SIM forecast 228,800 EUR against a budget of 225,000 EUR, 3,800 EUR over" in t for t in texts)
    assert any("PROVISIONAL" in t and "not confirmed free funding" in t for t in texts)


def test_capacity_chart_shows_months_teams_and_the_negative_balance(built, ground_truth):
    path, findings = built
    chk = findings["xl/charts/chart3.xml"]["checks"]
    assert chk["categories"] == ["2026-11", "2026-12", "2027-01", "2027-02"]
    assert chk["series_titles"] == ["Platform and Storage", "Network and Access", "Security Engineering"]
    assert chk["value_min"] == ["-100"]                                              # axis goes below zero with room for the -30 label
    xml = _chart_xml(path, 3)
    series = re.findall(r"<ser>.*?</ser>", xml, flags=re.S)
    assert [(i, re.findall(r"<dPt><idx val=\"(\d+)\"/>", x)) for i, x in enumerate(series)] == [(0, []), (1, ["1"]), (2, [])]   # NET, December
    ws = load_workbook(path)["Capacity"]
    row = next(r for r in ws.iter_rows(values_only=True) if r[0] == "Network and Access" and r[1] is not None and not isinstance(r[1], str))
    assert row[2] == -30                                                             # chart data: December balance
    assert '<tickLblPos val="low"/>' in xml and "<dLbls>" in xml                     # labels below the plot; value labels on bars
    texts = [str(c.value) for r in ws.iter_rows() for c in r if c.value]
    assert "Network and Access: December 2026 over-allocation of 30 engineer-hours." in texts


def test_status_chart_is_single_coloured_and_counts_all_demands(built, ground_truth):
    path, findings = built
    chk = findings["xl/charts/chart1.xml"]["checks"]
    assert len(chk["categories"]) == 12 and chk["series_titles"] == ["Demands"]
    xml = _chart_xml(path, 1)
    assert '<varyColors val="0"/>' in xml and "<legend>" not in xml
    ws = load_workbook(path)["KPI Summary"]
    start = next(r[0].row for r in ws.iter_rows() if r[0].value == "Demands by lifecycle status")
    assert sum(ws.cell(row=start + i, column=2).value for i in range(1, 13)) == ground_truth["demand_count"]


def test_kpi_summary_keeps_traceability_and_flags_exceptions(built, ground_truth):
    from conftest import sheet_rows
    path, _ = built
    ws = load_workbook(path)["KPI Summary"]
    header, rows = sheet_rows(ws, "Section")
    assert header == ["Section", "KPI", "Value", "Unit", "Definition", "Source records", "Details on sheet"]
    assert {r[0] for r in rows} == {"Demand pipeline", "Delivery performance", "Financial position (EUR)", "Data quality and capacity"}
    by = {r[1]: r for r in rows}
    assert by["Overdue open demands"][5] == ", ".join(ground_truth["overdue_open_ids"])
    assert by["Excluded, not converted: USD"][3] == "USD" and by["Excluded, not converted: USD"][2] == 5000
    assert ws.freeze_panes == "A5" and ws.auto_filter.ref.startswith("A4:G")
    assert len(ws.conditional_formatting) >= 10
    link = next(c for c in ws["G"] if c.value == "Forecast")
    assert link.hyperlink is not None and "Forecast" in (link.hyperlink.location or link.hyperlink.target or "")
    assert "PROVISIONAL" in ws["A2"].value and "fictional" in ws["A2"].value


def test_office_files_are_byte_reproducible(tmp_path, ds):
    """Two builds from the same data give identical files (timestamps pinned to the reporting cutoff)."""
    from infraflow.deck import build_deck
    from infraflow.excel_native import build_native_workbook
    for build, name in ((build_workbook, "a.xlsx"), (build_native_workbook, "b.xlsx"), (build_deck, "c.pptx")):
        build(ds, tmp_path / ("1" + name))
        build(ds, tmp_path / ("2" + name))
        assert (tmp_path / ("1" + name)).read_bytes() == (tmp_path / ("2" + name)).read_bytes(), name
