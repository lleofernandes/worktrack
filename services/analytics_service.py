"""
analytics_service.py — Cálculos analíticos por contrato/mês.
"""
from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from database.models import ContractType
from database.repository import (
    ContractRateRepository, HolidayRepository, WorkLogRepository,
)
from utils.calculations import (
    calc_actual_revenue, calc_expected_hours, calc_expected_revenue,
    calc_productivity, calc_remaining_hours, calc_worked_hours,
)


@dataclass
class MonthlyMetrics:
    contract_id: int
    company_name: str
    contract_label: str
    year: int
    month: int
    business_days: int       = 0
    worked_days: int         = 0
    expected_hours: Decimal  = field(default_factory=lambda: Decimal("0"))
    worked_hours: Decimal    = field(default_factory=lambda: Decimal("0"))
    productivity: Decimal    = field(default_factory=lambda: Decimal("0"))
    remaining_hours: Decimal = field(default_factory=lambda: Decimal("0"))
    expected_revenue: Decimal = field(default_factory=lambda: Decimal("0"))
    actual_revenue: Decimal   = field(default_factory=lambda: Decimal("0"))
    revenue_diff: Decimal     = field(default_factory=lambda: Decimal("0"))


@dataclass
class CompanyBarData:
    company_name: str
    worked_hours: Decimal
    actual_revenue: Decimal


@dataclass
class DailyRevenue:
    date: date
    worked_hours: Decimal
    revenue: Decimal


@dataclass
class MonthlyEvolution:
    year: int
    month: int
    worked_hours: Decimal
    expected_hours: Decimal
    actual_revenue: Decimal
    expected_revenue: Decimal
    productivity: Decimal


def _extract_hours(wl) -> Decimal:
    if wl.total_hours is not None:
        return Decimal(str(wl.total_hours))
    if wl.start_time and wl.end_time:
        try:
            return calc_worked_hours(
                wl.start_time, wl.end_time,
                wl.break_minutes,
                wl.extra_partner_minutes,
            )
        except ValueError:
            pass
    return Decimal("0")


def _calc_project_hours_revenue(
    contract,
    total_worked: Decimal,
) -> tuple[Decimal, Decimal]:

    if not contract.monthly_fee:       
        return Decimal("0"), Decimal("0")
    monthly_fee      = contract.monthly_fee      or Decimal("0")
    contracted_hours = contract.contracted_hours or Decimal("0")
    overage_rate     = contract.overage_rate     or Decimal("0")

    expected = monthly_fee

    if total_worked <= contracted_hours:
        actual = monthly_fee
    else:
        overage_hours = total_worked - contracted_hours
        actual = monthly_fee + (overage_hours * overage_rate)

    return expected.quantize(Decimal("0.01")), actual.quantize(Decimal("0.01"))


def get_monthly_metrics(
    session, contract_id: int, year: int, month: int
) -> MonthlyMetrics:
    from database.repository import ContractRepository
    contract = ContractRepository.get_by_id(session, contract_id)
    company_name   = contract.company.name if contract and contract.company else f"Contrato #{contract_id}"
    contract_label = f"{contract.contract_number or 'S/N'}" if contract else "—"

    metrics = MonthlyMetrics(
        contract_id=contract_id,
        company_name=company_name,
        contract_label=contract_label,
        year=year, month=month,
    )

    first_day = date(year, month, 1)
    last_day  = date(year, month, monthrange(year, month)[1])
    holidays  = HolidayRepository.get_in_range(session, first_day, last_day)

    biz_days = sum(
        1 for d in range(1, monthrange(year, month)[1] + 1)
        if date(year, month, d).weekday() < 5
        and date(year, month, d) not in holidays
    )
    metrics.business_days = biz_days

    contract_type = contract.contract_type if contract else ContractType.WORK_HOUR

    # ── Horas esperadas ──────────────────────────────────────────────────
    if contract_type == ContractType.PROJECT_HOURS:
        # Meta = horas contratadas no pacote (não dias úteis × 8h)
        metrics.expected_hours = contract.contracted_hours or Decimal("0")
    else:
        # WORK_HOUR e PROJECT: dias úteis × 8h
        metrics.expected_hours = calc_expected_hours(biz_days)

    # ── Work logs ────────────────────────────────────────────────────────
    worklogs = WorkLogRepository.list_by_contract_month(session, contract_id, year, month)
    metrics.worked_days = len({wl.date for wl in worklogs})

    total_worked   = Decimal("0")
    total_actual_r = Decimal("0")

    for wl in worklogs:
        h = _extract_hours(wl)
        total_worked += h

        # Receita por linha só faz sentido para WORK_HOUR (taxa × hora)
        # Para PROJECT_HOURS calculamos depois do total
        if contract_type == ContractType.WORK_HOUR:
            r = ContractRateRepository.get_active_rate(session, contract_id, wl.date)
            total_actual_r += calc_actual_revenue(h, r.hour_rate if r else Decimal("0"))

    metrics.worked_hours = total_worked.quantize(Decimal("0.0001"))

    # ── Receita esperada / realizada por tipo ────────────────────────────
    if contract_type == ContractType.PROJECT_HOURS:
        exp_rev, act_rev = _calc_project_hours_revenue(contract, metrics.worked_hours)
        metrics.expected_revenue = exp_rev
        metrics.actual_revenue   = act_rev

    elif contract_type == ContractType.WORK_HOUR:
        rate_obj = ContractRateRepository.get_active_rate(session, contract_id, first_day)
        rate     = rate_obj.hour_rate if rate_obj else Decimal("0")
        metrics.expected_revenue = calc_expected_revenue(metrics.expected_hours, rate)
        metrics.actual_revenue   = total_actual_r.quantize(Decimal("0.01"))

    else:
        # PROJECT fechado: sem cálculo automático (controlado via NF)
        metrics.expected_revenue = Decimal("0")
        metrics.actual_revenue   = Decimal("0")

    metrics.productivity    = calc_productivity(metrics.worked_hours, metrics.expected_hours)
    metrics.remaining_hours = calc_remaining_hours(metrics.worked_hours, metrics.expected_hours)
    metrics.revenue_diff    = (metrics.actual_revenue - metrics.expected_revenue).quantize(Decimal("0.01"))

    
    # # ── DEBUG — remover depois ───────────────────────────────────────────
    # import sys
    # print(
    #     f"[DEBUG] contract_id={contract_id}"
    #     f" | type={contract_type.value}"
    #     f" | monthly_fee={getattr(contract, 'monthly_fee', 'N/A')}"
    #     f" | expected_hours={metrics.expected_hours}"
    #     f" | worked_hours={metrics.worked_hours}"
    #     f" | expected_rev={metrics.expected_revenue}"
    #     f" | actual_rev={metrics.actual_revenue}",
    #     file=sys.stderr,
    #     flush=True,
    # )
    # # ────────────────────────────────────────────────────────────────────


    return metrics


