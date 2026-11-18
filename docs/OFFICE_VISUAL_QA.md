# Office deliverables: visual QA record

Files (regenerate with `.venv/bin/python -m infraflow all`; two builds are byte-identical):

| File | Generator |
|---|---|
| `reports/infraflow_management_workbook.xlsx` | `src/infraflow/excel_export.py` + `office_style.py` |
| `reports/infraflow_excel_native_exercise.xlsx` | `src/infraflow/excel_native.py` |
| `presentations/infraflow_executive_briefing.pptx` | `src/infraflow/deck.py` + `office_style.py` |

Status words: **TESTED** = automated test passes; **VISUALLY VERIFIED** = someone looked at the rendered file in the Office application; **REQUIRES USER VERIFICATION** = not yet looked at in Office after the latest change.

## 1. Defects found

| # | Where | Defect | How it was found |
|---|---|---|---|
| D1 | Workbook, Forecast chart | Legend drawn over the cost-centre labels and the x-axis title; y-axis title over the tick labels; labels crowded | Project owner in desktop Excel (2026-11-17) |
| D2 | Workbook, Capacity chart | Legend over the month labels and x-axis title; y-axis title over tick labels; months crowded around the legend | Project owner in desktop Excel |
| D3 | Workbook, all charts | Rounded chart corners; the single-series status chart would get a different colour per bar | Found in the copy Excel saved (`<c:roundedCorners val="1"/>`, `<c:varyColors val="1"/>`) |
| D4 | Workbook, Forecast and Capacity sheets | Notes written at fixed rows could sit under the chart | Code review (row arithmetic) |
| D5 | Deck, all charts | `roundedCorners` missing (PowerPoint reads it as true) | XML inspection |
| D6 | Deck, slide 1 | Unused space below the findings; tile widths not equal | Owner's screenshot review (earlier session) |
| D7 | Deck, slide 5 | Long decision texts in table cells | Owner's review |
| D8 | Exercise workbook | Instructions referred to a column name that does not exist ("Actual (Excel formula)"; the header is "Actual (SUMIFS)") | Code review |
| D9 | All three files | Binary changed on every build (timestamps), so Git could not show whether content changed | Hash comparison of two builds |
| D10 | Deck, slide 4 | Highlighted negative bar (-30 h) rendered unfilled in PowerPoint | Owner's screenshot 16, reviewed 2026-11-18 |

### Root cause of D1-D3

openpyxl 3.1 does not write `<c:overlay>`, `<c:roundedCorners>` or `<c:varyColors>` unless they are set. Desktop Excel reads a missing element as **true**. Evidence: in the workbook the owner saved from Excel, every title and the legend carried `<c:overlay val="1"/>`. With overlay on, Excel does not reserve space for the legend or the axis titles, so they are drawn on top of the axis labels. Making the chart bigger does not change this.

## 2. Corrections (source code)

