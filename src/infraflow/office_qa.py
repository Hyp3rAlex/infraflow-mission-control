"""Programmatic QA of the generated Office files.

This is NOT a renderer. It inspects the files the way the Office applications will read them:

Workbook charts (XML level)
* every title and the legend carry ``<c:overlay val="0"/>`` (a missing element means overlay in Excel)
* ``roundedCorners`` and ``varyColors`` are explicitly false
* plot area and legend have a manual layout and the legend sits below the plot area (no overlap)
* no axis titles (they collided with tick labels in Excel)
* category and series references resolve to non-empty worksheet cells with the expected labels
* chart anchors do not cover worksheet cells that hold text

Slide deck (geometry estimate)
* every shape lies inside the 13.333 x 7.5 in slide
* text boxes: estimated wrapped text height <= box height (Calibri, average glyph width 0.5 em,
  line height 1.2 em: deliberately conservative)
* tables: estimated rendered height (rows grow with wrapped text) does not run into the next shape
  or past the footer
* text-bearing shapes do not overlap (backgrounds without text are ignored)

The estimates cannot replace looking at the slides in PowerPoint; they catch the usual overflow and
overlap mistakes before a human review.
"""
from __future__ import annotations

import math
import re
import zipfile
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string, range_boundaries

EMU = 914400
SLIDE_W, SLIDE_H, FOOTER_TOP = 13.333, 7.5, 7.03
EM_WIDTH, LINE = 0.5, 1.2


# ---- workbook ---------------------------------------------------------------------------------------
def _cells(wb, ref: str) -> list:
    sheet, rng = ref.rsplit("!", 1)
    ws = wb[sheet.strip("'")]
    c1, r1, c2, r2 = range_boundaries(rng.replace("$", ""))
    return [ws.cell(row=r, column=col).value for r in range(r1, r2 + 1) for col in range(c1, c2 + 1)]


def workbook_chart_findings(path: Path) -> dict:
    """Return {chart file: {"checks": {...}, "problems": [...]}} for every chart in the workbook."""
    path = Path(path)
    wb = load_workbook(path)
    out = {}
    with zipfile.ZipFile(path) as z:
        names = sorted(n for n in z.namelist() if re.match(r"xl/charts/chart\d+\.xml", n))
        drawing_of = {}
        for d in (n for n in z.namelist() if re.match(r"xl/drawings/_rels/drawing\d+\.xml\.rels", n)):
            for target in re.findall(r'Target="([^"]+chart\d+\.xml)"', z.read(d).decode()):
                drawing_of["xl/charts/" + target.rsplit("/", 1)[-1]] = d.replace("_rels/", "").replace(".rels", "")
        sheet_of_drawing = {}
        for srel in (n for n in z.namelist() if re.match(r"xl/worksheets/_rels/sheet\d+\.xml\.rels", n)):
            for target in re.findall(r'Target="([^"]*drawings/drawing\d+\.xml)"', z.read(srel).decode()):
                sheet_of_drawing["xl/drawings/" + target.rsplit("/", 1)[-1]] = int(re.search(r"sheet(\d+)", srel).group(1))
        for name in names:
            s = z.read(name).decode()
            problems, checks = [], {}
            overlays = re.findall(r'<(?:c:)?overlay val="(\w+)"', s)
            n_titles_legends = len(re.findall(r"<(?:c:)?title>", s)) + len(re.findall(r"<(?:c:)?legend>", s))
            checks["overlay_false_everywhere"] = len(overlays) == n_titles_legends and all(v in ("0", "false") for v in overlays)
            checks["rounded_corners_off"] = re.search(r'<(?:c:)?roundedCorners val="(0|false)"', s) is not None
            checks["vary_colors_off"] = re.search(r'<(?:c:)?varyColors val="(0|false)"', s) is not None
            checks["axis_titles"] = len(re.findall(r"<(?:c:)?(?:catAx|valAx)>.*?<(?:c:)?title>", s, flags=re.S))
            layouts = re.findall(r"<(?:c:)?manualLayout>(.*?)</(?:c:)?manualLayout>", s, flags=re.S)
            boxes = [{k: float(v) for k, v in re.findall(r'<(?:c:)?([xywh]) val="([\d.]+)"', lay)} for lay in layouts]
            checks["manual_plot_layout"] = bool(boxes) and "inner" in layouts[0]
            has_legend = "<legend>" in s or "<c:legend>" in s
            if has_legend:
                checks["legend_below_plot"] = len(boxes) >= 2 and boxes[1]["y"] >= boxes[0]["y"] + boxes[0]["h"] + 0.07
                checks["legend_inside_chart"] = len(boxes) >= 2 and boxes[1]["y"] + boxes[1]["h"] <= 1.0
            cats = sorted(set(re.findall(r"<(?:c:)?cat>.*?<(?:c:)?f>(.*?)</(?:c:)?f>", s, flags=re.S)))
            titles = re.findall(r"<(?:c:)?tx><(?:c:)?strRef><(?:c:)?f>(.*?)</(?:c:)?f>", s)
            checks["categories"] = [v for ref in cats for v in _cells(wb, ref.replace("&apos;", "'"))]
            checks["series_titles"] = [v for ref in titles for v in _cells(wb, ref.replace("&apos;", "'"))]
            checks["value_min"] = re.findall(r'<(?:c:)?min val="([^"]+)"', s)
            checks["highlighted_points"] = len(re.findall(r"<(?:c:)?dPt>", s))
            if not checks["overlay_false_everywhere"]:
                problems.append("a title or the legend may be drawn over the plot (overlay not false)")
            for key in ("rounded_corners_off", "vary_colors_off", "manual_plot_layout"):
                if not checks[key]:
                    problems.append(f"{key} not set")
            if checks["axis_titles"]:
                problems.append("axis titles present")
            if has_legend and not (checks["legend_below_plot"] and checks["legend_inside_chart"]):
                problems.append("legend box overlaps the plot area or leaves the chart")
            if not checks["categories"] or any(v in (None, "") for v in checks["categories"]):
                problems.append("category labels missing or empty")
            if not checks["series_titles"] or any(not isinstance(v, str) or not v for v in checks["series_titles"]):
                problems.append("series titles missing")
            # anchor vs. text cells on the same sheet
            drawing = drawing_of.get(name)
            if drawing:
                dx = z.read(drawing).decode()
                frm = re.search(r"<(?:xdr:)?from><(?:xdr:)?col>(\d+)</(?:xdr:)?col>.*?<(?:xdr:)?row>(\d+)</(?:xdr:)?row>", dx, flags=re.S)
                ext = re.search(r'<(?:xdr:)?ext cx="(\d+)" cy="(\d+)"', dx)
                sheet_idx = sheet_of_drawing.get(drawing)
                if frm and ext and sheet_idx:
                    ws = wb.worksheets[sheet_idx - 1]
                    row0, col0 = int(frm.group(2)) + 1, int(frm.group(1)) + 1
                    height_rows = math.ceil(int(ext.group(2)) / 360000 / 0.53)
                    covered = []
                    for r in range(row0, row0 + height_rows + 1):
                        for col in range(col0, col0 + 8):
                            v = ws.cell(row=r, column=col).value
                            if v not in (None, ""):
                                covered.append(f"{ws.cell(row=r, column=col).coordinate}")
                    checks["anchor"] = dict(sheet=ws.title, from_row=row0, rows=height_rows)
                    if covered:
                        problems.append(f"chart covers cells with content: {', '.join(covered[:5])}")
            out[name] = dict(checks=checks, problems=problems)
    return out


