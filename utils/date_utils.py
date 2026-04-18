"""
date_utils.py — Utilitários de data para o Work Track.
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


def get_holidays_in_range(session: Session, start: date, end: date) -> set[date]:
    """Retorna conjunto de datas de feriados no intervalo (inclusivo)."""
    from database.models import Holiday

    return {
        h.date
        for h in session.query(Holiday)
        .filter(Holiday.date >= start, Holiday.date <= end)
        .all()
    }


def get_business_days(year: int, month: int, session: Session) -> list[date]:
    """Dias úteis do mês descontando feriados cadastrados."""
    weekdays = get_weekdays_in_month(year, month)
    if not weekdays:
        return []
    holidays = get_holidays_in_range(session, weekdays[0], weekdays[-1])
    return [d for d in weekdays if d not in holidays]


def count_business_days(year: int, month: int, session: Session) -> int:
    return len(get_business_days(year, month, session))


def get_worked_days(
    session: Session,
    company_id: int,
    year: int,
    month: int,
) -> int:
    """
    Conta quantos dias distintos foram apontados para a empresa no mês.
    Exclui fins de semana e feriados do cômputo.
    """
    from sqlalchemy import extract, func
    from database.models import WorkLog

    business_days = set(get_business_days(year, month, session))

    logged_dates = {
        row[0]
        for row in session.query(WorkLog.date)
        .filter(
            WorkLog.company_id == company_id,
            extract("year", WorkLog.date) == year,
            extract("month", WorkLog.date) == month,
        )
        .distinct()
        .all()
    }
    return len(logged_dates & business_days)
