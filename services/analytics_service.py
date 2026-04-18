"""
analytics_service.py — Camada analítica do Work Track.
Agrega dados de work_logs + contract_rates_history para gerar
as métricas do dashboard por empresa/mês/ano.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import extract
from sqlalchemy.orm import Session

from database.models import Company, WorkLog
from services.worklog_service import get_active_rate
from utils.calculations import (
    calc_actual_revenue,
    calc_expected_hours,
    calc_expected_revenue,
    calc_productivity,
    calc_remaining_hours,
    calc_revenue_diff,
    calc_worked_hours,
)
from utils.date_utils import count_business_days, get_worked_days


# ---------------------------------------------------------------------------
# Data classes de resultado
# ---------------------------------------------------------------------------

@dataclass
class MonthlyMetrics:
    """Métricas consolidadas de um mês para uma empresa."""
    company_id: int
    company_name: str
    year: int
    month: int

    business_days: int = 0
    worked_days: int = 0
    expected_hours: Decimal = Decimal("0")
    worked_hours: Decimal = Decimal("0")
    productivity: Decimal = Decimal("0")
    remaining_hours: Decimal = Decimal("0")

    hour_rate: Decimal = Decimal("0")
    expected_revenue: Decimal = Decimal("0")
    actual_revenue: Decimal = Decimal("0")
    revenue_diff: Decimal = Decimal("0")

    # Status derivado
    @property
    def is_on_track(self) -> bool:
        return self.productivity >= Decimal("100")

    @property
    def productivity_color(self) -> str:
        return "green" if self.is_on_track else "red"


@dataclass
class DailyRevenue:
    """Receita e horas de um dia específico (para gráfico de linha)."""
    date: date
    worked_hours: Decimal
    revenue: Decimal


@dataclass
class CompanyMonthSummary:
    """Resumo de horas por empresa em um mês (para gráfico de barras)."""
    company_name: str
    worked_hours: Decimal
    actual_revenue: Decimal


# ---------------------------------------------------------------------------
# Funções principais
# ---------------------------------------------------------------------------

def get_monthly_metrics(
    session: Session,
    company_id: int,
    year: int,
    month: int,
) -> MonthlyMetrics:
    """
    Calcula todas as métricas mensais para uma empresa:
    business_days, worked_days, expected/worked hours,
    productivity, remaining_hours, revenues e revenue_diff.

    hour_rate: usa a taxa vigente no último dia do mês
    (ou no dia atual se o mês for o corrente).
    """
    company = session.get(Company, company_id)
    metrics = MonthlyMetrics(
        company_id=company_id,
        company_name=company.name if company else f"Empresa #{company_id}",
        year=year,
        month=month,
    )

    # ── Dias úteis e dias trabalhados ────────────────────────────────────
    metrics.business_days = count_business_days(year, month, session)
    metrics.worked_days = get_worked_days(session, company_id, year, month)
    metrics.expected_hours = calc_expected_hours(metrics.business_days)

    # ── Worklogs do mês ──────────────────────────────────────────────────
    worklogs: list[WorkLog] = (
        session.query(WorkLog)
        .filter(
            WorkLog.company_id == company_id,
            extract("year", WorkLog.date) == year,
            extract("month", WorkLog.date) == month,
        )
        .all()
    )

    # ── Horas e receita realizada (rate por data) ────────────────────────
    total_worked = Decimal("0")
    total_actual_revenue = Decimal("0")

    for wl in worklogs:
        try:
            hours = calc_worked_hours(
                wl.start_time,
                wl.end_time,
                wl.break_minutes,
                float(wl.extra_partner_hours),
            )
        except ValueError:
            hours = Decimal("0")

        rate_obj = get_active_rate(session, company_id, wl.date)
        rate = rate_obj.hour_rate if rate_obj else Decimal("0")

        total_worked += hours
        total_actual_revenue += calc_actual_revenue(hours, rate)

    metrics.worked_hours = total_worked.quantize(Decimal("0.0001"))
    metrics.actual_revenue = total_actual_revenue.quantize(Decimal("0.01"))

    # ── Taxa vigente para receita esperada ───────────────────────────────
    today = date.today()
    ref_date = (
        today
        if (year == today.year and month == today.month)
        else date(year, month, 1)
    )
    rate_obj = get_active_rate(session, company_id, ref_date)
    metrics.hour_rate = rate_obj.hour_rate if rate_obj else Decimal("0")

    # ── Métricas derivadas ───────────────────────────────────────────────
    metrics.expected_revenue = calc_expected_revenue(metrics.expected_hours, metrics.hour_rate)
    metrics.productivity = calc_productivity(metrics.worked_hours, metrics.expected_hours)
    metrics.remaining_hours = calc_remaining_hours(metrics.worked_hours, metrics.expected_hours)
    metrics.revenue_diff = calc_revenue_diff(metrics.actual_revenue, metrics.expected_revenue)

    return metrics


def get_all_companies_metrics(
    session: Session,
    year: int,
    month: int,
) -> list[MonthlyMetrics]:
    """Retorna métricas mensais para TODAS as empresas cadastradas."""
    from database.models import Company

    companies = session.query(Company).order_by(Company.name).all()
    return [get_monthly_metrics(session, c.id, year, month) for c in companies]


def get_daily_revenue(
    session: Session,
    company_id: int,
    year: int,
    month: int,
) -> list[DailyRevenue]:
    """
    Receita e horas por dia do mês para uma empresa.
    Usado no gráfico de linha do dashboard.
    """
    worklogs: list[WorkLog] = (
        session.query(WorkLog)
        .filter(
            WorkLog.company_id == company_id,
            extract("year", WorkLog.date) == year,
            extract("month", WorkLog.date) == month,
        )
        .order_by(WorkLog.date)
        .all()
    )

    # Agrupa por data
    daily: dict[date, tuple[Decimal, Decimal]] = {}
    for wl in worklogs:
        try:
            hours = calc_worked_hours(
                wl.start_time, wl.end_time,
                wl.break_minutes, float(wl.extra_partner_hours)
            )
        except ValueError:
            hours = Decimal("0")

        rate_obj = get_active_rate(session, company_id, wl.date)
        rate = rate_obj.hour_rate if rate_obj else Decimal("0")
        revenue = calc_actual_revenue(hours, rate)

        if wl.date in daily:
            prev_h, prev_r = daily[wl.date]
            daily[wl.date] = (prev_h + hours, prev_r + revenue)
        else:
            daily[wl.date] = (hours, revenue)

    return [
        DailyRevenue(date=d, worked_hours=h, revenue=r)
        for d, (h, r) in sorted(daily.items())
    ]


def get_monthly_evolution(
    session: Session,
    company_id: int,
    year: int,
    months: int = 12,
) -> list[MonthlyMetrics]:
    """
    Evolução mensal dos últimos N meses até o mês atual.
    Usado no gráfico de linha mensal do dashboard.
    """
    today = date.today()
    results = []

    for i in range(months - 1, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        if y < year:
            continue
        results.append(get_monthly_metrics(session, company_id, y, m))

    return results


def get_company_bar_data(
    session: Session,
    year: int,
    month: int,
) -> list[CompanyMonthSummary]:
    """
    Horas e receita por empresa no mês — para o gráfico de barras.
    """
    metrics_list = get_all_companies_metrics(session, year, month)
    return [
        CompanyMonthSummary(
            company_name=m.company_name,
            worked_hours=m.worked_hours,
            actual_revenue=m.actual_revenue,
        )
        for m in metrics_list
        if m.worked_hours > 0
    ]
