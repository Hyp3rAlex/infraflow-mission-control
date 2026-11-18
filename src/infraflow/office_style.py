"""Shared visual design system for the Excel workbooks and the slide deck, and the Excel chart helper.

Palette (restrained, report style)
* NAVY       headings, primary structure
* BLUE_*     data series, ordered by lightness so that series stay distinguishable in grey-scale
             and for colour-vision deficiencies (dark -> mid -> light), with legend and labels as
             secondary encoding
* TEAL       positive outcome (gate passed, headroom)
* AMBER      warning / provisional
* RED        genuine negative: overrun, shortfall, failed gate (used sparingly)
* GREY_*     secondary text, gridlines, rules

Why the Excel chart helper exists
openpyxl 3.1 omits ``<c:overlay>``, ``<c:roundedCorners>`` and ``<c:varyColors>`` unless they are set
explicitly. Desktop Excel reads a missing element as ``true``: every chart title, axis title and legend
is then drawn *over* the plot area (legend on top of the category labels, axis titles on top of the
tick labels), corners are rounded and a single-series chart gets a different colour per bar. This was
seen by the project owner in Microsoft Excel and confirmed in the copy Excel saved
(``<c:overlay val="1"/>`` on every title and on the legend). ``style_bar_chart`` sets all three
explicitly, removes redundant axis titles and places plot area and legend with a manual layout so that
Excel does not have to auto-fit them.
"""
from __future__ import annotations

from openpyxl.chart.label import DataLabelList
from openpyxl.chart.layout import Layout, ManualLayout
from openpyxl.chart.marker import DataPoint
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.chart.text import RichText
from openpyxl.drawing.line import LineProperties
from openpyxl.drawing.text import CharacterProperties, Font as DrawingFont, Paragraph, ParagraphProperties, RichTextProperties

NAVY = "1F3864"
BLUE_DARK, BLUE_MID, BLUE_LIGHT = "1F3864", "4A7EBB", "A9C4E4"
TEAL = "2A8C82"
AMBER, AMBER_FILL = "B7791F", "FCEFD9"
RED, RED_FILL = "B42318", "FBE3E1"
GREY_TEXT, GREY_MUTED, GREY_RULE, GREY_FILL = "262626", "595959", "D9D9D9", "F2F4F7"
SERIES = [BLUE_DARK, BLUE_MID, BLUE_LIGHT]          # fixed order, never cycled
FONT = "Calibri"


def _rich(size_pt: float, bold: bool = False, colour: str = GREY_TEXT, rotate: int | None = None) -> RichText:
    cp = CharacterProperties(sz=int(size_pt * 100), b=bold, solidFill=colour, latin=DrawingFont(typeface=FONT))
    body = RichTextProperties(rot=rotate) if rotate is not None else RichTextProperties()
    return RichText(bodyPr=body, p=[Paragraph(pPr=ParagraphProperties(defRPr=cp), endParaRPr=cp)])


def _layout(x: float, y: float, w: float, h: float, inner: bool = False) -> Layout:
    return Layout(manualLayout=ManualLayout(layoutTarget="inner" if inner else None, xMode="edge", yMode="edge", x=x, y=y, w=w, h=h))