def get_all_contracts_metrics(session, year: int, month: int,
                               active_only=None) -> list[MonthlyMetrics]:
    from database.repository import ContractRepository
    contracts = ContractRepository.get_all(session, active_only=active_only)
    return [get_monthly_metrics(session, c.id, year, month) for c in contracts]


def get_company_bar_data(session, year: int, month: int) -> list[CompanyBarData]:
    from database.repository import ContractRepository
    contracts = ContractRepository.get_all(session)
    result = []
    for ct in contracts:
        m = get_monthly_metrics(session, ct.id, year, month)
        if m.worked_hours > 0:
            label = ct.company.name if ct.company else f"Contrato #{ct.id}"
            result.append(CompanyBarData(
                company_name=label,
                worked_hours=m.worked_hours,
                actual_revenue=m.actual_revenue,
            ))
    return result


def get_daily_revenue(session, contract_id: int, year: int, month: int) -> list[DailyRevenue]:
    from database.repository import ContractRepository
    contract = ContractRepository.get_by_id(session, contract_id)
    contract_type = contract.contract_type if contract else ContractType.WORK_HOUR

    worklogs = WorkLogRepository.list_by_contract_month(session, contract_id, year, month)
    daily: dict[date, tuple[Decimal, Decimal]] = {}

    for wl in worklogs:
        h = _extract_hours(wl)

        if contract_type == ContractType.WORK_HOUR:
            r = ContractRateRepository.get_active_rate(session, contract_id, wl.date)
            rev = calc_actual_revenue(h, r.hour_rate if r else Decimal("0"))
        else:
            # PROJECT_HOURS: distribui receita proporcional ao dia (aproximação)
            rev = Decimal("0")

        if wl.date in daily:
            ph, pr = daily[wl.date]
            daily[wl.date] = (ph + h, pr + rev)
        else:
            daily[wl.date] = (h, rev)

    # Para PROJECT_HOURS: distribui monthly_fee proporcionalmente às horas do dia
    if contract_type == ContractType.PROJECT_HOURS and daily:
        total_h = sum(h for h, _ in daily.values())
        if total_h > 0:
            _, act_rev = _calc_project_hours_revenue(contract, total_h)
            daily = {
                d: (h, (h / total_h * act_rev).quantize(Decimal("0.01")))
                for d, (h, _) in daily.items()
            }

    return [DailyRevenue(date=d, worked_hours=h, revenue=r)
            for d, (h, r) in sorted(daily.items())]


def get_monthly_evolution(session, contract_id: int,
                           year: int, months: int = 12) -> list[MonthlyEvolution]:
    result = []
    for m in range(1, min(months, 12) + 1):
        if date(year, m, 1) > date.today():
            break
        mt = get_monthly_metrics(session, contract_id, year, m)
        result.append(MonthlyEvolution(
            year=year, month=m,
            worked_hours=mt.worked_hours,
            expected_hours=mt.expected_hours,
            actual_revenue=mt.actual_revenue,
            expected_revenue=mt.expected_revenue,
            productivity=mt.productivity,
        ))
    return result
