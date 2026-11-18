"""Finance reconciliation and forecast.

Definitions (per cost centre, budget period = config.PERIOD_MONTHS, cutoff = dataset.as_of):

* actual            = sum of valid, unique invoices and credit notes dated on or before the cutoff
* open commitments  = for purchase orders with status ``open``:
                      max(approved_commitment - recognized_actual, 0)
                      -> the invoiced part of a PO is never counted a second time
* approved, not committed = period cost of demands that are approved but have no purchase order yet
* forecast EAC      = actual + open commitments + approved, not committed
* forecast variance = forecast EAC - approved budget of the period   (positive = overrun)
* uncommitted budget = budget - actual - open commitments

Currencies: every figure above is EUR. A ledger row carries ``amount`` and ``currency``. A non-EUR row is
converted only with an approved rate (``config.APPROVED_FX_RATES`` or the ``fx_rates`` argument); without
one it is excluded and reported **in its own currency**. Amounts in different currencies are never added
together: ``excluded_by_currency`` keeps one bucket per currency and ``sum_same_currency`` raises
``CurrencyMixError`` on a mixed list.

Unreconciled purchase orders: when the ledger's recognised amount differs from the linked valid invoices,
the open commitment is still computed from the ledger (the system of record), but the purchase order is
listed in ``unreconciled_pos`` with the EUR amount by which the forecast would change on invoice basis.

The forecast is a commitment-based scenario forecast, not a statistical prediction: it assumes that
open purchase orders are fully invoiced inside the period and that nothing else is approved.
Invalid rows are never dropped silently: each one is excluded from the totals *and* reported.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from . import config as c
from .models import CRITICAL, INFO, WARNING, Dataset, Demand, Exc, to_amount, to_date

PO_STATUSES = {"open", "closed", "cancelled"}


class CurrencyMixError(ValueError):
    """Raised when amounts in different currencies would be added without an approved conversion."""


def row_amount(row: dict):
    """Raw amount of a ledger row in the row's own currency (``amount``; ``amount_eur`` is the legacy column name)."""
    return row.get("amount", row.get("amount_eur"))


def sum_same_currency(rows: list[dict], currency: str) -> float:
    """Sum ``amount`` over rows, refusing any row that is not in ``currency``."""
    other = sorted({r.get("currency") or "?" for r in rows} - {currency})
    if other:
        raise CurrencyMixError(f"Cannot add {', '.join(other)} amounts to a {currency} total without an approved conversion rate.")
    return sum(r["amount"] or 0 for r in rows)


@dataclass
class CostCentreFinance:
    cost_center: str
    budget_period_eur: float = 0
    budget_to_date_eur: float = 0
    actual_eur: float = 0
    open_commitments_eur: float = 0
    approved_not_committed_eur: float = 0
    invoice_ids: list[str] = field(default_factory=list)
    po_ids: list[str] = field(default_factory=list)
    uncommitted_demand_ids: list[str] = field(default_factory=list)

    @property
    def uncommitted_budget_eur(self):
        return self.budget_period_eur - self.actual_eur - self.open_commitments_eur

    @property
    def variance_to_date_eur(self):
        return self.actual_eur - self.budget_to_date_eur

    @property
    def forecast_eac_eur(self):
        return self.actual_eur + self.open_commitments_eur + self.approved_not_committed_eur

    @property
    def forecast_variance_eur(self):
        return self.forecast_eac_eur - self.budget_period_eur

    @property
    def headroom_eur(self):
        return -self.forecast_variance_eur

    def as_dict(self) -> dict:
        return dict(cost_center=self.cost_center, budget_period_eur=self.budget_period_eur,
                    budget_to_date_eur=self.budget_to_date_eur, actual_eur=self.actual_eur,
                    open_commitments_eur=self.open_commitments_eur,
                    approved_not_committed_eur=self.approved_not_committed_eur,
                    uncommitted_budget_eur=self.uncommitted_budget_eur,
                    variance_to_date_eur=self.variance_to_date_eur, forecast_eac_eur=self.forecast_eac_eur,
                    forecast_variance_eur=self.forecast_variance_eur)


