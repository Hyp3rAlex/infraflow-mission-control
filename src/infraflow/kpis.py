"""Operational KPIs. Every KPI carries its definition and the record ids it was computed from."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from statistics import median

from . import config as c
from .capacity import CapacityResult
from .finance import FinanceResult
from .models import Dataset, to_date
from .scoring import priority_band, priority_score, review_queue


def K(value, definition: str, ids=None) -> dict:
    return dict(value=value, definition=definition, source_ids=sorted(ids) if ids is not None else [])


def business_days_between(start: date, end: date) -> int:
    """Working days after `start` up to and including `end` (Mon-Fri, no holiday calendar)."""
    days, d = 0, start
    while d < end:
        d += timedelta(days=1)
        if d.weekday() < 5:
            days += 1
    return days


def _first(events: list[dict], status: str) -> date | None:
    return next((to_date(e["occurred_at"]) for e in events if e["new_status"] == status), None)


def days_in_status(ds: Dataset, ext: str, status: str) -> int | None:
    """Days since the demand last entered its current status, measured at the cutoff."""
    entered = [to_date(e["occurred_at"]) for e in ds.events_for(ext) if e["new_status"] == status]
    return (ds.as_of - entered[-1]).days if entered else None


def last_activity(ds: Dataset, ext: str) -> date | None:
    ev = ds.events_for(ext)
    return to_date(ev[-1]["occurred_at"]) if ev else None


def compute(ds: Dataset, fin: FinanceResult, cap: CapacityResult) -> dict:
    as_of = ds.as_of
    demands = [d for d in ds.demands if d.requested_at is None or d.requested_at <= as_of]
    open_d = [d for d in demands if d.is_open]
    k: dict[str, dict] = {}
    k["total_demands"] = K(len(demands), "All registered records with a request date on or before the cutoff.", [d.external_id for d in demands])
    k["open_demands"] = K(len(open_d), "Records whose status is not Complete, Rejected or Routed Out.", [d.external_id for d in open_d])
    by_status = Counter(d.status for d in demands)
    k["by_status"] = K({s: by_status.get(s, 0) for s in c.STATUS_ORDER}, "Count of records per current lifecycle status (demands.csv).")
    bands = Counter(priority_band(priority_score(d)) for d in open_d)
    k["open_by_priority"] = K({b: bands.get(b, 0) for _, b in c.PRIORITY_BANDS}, "Open demands per priority band derived from the weighted score.")
    k["open_by_site"] = K(dict(sorted(Counter(d.site for d in open_d).items())), "Open demands per requesting site.")
    k["open_by_team"] = K({t: sum(1 for d in open_d if d.team == t) for t in c.TEAMS}, "Open demands per responsible delivery team.")
    k["open_by_category"] = K(dict(sorted(Counter(d.category for d in open_d).items())), "Open demands per service category.")

    week_start = as_of - timedelta(days=6)
    intake = [d for d in demands if d.requested_at and week_start <= d.requested_at <= as_of]
    k["intake_last_7_days"] = K(len(intake), f"Records requested from {week_start} to {as_of} inclusive.", [d.external_id for d in intake])
    k["intake_by_month"] = K(dict(sorted(Counter(d.requested_at.strftime("%Y-%m") for d in demands if d.requested_at).items())),
                             "Records per month of request date.")

    overdue = [d for d in open_d if d.due_at and d.due_at < as_of]
    k["overdue_open"] = K(len(overdue), "Open demands whose required-by date is before the cutoff.", [d.external_id for d in overdue])
    blocked = [d for d in open_d if d.blocked]
    k["blocked_open"] = K(len(blocked), "Open demands flagged as blocked with a recorded reason.", [d.external_id for d in blocked])
    stale = [d for d in open_d if d.status != c.DEFERRED and (last_activity(ds, d.external_id) is None
             or (as_of - last_activity(ds, d.external_id)).days >= c.STALE_DAYS)]
    k["stale_open"] = K(len(stale), f"Open, not deferred, and no status event for {c.STALE_DAYS} days or more.", [d.external_id for d in stale])
    unassigned = [d for d in open_d if not d.triage_owner]
    k["unassigned_open"] = K(len(unassigned), "Open demands without an assigned owner.", [d.external_id for d in unassigned])
    k["unassigned_pct"] = K(round(100 * len(unassigned) / len(open_d), 1) if open_d else None, "Unassigned open demands / open demands.")
    in_scope = [d for d in demands if d.status != c.ROUTED_OUT]
    complete = [d for d in in_scope if not d.missing_required()]
    k["completeness_pct"] = K(round(100 * len(complete) / len(in_scope), 1) if in_scope else None,
                              "Demands (excluding routed-out records) with every mandatory intake field filled / all such demands.",
                              [d.external_id for d in in_scope if d.missing_required()])
    pending = [d for d in open_d if d.status == c.READY_FOR_DECISION]
    k["approval_pending"] = K(len(pending), "Demands in Ready for Decision.", [d.external_id for d in pending])
    review_due = [d for d in open_d if d.status == c.DEFERRED and d.next_review_at and d.next_review_at <= as_of + timedelta(days=30)]
    k["deferred_review_due_30d"] = K(len(review_due), "Deferred demands with a next review date within 30 days of the cutoff.", [d.external_id for d in review_due])

    triage, lead, on_time, done_ids, done_month = [], [], [], [], Counter()
    for d in demands:
        ev = ds.events_for(d.external_id)
        sub, tri, done = _first(ev, c.SUBMITTED), _first(ev, c.TRIAGED), _first(ev, c.COMPLETE)
        if sub and tri:
            triage.append((d.external_id, business_days_between(sub, tri)))
        if d.status == c.COMPLETE and sub and done:
            lead.append((d.external_id, (done - sub).days))
            done_ids.append(d.external_id)
            done_month[done.strftime("%Y-%m")] += 1
            if d.due_at:
                on_time.append((d.external_id, done <= d.due_at))
    k["median_triage_business_days"] = K(median(v for _, v in triage) if triage else None,
                                         "Median working days from submission to the first Triaged event (status history); demands never triaged are excluded.",
                                         [i for i, _ in triage])
    k["median_lead_time_days"] = K(median(v for _, v in lead) if lead else None,
                                   "Median calendar days from submission to completion for completed demands.", [i for i, _ in lead])
    k["completed_total"] = K(len(done_ids), "Demands with status Complete.", done_ids)
    k["throughput_by_month"] = K(dict(sorted(done_month.items())), "Completed demands per month of the Complete event.")
    k["on_time_delivery_pct"] = K(round(100 * sum(1 for _, ok in on_time if ok) / len(on_time), 1) if on_time else None,
                                  "Completed demands finished on or before the required-by date / completed demands.",
                                  [i for i, ok in on_time if not ok])
    ageing = {}
    for d in open_d:
        days = days_in_status(ds, d.external_id, d.status)
        if days is not None:
            ageing[d.external_id] = days
    by_stage = defaultdict(list)
    for d in open_d:
        if d.external_id in ageing:
            by_stage[d.status].append(ageing[d.external_id])
    k["stage_ageing_median_days"] = K({s: median(v) for s, v in by_stage.items()},
                                      "Median days open demands have spent in their current status (from the latest matching status event).")
    k["stage_ageing_days"] = K(ageing, "Days in current status per open demand.")

    outcomes = Counter(r["decision"] for r in ds.decisions if (to_date(r.get("decided_at")) or date.max) <= as_of)
    k["decision_outcomes"] = K({o: outcomes.get(o, 0) for o in ("approved", "deferred", "rejected")},
                               "Recorded decisions on or before the cutoff (decisions.csv).", [r["decision_id"] for r in ds.decisions])
    routed = [d for d in demands if d.status == c.ROUTED_OUT]
    k["routed_out"] = K(len(routed), "Records routed out of the demand pipeline (incidents, standard service requests).", [d.external_id for d in routed])

    queue = review_queue(ds, fin, cap)
    hot = [r for r in queue if r["gates"].band in ("Highest", "High") and not r["gates"].all_pass]
    k["high_priority_not_approvable"] = K(len(hot), "Undecided or deferred demands in band High or Highest that fail at least one gate today.",
                                          [r["demand"].external_id for r in hot])
    util = {f"{t}|{m}": round(100 * cap.utilisation(t, m), 1) for (t, m) in sorted(cap.cells) if cap.utilisation(t, m) is not None}
    k["capacity_utilisation_pct"] = K(util, "Allocated hours / available hours per team and month (synthetic planning data).")
    over = [key for key, cell in cap.cells.items() if cell["allocated"] > cell["available"]]
    k["overallocated_team_months"] = K(len(over), "Team-months where allocated hours exceed available hours.", [f"{t}|{m}" for t, m in over])
    tot = fin.totals()
    for name in ("budget_period_eur", "actual_eur", "open_commitments_eur", "approved_not_committed_eur", "forecast_eac_eur", "forecast_variance_eur"):
        k["finance_" + name] = K(tot[name], f"Sum over cost centres of {name} (see finance.py for the definition).")
    k["finance_unmapped_actual_eur"] = K(fin.unmapped_actual_eur, "Valid spend booked to a cost centre without a budget.")
    k["finance_allocation_coverage_pct"] = K(None if fin.allocation_coverage is None else round(100 * fin.allocation_coverage, 2),
                                             "Valid spend mapped to a budgeted cost centre / all valid spend.")
    k["finance_unmapped_actual_eur"]["source_ids"] = sorted(fin.unmapped_invoice_ids)
    # Excluded invoice rows: one figure per currency. Amounts in different currencies are never added.
    buckets = fin.excluded_by_currency()
    eur_b = buckets.get(c.CURRENCY, dict(net=0, gross=0, invoice_ids=[]))
    k["finance_excluded_eur_gross"] = K(eur_b["gross"], "EUR invoice rows excluded as invalid, sum of absolute values. EUR rows only; duplicates not included.",
                                        eur_b["invoice_ids"])
    k["finance_excluded_eur_net"] = K(eur_b["net"], "EUR invoice rows excluded as invalid, signed sum. EUR rows only; duplicates not included.",
                                      eur_b["invoice_ids"])
    foreign = {cur: b for cur, b in buckets.items() if cur != c.CURRENCY}
    k["finance_excluded_foreign"] = K({cur: b["net"] for cur, b in foreign.items()},
                                      "Invoice rows excluded because they are not in EUR and no approved conversion rate exists, "
                                      "per original currency. Not converted and not part of any EUR figure.",
                                      [i for b in foreign.values() for i in b["invoice_ids"]])
    k["finance_unreconciled_po_eur"] = K(sum(abs(p["difference_eur"]) for p in fin.unreconciled_pos),
                                         "Absolute difference between the purchase-order ledger and the linked valid invoices. "
                                         "The forecast uses the ledger; it is unreliable by this amount until reconciled.",
                                         [p["po_id"] for p in fin.unreconciled_pos])
    k["finance_forecast_eac_invoice_basis_eur"] = K(tot["forecast_eac_eur"] + fin.forecast_uncertainty_eur,
                                                    "Forecast EAC if unreconciled purchase orders were valued from their invoices instead of the ledger.",
                                                    [p["po_id"] for p in fin.unreconciled_pos])
    return k
