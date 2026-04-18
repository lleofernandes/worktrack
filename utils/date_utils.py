"""
date_utils.py — Utilitários de data para o Work Track.
Queries de feriados delegadas ao HolidayRepository.
"""
from __future__ import annotations

from datetime import date, timedelta
from sqlalchemy.orm import Session


def get_weekdays_in_month(year: int, month: int) -> list[date]:
    """Todos os dias úteis (seg-sex) do mês, sem considerar feriados."""
    first = date(year, month, 1)
    if month == 12:
        last = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)

    return [
        first + timedelta(days=i)
        for i in range((last - first).days + 1)
        if (first + timedelta(days=i)).weekday() < 5
    ]


def get_business_days(year: int, month: int, session: Session) -> list[date]:
    """Dias úteis do mês descontando feriados via HolidayRepository."""
    from database.repository import HolidayRepository

    weekdays = get_weekdays_in_month(year, month)
    if not weekdays:
        return []

    holidays = HolidayRepository.get_in_range(session, weekdays[0], weekdays[-1])
    return [d for d in weekdays if d not in holidays]


def count_business_days(year: int, month: int, session: Session) -> int:
    return len(get_business_days(year, month, session))
