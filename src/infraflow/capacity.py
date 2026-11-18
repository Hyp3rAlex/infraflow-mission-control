"""Team capacity model.

Hours are engineer-hours per team and calendar month. ``capacity.csv`` holds available and
allocated hours; ``allocations.csv`` lists what the allocation consists of (``RUN`` = operations,
otherwise an approved demand). Remaining = available - allocated. An over-allocated month
contributes zero, not a negative number, to what can still be promised.

This is a planning aid for a demand board, not a scheduling optimiser: it ignores individual
skills, part-time availability and task ordering.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from . import config as c
from .models import CRITICAL, WARNING, Dataset, Demand, Exc, to_int


@dataclass
class CapacityResult:
    cells: dict[tuple[str, str], dict]        # (team, month) -> available / allocated / remaining / demand_ids
    exceptions: list[Exc]

    def months(self) -> list[str]:
        return sorted({m for _, m in self.cells})

    def remaining(self, team: str, month: str) -> int | None:
        cell = self.cells.get((team, month))
        return None if cell is None else cell["remaining"]

    def usable(self, team: str, months: list[str]) -> int | None:
        vals = [self.remaining(team, m) for m in months]
        if not vals or any(v is None for v in vals):
            return None
        return sum(max(v, 0) for v in vals)

    def utilisation(self, team: str, month: str) -> float | None:
        cell = self.cells.get((team, month))
        return None if not cell or not cell["available"] else cell["allocated"] / cell["available"]


def month_list(first: str, last: str) -> list[str]:
    y, m = map(int, first.split("-"))
    out = []
    while f"{y:04d}-{m:02d}" <= last:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def delivery_window(due_at: date | None, as_of: date, horizon: list[str]) -> list[str]:
    """Months in which the work can still be done: cutoff month up to the due month, inside the horizon."""
    start = as_of.strftime("%Y-%m")
    end = max(due_at.strftime("%Y-%m"), start) if due_at else start
    return [m for m in month_list(start, end) if m in horizon]


def assess(ds: Dataset) -> CapacityResult:
    exc: list[Exc] = []
    cells: dict[tuple[str, str], dict] = {}
    for r in ds.capacity:
        team, month = r.get("team", ""), r.get("month", "")
        available, allocated = to_int(r.get("available_hours")), to_int(r.get("allocated_hours"))
        if available is None or allocated is None or available < 0 or allocated < 0 or (team, month) in cells:
            exc.append(Exc("INVALID_CAPACITY_ROW", CRITICAL, f"{team}/{month}", "Capacity row is duplicated or has invalid hours; row excluded.",
                           source="capacity.csv"))
            continue
        cells[(team, month)] = dict(available=available, allocated=allocated, remaining=available - allocated,
                                    demand_ids=[], run_hours=0)
    demands = {d.external_id: d for d in ds.demands}
    detail: dict[tuple[str, str], int] = defaultdict(int)
    per_demand: dict[str, int] = defaultdict(int)
    for a in ds.allocations:
        key, ext, hours = (a.get("team", ""), a.get("month", "")), a.get("external_id", ""), to_int(a.get("hours"))
        if hours is None or hours < 0 or key not in cells:
            exc.append(Exc("INVALID_ALLOCATION_ROW", CRITICAL, f"{key[0]}/{key[1]}/{ext}", "Allocation row has invalid hours or an unknown team-month.",
                           source="allocations.csv"))
            continue
        detail[key] += hours
        if ext == "RUN":
            cells[key]["run_hours"] += hours
            continue
        cells[key]["demand_ids"].append(ext)
        per_demand[ext] += hours
        d = demands.get(ext)
        if d is None or d.status not in c.FUNDED:
            exc.append(Exc("ALLOCATION_WITHOUT_APPROVAL", WARNING, ext, f"{hours} h allocated in {key[1]} to a demand that is not approved.",
                           source="allocations.csv"))
    for key, cell in sorted(cells.items()):
        if detail.get(key, 0) != cell["allocated"]:
            exc.append(Exc("CAPACITY_LEDGER_MISMATCH", CRITICAL, f"{key[0]}/{key[1]}",
                           f"capacity.csv shows {cell['allocated']} h allocated, allocation lines total {detail.get(key, 0)} h.",
                           source="capacity.csv"))
        if cell["allocated"] > cell["available"]:
            exc.append(Exc("CAPACITY_OVERALLOCATED", WARNING, f"{key[0]}/{key[1]}",
                           f"{c.TEAMS.get(key[0], (key[0],))[0]} is allocated {cell['allocated']} h against {cell['available']} h available "
                           f"({cell['allocated'] - cell['available']} h over). Approved demands in this month: {', '.join(cell['demand_ids']) or 'none'}.",
                           source="capacity.csv"))
    for ext, hours in sorted(per_demand.items()):
        d = demands.get(ext)
        if d and d.hours is not None and hours > d.hours:
            exc.append(Exc("DEMAND_OVER_ALLOCATED", WARNING, ext, f"{hours} h allocated but only {d.hours} h estimated; hours may be double counted.",
                           source="allocations.csv"))
    return CapacityResult(cells, exc)


def capacity_gate(cap: CapacityResult, team: str, hours: int | None, due_at: date | None, as_of: date) -> tuple[bool | None, str, int | None]:
    """Can the team deliver `hours` between the cutoff and the due date with what is still unallocated?"""
    if not team or hours is None:
        return None, "Unavailable: delivery team or effort estimate missing.", None
    window = delivery_window(due_at, as_of, cap.months())
    usable = cap.usable(team, window)
    if usable is None:
        return None, "Unavailable: no capacity data for this team in the delivery window.", None
    ok = hours <= usable
    span = window[0] if len(window) == 1 else f"{window[0]} to {window[-1]}"
    return ok, (f"{hours} h needed, {usable} h unallocated for {c.TEAMS.get(team, (team,))[0]} in {span} "
                f"({'fits' if ok else f'shortfall of {hours - usable} h'})."), usable


def what_if(ds: Dataset, cap: CapacityResult, approve_ids: list[str], extra_hours: dict[tuple[str, str], int] | None = None,
            hours_override: dict[str, int] | None = None) -> dict:
    """Simulate approving demands in the given order.

    Each demand takes the earliest unallocated hours of its team inside its delivery window
    (cutoff month to due month). `extra_hours` adds capacity to team-months (for example released
    run work or overtime). Nothing is written back; the result is a comparison aid for a human decision.

    Every result separates four different "hours available" figures for the demand's window:

    * ``unallocated_today``          - what the capacity table shows now, with no hypothetical change.
                                       This is the figure the capacity gate and the reports use.
    * ``after_extra_capacity``       - the same after adding ``extra_hours`` (extra hours first absorb an
                                       existing over-allocation of that month).
    * ``taken_by_earlier_approvals`` - hours inside this window consumed by demands approved earlier in
                                       this simulation.
    * ``usable_for_this_demand``     - after_extra_capacity - taken_by_earlier_approvals; the demand fits
                                       if its effort is not larger. ``usable_before`` is the same number
                                       (kept for compatibility).

    ``remaining_after`` is what is left in the window once this demand has taken its hours (unchanged if
    it does not fit, because a demand that does not fit takes nothing).
    """
    baseline = {k: v["remaining"] for k, v in cap.cells.items()}
    remaining = dict(baseline)
    for key, hours in (extra_hours or {}).items():
        if key in remaining:
            remaining[key] += hours
    with_extra = dict(remaining)
    results = []
    for ext in approve_ids:
        d = ds.demand(ext)
        if d is None:
            results.append(dict(external_id=ext, fits=None, note="unknown demand"))
            continue
        need = (hours_override or {}).get(ext, d.hours)
        window = delivery_window(d.due_at, ds.as_of, cap.months())
        if need is None or not all((d.team, m) in remaining for m in window) or not window:
            results.append(dict(external_id=ext, fits=None, note="effort or capacity data missing"))
            continue
        free = lambda table: sum(max(table[(d.team, m)], 0) for m in window)
        today, extra, usable = free(baseline), free(with_extra), free(remaining)
        fits = need <= usable
        if fits:
            left = need
            for m in window:
                take = min(max(remaining[(d.team, m)], 0), left)
                remaining[(d.team, m)] -= take
                left -= take
        results.append(dict(external_id=ext, team=d.team, hours=need, window=window,
                            unallocated_today=today, after_extra_capacity=extra, taken_by_earlier_approvals=extra - usable,
                            usable_for_this_demand=usable, usable_before=usable, fits=fits,
                            shortfall=0 if fits else need - usable, remaining_after=free(remaining)))
    return dict(results=results, remaining=remaining)


def what_if_text(res: dict) -> str:
    """Plain-text table of a what-if result with the meaning of each column."""
    lines = ["Capacity what-if (simulation only; nothing is approved or written).",
             "Hours are team hours inside each demand's delivery window (cutoff month to due month).", "",
             f"{'Demand':<15}{'Team':<6}{'Window':<19}{'Need':>6}{'Today':>7}{'+Extra':>8}{'-Earlier':>10}{'Usable':>8}{'Result':>18}{'Left':>6}"]
    for r in res["results"]:
        if r.get("fits") is None:
            lines.append(f"{r['external_id']:<15}{r.get('note', '')}")
            continue
        window = r["window"][0] if len(r["window"]) == 1 else f"{r['window'][0]}..{r['window'][-1]}"
        verdict = "fits" if r["fits"] else f"short by {r['shortfall']} h"
        lines.append(f"{r['external_id']:<15}{r['team']:<6}{window:<19}{r['hours']:>6}{r['unallocated_today']:>7}{r['after_extra_capacity']:>8}"
                     f"{r['taken_by_earlier_approvals']:>10}{r['usable_for_this_demand']:>8}{verdict:>18}{r['remaining_after']:>6}")
    lines += ["", "Today    = unallocated hours in the capacity table now (the figure used by the capacity gate and the reports)",
              "+Extra   = the same after adding the hypothetical extra hours (--add-hours)",
              "-Earlier = hours in this window taken by demands approved earlier in this simulation",
              "Usable   = +Extra minus -Earlier; the demand fits if Need <= Usable",
              "Left     = unallocated hours in the window after this demand (unchanged if it does not fit)"]
    return "\n".join(lines)
