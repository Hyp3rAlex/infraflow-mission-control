"""Management workbook (openpyxl).

All numbers are written as static values computed in Python, so the workbook does not depend on
Excel recalculating formulas. Source-data sheets have grey tabs, calculated sheets blue tabs.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from . import config as c
from .finance import row_amount
from .models import Dataset
from .office_style import make_reproducible, AMBER, AMBER_FILL, BLUE_DARK, BLUE_LIGHT, BLUE_MID, GREY_MUTED, RED, RED_FILL, TEAL, highlight_point, style_bar_chart
from .reports import HERO, MODE, action_register, build_context, decisions_required, hero_facts
from .scoring import priority_band, priority_score

NAVY, GREY, BLUE = "1F3864", "7F7F7F", "2E75B6"
HEAD_FILL = PatternFill("solid", fgColor=NAVY)
HEAD_FONT = Font(bold=True, color="FFFFFF")
BAND = PatternFill("solid", fgColor="F2F2F2")
WARN = PatternFill("solid", fgColor=AMBER_FILL)
BAD = PatternFill("solid", fgColor=RED_FILL)
SECTION_FILL = PatternFill("solid", fgColor="DCE6F2")
THIN = Border(bottom=Side(style="thin", color="BFBFBF"))
EUR = '#,##0 "€";[Red]-#,##0 "€"'
HOURS = '#,##0" h";[Red]-#,##0" h"'
DATE = "yyyy-mm-dd"
TITLED_HEADER_ROW = 4            # sheets with a title block: title, status line, blank, header
ROW_CM = 0.53                    # default row height (15 pt) in cm, used to place charts and notes without overlap


def _rows_for(height_cm: float) -> int:
    return int(height_cm / ROW_CM) + 2


DATA_DICTIONARY = [
    ("demands.csv", "external_id", "Stable demand identifier ORION-REQ-NNN; key across all systems."),
    ("demands.csv", "demand_status", "Current lifecycle status (see Assumptions for the list)."),
    ("demands.csv", "business_impact / urgency / risk_reduction / strategic_alignment score", "Analyst rating 0-5 used for the priority score."),
    ("demands.csv", "estimated_one_time_eur / estimated_monthly_recurring_eur", "Cost estimate of the requested option in EUR."),
    ("demands.csv", "estimated_hours / delivery_team", "Delivery effort in engineer-hours and the responsible team."),
    ("demands.csv", "blocked / blocked_reason", "Flag and reason; blocked is not a status."),
    ("status_events.csv", "previous_status / new_status / occurred_at", "Append-only status history used for lead time, triage time and ageing."),
    ("decisions.csv", "approver_role / decision / rationale", "Human decision record; mandatory for approved, deferred and rejected."),
    ("budgets.csv", "approved_budget_eur", "Approved budget per cost centre and month."),
    ("actuals.csv", "invoice_id / amount / currency / credit_note_ref / po_id", "Invoices and credit notes in the currency of the row; negative amounts need a credit-note reference."),
    ("commitments.csv", "approved_commitment_eur / recognized_actual_eur / status", "Purchase orders; outstanding = max(approved - recognised, 0) for open orders."),
    ("capacity.csv", "available_hours / allocated_hours", "Engineer-hours per team and month."),
    ("allocations.csv", "external_id / hours", "What the allocation consists of: RUN (operations) or an approved demand."),
    ("options.csv", "one_time_eur / monthly_eur / hours", "Assessed options for a demand."),
]


def _sheet(wb, title: str, headers: list[str], rows: list[list], tab: str, money_cols=(), wrap_cols=(), widths=None,
           heading: str | None = None, status: str | None = None, hour_cols=(), date_cols=()):
    """One table per sheet. With `heading`, rows 1-2 hold a title and a status line and the table starts in row 4."""
    ws = wb.create_sheet(title)
    ws.sheet_properties.tabColor = tab
    top = 1
    if heading:
        ws.cell(row=1, column=1, value=heading).font = Font(bold=True, size=14, color=NAVY)
        if status:
            ws.cell(row=2, column=1, value=status).font = Font(bold=True, size=10, color=AMBER if "PROVISIONAL" in status else GREY_MUTED)
        ws.row_dimensions[1].height = 22
        top = TITLED_HEADER_ROW
    for j, h in enumerate(headers, 1):
        ws.cell(row=top, column=j, value=h)
    for i, r in enumerate(rows, top + 1):
        for j, v in enumerate(r, 1):
            ws.cell(row=i, column=j, value=v)
    for cell in ws[top]:
        cell.fill, cell.font = HEAD_FILL, HEAD_FONT
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[top].height = 32
    ws.freeze_panes = f"A{top + 1}"
    if rows:
        ws.auto_filter.ref = f"A{top}:{get_column_letter(len(headers))}{len(rows) + top}"
    for i, h in enumerate(headers, 1):
        letter = get_column_letter(i)
        longest = max([len(str(h)) * 0.8] + [len(str(r[i - 1])) for r in rows if i - 1 < len(r) and r[i - 1] is not None], default=10)
        ws.column_dimensions[letter].width = (widths or {}).get(h, min(max(longest + 3, 11), 60 if h in wrap_cols else 36))
        for row in ws.iter_rows(min_row=top + 1, max_row=top + len(rows), min_col=i, max_col=i):
            cell = row[0]
            cell.border = THIN
            if h in money_cols:
                cell.number_format = EUR
            elif h in hour_cols:
                cell.number_format = HOURS
            elif h in date_cols:
                cell.number_format = DATE
            numeric = isinstance(cell.value, (int, float)) and not isinstance(cell.value, bool)
            cell.alignment = Alignment(wrap_text=h in wrap_cols, vertical="top", horizontal="right" if numeric else None)
    return ws


def _note(ws, row: int, text: str, font, last_col: str = "K", chars_per_line: int = 170) -> None:
    """A note below a table: merged across the table width and wrapped (not part of any filtered range)."""
    ws.merge_cells(f"A{row}:{last_col}{row}")
    cell = ws.cell(row=row, column=1, value=text)
    cell.font, cell.alignment = font, Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[row].height = 15 * max(1, -(-len(text) // chars_per_line)) + 2


def _status_line(ds, crit: int) -> str:
    return (f"{c.ORG_NAME} (fictional, synthetic data)  |  Reporting cutoff {ds.as_of.isoformat()}  |  "
            + (f"PROVISIONAL: {crit} critical data exceptions open (sheet Exceptions)" if crit else "No critical data exceptions"))


def build_workbook(ds: Dataset, path: Path) -> dict:
    """Write the workbook and return the values placed in the KPI and Forecast sheets (for verification)."""
    ctx = build_context(ds)
    fin, cap, k = ctx["fin"], ctx["cap"], ctx["kpis"]
    wb = Workbook()
    ws = wb.active
    ws.title = "README"
    ws.sheet_properties.tabColor = NAVY
    crit = ctx["facts_crit"] = sum(1 for e in ctx["register"] if e.severity == "CRITICAL")
    lines = [("InfraFlow Mission Control - Management Workbook", True),
             (f"Organisation: {c.ORG_NAME} (fictional). All data is synthetic.", False),
             (f"Reporting date (cutoff, inclusive): {ds.as_of.isoformat()}", False),
             (f"Data mode: {MODE}", False),
             (f"Status: {'PROVISIONAL - ' + str(crit) + ' critical exceptions open (see Exceptions)' if crit else 'No critical exceptions'}", False),
             ("", False),
             ("Sheets", True),
             ("KPI Summary, Forecast, Capacity, Exceptions, Actions, Hero Scenario - calculated results (blue tabs)", False),
             ("Demand Register, Budget, Actuals, Commitments - source data with calculated flag columns marked 'calc:' (grey tabs)", False),
             ("Assumptions, Data Dictionary - definitions", False),
             ("", False),
             ("Notes", True),
             ("Numbers are static values computed by the Python pipeline; the workbook contains no formulas that need recalculation.", False),
             ("Charts: native, editable Excel charts. Titles and legends are set not to overlay the plot area (an earlier version showed overlapping labels in Excel).", False),
             ("Colours: navy/blue = data series, red = overrun or shortfall, amber = needs attention or provisional, teal = within budget.", False),
             ("Every KPI names the records it was computed from. Reports, slide deck and this workbook use the same data set.", False),
             ("Amounts are EUR unless a row states another currency. Non-EUR amounts are shown in their own currency and are never added to EUR figures.", False),
             ("The workbook is generated and read back with openpyxl. The project owner opened earlier versions in Microsoft Excel; this version must be re-checked after regeneration (checklist: docs/OFFICE_VISUAL_QA.md).", False),
             ("A separate file, infraflow_excel_native_exercise.xlsx, shows the same figures recalculated with Excel formulas and conditional formatting.", False)]
    for i, (text, bold) in enumerate(lines, 1):
        colour = AMBER if text.startswith("Status: PROVISIONAL") else (NAVY if bold else "000000")
        ws.cell(row=i, column=1, value=text).font = Font(bold=bold or text.startswith("Status: PROVISIONAL"), size=14 if i == 1 else 11, color=colour)
    ws.column_dimensions["A"].width = 120

    # KPI Summary -------------------------------------------------------------
    tot = fin.totals()
    status = _status_line(ds, crit)
    ids = lambda key: ", ".join(k[key]["source_ids"])
    D, F, Q = "Demand pipeline", "Delivery performance", "Data quality and capacity"
    M = "Financial position (EUR)"
    # section, KPI, value, unit, definition, source records, sheet to look at, attention rule
    kpi_rows = [
        [D, "Registered demands", k["total_demands"]["value"], "demands", k["total_demands"]["definition"], "demands.csv", "Demand Register", None],
        [D, "Open demands", k["open_demands"]["value"], "demands", k["open_demands"]["definition"], "demands.csv", "Demand Register", None],
        [D, "New in the last 7 days", k["intake_last_7_days"]["value"], "demands", k["intake_last_7_days"]["definition"], ids("intake_last_7_days"), "Demand Register", None],
        [D, "Awaiting decision", k["approval_pending"]["value"], "demands", k["approval_pending"]["definition"], ids("approval_pending"), "Actions", None],
        [D, "Overdue open demands", k["overdue_open"]["value"], "demands", k["overdue_open"]["definition"], ids("overdue_open"), "Demand Register", "warn"],
        [D, "Blocked open demands", k["blocked_open"]["value"], "demands", k["blocked_open"]["definition"], ids("blocked_open"), "Demand Register", "warn"],
        [D, "Stale open demands", k["stale_open"]["value"], "demands", k["stale_open"]["definition"], ids("stale_open"), "Demand Register", "warn"],
        [D, "Open demands without owner", k["unassigned_open"]["value"], "demands", k["unassigned_open"]["definition"], ids("unassigned_open"), "Demand Register", "warn"],
        [D, "Intake completeness %", k["completeness_pct"]["value"], "%", k["completeness_pct"]["definition"], "incomplete: " + ids("completeness_pct"), "Demand Register", None],
        [F, "Completed demands", k["completed_total"]["value"], "demands", k["completed_total"]["definition"], ids("completed_total"), "Demand Register", None],
        [F, "Median lead time (days)", k["median_lead_time_days"]["value"], "calendar days", k["median_lead_time_days"]["definition"], "status_events.csv", "Demand Register", None],
        [F, "Median triage time (working days)", k["median_triage_business_days"]["value"], "working days", k["median_triage_business_days"]["definition"], "status_events.csv", "Demand Register", None],
        [F, "On-time delivery %", k["on_time_delivery_pct"]["value"], "%", k["on_time_delivery_pct"]["definition"], "late: " + ids("on_time_delivery_pct"), "Demand Register", None],
        [F, "High/Highest demands failing a gate", k["high_priority_not_approvable"]["value"], "demands", k["high_priority_not_approvable"]["definition"], ids("high_priority_not_approvable"), "Actions", "warn"],
        [M, "Budget (period) EUR", tot["budget_period_eur"], "EUR", "Approved budget of all cost centres for the budget period.", "budgets.csv", "Forecast", None],
        [M, "Actual to date EUR", tot["actual_eur"], "EUR", "Valid, unique invoices and credit notes dated on or before the cutoff.", "actuals.csv", "Actuals", None],
        [M, "Open commitments EUR", tot["open_commitments_eur"], "EUR", "max(approved - recognised, 0) for open purchase orders.", "commitments.csv", "Commitments", None],
        [M, "Approved, not committed EUR", tot["approved_not_committed_eur"], "EUR", "Period cost of approved demands without a purchase order.", "demands.csv", "Forecast", None],
        [M, "Forecast EAC EUR", tot["forecast_eac_eur"], "EUR", "Actual + open commitments + approved, not committed. Ledger basis; provisional while critical exceptions are open.", "Forecast sheet", "Forecast", None],
        [M, "Forecast variance EUR", tot["forecast_variance_eur"], "EUR", "Forecast EAC - budget (positive = overrun, negative = headroom).", "Forecast sheet", "Forecast", "overrun"],
        [M, "Forecast EAC, invoice basis EUR", k["finance_forecast_eac_invoice_basis_eur"]["value"], "EUR", k["finance_forecast_eac_invoice_basis_eur"]["definition"], ids("finance_forecast_eac_invoice_basis_eur"), "Forecast", None],
        [M, "Unreconciled purchase orders EUR", k["finance_unreconciled_po_eur"]["value"], "EUR", k["finance_unreconciled_po_eur"]["definition"], ids("finance_unreconciled_po_eur"), "Commitments", "warn"],
        [M, "Unmapped spend EUR", fin.unmapped_actual_eur, "EUR", k["finance_unmapped_actual_eur"]["definition"], ", ".join(fin.unmapped_invoice_ids), "Actuals", "warn"],
        [M, "Excluded invalid invoices, gross EUR", k["finance_excluded_eur_gross"]["value"], "EUR", k["finance_excluded_eur_gross"]["definition"], ids("finance_excluded_eur_gross"), "Actuals", "warn"],
        [M, "Excluded invalid invoices, net EUR", k["finance_excluded_eur_net"]["value"], "EUR", k["finance_excluded_eur_net"]["definition"], ids("finance_excluded_eur_net"), "Actuals", None],
    ] + [
        [M, f"Excluded, not converted: {cur}", b["net"], cur, k["finance_excluded_foreign"]["definition"], ", ".join(b["invoice_ids"]), "Actuals", "foreign"]
        for cur, b in fin.excluded_by_currency().items() if cur != c.CURRENCY
    ] + [
        [Q, "Critical exceptions", crit, "findings", "Exception register entries with severity CRITICAL. While any is open, the report is PROVISIONAL.", "Exceptions", "Exceptions", "warn"],
        [Q, "Over-allocated team-months", k["overallocated_team_months"]["value"], "team-months", k["overallocated_team_months"]["definition"], ids("overallocated_team_months"), "Capacity", "warn"],
    ]
    heads = ["Section", "KPI", "Value", "Unit", "Definition", "Source records", "Details on sheet"]
    ws = _sheet(wb, "KPI Summary", heads, [r[:7] for r in kpi_rows], BLUE, wrap_cols=("Definition", "Source records"),
                widths={"Section": 24, "KPI": 36, "Value": 15, "Unit": 13, "Definition": 64, "Source records": 46, "Details on sheet": 18},
                heading="KPI Summary - infrastructure demand portfolio", status=status)
    top = TITLED_HEADER_ROW
    previous = None
    for n, r in enumerate(kpi_rows):
        row = top + 1 + n
        value, link = ws.cell(row=row, column=3), ws.cell(row=row, column=7)
        unit = r[3]
        value.number_format = EUR if unit == "EUR" else ("0.0" if unit in ("%", "calendar days", "working days") else
                                                        (f'#,##0 "{unit}"' if len(unit) == 3 and unit.isupper() else "#,##0"))
        value.font = Font(bold=r[1] in ("Open demands", "Awaiting decision", "Forecast EAC EUR", "Forecast variance EUR", "Critical exceptions"))
        link.hyperlink, link.font = f"#'{r[6]}'!A1", Font(color="0563C1", underline="single")
        if r[0] != previous:
            for col in range(1, 8):
                ws.cell(row=row, column=col).border = Border(top=Side(style="medium", color=NAVY), bottom=Side(style="thin", color="BFBFBF"))
            ws.cell(row=row, column=1).font = Font(bold=True, color=NAVY)
            previous = r[0]
        else:
            ws.cell(row=row, column=1).font = Font(color="A6A6A6")
        ref = f"C{row}"
        if r[7] == "warn":                    # material exception: amber when the value is above zero
            ws.conditional_formatting.add(ref, CellIsRule(operator="greaterThan", formula=["0"], fill=WARN, font=Font(bold=True, color="7F4F00")))
        elif r[7] == "overrun":               # red only for a genuine overrun
            ws.conditional_formatting.add(ref, CellIsRule(operator="greaterThan", formula=["0"], fill=BAD, font=Font(bold=True, color=RED)))
        elif r[7] == "foreign":
            ws.conditional_formatting.add(ref, CellIsRule(operator="notEqual", formula=["0"], fill=WARN, font=Font(bold=True, color="7F4F00")))
    ws.cell(row=top - 1, column=1, value="Amber = needs attention when above zero. Red = overrun. Non-EUR amounts are shown in their own currency and are not part of any EUR figure.").font = Font(italic=True, size=9, color=GREY_MUTED)
    start = top + len(kpi_rows) + 3
    ws.cell(row=start, column=1, value="Demands by lifecycle status").font = Font(bold=True, color=NAVY)
    ws.cell(row=start, column=2, value="Demands").font = Font(bold=True, color=NAVY)
    by_status = list(k["by_status"]["value"].items())
    for i, (st, n) in enumerate(reversed(by_status), 1):      # reversed: a horizontal bar chart draws the first row at the bottom
        ws.cell(row=start + i, column=1, value=c.STATUS_LABEL[st])
        ws.cell(row=start + i, column=2, value=n)
    chart = BarChart()
    chart.type, chart.title = "bar", "Demands by lifecycle status (number of demands, all 50)"
    chart.add_data(Reference(ws, min_col=2, min_row=start, max_row=start + len(by_status)), titles_from_data=True)
    chart.set_categories(Reference(ws, min_col=1, min_row=start + 1, max_row=start + len(by_status)))
    style_bar_chart(chart, value_format="0", colours=[BLUE_MID], legend=False, labels="all", plot=(0.22, 0.12, 0.72, 0.84), value_min=0, gap_width=50)
    chart.height, chart.width = 11, 18
    ws.add_chart(chart, f"D{start}")

    # Demand Register -----------------------------------------------------------
    gates = {r["demand"].external_id: r["gates"] for r in ctx["queue"]}
    heads = ["External ID", "Title", "Type", "Status", "calc: Score", "calc: Priority band", "Site", "Department", "Category", "Requested", "Due", "Owner",
             "Team", "Hours", "Cost centre", "One-time EUR", "Monthly EUR", "Security review", "Blocked", "Blocked reason", "Depends on", "Decision",
             "Decision date", "Decided by", "Next review", "calc: Funding gate", "calc: Capacity gate", "calc: Overdue"]
    rows = []
    for d in ds.demands:
        g = gates.get(d.external_id)
        score = priority_score(d)
        rows.append([d.external_id, d.title, d.request_type, c.STATUS_LABEL.get(d.status, d.status), score, priority_band(score), d.site, d.department, d.category,
                     d.requested_at, d.due_at, d.triage_owner or "UNASSIGNED", c.TEAMS[d.team][0] if d.team in c.TEAMS else d.team, d.hours, d.cost_center or "MISSING",
                     d.one_time, d.monthly, d.security_status, "yes" if d.blocked else "no", d.blocked_reason, d.depends_on, d.decision_outcome, d.decision_date,
                     d.decision_owner, d.next_review_at,
                     "" if g is None else {True: "pass", False: "FAIL", None: "unavailable"}[g.funding_pass],
                     "" if g is None else {True: "pass", False: "FAIL", None: "unavailable"}[g.capacity_pass],
                     "yes" if d.is_open and d.due_at and d.due_at < ds.as_of else "no"])
    ws = _sheet(wb, "Demand Register", heads, rows, GREY, money_cols=("One-time EUR", "Monthly EUR"), wrap_cols=("Title", "Blocked reason"),
                widths={"Title": 48, "Blocked reason": 50, "External ID": 16, "Requested": 12, "Due": 12, "Decision date": 12, "Next review": 12,
                        "Owner": 26, "Team": 22, "Decided by": 30, "Depends on": 15},
                date_cols=("Requested", "Due", "Decision date", "Next review"), hour_cols=("Hours",))
    for row in ws.iter_rows(min_row=2):
        if row[11].value == "UNASSIGNED" or row[14].value == "MISSING" or row[27].value == "yes":
            for cell in (row[11], row[14], row[27]):
                if cell.value in ("UNASSIGNED", "MISSING", "yes"):
                    cell.fill = WARN

    # Budget ---------------------------------------------------------------------------
    months = c.PERIOD_MONTHS
    rows = []
    for cc in fin.by_cc:
        for m in months:
            b, a = fin.monthly_budget.get((cc, m), 0), fin.monthly_actual.get((cc, m), 0)
            rows.append([cc, c.COST_CENTERS[cc][0], m, b, a, a - b, "to date" if m <= ds.as_of.strftime("%Y-%m") else "future"])
    _sheet(wb, "Budget", ["Cost centre", "Name", "Month", "Approved budget EUR", "calc: Actual EUR", "calc: Variance EUR", "calc: Period"], rows, GREY,
           money_cols=("Approved budget EUR", "calc: Actual EUR", "calc: Variance EUR"))

    # Actuals ----------------------------------------------------------------------------
    excluded = {}
    seen = set()
    reasons = {x["invoice_id"]: x["reason"] for x in fin.excluded}
    cutoff_ids = {x["invoice_id"] for x in fin.after_cutoff}
    rows = []
    for a in ds.actuals:
        iid = a["invoice_id"]
        dup = iid in seen
        seen.add(iid)
        reason = "DUPLICATE_INVOICE" if dup else ("AFTER_CUTOFF" if iid in cutoff_ids else (reasons.get(iid, "") if reasons.get(iid) != "DUPLICATE_INVOICE" else ""))
        if not reason and a["cost_center"] not in fin.by_cc:
            reason = "UNMAPPED (counted as unmapped spend)"
        try:
            amount = float(row_amount(a))
        except (TypeError, ValueError):
            amount = row_amount(a)
        rows.append([iid, a["invoice_date"], a["month"], a["cost_center"], a["external_id"], amount, a["currency"], a["credit_note_ref"], a["po_id"],
                     "no" if reason else "yes", reason])
    ws = _sheet(wb, "Actuals", ["Invoice", "Invoice date", "Month", "Cost centre", "Demand", "Amount", "Currency", "Credit-note ref", "PO",
                                "calc: In cost-centre totals", "calc: Reason if not"], rows, GREY, widths={"calc: Reason if not": 36, "Invoice date": 13})
    for row in ws.iter_rows(min_row=2):
        cur = row[6].value or "?"
        row[5].number_format = EUR if cur == c.CURRENCY else f'#,##0 "{cur}";-#,##0 "{cur}"'      # each amount in its own currency
        if row[9].value == "no":
            for cell in row:
                cell.fill = WARN

    # Commitments ---------------------------------------------------------------------------
    rows = [[p["po_id"], p["month"], p["cost_center"], p["external_id"] or "run contract", float(p["approved_commitment_eur"]), float(p["recognized_actual_eur"]),
             p["status"], fin.po_outstanding.get(p["po_id"])] for p in ds.commitments]
    _sheet(wb, "Commitments", ["PO", "Month", "Cost centre", "Demand", "Approved commitment EUR", "Recognised actual EUR", "Status", "calc: Outstanding EUR"], rows, GREY,
           money_cols=("Approved commitment EUR", "Recognised actual EUR", "calc: Outstanding EUR"))

    # Forecast ----------------------------------------------------------------------------------
    keys = ["budget_period_eur", "budget_to_date_eur", "actual_eur", "variance_to_date_eur", "open_commitments_eur", "approved_not_committed_eur",
            "uncommitted_budget_eur", "forecast_eac_eur", "forecast_variance_eur"]
    heads = ["Cost centre", "Name", "Budget (period)", "Budget to date", "Actual", "Variance to date", "Open commitments", "Approved, not committed",
             "Uncommitted budget", "Forecast EAC", "Forecast variance"]
    rows = [[cc, c.COST_CENTERS[cc][0]] + [f.as_dict()[x] for x in keys] for cc, f in fin.by_cc.items()]
    rows.append(["TOTAL", "All cost centres"] + [tot[x] for x in keys])
    ws = _sheet(wb, "Forecast", heads, rows, BLUE, money_cols=tuple(heads[2:]),
                widths={"Cost centre": 15, "Name": 30, **{h: 15 for h in heads[2:]}},
                heading="Forecast at completion by cost centre (EUR, budget period " + f"{c.PERIOD_MONTHS[0]} to {c.PERIOD_MONTHS[-1]})", status=status)
    top = TITLED_HEADER_ROW
    first, last = top + 1, top + len(rows) - 1          # cost-centre rows; the TOTAL row follows
    for cell in ws[top + len(rows)]:
        cell.font = Font(bold=True)
        cell.border = Border(top=Side(style="thin", color=NAVY), bottom=Side(style="double", color=NAVY))
    # Excel conditional formatting: overrun red, headroom teal (re-evaluated if a value is edited)
    ws.conditional_formatting.add(f"K{first}:K{last + 1}", CellIsRule(operator="greaterThan", formula=["0"], fill=BAD, font=Font(bold=True, color=RED)))
    ws.conditional_formatting.add(f"K{first}:K{last + 1}", CellIsRule(operator="lessThanOrEqual", formula=["0"], font=Font(color=TEAL)))
    over = [(cc, f) for cc, f in fin.by_cc.items() if f.forecast_variance_eur > 0]
    note_row = top + len(rows) + 2
    notes = [("Overrun: " + "; ".join(f"{cc} forecast {f.forecast_eac_eur:,.0f} EUR against a budget of {f.budget_period_eur:,.0f} EUR, {f.forecast_variance_eur:,.0f} EUR over" for cc, f in over)
              if over else "No cost centre is forecast over budget.", Font(bold=True, color=RED if over else TEAL)),
             (f"Overall: forecast {tot['forecast_eac_eur']:,.0f} EUR against {tot['budget_period_eur']:,.0f} EUR, {-tot['forecast_variance_eur']:,.0f} EUR below budget on the ledger basis. "
              f"PROVISIONAL: {crit} critical data exceptions; " + (f"{fin.unreconciled_pos[0]['po_id']} is not reconciled (invoice basis {tot['forecast_eac_eur'] + fin.forecast_uncertainty_eur:,.0f} EUR). " if fin.unreconciled_pos else "")
              + "The headroom is not confirmed free funding.", Font(bold=True, color=NAVY)),
             ("Forecast EAC = Actual + Open commitments + Approved, not committed. Variance = Forecast EAC - Budget (positive = overrun).", Font(italic=True, color=GREY_MUTED)),
             ("Open commitment = max(approved - recognised, 0) for open purchase orders; invoiced amounts are not counted twice. Commitment-based scenario forecast, not a statistical prediction.", Font(italic=True, color=GREY_MUTED))]
    for n, (text, font) in enumerate(notes):
        _note(ws, note_row + n, text, font)
    chart_row = note_row + len(notes) + 1
    chart = BarChart()
    chart.type, chart.title = "col", "Budget, actual and forecast at completion by cost centre (EUR)"
    for col in (3, 5, 10):
        chart.add_data(Reference(ws, min_col=col, min_row=top, max_row=last), titles_from_data=True)
    chart.set_categories(Reference(ws, min_col=1, min_row=first, max_row=last))
    style_bar_chart(chart, value_format='€#,##0,"k"', colours=[BLUE_LIGHT, BLUE_MID, BLUE_DARK], labels=2, label_format='€#,##0,"k"',
                    plot=(0.08, 0.13, 0.90, 0.62), legend_box=(0.20, 0.89, 0.60, 0.08), value_min=0, gap_width=70)
    for n, (cc, f) in enumerate(fin.by_cc.items()):
        if f.forecast_variance_eur > 0:
            highlight_point(chart.series[2], n, RED)              # forecast bar of an over-budget cost centre
    chart.height, chart.width = 11.5, 26
    ws.add_chart(chart, f"A{chart_row}")
    ws.cell(row=chart_row + _rows_for(11.5), column=1,
            value="Red forecast bar = forecast above the period budget. Values in thousand EUR. Cost-centre names: column B of the table above.").font = Font(italic=True, size=9, color=GREY_MUTED)

    # Capacity ---------------------------------------------------------------------------------------
    rows = []
    for (team, m), cell in sorted(cap.cells.items()):
        rows.append([c.TEAMS[team][0], m, cell["available"], cell["run_hours"], cell["allocated"] - cell["run_hours"], cell["allocated"], cell["remaining"],
                     round(100 * cell["allocated"] / cell["available"], 1), ", ".join(cell["demand_ids"])])
    ws = _sheet(wb, "Capacity", ["Team", "Month", "Available h", "Run h", "Demand h", "Allocated h", "calc: Remaining h", "calc: Utilisation %", "Approved demands"],
                rows, BLUE, wrap_cols=("Approved demands",), widths={"Team": 24, "Month": 10, "Approved demands": 60, "calc: Utilisation %": 13},
                heading="Team capacity in engineer-hours (synthetic planning data)", status=status,
                hour_cols=("Available h", "Run h", "Demand h", "Allocated h", "calc: Remaining h"))
    top = TITLED_HEADER_ROW
    ws.conditional_formatting.add(f"G{top + 1}:G{top + len(rows)}", CellIsRule(operator="lessThan", formula=["0"], fill=BAD, font=Font(bold=True, color=RED)))
    ws.conditional_formatting.add(f"H{top + 1}:H{top + len(rows)}", CellIsRule(operator="greaterThan", formula=["100"], fill=BAD, font=Font(bold=True, color=RED)))
    for row in ws.iter_rows(min_row=top + 1, max_row=top + len(rows), min_col=8, max_col=8):
        row[0].number_format = '0.0"%"'
    fwd = [m for m in cap.months() if m >= ds.as_of.strftime("%Y-%m")]
    base = top + len(rows) + 3
    ws.cell(row=base, column=1, value="Unallocated engineer-hours, cutoff month onwards (chart data)").font = Font(bold=True, color=NAVY)
    ws.cell(row=base + 1, column=1, value="Team").font = Font(bold=True)
    for j, m in enumerate(fwd):
        ws.cell(row=base + 1, column=2 + j, value=m).font = Font(bold=True)
        ws.cell(row=base + 1, column=2 + j).alignment = Alignment(horizontal="right")
    shortfalls = []
    for i, team in enumerate(c.TEAMS):
        ws.cell(row=base + 2 + i, column=1, value=c.TEAMS[team][0])
        for j, m in enumerate(fwd):
            v = cap.cells[(team, m)]["remaining"]
            cell = ws.cell(row=base + 2 + i, column=2 + j, value=v)
            cell.number_format = HOURS
            if v < 0:
                shortfalls.append((i, j, team, m, v))
    ws.conditional_formatting.add(f"B{base + 2}:{get_column_letter(1 + len(fwd))}{base + 1 + len(c.TEAMS)}",
                                  CellIsRule(operator="lessThan", formula=["0"], fill=BAD, font=Font(bold=True, color=RED)))
    callout = base + 2 + len(c.TEAMS) + 1
    month_name = lambda m: date(int(m[:4]), int(m[5:]), 1).strftime("%B %Y")
    texts = [f"{c.TEAMS[team][0]}: {month_name(m)} over-allocation of {-v} engineer-hours." for _, _, team, m, v in shortfalls] or ["No team is over-allocated."]
    for n, t in enumerate(texts):
        _note(ws, callout + n, t, Font(bold=True, color=RED if shortfalls else TEAL, size=12), last_col="I", chars_per_line=150)
    _note(ws, callout + len(texts), "Unallocated = available - allocated (run work + approved demands), as of the cutoff, before any pending request is approved. "
          "Capacity gate: effort <= sum of unallocated hours from the cutoff month to the due month; an over-allocated month counts as zero.",
          Font(italic=True, color=GREY_MUTED), last_col="I", chars_per_line=170)
    chart_row = callout + len(texts) + 2
    chart = BarChart()
    chart.type, chart.title = "col", "Unallocated engineer-hours by team and month (below zero = over-allocated)"
    chart.add_data(Reference(ws, min_col=1, max_col=1 + len(fwd), min_row=base + 2, max_row=base + 1 + len(c.TEAMS)), from_rows=True, titles_from_data=True)
    chart.set_categories(Reference(ws, min_col=2, max_col=1 + len(fwd), min_row=base + 1))
    lowest = min(cap.cells[(t, m)]["remaining"] for t in c.TEAMS for m in fwd)
    style_bar_chart(chart, value_format="#,##0", colours=[BLUE_DARK, BLUE_MID, BLUE_LIGHT], labels="all", label_format='#,##0;-#,##0',
                    plot=(0.08, 0.13, 0.90, 0.62), legend_box=(0.15, 0.89, 0.70, 0.08), gap_width=90,
                    value_min=50 * ((lowest - 30) // 50) if lowest < 0 else 0)      # room below zero for the negative bar and its label
    for i, j, *_ in shortfalls:
        highlight_point(chart.series[i], j, RED)
    chart.height, chart.width = 11.5, 24
    ws.add_chart(chart, f"A{chart_row}")
    ws.cell(row=chart_row + _rows_for(11.5), column=1,
            value="Red bar = negative balance (more hours allocated than available). Values are engineer-hours.").font = Font(italic=True, size=9, color=GREY_MUTED)

    # Exceptions, Actions, Hero ------------------------------------------------------------------------
    rows = [[e.severity, e.code, e.record_id, e.source, e.cost_center, e.amount_eur, e.amount_original, e.currency if e.amount_original is not None else "",
             e.message, e.risk, e.proposed_action, e.decision_owner, e.due_date]
            for e in ctx["register"]]
    ws = _sheet(wb, "Exceptions", ["Severity", "Code", "Record", "Source", "Cost centre", "Amount EUR", "Amount in other currency", "Other currency", "Finding", "Risk", "Proposed action", "Decision owner", "Due date"],
                rows, BLUE, money_cols=("Amount EUR",), wrap_cols=("Finding", "Risk", "Proposed action"),
                widths={"Severity": 11, "Code": 28, "Record": 15, "Finding": 60, "Risk": 45, "Proposed action": 55, "Decision owner": 26, "Due date": 12})
    for row in ws.iter_rows(min_row=2):
        if row[0].value == "CRITICAL":
            row[0].fill, row[0].font = BAD, Font(bold=True, color=RED)
        elif row[0].value == "WARNING":
            row[0].fill = WARN
        if row[6].value is not None and row[7].value:
            row[6].number_format = f'#,##0 "{row[7].value}";-#,##0 "{row[7].value}"'      # own currency, never EUR
    rows = [["Decision required", x["topic"], x["decision"], x["owner"], x["due"]] for x in decisions_required(ctx)]
    rows += [[a["kind"], a["ref"], a["action"], a["owner"], a["due"]] for a in action_register(ctx)]
    _sheet(wb, "Actions", ["Type", "Reference", "Action / decision needed", "Owner", "Due"], rows, BLUE, wrap_cols=("Reference", "Action / decision needed"),
           widths={"Reference": 46, "Action / decision needed": 90})
    h = hero_facts(ctx)
    rows = [["One-time cost EUR"] + [o["one_time_eur"] for o in h["options"]], ["Monthly cost EUR"] + [o["monthly_eur"] for o in h["options"]],
            ["Cost in budget period EUR"] + [o["period_cost_eur"] for o in h["options"]], ["12-month total EUR"] + [o["total_12_month_eur"] for o in h["options"]],
            ["Effort h"] + [o["hours"] for o in h["options"]], ["Unallocated team hours in window"] + [o["hours_available"] for o in h["options"]],
            [f"{h['cost_center']} forecast if approved EUR"] + [o["scenario_eac_eur"] for o in h["options"]],
            [f"{h['cost_center']} budget EUR", h["cc_budget_eur"], h["cc_budget_eur"]],
            ["Funding gate"] + ["pass" if o["funding_pass"] else "FAIL" for o in h["options"]], ["Capacity gate"] + ["pass" if o["capacity_pass"] else "FAIL" for o in h["options"]],
            ["Decision", f"{h['decision']['decision'].upper()} on {h['decision']['decided_at']} by {h['decision']['approver_role']}", f"Next review {h['next_review_at']}"]]
    ws = _sheet(wb, "Hero Scenario", [f"{HERO} {h['title']}"] + [f"Option {o['option_id']}: {o['name']}" for o in h["options"]], rows, BLUE,
                widths={f"{HERO} {h['title']}": 52, f"Option A: {h['options'][0]['name']}": 58, f"Option B: {h['options'][1]['name']}": 44})
    for row in ws.iter_rows(min_row=2):
        if str(row[0].value).endswith("EUR"):
            row[1].number_format = row[2].number_format = EUR

    # Assumptions, Data Dictionary --------------------------------------------------------------------------
    rows = [["Reporting cutoff", ds.as_of.isoformat() + " inclusive"], ["Budget period", f"{months[0]} to {months[-1]}"], ["Currency", "All totals are EUR. A non-EUR invoice is converted only with a conversion rate approved by Finance (none is approved); otherwise it is excluded, flagged and shown in its own currency, never added to a EUR figure"],
            ["Unreconciled purchase orders", "Open commitment uses the purchase-order ledger; a difference to the linked invoices is a critical exception and is shown as forecast uncertainty"],
            ["Recurring cost in period", "Monthly cost x number of period months after the planned go-live month"],
            ["12-month option total", "Setup + 12 x monthly cost, undiscounted"],
            ["Priority score", "100 x (0.35 impact + 0.25 urgency + 0.25 risk reduction + 0.15 strategic alignment) / 5"],
            ["Priority bands", "; ".join(f">= {f}: {n}" for f, n in c.PRIORITY_BANDS)],
            ["Funding gate", "Cost-centre forecast EAC + period cost of the demand <= period budget"],
            ["Capacity gate", "Effort <= unallocated hours of the team from the cutoff month to the due month"],
            ["Approval", "Always a recorded decision by an authorised human role; the score never approves"],
            ["Stale", f"Open, not deferred, no status event for {c.STALE_DAYS} days"],
            ["Lifecycle statuses", ", ".join(c.STATUS_LABEL[s] for s in c.STATUS_ORDER)],
            ["Capacity data", "Synthetic planning hours; skills and task order are not modelled"],
            ["Verification", "Totals in this workbook are compared with independently built ground truth by the automated tests"]]
    _sheet(wb, "Assumptions", ["Topic", "Assumption / definition"], rows, NAVY, wrap_cols=("Assumption / definition",), widths={"Assumption / definition": 110, "Topic": 28})
    _sheet(wb, "Data Dictionary", ["File", "Field", "Meaning"], [list(x) for x in DATA_DICTIONARY], NAVY, wrap_cols=("Meaning",), widths={"Meaning": 90, "Field": 50})

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.properties.creator = "InfraFlow Mission Control"
    wb.save(path)
    make_reproducible(path, ds.as_of)
    return dict(kpi={r[1]: r[2] for r in kpi_rows}, forecast_totals=tot)
