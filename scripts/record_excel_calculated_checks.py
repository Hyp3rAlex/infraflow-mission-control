"""Record the check-cell values that desktop Microsoft Excel calculated in a saved copy of the
exercise workbook. The saved file itself is not committed (it contains a local file path in its
metadata); this script extracts only the evidence: application, version, save time, SHA-256, and
the value Excel stored in every check cell of the sheet 'Analysis'.

Usage: .venv/bin/python scripts/record_excel_calculated_checks.py <file saved by Excel> [output.json]
"""
import hashlib
import json
import re
import sys
import warnings
import zipfile
from pathlib import Path

from openpyxl import load_workbook

src = Path(sys.argv[1])
out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parents[1] / "evidence" / "excel_desktop_native_checks.json"
with zipfile.ZipFile(src) as z:
    app = z.read("docProps/app.xml").decode()
    core = z.read("docProps/core.xml").decode()
    has_calc_chain = "xl/calcChain.xml" in z.namelist()
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    values = load_workbook(src, data_only=True)["Analysis"]
    formulas = load_workbook(src, data_only=False)["Analysis"]
checks = {}
for row in values.iter_rows():
    for cell in row:
        if cell.value in ("OK", "DIFF", "ALL OK", "CHECK DIFFERENCES"):
            checks[cell.coordinate] = dict(value=cell.value, formula=formulas[cell.coordinate].value)
record = dict(
    file_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),
    application=re.search(r"<Application>(.*?)</Application>", app).group(1),
    app_version=re.search(r"<AppVersion>(.*?)</AppVersion>", app).group(1),
    saved_at=re.search(r"<dcterms:modified[^>]*>(.*?)</dcterms:modified>", core).group(1),
    calc_chain_present=has_calc_chain,
    check_cells=len([c for c in checks.values() if c["value"] in ("OK", "DIFF")]),
    not_ok=[k for k, c in checks.items() if c["value"] in ("DIFF", "CHECK DIFFERENCES")],
    summary_cell={k: c["value"] for k, c in checks.items() if c["value"] in ("ALL OK", "CHECK DIFFERENCES")},
    cells=checks,
    note="Values cached by Microsoft Excel when the project owner opened and saved the generated workbook. "
         "Extracted by scripts/record_excel_calculated_checks.py; the saved file is not part of the repository.",
)
out.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
print(f"{record['application']} {record['app_version']}, saved {record['saved_at']}: {record['check_cells']} check cells, "
      f"not OK: {record['not_ok'] or 'none'}, summary {record['summary_cell']} -> {out}")
