"""
worklog_service.py — Regras de negócio para apontamento de horas.
Queries delegadas ao WorkLogRepository / ContractRateRepository.
"""
from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from core.config import MAX_HOURS_PER_DAY
from database.models import Company, ContractRateHistory, Project, WorkLog
from database.repository import (
    CompanyRepository,
    ContractRateRepository,
    ProjectRepository,
    WorkLogRepository,
)
from utils.calculations import calc_worked_hours


# ---------------------------------------------------------------------------
# Consultas auxiliares (facades para UI)
# ---------------------------------------------------------------------------

def get_all_companies(session: Session) -> list[Company]:
    return CompanyRepository.get_all(session)


def get_projects_by_company(session: Session, company_id: int) -> list[Project]:
    return ProjectRepository.get_all_by_company(session, company_id)


def get_active_rate(
    session: Session, company_id: int, ref_date: date
) -> Optional[ContractRateHistory]:
    return ContractRateRepository.get_active_rate(session, company_id, ref_date)


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
    Valida campos do apontamento e retorna as horas calculadas.
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
# CRUD
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
    validate_worklog(date_, start_time, end_time, break_minutes, extra_partner_hours)

    return WorkLogRepository.create(
        session,
        company_id=company_id,
        project_id=project_id or None,
        date=date_,
        start_time=start_time,
        end_time=end_time,
        break_minutes=break_minutes,
        extra_partner_hours=Decimal(str(extra_partner_hours)),
        description=description or None,
    )


def list_worklogs(
    session: Session,
    company_id: Optional[int] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
) -> list[WorkLog]:
    return WorkLogRepository.list_filtered(session, company_id, month, year)


def delete_worklog(session: Session, worklog_id: int) -> bool:
    return WorkLogRepository.delete(session, worklog_id)