| # | Change | File |
|---|---|---|
| D1-D3 | `style_bar_chart`: `overlay=False` on chart title and legend; `roundedCorners=False`; `varyColors=False`; axis titles removed (units are in the chart title and in the number format); manual layout for the inner plot area (8%/13%/90%/62% of the chart) and a separate legend box below it (y 89%, h 8%); category labels at `low` (below the plot even for negative bars); visible baseline at zero; value axis from 0 for money; data labels outside bar ends | `office_style.py` |
| D1 | Forecast chart: categories `Forecast!A5:A9` (five cost-centre codes), series titles from the header row, values from columns C/E/J; colours light/mid/dark blue (budget/actual/forecast); forecast bar of CC-ENG-SIM red; value labels on the forecast series in EUR thousand; 26 x 11.5 cm; conditional formatting on the variance column (red > 0, teal <= 0); overrun and overall statement in text above the chart | `excel_export.py` |
| D2 | Capacity chart: categories = the four month labels, series = the three team names; NET December bar red; value labels on every bar; axis minimum -100 h so the -30 h bar and its label have room; conditional formatting on negative remaining hours and utilisation > 100%; callout "Network and Access: December 2026 over-allocation of 30 engineer-hours." | `excel_export.py` |
| D4 | Chart rows placed after the notes, and notes after the chart, computed from the chart height (`_rows_for`) | `excel_export.py` |
| - | KPI Summary: title and status line (PROVISIONAL, cutoff, fictional data), section column (demand pipeline, delivery, finance, data quality and capacity), unit column, number formats per unit, links to the detail sheet, conditional formatting for material exceptions (amber) and overrun (red), USD row in its own currency | `excel_export.py` |
| - | Other sheets: dates as dates (`yyyy-mm-dd`), hours with " h", Actuals and Exceptions amounts in their own currency, severity colours, column widths, numbers right-aligned, filters and frozen panes kept | `excel_export.py` |
| D5 | `roundedCorners=0`, `varyColors=0` on every deck chart | `deck.py` |
| D6 | Slide 1: four equal tiles, one headline message, key findings (left) and "Why the figures are provisional" panel (right) | `deck.py` |
| - | Slide 2: largest open queue dark, closed statuses light; overdue/blocked/unowned values amber | `deck.py` |
| - | Slide 3: CC-ENG-SIM forecast bar red; table Budget / Forecast / Variance with variance colours; forecast composition (actual + commitments + approved, not committed); amber caveat box (excluded EUR, USD not converted, unmapped, PO-015); headroom called "provisional, not confirmed free funding" | `deck.py` |
| - | Slide 4: capacity chart with red -30 h bar and callout; option table with red FAILS / teal passes / amber open condition; the 180 h explained as 60 h (November) + 120 h (December); decision date vs. reporting cutoff stated | `deck.py` |
| D7 | Slide 5: three decisions with one-line decision text; separate follow-up table (action, owner, due) | `deck.py` |
| D8 | First sheet rewritten: what it demonstrates, input vs. formulas, how to recalculate, where the 27 checks are, PivotTable as a manual exercise | `excel_native.py` |
| D9 | `make_reproducible`: zip entry dates and document dates set to the reporting cutoff (also inside the chart data embedded in the deck) | `office_style.py` |

No calculation, source record, Jira issue or Confluence page was changed. Data regenerated byte-identical; Confluence page sources regenerated without differences.

## 3. Tests (TESTED)

`tests/test_office_charts.py`, `tests/test_deck.py`, `tests/test_excel_native.py`, `tests/test_cross_artifact_consistency.py`:

- a plain openpyxl chart reproduces the defect (no overlay element, axis titles) - control case for the check;
- every workbook chart: overlay false on title and legend, no rounded corners, no varied colours, no axis titles, manual plot layout, legend box below the plot and inside the chart, categories and series titles resolve to non-empty cells, chart does not cover cells with content;
- Forecast chart: categories are the five cost-centre codes; series values equal the ground truth; only CC-ENG-SIM highlighted; axis from 0;
- Capacity chart: months and team names; NET December is -30 and the only highlighted bar; axis minimum below zero;
- KPI Summary: sections, source records, links, conditional formatting, provisional status line;
- deck: figures equal the ground truth; layout estimate finds no overflow or overlap on any slide; charts have no rounded corners or varied colours; overrun and shortfall highlighted;
- exercise workbook: 27 check formulas, the instructions name the right cells; evidence record from desktop Excel;
- the reference figures agree across facts JSON, workbook, deck, Confluence page source and e-mail; the old mixed-currency figure appears nowhere;
- two builds are byte-identical.

## 4. Visual inspections actually performed

