"""Evaluate the formulas of the Excel-native exercise workbook WITHOUT Excel.

Uses the third-party Python library `formulas` (not a project dependency) as an independent
spreadsheet engine: `pip install formulas` into any environment, then

    python scripts/verify_native_formulas.py reports/infraflow_excel_native_exercise.xlsx

Prints every check cell of the sheet 'Analysis' and exits 1 if any is not OK.
This is NOT a test in Microsoft Excel; it only shows that the formulas, evaluated by a second
engine, reproduce the Python values.
"""
import sys

import formulas

path = sys.argv[1] if len(sys.argv) > 1 else "reports/infraflow_excel_native_exercise.xlsx"
model = formulas.ExcelModel().loads(path).finish()
solution = model.calculate()
book = next(iter(model.books))
checks, bad = {}, 0
for key, cell in solution.items():
    if "ANALYSIS" not in key.upper() or ":" in key.split("!")[-1]:
        continue
    try:
        value = cell.value[0, 0]
    except Exception:
        continue
    if value in ("OK", "DIFF", "ALL OK", "CHECK DIFFERENCES"):
        checks[key] = value
        bad += value in ("DIFF", "CHECK DIFFERENCES")
for key in sorted(checks):
    print(f"{key.split('!')[-1]:>8}  {checks[key]}")
print(f"{len(checks)} check cells evaluated, {bad} not OK")
sys.exit(1 if bad or not checks else 0)