def style_bar_chart(chart, *, value_format: str = "#,##0", colours: list[str] | None = None, legend: bool = True,
                    labels: str | None = None, label_format: str | None = None, plot: tuple[float, float, float, float] | None = None,
                    legend_box: tuple[float, float, float, float] = (0.10, 0.90, 0.80, 0.08), value_min: float | None = None,
                    gap_width: int = 80) -> None:
    """Make an openpyxl bar chart render cleanly in desktop Excel.

    plot       inner plot area (x, y, w, h) as fractions of the chart; tick labels sit outside it
    legend_box legend area below the plot (x, y, w, h); ignored without legend
    labels     None, "all" (every series) or a series index whose bars get value labels
    """
    chart.roundedCorners = False
    chart.style = 2
    chart.varyColors = False
    if chart.title is not None:
        chart.title.overlay = False
        chart.title.tx.rich.p[0].pPr = ParagraphProperties(defRPr=CharacterProperties(sz=1200, b=True, solidFill=NAVY, latin=DrawingFont(typeface=FONT)))
    horizontal = chart.type == "bar"
    cat, val = chart.x_axis, chart.y_axis
    cat.delete = val.delete = False
    cat.title = val.title = None                     # units are in the chart title and the number format
    cat.tickLblPos = "low"                           # category labels below the plot even when bars are negative
    cat.majorTickMark = val.majorTickMark = "none"
    cat.txPr, val.txPr = _rich(10), _rich(9, colour=GREY_MUTED)
    cat.spPr = GraphicalProperties(ln=LineProperties(solidFill="808080", w=12700))       # visible zero baseline
    val.spPr = GraphicalProperties(ln=LineProperties(noFill=True))
    val.majorGridlines.spPr = GraphicalProperties(ln=LineProperties(solidFill=GREY_RULE, w=6350))
    val.number_format = value_format
    val.numFmt.sourceLinked = False
    if value_min is not None:
        val.scaling.min = value_min
    chart.gapWidth = gap_width
    if horizontal:
        cat.scaling.orientation = "minMax"
    x, y, w, h = plot or ((0.22, 0.13, 0.72, 0.80) if horizontal else (0.08, 0.13, 0.89, 0.62))
    chart.layout = _layout(x, y, w, h, inner=True)
    if legend:
        chart.legend.position = "b"
        chart.legend.overlay = False
        chart.legend.layout = _layout(*legend_box)
        chart.legend.txPr = _rich(10)
    else:
        chart.legend = None
    for i, series in enumerate(chart.series):
        colour = (colours or SERIES)[i % len(colours or SERIES)]
        series.graphicalProperties.solidFill = colour
        series.graphicalProperties.line.solidFill = colour
        series.invertIfNegative = False
        if labels == "all" or labels == i:
            series.dLbls = DataLabelList()
            series.dLbls.showVal = True
            series.dLbls.showSerName = series.dLbls.showCatName = series.dLbls.showLegendKey = series.dLbls.showPercent = False
            series.dLbls.showBubbleSize = False
            series.dLbls.numFmt = label_format or value_format
            series.dLbls.position = "outEnd"
            series.dLbls.txPr = _rich(9, colour=GREY_TEXT)


def highlight_point(series, idx: int, fill: str, outline: str | None = None) -> None:
    """Give one bar its own fill (e.g. an overrun or a negative balance), keeping the series."""
    pt = DataPoint(idx=idx, invertIfNegative=False)
    pt.graphicalProperties.solidFill = fill
    pt.graphicalProperties.line.solidFill = outline or fill
    series.dPt.append(pt)


def make_reproducible(path, when) -> None:
    """Rewrite an .xlsx/.pptx so that two builds from the same data are byte-identical.

    openpyxl and python-pptx stamp the current time into docProps/core.xml and into every zip entry.
    Here both are set to the reporting cutoff; the content is not touched.
    """
    import re
    import zipfile
    from pathlib import Path

    import io

    stamp = f"{when.isoformat()}T00:00:00Z"

    def normalise(blob: bytes) -> bytes:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            entries = [(i.filename, z.read(i.filename)) for i in z.infolist()]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
            for name, data in entries:
                if name == "docProps/core.xml":
                    text = data.decode("utf-8")
                    text = re.sub(r"(<dcterms:(?:created|modified)[^>]*>)[^<]*(</dcterms:(?:created|modified)>)", rf"\g<1>{stamp}\g<2>", text)
                    data = text.encode("utf-8")
                elif name.endswith(".xlsx"):          # chart data embedded in a slide deck
                    data = normalise(data)
                info = zipfile.ZipInfo(name, date_time=(when.year, when.month, when.day, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                out.writestr(info, data)
        return buf.getvalue()

    path = Path(path)
    path.write_bytes(normalise(path.read_bytes()))
