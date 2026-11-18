"""Command line interface: python -m infraflow <command>."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from . import config as c


def _dataset(args):
    from .models import load_dataset
    return load_dataset(Path(args.data), date.fromisoformat(args.as_of))


def cmd_seed(args) -> int:
    from .generator import generate
    truth = generate(Path(args.data))
    print(f"Wrote synthetic datasets to {args.data}: {truth['demand_count']} demands, cutoff {truth['as_of']}, seed {truth['seed']}")
    return 0


def cmd_validate(args) -> int:
    from .validator import build_register
    reg = build_register(_dataset(args))
    for e in reg:
        print(f"{e.severity:8} {e.code:28} {e.record_id:18} {e.message}")
    crit = sum(1 for e in reg if e.severity == "CRITICAL")
    print(f"\n{len(reg)} findings, {crit} critical. Report status: {'PROVISIONAL' if crit else 'CLEAN'}")
    return 2 if crit and args.strict else 0


def cmd_report(args) -> int:
    from .reports import write_all
    res = write_all(_dataset(args), Path(args.output))
    print(f"Wrote {len(res['files'])} files to {args.output} ({'PROVISIONAL' if res['facts']['provisional'] else 'CLEAN'})")
    return 0


def cmd_excel(args) -> int:
    from .excel_export import build_workbook
    build_workbook(_dataset(args), Path(args.output))
    print(f"Wrote {args.output}")
    return 0


def cmd_deck(args) -> int:
    from .deck import build_deck
    build_deck(_dataset(args), Path(args.output))
    print(f"Wrote {args.output}")
    return 0


def cmd_whatif(args) -> int:
    from .capacity import assess, what_if, what_if_text
    ds = _dataset(args)
    extra = {}
    for item in args.add_hours or []:
        team, month, hours = item.split(":")
        extra[(team, month)] = int(hours)
    res = what_if(ds, assess(ds), args.approve, extra_hours=extra)
    if getattr(args, "json", False):
        for r in res["results"]:
            print(json.dumps(r))
    else:
        print(what_if_text(res))
    return 0


def cmd_all(args) -> int:
    args.output = str(c.REPORTS_DIR)
    cmd_report(args)
    args.output = str(c.REPORTS_DIR / "infraflow_management_workbook.xlsx")
    cmd_excel(args)
    args.output = str(c.REPORTS_DIR / "infraflow_excel_native_exercise.xlsx")
    cmd_excel_native(args)
    args.output = str(c.PRESENTATIONS_DIR / "infraflow_executive_briefing.pptx")
    return cmd_deck(args)


def cmd_excel_native(args) -> int:
    from .excel_native import build_native_workbook
    build_native_workbook(_dataset(args), Path(args.output))
    print(f"Wrote {args.output} (formulas are calculated by Excel on opening)")
    return 0


def cmd_jira(args) -> int:
    from . import jira_sync
    return jira_sync.main(args)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="infraflow", description="InfraFlow Mission Control (synthetic demand-management demonstrator)")
    p.add_argument("--data", default=str(c.DATA_DIR), help="dataset directory")
    p.add_argument("--as-of", default=c.AS_OF.isoformat(), help="reporting cutoff YYYY-MM-DD")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("seed", help="regenerate the synthetic datasets and ground truth").set_defaults(fn=cmd_seed)
    v = sub.add_parser("validate", help="print the exception register")
    v.add_argument("--strict", action="store_true", help="exit with code 2 if critical findings exist")
    v.set_defaults(fn=cmd_validate)
    r = sub.add_parser("report", help="write all Markdown reports and report_facts.json")
    r.add_argument("--output", default=str(c.REPORTS_DIR))
    r.set_defaults(fn=cmd_report)
    x = sub.add_parser("export-excel", help="write the management workbook")
    x.add_argument("--output", default=str(c.REPORTS_DIR / "infraflow_management_workbook.xlsx"))
    x.set_defaults(fn=cmd_excel)
    n = sub.add_parser("export-excel-native", help="write the Excel-native exercise workbook (formulas, conditional formatting)")
    n.add_argument("--output", default=str(c.REPORTS_DIR / "infraflow_excel_native_exercise.xlsx"))
    n.set_defaults(fn=cmd_excel_native)
    d = sub.add_parser("deck", help="write the executive slide deck")
    d.add_argument("--output", default=str(c.PRESENTATIONS_DIR / "infraflow_executive_briefing.pptx"))
    d.set_defaults(fn=cmd_deck)
    w = sub.add_parser("what-if", help="simulate approving demands against team capacity")
    w.add_argument("approve", nargs="+", help="demand ids in approval order")
    w.add_argument("--add-hours", nargs="*", help="extra capacity as TEAM:YYYY-MM:HOURS")
    w.add_argument("--json", action="store_true", help="one JSON object per demand instead of the table")
    w.set_defaults(fn=cmd_whatif)
    sub.add_parser("all", help="reports + workbook + deck").set_defaults(fn=cmd_all)
    j = sub.add_parser("jira", help="Jira integration (dry-run unless --apply and INFRAFLOW_ALLOW_WRITE=1)")
    j.add_argument("action", choices=["plan", "pull", "seed", "reconcile", "filters", "coverage", "live"])
    j.add_argument("--today", help="with live: evaluation date YYYY-MM-DD (default: the snapshot date)")
    j.add_argument("--missing", action="store_true", help="with plan: only demands that have no Jira issue yet")
    j.add_argument("--apply", action="store_true", help="perform writes (also requires INFRAFLOW_ALLOW_WRITE=1)")
    j.add_argument("--snapshot", help="path of a Jira snapshot JSON (for reconcile, or output of pull)")
    j.add_argument("--output", help="output file")
    j.set_defaults(fn=cmd_jira)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
