"""Structure of the Excel-native exercise workbook. Formula *results* need Excel (or the optional
scripts/verify_native_formulas.py); here we check what the generator is responsible for."""
import re

import pytest
from openpyxl import load_workbook

from infraflow.excel_native import build_native_workbook


@pytest.fixture(scope="module")
def native(tmp_path_factory, ds):
    path = tmp_path_factory.mktemp("native") / "native.xlsx"
    info = build_native_workbook(ds, path)
    return load_workbook(path), info


def test_sheets_tables_and_formulas_exist(native):
    wb, _ = native
    assert wb.sheetnames == ["How to use", "Analysis", "Invoices", "Demands", "Cost centres"]
    assert set(wb["Invoices"].tables) == {"tblInvoices"} and set(wb["Demands"].tables) == {"tblDemands"} and set(wb["Cost centres"].tables) == {"tblCostCentres"}
    formulas = [c.value for row in wb["Analysis"].iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("=")]
    used = {name for f in formulas for name in re.findall(r"([A-Z]+)\(", f)}
    assert {"SUMIFS", "COUNTIFS", "COUNTIF", "INDEX", "MATCH", "IFERROR", "IF", "SUM"} <= used
    assert len(formulas) >= 100
    assert len(wb["Analysis"].data_validations.dataValidation) == 1
    assert len(wb["Analysis"].conditional_formatting) >= 6 and len(wb["Invoices"].conditional_formatting) >= 2
    assert wb["Demands"].max_row == 51


def test_every_amount_formula_is_restricted_to_one_currency(native):
    """No SUMIFS over the invoice amounts may run without a currency criterion."""
    wb, _ = native
    for row in wb["Analysis"].iter_rows():
        for cell in row:
            if isinstance(cell.value, str) and "SUMIFS('Invoices'!$E" in cell.value:
                assert re.search(r"'Invoices'!\$F\$2:\$F\$\d+,(\"[A-Z]{3}\")", cell.value), f"{cell.coordinate} sums amounts without a currency filter"


def test_python_reference_values_and_no_cross_currency_total(native, ground_truth):
    wb, info = native
    assert info["actual_by_cc"] == {cc: v["actual_eur"] for cc, v in ground_truth["finance"].items()}
    assert info["excluded"] == {"Excluded as invalid|EUR": 1900, "Excluded as invalid|USD": 5000, "Unmapped cost centre|EUR": 4300, "Dated after the cutoff|EUR": 6400}
    ws = wb["Analysis"]
    block = [[c.value for c in row] for row in ws.iter_rows(min_row=14, max_row=21, max_col=6)]
    kinds = [r for r in block if r[1] in ("EUR", "USD")]
    assert [(r[0], r[1], r[4]) for r in kinds] == [("Excluded as invalid", "EUR", 1900), ("Excluded as invalid", "USD", 5000),
                                                   ("Unmapped cost centre", "EUR", 4300), ("Dated after the cutoff", "EUR", 6400)]
    assert not any(isinstance(r[3], str) and r[3].startswith("=SUM(") for r in block)          # no total across currencies
    usd = next(r for r in ws.iter_rows(min_row=14, max_row=21) if r[1].value == "USD")
    assert "USD" in usd[3].number_format and "€" not in usd[3].number_format
    inv = {r[0]: r for r in wb["Invoices"].iter_rows(min_row=2, values_only=True)}
    assert inv["INV-9006"][4:8] == (5000, "USD", "no", "UNSUPPORTED_CURRENCY")


def test_instructions_match_the_workbook(native):
    """The first sheet names the summary cell, the number of checks and the column of the SUMIFS actuals; they must be true."""
    wb, _ = native
    text = " ".join(str(c.value) for c in wb["How to use"]["A"] if c.value)
    ws = wb["Analysis"]
    checks = [c for row in ws.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith('=IF(') and '"OK","DIFF"' in c.value]
    summary = [c for row in ws.iter_rows() for c in row if isinstance(c.value, str) and "ALL OK" in c.value]
    assert len(checks) == 27 and "all 27 checks" in text
    assert len(summary) == 1 and f"Cell {summary[0].coordinate} summarises" in text
    assert ws["C6"].value == "Actual (SUMIFS)" and "column C 'Actual (SUMIFS)'" in text
    assert "not included in this file" in text and "PivotTable" in text and "PROVISIONAL" in text and "synthetic" in text


def test_desktop_excel_evidence_record():
    """Evidence extracted from the copy the project owner saved in Microsoft Excel (values Excel calculated)."""
    import json

    from infraflow import config as c
    rec = json.loads((c.ROOT / "evidence" / "excel_desktop_native_checks_2026-11-17.json").read_text())
    assert rec["application"] == "Microsoft Excel" and rec["calc_chain_present"] is True
    assert rec["check_cells"] == 27 and rec["not_ok"] == [] and rec["summary_cell"] == {"B45": "ALL OK"}