@dataclass
class FinanceResult:
    as_of: date
    by_cc: dict[str, CostCentreFinance]
    monthly_actual: dict[tuple[str, str], float]
    monthly_budget: dict[tuple[str, str], float]
    unmapped_actual_eur: float
    excluded: list[dict]                 # rows left out of the totals, with the reason
    after_cutoff: list[dict]
    exceptions: list[Exc]
    po_outstanding: dict[str, float]
    actual_by_demand: dict[str, float]
    unmapped_invoice_ids: list[str] = field(default_factory=list)
    unreconciled_pos: list[dict] = field(default_factory=list)

    def excluded_by_currency(self, include_duplicates: bool = False) -> dict[str, dict]:
        """Excluded invoice rows, one bucket per currency. Buckets are never added to each other.

        ``net`` is the signed sum, ``gross`` the sum of absolute values (a wrongly signed row is still
        an excluded row). Duplicates are left out by default: their amount is already counted once.
        """
        out: dict[str, dict] = {}
        for x in self.excluded:
            if x["reason"] == "DUPLICATE_INVOICE" and not include_duplicates:
                continue
            b = out.setdefault(x["currency"] or "?", dict(rows=[]))
            b["rows"].append(x)
        for cur, b in out.items():
            b["net"] = sum_same_currency(b["rows"], cur)
            b["gross"] = sum(abs(r["amount"] or 0) for r in b["rows"])
            b["invoice_ids"] = [r["invoice_id"] for r in b["rows"]]
        return dict(sorted(out.items()))

    @property
    def forecast_uncertainty_eur(self) -> float:
        """EUR by which the forecast would change if unreconciled purchase orders were valued from invoices."""
        return sum(p["forecast_effect_eur"] for p in self.unreconciled_pos)

    def totals(self) -> dict:
        keys = ["budget_period_eur", "budget_to_date_eur", "actual_eur", "open_commitments_eur",
                "approved_not_committed_eur", "uncommitted_budget_eur", "variance_to_date_eur",
                "forecast_eac_eur", "forecast_variance_eur"]
        return {k: sum(v.as_dict()[k] for v in self.by_cc.values()) for k in keys}

    @property
    def allocation_coverage(self) -> float | None:
        """Share of valid recorded spend that is mapped to a known cost centre."""
        mapped = sum(v.actual_eur for v in self.by_cc.values())
        total = mapped + self.unmapped_actual_eur
        return None if total == 0 else mapped / total


def recurring_months(go_live_month: str) -> int:
    return sum(1 for m in c.PERIOD_MONTHS if m > go_live_month)


def completion_date(ds: Dataset, external_id: str) -> date | None:
    done = [e for e in ds.events_for(external_id) if e["new_status"] == c.COMPLETE]
    return to_date(done[-1]["occurred_at"]) if done else None


def period_cost(one_time, monthly, go_live_month: str) -> float | None:
    """Cost falling into the budget period: one-time cost plus recurring cost for the months after go-live."""
    if one_time is None or monthly is None or not go_live_month:
        return None
    return one_time + monthly * recurring_months(go_live_month)


def demand_period_cost(ds: Dataset, d: Demand) -> float | None:
    done = completion_date(ds, d.external_id)
    go_live = done.strftime("%Y-%m") if done else (d.due_at.strftime("%Y-%m") if d.due_at else "")
    return period_cost(d.one_time, d.monthly, go_live)


def option_total_12_month(one_time: float, monthly: float) -> float:
    """Undiscounted 12-month cost of an option: setup plus twelve months of run cost."""
    return one_time + monthly * 12


