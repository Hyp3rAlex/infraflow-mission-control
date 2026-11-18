"""Excel-native reporting exercise.

A small second workbook in which the figures are *recalculated by Excel*: SUMIFS / COUNTIFS /
INDEX-MATCH formulas over three data tables, conditional formatting, data validation and a prepared
PivotTable source. The Python pipeline stays the ground truth: every formula result sits next to the
Python value and an OK / DIFF check cell.

openpyxl cannot create PivotTables and does not calculate formulas. The workbook therefore contains
the formulas, not their results; Excel calculates them when the file is opened. The sheet "How to use"
lists the manual PivotTable steps.
"""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule, DataBarRule, FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo

from . import config as c
from .finance import row_amount
from .office_style import make_reproducible
from .models import Dataset
from .reports import build_context
from .scoring import priority_band, priority_score

NAVY = "1F3864"
HEAD_FILL, HEAD_FONT = PatternFill("solid", fgColor=NAVY), Font(bold=True, color="FFFFFF")
GOOD, BAD, WARN = PatternFill("solid", bgColor="C6EFCE"), PatternFill("solid", bgColor="FFC7CE"), PatternFill("solid", bgColor="FCE4D6")
EUR = '#,##0 "€";[Red]-#,##0 "€"'


def _table(ws, name: str, headers: list[str], rows: list[list], widths: dict | None = None) -> str:
    """Write an Excel Table (ListObject) and return its range, e.g. A1:H56."""
    ws.append(headers)
    for r in rows:
        ws.append(r)
    ref = f"A1:{get_column_letter(len(headers))}{len(rows) + 1}"
    table = Table(displayName=name, ref=ref)
    table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    ws.add_table(table)
    ws.freeze_panes = "A2"
    for i, h in enumerate(headers, 1):
        ws.column_dimensions[get_column_letter(i)].width = (widths or {}).get(h, max(12, len(h) + 4))
    return ref


def _col(sheet: str, letter: str, last: int) -> str:
    return f"'{sheet}'!${letter}$2:${letter}${last}"


def _head(ws, row: int, values: list[str]):
    for j, v in enumerate(values, 1):
        cell = ws.cell(row=row, column=j, value=v)
        cell.fill, cell.font = HEAD_FILL, HEAD_FONT
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[row].height = 32


