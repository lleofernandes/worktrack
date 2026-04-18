"""
repository.py — Repository Pattern do Work Track.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import extract
from sqlalchemy.orm import Session

from database.models import (
    Company, ContractRateHistory, Holiday,
    Invoice, Project, WorkLog,
)


class CompanyRepository:

    @staticmethod
    def get_all(session: Session, active_only: Optional[bool] = None) -> list[Company]:
        q = session.query(Company).order_by(Company.name)
        if active_only is True:
            q = q.filter(Company.end_date == None)   # noqa: E711
        elif active_only is False:
            q = q.filter(Company.end_date != None)   # noqa: E711
        return q.all()

    @staticmethod
    def get_by_id(session: Session, company_id: int) -> Optional[Company]:
        return session.get(Company, company_id)

    @staticmethod
    def get_by_cnpj(session: Session, cnpj: str) -> Optional[Company]:
        return session.query(Company).filter(Company.cnpj == cnpj).first()

    @staticmethod
    def create(session: Session, **kwargs) -> Company:
        company = Company(**kwargs)
        session.add(company)
        session.flush()
        return company

    @staticmethod
    def delete(session: Session, company_id: int) -> bool:
        obj = session.get(Company, company_id)
        if obj:
            session.delete(obj)
            return True
        return False


class ContractRateRepository:

    @staticmethod
    def get_active_rate(session: Session, company_id: int, ref_date: date) -> Optional[ContractRateHistory]:
        return (
            session.query(ContractRateHistory)
            .filter(
                ContractRateHistory.company_id == company_id,
                ContractRateHistory.start_date <= ref_date,
                (ContractRateHistory.end_date == None) | (ContractRateHistory.end_date >= ref_date),  # noqa: E711
            )
            .order_by(ContractRateHistory.start_date.desc())
            .first()
        )

    @staticmethod
    def get_all_by_company(session: Session, company_id: int) -> list[ContractRateHistory]:
        return (
            session.query(ContractRateHistory)
            .filter(ContractRateHistory.company_id == company_id)
            .order_by(ContractRateHistory.start_date.desc())
            .all()
        )

    @staticmethod
    def create(session: Session, company_id: int, hour_rate: Decimal,
               start_date: date, end_date: Optional[date] = None) -> ContractRateHistory:
        rate = ContractRateHistory(company_id=company_id, hour_rate=hour_rate,
                                   start_date=start_date, end_date=end_date)
        session.add(rate)
        session.flush()
        return rate

    @staticmethod
    def close_current_rate(session: Session, company_id: int, end_date: date) -> Optional[ContractRateHistory]:
        current = (
            session.query(ContractRateHistory)
            .filter(ContractRateHistory.company_id == company_id,
                    ContractRateHistory.end_date == None)  # noqa: E711
            .first()
        )
        if current:
            current.end_date = end_date
        return current


class ProjectRepository:

    @staticmethod
    def get_all_by_company(session: Session, company_id: int) -> list[Project]:
        return (
            session.query(Project)
            .filter(Project.company_id == company_id)
            .order_by(Project.name)
            .all()
        )

    @staticmethod
    def get_by_id(session: Session, project_id: int) -> Optional[Project]:
        return session.get(Project, project_id)

    @staticmethod
    def create(session: Session, company_id: int, name: str,
               description: Optional[str] = None) -> Project:
        project = Project(company_id=company_id, name=name, description=description)
        session.add(project)
        session.flush()
        return project

    @staticmethod
    def delete(session: Session, project_id: int) -> bool:
        obj = session.get(Project, project_id)
        if obj:
            session.delete(obj)
            return True
        return False


class WorkLogRepository:

    @staticmethod
    def create(session: Session, **kwargs) -> WorkLog:
        worklog = WorkLog(**kwargs)
        session.add(worklog)
        session.flush()
        return worklog

    @staticmethod
    def get_by_id(session: Session, worklog_id: int) -> Optional[WorkLog]:
        return session.get(WorkLog, worklog_id)

    @staticmethod
    def list_filtered(session: Session, company_id: Optional[int] = None,
                      month: Optional[int] = None, year: Optional[int] = None) -> list[WorkLog]:
        q = session.query(WorkLog).order_by(WorkLog.date.desc(), WorkLog.start_time.desc())
        if company_id:
            q = q.filter(WorkLog.company_id == company_id)
        if year:
            q = q.filter(extract("year", WorkLog.date) == year)
        if month:
            q = q.filter(extract("month", WorkLog.date) == month)
        return q.all()

    @staticmethod
    def list_by_company_month(session: Session, company_id: int,
                               year: int, month: int) -> list[WorkLog]:
        return (
            session.query(WorkLog)
            .filter(WorkLog.company_id == company_id,
                    extract("year", WorkLog.date) == year,
                    extract("month", WorkLog.date) == month)
            .order_by(WorkLog.date)
            .all()
        )

    @staticmethod
    def get_distinct_months_by_company(session: Session, company_id: int,
                                        year: int) -> list[int]:
        rows = (
            session.query(extract("month", WorkLog.date).label("m"))
            .filter(WorkLog.company_id == company_id,
                    extract("year", WorkLog.date) == year)
            .distinct()
            .all()
        )
        return sorted([int(r.m) for r in rows])

    @staticmethod
    def get_distinct_dates(session: Session, company_id: int,
                            year: int, month: int) -> set[date]:
        rows = (
            session.query(WorkLog.date)
            .filter(WorkLog.company_id == company_id,
                    extract("year", WorkLog.date) == year,
                    extract("month", WorkLog.date) == month)
            .distinct()
            .all()
        )
        return {r[0] for r in rows}

    @staticmethod
    def get_months_with_logs(session: Session, company_id: int,
                              year: int) -> set[int]:
        rows = (
            session.query(extract("month", WorkLog.date).label("m"))
            .filter(WorkLog.company_id == company_id,
                    extract("year", WorkLog.date) == year)
            .distinct()
            .all()
        )
        return {int(r.m) for r in rows}

    @staticmethod
    def delete(session: Session, worklog_id: int) -> bool:
        obj = session.get(WorkLog, worklog_id)
        if obj:
            session.delete(obj)
            return True
        return False


class InvoiceRepository:

    @staticmethod
    def create(session: Session, **kwargs) -> Invoice:
        invoice = Invoice(**kwargs)
        session.add(invoice)
        session.flush()
        return invoice

    @staticmethod
    def get_by_id(session: Session, invoice_id: int) -> Optional[Invoice]:
        return session.get(Invoice, invoice_id)

    @staticmethod
    def exists_by_number(session: Session, company_id: int,
                          invoice_number: str, exclude_id: Optional[int] = None) -> bool:
        q = session.query(Invoice).filter(Invoice.company_id == company_id,
                                           Invoice.invoice_number == invoice_number.strip())
        if exclude_id:
            q = q.filter(Invoice.id != exclude_id)
        return q.first() is not None

    @staticmethod
    def get_months_with_invoices(session: Session, company_id: int, year: int) -> set[int]:
        rows = (
            session.query(extract("month", Invoice.issue_date).label("m"))
            .filter(Invoice.company_id == company_id,
                    extract("year", Invoice.issue_date) == year)
            .distinct()
            .all()
        )
        return {int(r.m) for r in rows}

    @staticmethod
    def list_filtered(session: Session, company_id: Optional[int] = None,
                      month: Optional[int] = None, year: Optional[int] = None) -> list[Invoice]:
        q = session.query(Invoice).order_by(Invoice.issue_date.desc())
        if company_id:
            q = q.filter(Invoice.company_id == company_id)
        if year:
            q = q.filter(extract("year", Invoice.issue_date) == year)
        if month:
            q = q.filter(extract("month", Invoice.issue_date) == month)
        return q.all()

    @staticmethod
    def delete(session: Session, invoice_id: int) -> bool:
        obj = session.get(Invoice, invoice_id)
        if obj:
            session.delete(obj)
            return True
        return False


class HolidayRepository:

    @staticmethod
    def get_in_range(session: Session, start: date, end: date) -> set[date]:
        return {
            h.date
            for h in session.query(Holiday)
            .filter(Holiday.date >= start, Holiday.date <= end)
            .all()
        }

    @staticmethod
    def get_all(session: Session) -> list[Holiday]:
        return session.query(Holiday).order_by(Holiday.date).all()

    @staticmethod
    def create(session: Session, date_: date, description: str,
               is_national: bool = True, is_optional: bool = False,
               observation: Optional[str] = None) -> Holiday:
        holiday = Holiday(date=date_, description=description,
                          is_national=is_national, is_optional=is_optional,
                          observation=observation)
        session.add(holiday)
        session.flush()
        return holiday

    @staticmethod
    def delete(session: Session, holiday_id: int) -> bool:
        obj = session.get(Holiday, holiday_id)
        if obj:
            session.delete(obj)
            return True
        return False
