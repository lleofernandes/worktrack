"""
calculations.py — Cálculos puros de horas e receita.
Sem dependência de banco — testável de forma isolada.
"""
from __future__ import annotations

from datetime import time
from decimal import Decimal, ROUND_HALF_UP


def calc_worked_hours(
    start: time,
    end: time,
    break_minutes: int,
    extra_partner_minutes: int,
) -> Decimal:
    """
    Calcula horas trabalhadas:
        (end - start) - break_minutes + extra_partner_minutes
    Lança ValueError se resultado negativo ou horários incoerentes.
    """
    start_minutes = start.hour * 60 + start.minute
    end_minutes = end.hour * 60 + end.minute

    if end_minutes <= start_minutes:
        raise ValueError("end_time deve ser posterior a start_time.")

    net_minutes = end_minutes - start_minutes - break_minutes + extra_partner_minutes
    net_hours = Decimal(str(net_minutes)) / Decimal("60")
    # net_hours += Decimal(str(extra_partner_minutes))

    if net_hours < 0:
        raise ValueError(
            f"Total de horas calculado é negativo ({net_hours:.2f}h)."            
        )

    return net_hours.quantize(Decimal("0.0001"))


def calc_expected_hours(business_days: int, hours_per_day: int = 8) -> Decimal:
    """Horas esperadas no mês: business_days × hours_per_day."""
    return Decimal(str(business_days * hours_per_day))


def calc_productivity(worked: Decimal, expected: Decimal) -> Decimal:
    """Produtividade em % (ex: 95.50). Retorna 0 se expected = 0."""
    if expected == 0:
        return Decimal("0.00")
    return (worked / expected * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calc_remaining_hours(worked: Decimal, expected: Decimal) -> Decimal:
    """Horas restantes para atingir a meta (pode ser negativo se exceder)."""
    return (expected - worked).quantize(Decimal("0.0001"))


def calc_actual_revenue(worked_hours: Decimal, hour_rate: Decimal) -> Decimal:
    """Receita realizada: worked_hours × hour_rate."""
    return (worked_hours * hour_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calc_expected_revenue(expected_hours: Decimal, hour_rate: Decimal) -> Decimal:
    """Receita esperada: expected_hours × hour_rate."""
    return (expected_hours * hour_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calc_revenue_diff(actual: Decimal, expected: Decimal) -> Decimal:
    """Diferença entre receita realizada e esperada (positivo = acima da meta)."""
    return (actual - expected).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
