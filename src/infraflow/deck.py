"""Executive slide deck (python-pptx, native editable charts). Five slides, one data set.

Design system: ``office_style`` (navy structure, blue series ordered dark -> light, teal = passed /
headroom, amber = provisional, red = overrun / shortfall / failed gate). No dual axes, no animations.
Every figure comes from ``build_context``; nothing is typed in by hand.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION, XL_TICK_LABEL_POSITION
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

from . import config as c
from . import office_style as st
from .models import Dataset
from .reports import HERO, action_register, build_context, decisions_required, eur, hero_facts

rgb = RGBColor.from_string
NAVY, INK, MUTED, RULE = rgb(st.NAVY), rgb(st.GREY_TEXT), rgb(st.GREY_MUTED), rgb(st.GREY_RULE)
SERIES = [rgb(x) for x in st.SERIES]
TEAL, AMBER, RED = rgb(st.TEAL), rgb(st.AMBER), rgb(st.RED)
AMBER_FILL, RED_FILL, TEAL_FILL = rgb(st.AMBER_FILL), rgb(st.RED_FILL), rgb("E3F2EF")
AMBER_TEXT = rgb("7A4A00")
TILE_FILL, WHITE, ROW_ALT = rgb(st.GREY_FILL), rgb("FFFFFF"), rgb("F7F8FA")
SLIDE_W, SLIDE_H = 13.333, 7.5


def _text(slide, x, y, w, h, text, size=14, bold=False, color=INK, align=PP_ALIGN.LEFT, space_after=6, anchor=MSO_ANCHOR.TOP):
    """Text box. `text` is a string, a list of strings, or a list of (string, {bold, color, size}) pairs."""
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    lines = text if isinstance(text, list) else [text]
    for i, line in enumerate(lines):
        line, fmt = (line if isinstance(line, tuple) else (line, {}))
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        run = p.add_run()
        run.text = line
        run.font.size = Pt(fmt.get("size", size))
        run.font.bold = fmt.get("bold", bold)
        run.font.color.rgb = fmt.get("color", color)
        run.font.name = st.FONT
        p.space_after = Pt(space_after)
    return box


def _rect(slide, x, y, w, h, fill, line=None):
    shape = slide.shapes.add_shape(1, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = Pt(1.25)
    shape.shadow.inherit = False
    return shape


def _frame(prs, title: str, subtitle: str, ctx: dict, n: int):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _rect(slide, 0, 0, SLIDE_W, 0.12, NAVY)
    _text(slide, 0.5, 0.28, 10.1, 0.6, title, 26, True, NAVY)
    _text(slide, 0.5, 0.9, 10.1, 0.4, subtitle, 13, False, MUTED)
    if ctx["provisional"]:
        crit = sum(1 for x in ctx["register"] if x.severity == "CRITICAL")
        tag = _rect(slide, 10.75, 0.34, 2.08, 0.62, AMBER_FILL, AMBER)
        tf = tag.text_frame
        tf.margin_top = tf.margin_bottom = Inches(0.02)
        tf.text = "PROVISIONAL"
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        r = tf.paragraphs[0].runs[0]
        r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(13), True, AMBER_TEXT, st.FONT
        p = tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = f"{crit} critical data exceptions"
        r.font.size, r.font.color.rgb, r.font.name = Pt(9), AMBER_TEXT, st.FONT
    _text(slide, 0.5, 7.05, 11.6, 0.3, f"{c.ORG_NAME}: fictional organisation, synthetic data  |  Cutoff {ctx['ds'].as_of.isoformat()}  |  "
          "Source: InfraFlow reporting data set, not a live system extract", 9, False, MUTED)
    _text(slide, 12.3, 7.05, 0.55, 0.3, str(n), 9, False, MUTED, PP_ALIGN.RIGHT)
    return slide


def _tile(slide, x, y, w, h, label: str, value: str, note: str = "", accent=None):
    _rect(slide, x, y, w, h, TILE_FILL)
    if accent is not None:
        _rect(slide, x, y, 0.07, h, accent)
    _text(slide, x + 0.15, y + 0.06, w - 0.25, 0.3, label, 12, False, MUTED, space_after=0)
    _text(slide, x + 0.15, y + 0.36, w - 0.25, 0.62, value, 28, True, NAVY, space_after=0)
    if note:
        _text(slide, x + 0.15, y + 1.0, w - 0.25, h - 1.04, note, 11, False, MUTED, space_after=0)


def _table(slide, x, y, w, headers: list[str], rows: list[list], widths: list[float], size: int = 12, row_h: float = 0.4,
           fills: dict | None = None, fonts: dict | None = None, bold_rows=()):
    """Table with explicit row heights. fills/fonts: {(row, col): RGBColor} for data cells (row 1 = first data row)."""
    shape = slide.shapes.add_table(len(rows) + 1, len(headers), Inches(x), Inches(y), Inches(w), Inches(row_h * (len(rows) + 1)))
    tbl = shape.table
    tbl.first_row = True
    for j, wid in enumerate(widths):
        tbl.columns[j].width = Inches(wid)
    for i in range(len(rows) + 1):
        tbl.rows[i].height = Inches(row_h)
    for j, head in enumerate(headers):
        cell = tbl.cell(0, j)
        cell.text = head
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        run = cell.text_frame.paragraphs[0].runs[0]
        run.font.size, run.font.bold, run.font.color.rgb, run.font.name = Pt(size), True, WHITE, st.FONT
    for i, row in enumerate(rows, 1):
        for j, val in enumerate(row):
            cell = tbl.cell(i, j)
            cell.text = str(val)
            cell.fill.solid()
            cell.fill.fore_color.rgb = (fills or {}).get((i, j), WHITE if i % 2 else ROW_ALT)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_top = cell.margin_bottom = Inches(0.03)
            for p in cell.text_frame.paragraphs:
                for run in p.runs:
                    run.font.size, run.font.name = Pt(size), st.FONT
                    run.font.color.rgb = (fonts or {}).get((i, j), INK)
                    run.font.bold = i in bold_rows or (i, j) in (fonts or {})
                if j > 0 and str(val)[:1] in "€-0123456789" and not str(val).endswith("%") and "\n" not in str(val):
                    p.alignment = PP_ALIGN.RIGHT
    return tbl


def _no_rounded_corners(chart) -> None:
    """PowerPoint, like Excel, reads a missing <c:roundedCorners> as true."""
    space = chart._chartSpace
    if space.find(qn("c:roundedCorners")) is None:
        el = etree.Element(qn("c:roundedCorners"))
        el.set("val", "0")
        anchor = space.find(qn("c:lang"))
        if anchor is None:
            anchor = space.find(qn("c:date1904"))
        if anchor is not None:
            anchor.addnext(el)
        else:
            space.insert(0, el)


def _chart(slide, x, y, w, h, kind, categories: list[str], series: list[tuple[str, list]], title: str, number_format: str = "#,##0",
           colours=None, labels: bool | int = False, label_format: str | None = None, value_min=None):
    data = CategoryChartData()
    data.categories = categories
    for name, values in series:
        data.add_series(name, values)
    chart = slide.shapes.add_chart(kind, Inches(x), Inches(y), Inches(w), Inches(h), data).chart
    _no_rounded_corners(chart)
    chart.font.name, chart.font.size = st.FONT, Pt(10)
    chart.has_title = True
    chart.chart_title.text_frame.text = title
    run = chart.chart_title.text_frame.paragraphs[0].runs[0]
    run.font.size, run.font.bold, run.font.color.rgb = Pt(13), True, NAVY
    chart.has_legend = len(series) > 1
    if chart.has_legend:
        chart.legend.position, chart.legend.include_in_layout = XL_LEGEND_POSITION.BOTTOM, False
        chart.legend.font.size = Pt(11)
    plot = chart.plots[0]
    plot.vary_by_categories = False
    plot.gap_width = 70
    plot.overlap = -10 if len(series) > 1 else 0
    for i, s in enumerate(plot.series):
        s.format.fill.solid()
        s.format.fill.fore_color.rgb = (colours or SERIES)[i % len(colours or SERIES)]
        s.invert_if_negative = False
        if labels is True or labels == i:
            s.data_labels.show_value = True
            s.data_labels.font.size = Pt(10)
            s.data_labels.font.color.rgb = INK
            s.data_labels.number_format, s.data_labels.number_format_is_linked = label_format or number_format, False
            s.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
    va, ca = chart.value_axis, chart.category_axis
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = RULE
    va.format.line.fill.background()
    va.tick_labels.font.size, va.tick_labels.font.color.rgb = Pt(10), MUTED
    ca.tick_labels.font.size = Pt(11)
    va.tick_labels.number_format, va.tick_labels.number_format_is_linked = number_format, False
    ca.format.line.color.rgb = rgb("808080")
    ca.tick_label_position = XL_TICK_LABEL_POSITION.LOW      # labels below the plot even when bars are negative
    va.has_title = ca.has_title = False
    if value_min is not None:
        va.minimum_scale = value_min
    return chart


def _point(chart, series_idx: int, point_idx: int, colour) -> None:
    """Give one bar its own fill. The data point also needs <c:invertIfNegative val="0"/>: without it
    PowerPoint inverts a negative bar to white (seen on slide 4 in the owner's screenshot)."""
    pt = chart.plots[0].series[series_idx].points[point_idx]
    pt.format.fill.solid()
    pt.format.fill.fore_color.rgb = colour
    dpt = pt._ser.get_or_add_dPt_for_point(point_idx)          # the <c:dPt> element of this bar
    if dpt.find(qn("c:invertIfNegative")) is None:
        el = etree.Element(qn("c:invertIfNegative"))
        el.set("val", "0")
        dpt.find(qn("c:idx")).addnext(el)


def short_decision(x: dict) -> str:
    """One-line decision text for the slide; the full text stays in the reports and the workbook."""
    text = x["decision"]
    if text.startswith("Cannot be approved as submitted ("):
        gates = text[text.index("(") + 1:text.index(")")]
        return f"Fails the {gates.replace(', ', ' and ')} gate{'s' if ',' in gates else ''}: defer with a review date, reduce scope, or reallocate."
    if text.startswith("Approve or defer; all gates pass"):
        return "All gates pass: approve or defer."
    return text


def _month_name(m: str) -> str:
    return date(int(m[:4]), int(m[5:]), 1).strftime("%B %Y")


def build_deck(ds: Dataset, path: Path) -> dict:
    ctx = build_context(ds)
    fin, cap, k = ctx["fin"], ctx["cap"], ctx["kpis"]
    tot, h, req = fin.totals(), hero_facts(ctx), decisions_required(ctx)
    crit = [x for x in ctx["register"] if x.severity == "CRITICAL"]
    over = [(cc, f) for cc, f in fin.by_cc.items() if f.forecast_variance_eur > 0]
    shortfalls = [(t, m, cell["remaining"]) for (t, m), cell in sorted(cap.cells.items()) if cell["remaining"] < 0 and m >= ds.as_of.strftime("%Y-%m")]
    top = ctx["queue"][0]
    headroom, headroom_inv = -tot["forecast_variance_eur"], -(tot["forecast_variance_eur"] + fin.forecast_uncertainty_eur)
    pending = k["approval_pending"]["value"]
    buckets = fin.excluded_by_currency()
    eur_b = buckets.get(c.CURRENCY)
    foreign = [(cur, b) for cur, b in buckets.items() if cur != c.CURRENCY]
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(SLIDE_W), Inches(SLIDE_H)

    # 1 - overview --------------------------------------------------------------
    s = _frame(prs, "Infrastructure demand portfolio: overview", "Executive summary for the Infrastructure Demand Board", ctx, 1)
    tw, gap = 2.925, 0.21
    xs = [0.5 + i * (tw + gap) for i in range(4)]
    _tile(s, xs[0], 1.45, tw, 1.55, "Open demands", str(k["open_demands"]["value"]),
          f"of {k['total_demands']['value']} registered; {k['intake_last_7_days']['value']} new this week")
    _tile(s, xs[1], 1.45, tw, 1.55, "Awaiting a board decision", str(pending), f"{k['high_priority_not_approvable']['value']} High/Highest demands fail a gate")
    _tile(s, xs[2], 1.45, tw, 1.55, "Forecast at completion", eur(tot["forecast_eac_eur"]),
          f"budget {eur(tot['budget_period_eur'])}; {eur(headroom)} below (provisional)")
    _tile(s, xs[3], 1.45, tw, 1.55, "Critical data exceptions", str(len(crit)), "figures stay provisional until they are closed", accent=AMBER)
    n_constraints = len(over) + len(shortfalls)
    _text(s, 0.5, 3.2, 12.33, 0.75,
          f"Below budget overall, but {len(crit)} data exceptions, {n_constraints} budget and capacity constraints and {pending} pending decisions need management attention.",
          17, True, NAVY, space_after=0)
    _text(s, 0.5, 4.05, 7.45, 0.35, "Key findings", 13, True, NAVY, space_after=0)
    sf = shortfalls[0] if shortfalls else None
    _text(s, 0.5, 4.45, 7.45, 2.45, [
        f"•  Delivery: {k['overdue_open']['value']} demands are overdue, {k['blocked_open']['value']} blocked and {k['unassigned_open']['value']} have no owner.",
        "•  Budget: " + (f"{over[0][0]} is forecast {eur(over[0][1].forecast_variance_eur)} over its budget; the other cost centres have headroom." if over else "no cost centre is forecast over budget."),
        "•  Capacity: " + (f"{c.TEAMS[sf[0]][0]} is over-allocated by {-sf[2]} h in {_month_name(sf[1])}; " if sf else "")
        + f"the top-scored request ({top['demand'].external_id}) is affordable but cannot be staffed in time.",
        f"•  {HERO}: deferred on {h['decision']['decided_at']} although it scores {h['score']:.0f}; re-review on {h['next_review_at']}."], 13, space_after=8)
    _rect(s, 8.2, 4.05, 4.63, 2.8, AMBER_FILL)
    _rect(s, 8.2, 4.05, 0.07, 2.8, AMBER)
    caveats = [("Why the figures are provisional", {"bold": True, "color": AMBER_TEXT, "size": 13})]
    if eur_b:
        caveats.append(f"{len(eur_b['rows'])} invalid EUR invoices excluded ({eur(eur_b['gross'])} gross)")
    caveats += [f"{cur} {b['net']:,.0f} excluded, not converted (no approved rate)" for cur, b in foreign]
    if fin.unmapped_actual_eur:
        caveats.append(f"{eur(fin.unmapped_actual_eur)} spent on a cost centre without budget")
    caveats += [f"{p['po_id']}: ledger and invoices differ by {eur(abs(p['difference_eur']))}" for p in fin.unreconciled_pos]
    caveats.append(("Owners and due dates: slide 5", {"color": MUTED, "size": 11}))
    _text(s, 8.4, 4.15, 4.35, 2.6, caveats, 12, False, INK, space_after=5)

    # 2 - pipeline ----------------------------------------------------------------
    s = _frame(prs, "Demand pipeline and operational performance", f"Where the {k['total_demands']['value']} registered demands stand, and how the process performs", ctx, 2)
    statuses = [x for x in c.STATUS_ORDER if k["by_status"]["value"][x]]
    order = list(reversed(statuses))                       # horizontal bars: first category is drawn at the bottom
    counts = [k["by_status"]["value"][x] for x in order]
    chart = _chart(s, 0.5, 1.45, 7.3, 5.15, XL_CHART_TYPE.BAR_CLUSTERED, [c.STATUS_LABEL[x] for x in order], [("Demands", counts)],
                   "Demands by lifecycle status (number of demands)", "0", colours=[rgb(st.BLUE_MID)], labels=True, value_min=0)
    open_counts = {x: k["by_status"]["value"][x] for x in order if x not in c.TERMINAL}
    biggest = max(open_counts.values())
    for i, x in enumerate(order):
        if x in c.TERMINAL:
            _point(chart, 0, i, rgb(st.BLUE_LIGHT))
        elif open_counts[x] == biggest:
            _point(chart, 0, i, NAVY)
    _text(s, 0.5, 6.62, 7.3, 0.35, "Dark bar: largest open queue. Light bars: closed (complete, rejected, routed out).", 10, False, MUTED, space_after=0)
    perf = [["Awaiting decision", str(pending)],
            ["Overdue open demands", str(k["overdue_open"]["value"])], ["Blocked open demands", str(k["blocked_open"]["value"])],
            ["Open demands without owner", f"{k['unassigned_open']['value']} ({k['unassigned_pct']['value']}%)"],
            ["Intake completeness", f"{k['completeness_pct']['value']}%"], ["Median triage time", f"{k['median_triage_business_days']['value']} working days"],
            ["Median lead time", f"{k['median_lead_time_days']['value']} days"], ["Delivered on time", f"{k['on_time_delivery_pct']['value']}% of {k['completed_total']['value']}"]]
    warn = {(i, 1): AMBER_FILL for i, (_, v) in enumerate(perf, 1) if i in (2, 3, 4) and not v.startswith("0")}
    _table(s, 8.1, 1.55, 4.75, ["Measure", "Value"], perf, [2.75, 2.0], 12, 0.42, fills=warn, fonts={key: AMBER_TEXT for key in warn})
    _text(s, 8.1, 5.5, 4.75, 1.2, [("Needs attention (amber)", {"bold": True, "color": AMBER_TEXT}),
                                   "Overdue, blocked and unowned demands each have an owner and a due date in the action register."], 12, space_after=4)

    # 3 - finance -------------------------------------------------------------------
    s = _frame(prs, "Budget, actuals, commitments and forecast", f"Budget period {c.PERIOD_MONTHS[0]} to {c.PERIOD_MONTHS[-1]}, EUR, ledger basis", ctx, 3)
    ccs = list(fin.by_cc)
    chart = _chart(s, 0.5, 1.45, 6.85, 4.65, XL_CHART_TYPE.COLUMN_CLUSTERED, [x.replace("CC-", "") for x in ccs],
                   [("Budget", [fin.by_cc[x].budget_period_eur for x in ccs]), ("Actual", [fin.by_cc[x].actual_eur for x in ccs]),
                    ("Forecast at completion", [fin.by_cc[x].forecast_eac_eur for x in ccs])],
                   "Budget, actual and forecast by cost centre (EUR thousand)", '€#,##0,"k"', value_min=0)
    for i, x in enumerate(ccs):
        if fin.by_cc[x].forecast_variance_eur > 0:
            _point(chart, 2, i, RED)
    _text(s, 0.5, 6.12, 6.85, 0.3, "Red bar: forecast above budget. Cost-centre codes without the CC- prefix.", 10, False, MUTED, space_after=0)
    rows, fills, fonts = [], {}, {}
    for i, (x, f) in enumerate(fin.by_cc.items(), 1):
        rows.append([x.replace("CC-", ""), eur(f.budget_period_eur), eur(f.forecast_eac_eur), eur(f.forecast_variance_eur)])
        if f.forecast_variance_eur > 0:
            fills[(i, 3)], fonts[(i, 3)] = RED_FILL, RED
        else:
            fonts[(i, 3)] = TEAL
    rows.append(["Total", eur(tot["budget_period_eur"]), eur(tot["forecast_eac_eur"]), eur(tot["forecast_variance_eur"])])
    _table(s, 7.6, 1.5, 5.25, ["Cost centre", "Budget", "Forecast", "Variance*"], rows, [1.35, 1.3, 1.3, 1.3], 12, 0.4, fills, fonts, bold_rows=(len(rows),))
    _text(s, 7.6, 4.3, 5.25, 0.62, [f"Forecast = actual {eur(tot['actual_eur'])} + open commitments {eur(tot['open_commitments_eur'])} + approved, not committed {eur(tot['approved_not_committed_eur'])}.",
                                   "* Variance = forecast - budget; positive = over budget."], 10, False, MUTED, space_after=0)
    box = [("Provisional - not in these figures", {"bold": True, "color": AMBER_TEXT, "size": 12})]
    if eur_b:
        box.append(f"Invalid EUR invoices: {eur(eur_b['gross'])} gross ({', '.join(eur_b['invoice_ids'])})")
    box += [f"{cur} {b['net']:,.0f} not converted ({', '.join(b['invoice_ids'])}); never added to EUR" for cur, b in foreign]
    if fin.unmapped_actual_eur:
        box.append(f"Unmapped spend: {eur(fin.unmapped_actual_eur)} ({', '.join(fin.unmapped_invoice_ids)})")
    box += [f"{p['po_id']} not reconciled: invoice basis {eur(tot['forecast_eac_eur'] + fin.forecast_uncertainty_eur)}" for p in fin.unreconciled_pos]
    _rect(s, 7.6, 4.97, 5.25, 1.38, AMBER_FILL)
    _rect(s, 7.6, 4.97, 0.07, 1.38, AMBER)
    _text(s, 7.75, 5.0, 5.05, 1.33, box, 11, False, INK, space_after=1)
    _text(s, 0.5, 6.42, 12.33, 0.55,
          (f"{over[0][0]} is forecast {eur(over[0][1].forecast_variance_eur)} over budget. " if over else "")
          + f"Overall {eur(headroom)} below budget on the ledger basis ({eur(headroom_inv)} on invoice basis): provisional, not confirmed free funding.",
          13, True, NAVY, space_after=0)

    # 4 - capacity and hero -----------------------------------------------------------
    s = _frame(prs, "Capacity risks and the key trade-off", f"Unallocated engineer-hours, and why {HERO} was deferred", ctx, 4)
    fwd = [m for m in cap.months() if m >= ds.as_of.strftime("%Y-%m")]
    teams = list(c.TEAMS)
    chart = _chart(s, 0.5, 1.45, 6.2, 3.85, XL_CHART_TYPE.COLUMN_CLUSTERED, fwd,
                   [(c.TEAMS[t][0], [cap.cells[(t, m)]["remaining"] for m in fwd]) for t in teams],
                   "Unallocated engineer-hours by team and month", '#,##0', labels=True, label_format='#,##0;-#,##0',
                   value_min=50 * ((min(v for *_, v in shortfalls) - 30) // 50) if shortfalls else 0)
    for t, m, _ in shortfalls:
        _point(chart, teams.index(t), fwd.index(m), RED)
    hero_d = ds.demand(HERO)
    window_months = [m for m in fwd if m <= hero_d.due_at.strftime("%Y-%m")]
    window_txt = " + ".join(f"{cap.cells[(h['team'], m)]['remaining']} h ({_month_name(m).split()[0]})" for m in window_months)
    notes = [(f"{c.TEAMS[t][0]}: {_month_name(m)} over-allocation of {-v} engineer-hours (red bar).", {"bold": True, "color": RED}) for t, m, v in shortfalls]
    notes += ["Unallocated = available hours minus run work and approved demands, as of the reporting cutoff. Below zero = over-allocated. "
              "No pending request is assumed approved."]
    _text(s, 0.5, 5.4, 6.2, 1.55, notes, 11, space_after=5)
    a, b = h["options"]
    _text(s, 7.0, 1.4, 5.85, 0.55, [(f"{HERO}: {h['title']}", {"bold": True, "color": NAVY, "size": 13}),
                                    (f"Priority score {h['score']:.0f} ({h['band']}); two options assessed", {"color": MUTED, "size": 11})], space_after=0)
    gate = lambda ok, why: ("passes", False) if ok else (f"FAILS: {why}", True)
    fa, fb = gate(a["funding_pass"], f"{eur(a['scenario_eac_eur'] - h['cc_budget_eur'])} over"), gate(b["funding_pass"], "over budget")
    ca, cb = gate(a["capacity_pass"], f"{a['hours'] - a['hours_available']} h short"), gate(b["capacity_pass"], f"{b['hours'] - b['hours_available']} h short")
    rows = [["Scope", "full 40 TB", "about 16 TB freed (40%)"],
            ["Cost in budget period", eur(a["period_cost_eur"]), eur(b["period_cost_eur"])],
            [f"Funding gate ({eur(h['cc_headroom_eur'])} headroom)", fa[0], fb[0]],
            ["Effort", f"{a['hours']} h", f"{b['hours']} h"],
            [f"Capacity gate ({a['hours_available']} h free)", ca[0], cb[0]],
            ["Open condition", "-", "retention-class sign-off"]]
    fills, fonts = {}, {}
    for i, pair in ((3, (fa, fb)), (5, (ca, cb))):
        for j, r in ((1, pair[0]), (2, pair[1])):
            fills[(i, j)], fonts[(i, j)] = (RED_FILL, RED) if r[1] else (TEAL_FILL, TEAL)
    fills[(6, 2)], fonts[(6, 2)] = AMBER_FILL, AMBER_TEXT
    _table(s, 7.0, 2.02, 5.85, ["Criterion", "A: more managed storage", "B: archive and optimise"], rows, [2.35, 1.75, 1.75], 11, 0.41, fills, fonts)
    _text(s, 7.0, 5.1, 5.85, 1.88, [
        (f"Decision {h['decision']['decided_at']}: deferred by the {h['decision']['approver_role']}; re-review {h['next_review_at']} "
         f"(follow-up: {h['decision']['followup_owner']}).", {"bold": True, "color": NAVY}),
        f"A fails both gates. B passes them but is not approved: it covers about 40% of the need and the data owners' retention sign-off is open. "
        f"12-month cost: A {eur(a['total_12_month_eur'])}, B {eur(b['total_12_month_eur'])}.",
        f"{a['hours_available']} h = {c.TEAMS[h['team']][0]} unallocated in the delivery window: {window_txt}. Gate figures as of the {ds.as_of.isoformat()} cutoff."],
        11, space_after=5)

    # 5 - recommendations ----------------------------------------------------------------
    s = _frame(prs, "Decisions, responsibilities and next steps", "What the board decides, who acts next, and by when. Scores order the queue; accountable roles decide.", ctx, 5)
    _text(s, 0.5, 1.4, 12.33, 0.35, f"Board decisions (top 3 of {len(req)} open; full list in the decision and action register)", 13, True, NAVY, space_after=0)
    rows = []
    for i, x in enumerate(req[:3], 1):
        ext, _, title = x["topic"].partition(" ")
        rows.append([str(i), f"{ext}\n{title}", short_decision(x), x["owner"], x["due"]])
    _table(s, 0.5, 1.8, 12.33, ["#", "Demand", "Decision needed", "Owner", "Due"], rows, [0.4, 4.0, 4.45, 2.28, 1.2], 12, 0.62)
    acts = {a_["ref"]: a_ for a_ in action_register(ctx)}
    crit_owners: dict[str, int] = {}
    for e in crit:
        owner = acts[e.record_id]["owner"] if e.record_id in acts else e.decision_owner
        crit_owners[owner] = crit_owners.get(owner, 0) + 1
    crit_due = min(acts[e.record_id]["due"] for e in crit if e.record_id in acts)
    follow = [[f"Close the {len(crit)} critical data exceptions so the report is no longer provisional",
               ", ".join(f"{o} ({n})" for o, n in sorted(crit_owners.items(), key=lambda kv: -kv[1])), crit_due]]
    for cc, f in over:
        follow.append([f"Resolve the {cc} overrun of {eur(f.forecast_variance_eur)}: reallocate, defer or accept", acts[cc]["owner"], acts[cc]["due"]])
    for t, m, v in shortfalls:
        ref = f"{t}/{m}"
        follow.append([f"Re-plan {c.TEAMS[t][0]} for {_month_name(m)} ({-v} h over-allocated)", acts[ref]["owner"], acts[ref]["due"]])
    follow.append([f"Prepare the {HERO} re-review: retention-class sign-off for Option B", h["decision"]["followup_owner"], h["next_review_at"]])
    _text(s, 0.5, 4.5, 12.33, 0.35, "Follow-up actions", 13, True, NAVY, space_after=0)
    _table(s, 0.5, 4.87, 12.33, ["Action", "Owner", "Due"], follow, [6.2, 4.93, 1.2], 12, 0.36)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    prs.core_properties.title, prs.core_properties.author = "Infrastructure demand portfolio briefing (synthetic)", "InfraFlow Mission Control"
    prs.core_properties.last_modified_by = "InfraFlow Mission Control"
    prs.save(path)
    st.make_reproducible(path, ds.as_of)
    return dict(slides=len(prs.slides), forecast_eac_eur=tot["forecast_eac_eur"])