def reconcile(ds: Dataset, fx_rates: dict[str, float] | None = None) -> FinanceResult:
    as_of, exc = ds.as_of, []
    fx_rates = dict(c.APPROVED_FX_RATES if fx_rates is None else fx_rates)
    as_of_month = as_of.strftime("%Y-%m")
    by_cc: dict[str, CostCentreFinance] = {}
    monthly_budget: dict[tuple[str, str], float] = {}
    for b in ds.budgets:
        cc, month, amount = b.get("cost_center", ""), b.get("month", ""), to_amount(b.get("approved_budget_eur"))
        if amount is None or amount < 0 or month not in c.PERIOD_MONTHS or not cc:
            exc.append(Exc("INVALID_BUDGET_ROW", CRITICAL, f"{cc}/{month}", "Budget row has an invalid amount, month or cost centre.",
                           source="budgets.csv", cost_center=cc))
            continue
        if (cc, month) in monthly_budget:
            exc.append(Exc("DUPLICATE_BUDGET_ROW", CRITICAL, f"{cc}/{month}", "Budget defined twice for the same month.",
                           source="budgets.csv", cost_center=cc, amount_eur=amount))
            continue
        monthly_budget[(cc, month)] = amount
        f = by_cc.setdefault(cc, CostCentreFinance(cc))
        f.budget_period_eur += amount
        if month <= as_of_month:
            f.budget_to_date_eur += amount

    demands = {d.external_id: d for d in ds.demands}
    po_ids = {p.get("po_id", "") for p in ds.commitments}
    all_invoice_ids = {a.get("invoice_id", "") for a in ds.actuals}
    seen: set[str] = set()
    excluded, after_cutoff = [], []
    monthly_actual: dict[tuple[str, str], float] = defaultdict(float)
    invoiced_per_po: dict[str, float] = defaultdict(float)
    actual_by_demand: dict[str, float] = defaultdict(float)
    unmapped, unmapped_ids, unreconciled = 0, [], []

    def drop(row, code, severity, message, amount=None):
        cur = (row.get("currency") or "").strip() or "?"
        is_eur = cur == c.CURRENCY
        excluded.append(dict(invoice_id=row.get("invoice_id", ""), reason=code, amount=amount, currency=cur,
                             amount_eur=amount if is_eur else None, cost_center=row.get("cost_center", "")))
        exc.append(Exc(code, severity, row.get("invoice_id", ""), message, source="actuals.csv",
                       cost_center=row.get("cost_center", ""), amount_eur=amount if is_eur else None,
                       currency=cur, amount_original=None if is_eur else amount))

    for a in ds.actuals:
        iid, cc = a.get("invoice_id", ""), a.get("cost_center", "")
        amount, day = to_amount(row_amount(a)), to_date(a.get("invoice_date"))
        cur = (a.get("currency") or "").strip()
        if iid in seen:
            drop(a, "DUPLICATE_INVOICE", WARNING, f"Invoice id {iid} appears more than once; counted once.", amount)
            continue
        seen.add(iid)
        if day is None:
            drop(a, "INVALID_DATE", CRITICAL, f"Invoice date '{a.get('invoice_date')}' is not a valid date; row excluded.", amount)
            continue
        if cur != c.CURRENCY:
            rate = fx_rates.get(cur)
            if rate is None or amount is None:
                drop(a, "UNSUPPORTED_CURRENCY", CRITICAL,
                     f"Amount is in '{cur}' and no approved conversion rate to EUR exists; row excluded and reported in {cur or 'its own currency'}, not added to any EUR figure.", amount)
                continue
            original = amount
            amount = to_amount(round(original * rate, 2))
            exc.append(Exc("FX_CONVERTED", INFO, iid, f"{cur} {original:,.2f} converted to EUR at the approved rate {rate}.",
                           source="actuals.csv", cost_center=cc, amount_eur=amount, currency=cur, amount_original=original))
        if amount is None or amount == 0:
            drop(a, "INVALID_AMOUNT", CRITICAL, f"Amount '{row_amount(a)}' is missing, zero or not numeric; row excluded.", amount)
            continue
        if amount < 0:
            ref = a.get("credit_note_ref", "")
            if not ref:
                drop(a, "INVALID_AMOUNT", CRITICAL, "Negative amount without a credit-note reference; row excluded.", amount)
                continue
            if ref not in all_invoice_ids or ref == iid:
                drop(a, "INVALID_CREDIT_NOTE", CRITICAL, f"Credit note refers to unknown invoice '{ref}'; row excluded.", amount)
                continue
        if day > as_of:
            after_cutoff.append(dict(invoice_id=iid, amount_eur=amount, invoice_date=day.isoformat(), cost_center=cc))
            continue
        month = day.strftime("%Y-%m")
        if month not in c.PERIOD_MONTHS:
            drop(a, "OUT_OF_PERIOD", CRITICAL, f"Invoice month {month} is outside the budget period; row excluded.", amount)
            continue
        if (a.get("month") or "") != month:
            exc.append(Exc("PERIOD_MISMATCH", WARNING, iid, f"Month column '{a.get('month')}' differs from invoice date {day}; the date is used.",
                           source="actuals.csv", cost_center=cc, amount_eur=amount))
        if cc not in by_cc:
            unmapped += amount
            unmapped_ids.append(iid)
            exc.append(Exc("UNKNOWN_COST_CENTER", CRITICAL, iid, f"Cost centre '{cc}' has no budget; amount is reported as unmapped spend.",
                           source="actuals.csv", cost_center=cc, amount_eur=amount))
            continue
        ext, po = a.get("external_id", ""), a.get("po_id", "")
        if ext:
            d = demands.get(ext)
            if d is None:
                exc.append(Exc("MISSING_REFERENCE", WARNING, iid, f"Invoice refers to demand '{ext}', which does not exist.",
                               source="actuals.csv", cost_center=cc, amount_eur=amount))
            elif d.status not in c.FUNDED or (d.decision_date and day < d.decision_date):
                exc.append(Exc("UNAPPROVED_SPEND", WARNING, iid, f"Spend booked on {ext} without an approval decision at the invoice date.",
                               source="actuals.csv", cost_center=cc, amount_eur=amount))
            actual_by_demand[ext] += amount
        if po and po not in po_ids:
            exc.append(Exc("UNKNOWN_PO", WARNING, iid, f"Invoice refers to purchase order '{po}', which does not exist.",
                           source="actuals.csv", cost_center=cc, amount_eur=amount))
        elif po:
            invoiced_per_po[po] += amount
        f = by_cc[cc]
        f.actual_eur += amount
        f.invoice_ids.append(iid)
        monthly_actual[(cc, month)] += amount

    po_outstanding: dict[str, float] = {}
    seen_po: set[str] = set()
    demands_with_po: set[str] = set()
    for p in ds.commitments:
        pid, cc, status = p.get("po_id", ""), p.get("cost_center", ""), p.get("status", "")
        approved, recognized = to_amount(p.get("approved_commitment_eur")), to_amount(p.get("recognized_actual_eur"))
        bad = None
        if pid in seen_po:
            bad = "Purchase order id appears more than once."
        elif approved is None or recognized is None or approved < 0:
            bad = "Commitment amounts are missing, negative or not numeric."
        elif status not in PO_STATUSES:
            bad = f"Unknown purchase order status '{status}'."
        elif p.get("month", "") not in c.PERIOD_MONTHS:
            bad = f"Commitment month '{p.get('month')}' is outside the budget period."
        elif cc not in by_cc:
            bad = f"Cost centre '{cc}' has no budget."
        seen_po.add(pid)
        if bad:
            exc.append(Exc("INVALID_COMMITMENT", CRITICAL, pid, bad + " Row excluded.", source="commitments.csv",
                           cost_center=cc, amount_eur=approved))
            continue
        if p.get("external_id"):
            demands_with_po.add(p["external_id"])
        invoiced = invoiced_per_po.get(pid, 0)
        if invoiced != recognized:
            exc.append(Exc("PO_RECONCILIATION_MISMATCH", CRITICAL, pid,
                           f"Ledger shows {recognized:,.0f} EUR recognised, linked valid invoices total {invoiced:,.0f} EUR.",
                           source="commitments.csv", cost_center=cc, amount_eur=invoiced - recognized))
            ledger_out = max(approved - recognized, 0) if status == "open" else 0
            invoice_out = max(approved - invoiced, 0) if status == "open" else 0
            unreconciled.append(dict(po_id=pid, cost_center=cc, external_id=p.get("external_id", ""), approved_eur=approved,
                                     ledger_recognized_eur=recognized, invoiced_eur=invoiced, difference_eur=invoiced - recognized,
                                     outstanding_ledger_basis_eur=ledger_out, outstanding_invoice_basis_eur=invoice_out,
                                     forecast_effect_eur=invoice_out - ledger_out))
        if recognized > approved:
            exc.append(Exc("PO_OVER_RECOGNIZED", WARNING, pid,
                           f"Recognised {recognized:,.0f} EUR exceeds the approved commitment of {approved:,.0f} EUR.",
                           source="commitments.csv", cost_center=cc, amount_eur=recognized - approved))
        outstanding = max(approved - recognized, 0) if status == "open" else 0
        po_outstanding[pid] = outstanding
        by_cc[cc].open_commitments_eur += outstanding
        by_cc[cc].po_ids.append(pid)

    for d in ds.demands:
        if d.status in c.FUNDED and d.external_id not in demands_with_po and d.cost_center in by_cc:
            cost = demand_period_cost(ds, d)
            if cost is None:
                exc.append(Exc("FORECAST_INPUT_MISSING", CRITICAL, d.external_id,
                               "Approved demand has no usable cost estimate; it is missing from the forecast.",
                               source="demands.csv", cost_center=d.cost_center))
                continue
            by_cc[d.cost_center].approved_not_committed_eur += cost
            by_cc[d.cost_center].uncommitted_demand_ids.append(d.external_id)

    for cc, f in by_cc.items():
        if f.forecast_variance_eur > 0:
            exc.append(Exc("FORECAST_OVERRUN", WARNING, cc,
                           f"Forecast at completion {f.forecast_eac_eur:,.0f} EUR exceeds the period budget of {f.budget_period_eur:,.0f} EUR.",
                           source="forecast", cost_center=cc, amount_eur=f.forecast_variance_eur))
    for row in after_cutoff:
        exc.append(Exc("AFTER_CUTOFF", INFO, row["invoice_id"], f"Invoice dated {row['invoice_date']} is after the cutoff and not included.",
                       source="actuals.csv", cost_center=row["cost_center"], amount_eur=row["amount_eur"]))
    return FinanceResult(as_of, by_cc, dict(monthly_actual), monthly_budget, unmapped, excluded, after_cutoff, exc,
                         po_outstanding, dict(actual_by_demand), unmapped_ids, unreconciled)


def funding_gate(fin: FinanceResult, cost_center: str, extra_cost: float | None) -> tuple[bool | None, str]:
    """Would the cost centre stay within its period budget if `extra_cost` were added to the forecast?"""
    f = fin.by_cc.get(cost_center)
    if f is None:
        return None, "Unavailable: no budget is defined for this cost centre."
    if extra_cost is None:
        return None, "Unavailable: cost estimate missing."
    after = f.forecast_eac_eur + extra_cost
    ok = after <= f.budget_period_eur
    return ok, (f"Forecast {f.forecast_eac_eur:,.0f} + request {extra_cost:,.0f} = {after:,.0f} EUR against a budget of "
                f"{f.budget_period_eur:,.0f} EUR ({'within budget' if ok else f'overrun of {after - f.budget_period_eur:,.0f} EUR'}).")


def scenario(fin: FinanceResult, additions: dict[str, float]) -> dict[str, dict]:
    """What-if: forecast per cost centre if the given extra period costs were approved."""
    out = {}
    for cc, f in fin.by_cc.items():
        eac = f.forecast_eac_eur + additions.get(cc, 0)
        out[cc] = dict(forecast_eac_eur=eac, forecast_variance_eur=eac - f.budget_period_eur)
    return out