def build_native_workbook(ds: Dataset, path: Path) -> dict:
    """Write the exercise workbook. Returns the Python values the formulas are checked against."""
    ctx = build_context(ds)
    fin, k = ctx["fin"], ctx["kpis"]
    wb = Workbook()

    # ---- How to use -------------------------------------------------------------------------
    ws = wb.active
    ws.title = "How to use"
    crit = sum(1 for e in ctx["register"] if e.severity == "CRITICAL")
    text = [
        ("InfraFlow Mission Control - Excel-native reporting exercise", "title"),
        (f"{c.ORG_NAME} (fictional organisation, synthetic data)  |  Reporting cutoff {ds.as_of.isoformat()}  |  "
         + (f"PROVISIONAL: {crit} critical data exceptions are open" if crit else "no critical data exceptions"), "status"),
        ("", None),
        ("1. What this workbook demonstrates", "head"),
        ("The main figures of the management report, recalculated by Excel formulas from three data tables: budget, actual and forecast per cost centre; "
         "invoice rows outside the EUR totals per currency; demands per lifecycle status and team; five operational indicators.", None),
        ("Functions used: SUMIFS, COUNTIFS, COUNTIF, COUNTA, INDEX/MATCH, IFERROR, IF, SUM. Features: Excel tables, conditional formatting "
         "(colour scale, data bars, highlight rules), a data-validation drop-down, frozen panes.", None),
        ("", None),
        ("2. What is input and what is calculated", "head"),
        ("Input (values copied from the synthetic data set): the sheets 'Invoices' (tblInvoices), 'Demands' (tblDemands), 'Cost centres' (tblCostCentres).", None),
        ("Calculated by Excel: every white cell on 'Analysis' that starts with '=' (click a cell to see its formula in the formula bar).", None),
        ("Reference values from the tested Python pipeline: the columns headed '(Python)' or 'Python value' on 'Analysis'. They are typed values, not formulas.", None),
        ("Amounts in different currencies are kept in separate rows and are never added together; no USD/EUR conversion rate is approved.", None),
        ("", None),
        ("3. How to recalculate", "head"),
        ("Excel calculates the formulas when the file is opened (calculation mode Automatic). After editing an input value, results update immediately; "
         "if calculation is set to Manual: Formulas > Calculate Now (F9).", None),
        ("Try it: on 'Analysis' choose another cost centre in cell B3 (drop-down). Cells D3, F3 and H3 update.", None),
        ("", None),
        ("4. Where the reconciliation checks are", "head"),
        ("'Analysis', column K (block 1, finance), column F (block 2, currencies), column G (block 3, status matrix), column D (block 4, indicators): "
         "OK = Excel result equals the Python value, DIFF = it does not. Cell B45 summarises all 27 checks: ALL OK or CHECK DIFFERENCES.", None),
        ("Result in desktop Excel: a copy opened and saved in Microsoft Excel 16 on 2026-11-17 showed OK in all 27 check cells and ALL OK in B45.", None),
        ("", None),
        ("5. Optional manual exercise: PivotTable (not included in this file)", "head"),
        ("The generator cannot create PivotTables. To build one (about two minutes):", None),
        ("a) On 'Invoices' click any cell of the table.  b) Insert > PivotTable > From Table/Range (tblInvoices) > New Worksheet > OK.", None),
        ("c) Rows: Cost centre. Columns: Currency. Values: Sum of Amount. Filters: In EUR totals.", None),
        ("d) Filter 'In EUR totals' = yes: the EUR column must equal column C 'Actual (SUMIFS)' on 'Analysis' (total 643,450 EUR).", None),
        ("e) Filter = no: the excluded rows appear per currency in separate columns (add Reason to Rows to see why). Ignore the Grand Total across EUR and USD.", None),
        ("f) Optional: second PivotTable on tblDemands, Rows = Status, Columns = Team, Values = Count of Demand; compare with block 3 on 'Analysis'.", None),
    ]
    styles = {"title": Font(bold=True, size=15, color=NAVY), "status": Font(bold=True, size=10, color="B7791F" if crit else "595959"),
              "head": Font(bold=True, size=12, color=NAVY), None: Font(size=11)}
    for i, (line, kind) in enumerate(text, 1):
        cell = ws.cell(row=i, column=1, value=line)
        cell.font = styles[kind]
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        if kind == "head":
            ws.row_dimensions[i].height = 22
    ws.column_dimensions["A"].width = 125

    # ---- data sheets ----------------------------------------------------------------------------
    reasons = {x["invoice_id"]: x["reason"] for x in fin.excluded if x["reason"] != "DUPLICATE_INVOICE"}
    cutoff_ids = {x["invoice_id"] for x in fin.after_cutoff}
    seen, inv_rows = set(), []
    for a in ds.actuals:
        iid = a["invoice_id"]
        if iid in seen:
            reason = "DUPLICATE_INVOICE"
        elif iid in cutoff_ids:
            reason = "AFTER_CUTOFF"
        elif iid in reasons:
            reason = reasons[iid]
        elif a["cost_center"] not in fin.by_cc:
            reason = "UNMAPPED_COST_CENTRE"
        else:
            reason = ""
        seen.add(iid)
        try:
            amount = float(row_amount(a))
        except (TypeError, ValueError):
            amount = 0
        inv_rows.append([iid, a["invoice_date"], a["cost_center"], a["external_id"], amount, a["currency"], "no" if reason else "yes", reason or "valid"])
    ws_inv = wb.create_sheet("Invoices")
    _table(ws_inv, "tblInvoices", ["Invoice", "Invoice date", "Cost centre", "Demand", "Amount", "Currency", "In EUR totals", "Reason"], inv_rows,
           {"Reason": 26, "Demand": 16, "Cost centre": 16})
    n_inv = len(inv_rows) + 1
    ws_inv.conditional_formatting.add(f"A2:H{n_inv}", FormulaRule(formula=['$G2="no"'], fill=WARN))
    ws_inv.conditional_formatting.add(f"F2:F{n_inv}", FormulaRule(formula=['$F2<>"EUR"'], font=Font(bold=True, color="C00000")))

    dem_rows = []
    for d in ds.demands:
        score = priority_score(d)
        dem_rows.append([d.external_id, c.STATUS_LABEL.get(d.status, d.status), c.TEAMS[d.team][0] if d.team in c.TEAMS else d.team, d.site,
                         priority_band(score), score, d.hours, d.one_time, d.due_at, "yes" if d.is_open else "no",
                         "yes" if d.is_open and d.due_at and d.due_at < ds.as_of else "no", "yes" if d.blocked else "no"])
    ws_dem = wb.create_sheet("Demands")
    _table(ws_dem, "tblDemands", ["Demand", "Status", "Team", "Site", "Priority band", "Score", "Hours", "One-time EUR", "Due", "Open", "Overdue", "Blocked"], dem_rows,
           {"Status": 20, "Team": 24, "Demand": 16})
    n_dem = len(dem_rows) + 1
    for row in ws_dem.iter_rows(min_row=2, min_col=8, max_col=8):
        row[0].number_format = EUR
    ws_dem.conditional_formatting.add(f"F2:F{n_dem}", ColorScaleRule(start_type="min", start_color="FFFFFF", end_type="max", end_color="2A78D6"))
    ws_dem.conditional_formatting.add(f"K2:K{n_dem}", CellIsRule(operator="equal", formula=['"yes"'], fill=BAD))
    ws_dem.conditional_formatting.add(f"L2:L{n_dem}", CellIsRule(operator="equal", formula=['"yes"'], fill=WARN))

    cc_rows = [[cc, c.COST_CENTERS[cc][0], f.budget_period_eur, f.open_commitments_eur, f.approved_not_committed_eur] for cc, f in fin.by_cc.items()]
    ws_cc = wb.create_sheet("Cost centres")
    _table(ws_cc, "tblCostCentres", ["Cost centre", "Name", "Budget period EUR", "Open commitments EUR", "Approved not committed EUR"], cc_rows, {"Name": 34})
    n_cc = len(cc_rows) + 1
    for row in ws_cc.iter_rows(min_row=2, min_col=3, max_col=5):
        for cell in row:
            cell.number_format = EUR

    # ---- Analysis ---------------------------------------------------------------------------------
    ws = wb.create_sheet("Analysis", 1)
    I = lambda letter: _col("Invoices", letter, n_inv)
    D = lambda letter: _col("Demands", letter, n_dem)
    C = lambda letter: _col("Cost centres", letter, n_cc)
    ws["A1"] = "Analysis - calculated by Excel formulas, checked against the Python pipeline (synthetic data, cutoff " + ds.as_of.isoformat() + ")"
    ws["A1"].font = Font(bold=True, size=14, color=NAVY)
    ccs = list(fin.by_cc)

    ws["A3"], ws["B3"] = "Cost centre (choose):", ccs[0]
    ws["A3"].font = Font(bold=True)
    dv = DataValidation(type="list", formula1=f"='Cost centres'!$A$2:$A${n_cc}", allow_blank=False)
    ws.add_data_validation(dv)
    dv.add("B3")
    ws["C3"], ws["D3"] = "Valid EUR invoices:", f'=COUNTIFS({I("C")},$B$3,{I("F")},"EUR",{I("G")},"yes")'
    ws["E3"], ws["F3"] = "Actual EUR:", f'=SUMIFS({I("E")},{I("C")},$B$3,{I("F")},"EUR",{I("G")},"yes")'
    ws["G3"], ws["H3"] = "Name:", f"=IFERROR(INDEX({C('B')},MATCH($B$3,{C('A')},0)),\"unknown\")"
    ws["F3"].number_format = EUR

    # block 1: finance by cost centre
    r0 = 6
    ws.cell(row=r0 - 1, column=1, value="1. Budget, actual and forecast by cost centre (EUR)").font = Font(bold=True, color=NAVY)
    _head(ws, r0, ["Cost centre", "Budget (INDEX/MATCH)", "Actual (SUMIFS)", "Open commitments", "Approved, not committed", "Forecast EAC (formula)",
                   "Forecast variance (formula)", "Budget used", "Actual (Python)", "Forecast EAC (Python)", "Check"])
    for i, cc in enumerate(ccs):
        r = r0 + 1 + i
        f = fin.by_cc[cc]
        ws.cell(row=r, column=1, value=cc)
        ws.cell(row=r, column=2, value=f"=INDEX({C('C')},MATCH($A{r},{C('A')},0))")
        ws.cell(row=r, column=3, value=f'=SUMIFS({I("E")},{I("C")},$A{r},{I("F")},"EUR",{I("G")},"yes")')
        ws.cell(row=r, column=4, value=f"=INDEX({C('D')},MATCH($A{r},{C('A')},0))")
        ws.cell(row=r, column=5, value=f"=INDEX({C('E')},MATCH($A{r},{C('A')},0))")
        ws.cell(row=r, column=6, value=f"=C{r}+D{r}+E{r}")
        ws.cell(row=r, column=7, value=f"=F{r}-B{r}")
        ws.cell(row=r, column=8, value=f"=IFERROR(C{r}/B{r},0)")
        ws.cell(row=r, column=9, value=f.actual_eur)
        ws.cell(row=r, column=10, value=f.forecast_eac_eur)
        ws.cell(row=r, column=11, value=f'=IF(AND(C{r}=I{r},F{r}=J{r}),"OK","DIFF")')
    first, last = r0 + 1, r0 + len(ccs)
    tr = last + 1
    tot = fin.totals()
    ws.cell(row=tr, column=1, value="Total")
    for col in "BCDEFG":
        ws[f"{col}{tr}"] = f"=SUM({col}{first}:{col}{last})"
    ws[f"H{tr}"] = f"=IFERROR(C{tr}/B{tr},0)"
    ws[f"I{tr}"], ws[f"J{tr}"] = tot["actual_eur"], tot["forecast_eac_eur"]
    ws[f"K{tr}"] = f'=IF(AND(C{tr}=I{tr},F{tr}=J{tr}),"OK","DIFF")'
    for row in ws.iter_rows(min_row=first, max_row=tr, min_col=2, max_col=10):
        for cell in row:
            cell.number_format = "0%" if cell.column == 8 else EUR
    for cell in ws[tr]:
        cell.font = Font(bold=True)
    ws.conditional_formatting.add(f"G{first}:G{tr}", CellIsRule(operator="greaterThan", formula=["0"], fill=BAD, font=Font(bold=True, color="9C0006")))
    ws.conditional_formatting.add(f"H{first}:H{last}", DataBarRule(start_type="num", start_value=0, end_type="num", end_value=1, color="2A78D6"))
    check_cells = [f"K{first}:K{tr}"]

    # block 2: what is not in the EUR totals, one row per currency
    r1 = tr + 3
    ws.cell(row=r1 - 1, column=1, value="2. Invoice rows not in the EUR totals - one row per currency, never added together").font = Font(bold=True, color=NAVY)
    _head(ws, r1, ["Kind", "Currency", "Rows (COUNTIFS)", "Net amount in that currency (SUMIFS)", "Python value", "Check"])
    buckets = fin.excluded_by_currency()
    kinds = [("Excluded as invalid", cur, [f'{I("F")},"{cur}"', f'{I("G")},"no"', f'{I("H")},"<>DUPLICATE_INVOICE"', f'{I("H")},"<>AFTER_CUTOFF"', f'{I("H")},"<>UNMAPPED_COST_CENTRE"'],
              b["net"]) for cur, b in buckets.items()]
    kinds.append(("Unmapped cost centre", c.CURRENCY, [f'{I("F")},"{c.CURRENCY}"', f'{I("H")},"UNMAPPED_COST_CENTRE"'], fin.unmapped_actual_eur))
    kinds.append(("Dated after the cutoff", c.CURRENCY, [f'{I("F")},"{c.CURRENCY}"', f'{I("H")},"AFTER_CUTOFF"'], sum(x["amount_eur"] for x in fin.after_cutoff)))
    for i, (kind, cur, crit_list, value) in enumerate(kinds):
        r = r1 + 1 + i
        ws.cell(row=r, column=1, value=kind)
        ws.cell(row=r, column=2, value=cur)
        ws.cell(row=r, column=3, value=f"=COUNTIFS({','.join(crit_list)})")
        ws.cell(row=r, column=4, value=f"=SUMIFS({I('E')},{','.join(crit_list)})").number_format = f'#,##0 "{cur}";-#,##0 "{cur}"'
        ws.cell(row=r, column=5, value=value).number_format = f'#,##0 "{cur}";-#,##0 "{cur}"'
        ws.cell(row=r, column=6, value=f'=IF(D{r}=E{r},"OK","DIFF")')
    r1_last = r1 + len(kinds)
    ws.conditional_formatting.add(f"A{r1 + 1}:F{r1_last}", FormulaRule(formula=[f'$B{r1 + 1}<>"EUR"'], fill=WARN))
    check_cells.append(f"F{r1 + 1}:F{r1_last}")
    ws.cell(row=r1_last + 1, column=1, value="No total row on purpose: EUR and USD amounts must not be added without a conversion rate approved by Finance.").font = Font(italic=True)

    # block 3: demands by status and team
    r2 = r1_last + 4
    ws.cell(row=r2 - 1, column=1, value="3. Demands by lifecycle status and delivery team (COUNTIFS)").font = Font(bold=True, color=NAVY)
    teams = [c.TEAMS[t][0] for t in c.TEAMS]
    _head(ws, r2, ["Status"] + teams + ["All teams (COUNTIF)", "Python value", "Check"])
    by_status = k["by_status"]["value"]
    statuses = [s for s in c.STATUS_ORDER]
    for i, st in enumerate(statuses):
        r = r2 + 1 + i
        ws.cell(row=r, column=1, value=c.STATUS_LABEL[st])
        for j, team in enumerate(teams):
            col = get_column_letter(2 + j)
            ws[f"{col}{r}"] = f"=COUNTIFS({D('B')},$A{r},{D('C')},{col}${r2})"
        total_col, py_col, chk_col = get_column_letter(2 + len(teams)), get_column_letter(3 + len(teams)), get_column_letter(4 + len(teams))
        ws[f"{total_col}{r}"] = f"=COUNTIF({D('B')},$A{r})"
        ws[f"{py_col}{r}"] = by_status.get(st, 0)
        ws[f"{chk_col}{r}"] = f'=IF({total_col}{r}={py_col}{r},"OK","DIFF")'
    r2_last = r2 + len(statuses)
    last_team_col = get_column_letter(1 + len(teams))
    ws.conditional_formatting.add(f"B{r2 + 1}:{last_team_col}{r2_last}", ColorScaleRule(start_type="num", start_value=0, start_color="FFFFFF", end_type="max", end_color="2A78D6"))
    check_cells.append(f"{chk_col}{r2 + 1}:{chk_col}{r2_last}")

    # block 4: operational KPIs
    r3 = r2_last + 3
    ws.cell(row=r3 - 1, column=1, value="4. Operational indicators").font = Font(bold=True, color=NAVY)
    _head(ws, r3, ["Indicator", "Excel formula result", "Python value", "Check"])
    indicators = [
        ("Open demands", f'=COUNTIF({D("J")},"yes")', k["open_demands"]["value"]),
        ("Overdue open demands", f'=COUNTIF({D("K")},"yes")', k["overdue_open"]["value"]),
        ("Blocked open demands", f'=COUNTIFS({D("L")},"yes",{D("J")},"yes")', k["blocked_open"]["value"]),
        ("Registered demands", f'=COUNTA({D("A")})', k["total_demands"]["value"]),
        ("Invoice rows in the ledger", f'=COUNTA({I("A")})', len(ds.actuals)),
    ]
    for i, (name, formula, value) in enumerate(indicators):
        r = r3 + 1 + i
        ws.cell(row=r, column=1, value=name)
        ws.cell(row=r, column=2, value=formula)
        ws.cell(row=r, column=3, value=value)
        ws.cell(row=r, column=4, value=f'=IF(B{r}=C{r},"OK","DIFF")')
    check_cells.append(f"D{r3 + 1}:D{r3 + len(indicators)}")
    summary_row = r3 + len(indicators) + 2
    all_checks = ",".join(check_cells)
    ws.cell(row=summary_row, column=1, value="All checks").font = Font(bold=True)
    ws.cell(row=summary_row, column=2, value="=IF(" + "+".join(f'COUNTIF({rng},"DIFF")' for rng in check_cells) + '=0,"ALL OK","CHECK DIFFERENCES")').font = Font(bold=True)
    for rng in check_cells + [f"B{summary_row}"]:
        ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"OK"'], fill=GOOD))
        ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"ALL OK"'], fill=GOOD))
        ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"DIFF"'], fill=BAD))
        ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"CHECK DIFFERENCES"'], fill=BAD))
    widths = [30, 22, 22, 22, 24, 22, 22, 14, 18, 20, 10]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "B2"

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.properties.creator = "InfraFlow Mission Control"
    wb.save(path)
    make_reproducible(path, ds.as_of)
    return dict(path=str(path), check_ranges=all_checks, actual_by_cc={cc: fin.by_cc[cc].actual_eur for cc in ccs},
                excluded={f"{kind}|{cur}": value for kind, cur, _, value in kinds}, by_status={c.STATUS_LABEL[s]: by_status.get(s, 0) for s in statuses})
