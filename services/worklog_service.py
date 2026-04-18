"""
worklog_service.py — Regras de negócio para apontamento de horas.
Toda lógica fica aqui; o form (UI) apenas chama este service.
"""
from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from config import MAX_HOURS_PER_DAY
from database.models import Company, ContractRateHistory, Project, WorkLog
from utils.calculations import calc_worked_hours


# ---------------------------------------------------------------------------
# Consultas auxiliares
# ---------------------------------------------------------------------------

def get_all_companies(session: Session) -> list[Company]:
    return session.query(Company).order_by(Company.name).all()


def get_projects_by_company(session: Session, company_id: int) -> list[Project]:
    return (
        session.query(Project)
        .filter(Project.company_id == company_id)
        .order_by(Project.name)
        .all()
    )


def get_active_rate(session: Session, company_id: int, ref_date: date) -> Optional[ContractRateHistory]:
    """
    Busca o hour_rate vigente para a empresa na data informada.
    Regra: start_date <= ref_date AND (end_date IS NULL OR end_date >= ref_date)
    """
    return (
        session.query(ContractRateHistory)
        .filter(
            ContractRateHistory.company_id == company_id,
            ContractRateHistory.start_date <= ref_date,
            (ContractRateHistory.end_date == None)  # noqa: E711
            | (ContractRateHistory.end_date >= ref_date),
        )
        .order_by(ContractRateHistory.start_date.desc())
        .first()
    )


# ---------------------------------------------------------------------------
# Validações
# ---------------------------------------------------------------------------

class WorkLogValidationError(Exception):
    pass


def validate_worklog(
    date_: date,
    start_time: time,
    end_time: time,
    break_minutes: int,
    extra_partner_hours: float,
) -> Decimal:
    """
    Valida os campos do apontamento e retorna as horas calculadas.
    Lança WorkLogValidationError em caso de inconsistência.
    """
    if start_time >= end_time:
        raise WorkLogValidationError("Horário de início deve ser anterior ao horário de término.")

    if break_minutes < 0:
        raise WorkLogValidationError("Intervalo não pode ser negativo.")

    if extra_partner_hours < 0:
        raise WorkLogValidationError("Horas extras de parceiro não podem ser negativas.")

    try:
        worked = calc_worked_hours(start_time, end_time, break_minutes, extra_partner_hours)
    except ValueError as e:
        raise WorkLogValidationError(str(e))

    if worked > MAX_HOURS_PER_DAY:
        raise WorkLogValidationError(
            f"Total de horas ({worked:.2f}h) excede o limite diário de {MAX_HOURS_PER_DAY}h."
        )

    return worked


# ---------------------------------------------------------------------------
# Criação
# ---------------------------------------------------------------------------

def create_worklog(
    session: Session,
    company_id: int,
    date_: date,
    start_time: time,
    end_time: time,
    break_minutes: int,
    extra_partner_hours: float,
    description: Optional[str],
    project_id: Optional[int],
) -> WorkLog:
    """
    Valida e persiste um novo apontamento de horas.
    Retorna o objeto WorkLog criado.
    """
    # Valida e calcula horas (lança WorkLogValidationError se inválido)
    validate_worklog(date_, start_time, end_time, break_minutes, extra_partner_hours)

    worklog = WorkLog(
        company_id=company_id,
        project_id=project_id or None,
        date=date_,
        start_time=start_time,
        end_time=end_time,
        break_minutes=break_minutes,
        extra_partner_hours=Decimal(str(extra_partner_hours)),
        description=description or None,
    )
    session.add(worklog)
    session.flush()  # Gera o ID sem fazer commit (commit é feito pelo get_session)
    return worklog


# ---------------------------------------------------------------------------
# Listagem
# ---------------------------------------------------------------------------

def list_worklogs(
    session: Session,
    company_id: Optional[int] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
) -> list[WorkLog]:
    """Lista apontamentos com filtros opcionais."""
    from sqlalchemy import extract

    q = session.query(WorkLog).order_by(WorkLog.date.desc(), WorkLog.start_time.desc())

    if company_id:
        q = q.filter(WorkLog.company_id == company_id)
    if year:
        q = q.filter(extract("year", WorkLog.date) == year)
    if month:
        q = q.filter(extract("month", WorkLog.date) == month)

    return q.all()


def delete_worklog(session: Session, worklog_id: int) -> bool:
    """Remove um apontamento. Retorna True se encontrado e deletado."""
    obj = session.get(WorkLog, worklog_id)
    if obj:
        session.delete(obj)
        return True
    return False