# ---- slide deck ---------------------------------------------------------------------------------------
def _lines(text: str, size_pt: float, width_in: float, bold: bool = False) -> int:
    per_line = max(1, int(width_in * 72 / (size_pt * (EM_WIDTH + (0.03 if bold else 0)))))
    return sum(max(1, math.ceil(len(part) / per_line)) for part in text.split("\n"))


def _frame_height(tf, width_in: float) -> float:
    total = 0.0
    for p in tf.paragraphs:
        size = max([r.font.size.pt for r in p.runs if r.font.size] or [18])
        bold = any(r.font.bold for r in p.runs)
        text = "".join(r.text for r in p.runs)
        total += _lines(text, size, width_in, bold) * size * LINE / 72
        total += (p.space_after.pt if p.space_after is not None else 0) / 72
    return total


def _table_height(tbl) -> float:
    total = 0.0
    for r in tbl.rows:
        need = 0.0
        for j, cell in enumerate(r.cells):
            width = tbl.columns[j].width / EMU - (cell.margin_left + cell.margin_right) / EMU
            need = max(need, _frame_height(cell.text_frame, width) + (cell.margin_top + cell.margin_bottom) / EMU)
        total += max(r.height / EMU, need)
    return total


def deck_layout_findings(path: Path) -> list[dict]:
    from pptx import Presentation
    prs = Presentation(path)
    out = []
    for n, slide in enumerate(prs.slides, 1):
        problems, boxes = [], []
        for sh in slide.shapes:
            x, y, w, h = sh.left / EMU, sh.top / EMU, sh.width / EMU, sh.height / EMU
            name = (sh.text_frame.text[:40] if sh.has_text_frame and sh.text_frame.text else ("table" if sh.has_table else ("chart" if sh.has_chart else "shape")))
            if x < -0.01 or y < -0.01 or x + w > SLIDE_W + 0.01 or y + h > SLIDE_H + 0.01:
                problems.append(f"'{name}' extends beyond the slide")
            if sh.has_table:
                rendered = _table_height(sh.table)
                boxes.append((name, x, y, w, rendered))
                if y + rendered > FOOTER_TOP + 0.01 and y < FOOTER_TOP:
                    problems.append(f"table '{name}' estimated to reach {y + rendered:.2f} in, into the footer")
            elif sh.has_chart:
                boxes.append((name, x, y, w, h))
            elif sh.has_text_frame and sh.text_frame.text.strip():
                tf = sh.text_frame
                inner_w = w - (tf.margin_left + tf.margin_right) / EMU
                need = _frame_height(tf, inner_w) + (tf.margin_top + tf.margin_bottom) / EMU
                if need > h + 0.05:
                    problems.append(f"text '{name}' needs about {need:.2f} in, box is {h:.2f} in")
                boxes.append((name, x, y, w, max(h, need)))
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                ox = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
                oy = min(a[2] + a[4], b[2] + b[4]) - max(a[2], b[2])
                if ox > 0.02 and oy > 0.02:
                    problems.append(f"'{a[0]}' and '{b[0]}' overlap ({ox:.2f} x {oy:.2f} in)")
        out.append(dict(slide=n, shapes=len(slide.shapes), problems=problems))
    return out