| Inspection | Result |
|---|---|
| Rendering in the build environment | Not possible: no Office application or renderer under WSL2; installing one was not permitted. |
| Chart XML as Excel wrote it back (owner's saved copy, before the fix) | Inspected: confirmed the overlay root cause. |
| Slide geometry | Estimated by `office_qa.deck_layout_findings`, a conservative glyph-width model, not a rendering. |
| **Owner's screenshots in Microsoft Excel and PowerPoint, 2026-11-18** (`evidence/screenshots/14-20`) | Reviewed one by one against the checklist in section 6; results below. |
| Exercise workbook formulas in desktop Excel | Values Excel calculated: 27/27 check cells OK, B45 "ALL OK" (`evidence/excel_desktop_native_checks_2026-11-17.json`). |

Screenshot review (checklist numbers from section 6):

| Item | Result |
|---|---|
| Forecast chart (screenshot 14), items 1-6 | **Pass.** The five cost-centre labels are readable, the legend sits in its own row, there are no axis titles, the axis runs €0k-€400k, the CC-ENG-SIM bar is red and the overrun text is present. The forecast labels show full values ("228 800 €", Excel locale formatting) rather than "€229k"; acceptable. |
| Capacity chart (screenshot 15), items 7-10 | **Pass.** Months and legend are separate, the -30 h bar is red below a visible zero line, and the callout is present. |
| KPI Summary, items 11-12 | Not in a screenshot: **requires user verification**. |
| Exercise workbook, item 13 | Formulas verified by Excel-calculated values; first sheet not in a screenshot. |
| Slides 1, 2, 3, 5 (screenshots 19, 18, 17, 20), items 14, 15, 17 | **Pass.** No overflow or overlap; the caveat box is fully visible; tables end above the footer. Slide 1 leaves empty space in the lower part of the amber panel (cosmetic). |
| Slide 4, item 16 | First capture: **defect D10**, the -30 h December bar was drawn unfilled (white with a dark outline) although the slide text says "red bar". **After the fix (owner's recapture, screenshot 16, 2026-11-18): pass.** The bar is red below zero, labelled -30; option-table colours are correct. |

**D10, root cause and fix:** python-pptx writes the highlighted data point (`<c:dPt>`) without `<c:invertIfNegative>`. PowerPoint then inverts a negative bar's fill to white. Excel drew the same construct correctly because openpyxl writes the element. `deck._point` now adds `<c:invertIfNegative val="0"/>` to every highlighted point, and a test checks this. **Verified:** the owner opened the regenerated deck in desktop PowerPoint and recaptured slide 4 (screenshot 16 replaced on 2026-11-18); the bar renders red.

## 5. Status per deliverable

| Deliverable | TESTED | VISUALLY VERIFIED | REQUIRES USER VERIFICATION |
|---|---|---|---|
| Forecast chart labels, legend, overrun | yes | **yes** (screenshot 14) | no |
| Capacity chart labels, legend, -30 h bar | yes | **yes** (screenshot 15) | no |
| Status chart and KPI Summary | yes | no | yes |
| Exercise workbook formulas | yes | **yes** (Excel-calculated values) | first sheet text only |
| Deck slides 1-5 | yes, including the D10 fix | **yes** (screenshots 19, 18, 17, 16 recaptured after the fix, 20) | no |

The chart-label overlap defects D1 and D2 are resolved: the owner's Excel screenshots show the fixed charts.

## 6. Manual check in Microsoft Office (about 10 minutes)

Open the files from `reports/` and `presentations/` after pulling the latest commit. If Excel shows "Protected View", click *Enable Editing* so charts are fully drawn.

**Workbook - sheet Forecast** (screenshot requested: chart area)
1. Chart title on one line at the top, no other text over it.
2. Five labels under the bars: CC-ENG-DATA, CC-ENG-SIM, CC-DIG-INFRA, CC-SEC-OPS, CC-COLLAB - fully readable, not overlapped.
3. Legend (Budget (period), Actual, Forecast EAC) in its own row below the cost-centre labels, not touching them.
4. Left axis shows €0k ... €400k (or similar) with no axis title over the numbers.
5. The CC-ENG-SIM forecast bar is red and labelled €229k; it is higher than its budget bar (€225k).
6. Text above the chart: "Overrun: CC-ENG-SIM forecast 228,800 EUR against a budget of 225,000 EUR, 3,800 EUR over".

**Workbook - sheet Capacity** (screenshot requested: chart area)
7. Four month labels 2026-11, 2026-12, 2027-01, 2027-02 below the plot, readable.
8. Legend with the three team names below the month labels, not overlapping them.
9. A red bar below the zero line in 2026-12 (Network and Access) labelled -30; zero line visible.
10. Callout above the chart: "Network and Access: December 2026 over-allocation of 30 engineer-hours."

**Workbook - sheet KPI Summary**
11. Title, amber PROVISIONAL line, sections visible; amber cells for overdue, blocked, unowned, unreconciled, unmapped, excluded, USD, critical exceptions, over-allocation; links in the last column open the sheets.
12. Status chart: one colour, 12 status labels readable, values at the bar ends.

**Exercise workbook**
13. Sheet Analysis: all check cells green "OK", B45 "ALL OK". First sheet readable without horizontal scrolling at 100% zoom.

**Deck** (screenshots requested: slides 1, 3, 4, 5)
14. No text runs outside a box or over another element; nothing hidden behind the PROVISIONAL tag.
15. Slide 3: CC-ENG-SIM forecast bar red; caveat box text fully visible.
16. Slide 4: -30 bar red below zero with its label; option table colours (red FAILS, teal passes, amber open condition).
17. Slide 5: both tables end above the footer line.

Record the result and change the "REQUIRES USER VERIFICATION" cells in section 5.
