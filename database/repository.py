"""
repository.py — Repository Pattern (Company / Contract / Rate / WorkLog / Invoice / Holiday)
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import extract
from sqlalchemy.orm import Session, joinedload

from database.models import (
    Company, Contract, ContractRateHistory,
    Holiday, Invoice, Project, WorkLog,
)


# ---------------------------------------------------------------------------
class CompanyRepository:

    @staticmethod
    def get_all(session: Session) -> list[Company]:
        return session.query(Company).order_by(Company.name).all()

    @staticmethod
    def get_by_id(session: Session, company_id: int) -> Optional[Company]:
        return session.get(Company, company_id)

    @staticmethod
    def get_by_cnpj(session: Session, cnpj: str) -> Optional[Company]:
        return session.query(Company).filter(Company.cnpj == cnpj).first()

    @staticmethod
    def create(session: Session, **kwargs) -> Company:
        obj = Company(**kwargs)
        session.add(obj)
        session.flush()
        return obj

    @staticmethod
    def delete(session: Session, company_id: int) -> bool:
        obj = session.get(Company, company_id)
        if obj:
            session.delete(obj)
            return True
        return False


# ---------------------------------------------------------------------------
class ContractRepository:

    @staticmethod
    def get_all(session: Session, active_only: Optional[bool] = None) -> list[Contract]:
        q = (session.query(Contract)
             .options(joinedload(Contract.company))
             .order_by(Contract.start_date.desc()))
        if active_only is True:
            q = q.filter(
                (Contract.end_date == None) | (Contract.end_date >= date.today())  # noqa
            )
        elif active_only is False:
            q = q.filter(Contract.end_date < date.today())
        return q.all()

    @staticmethod
    def get_by_id(session: Session, contract_id: int) -> Optional[Contract]:
        return (session.query(Contract)
                .options(joinedload(Contract.company),
                         joinedload(Contract.rate_history))
                .filter(Contract.id == contract_id)
                .first())

    @staticmethod
    def get_by_company(session: Session, company_id: int,
                        active_only: Optional[bool] = None) -> list[Contract]:
        q = (session.query(Contract)
             .filter(Contract.company_id == company_id)
             .order_by(Contract.start_date.desc()))
        if active_only is True:
            q = q.filter(
                (Contract.end_date == None) | (Contract.end_date >= date.today())  # noqa
            )
        return q.all()

    @staticmethod
    def create(session: Session, **kwargs) -> Contract:
        obj = Contract(**kwargs)
        session.add(obj)
        session.flush()
        return obj

    @staticmethod
    def delete(session: Session, contract_id: int) -> bool:
        obj = session.get(Contract, contract_id)
        if obj:
            session.delete(obj)
            return True
        return False


# ---------------------------------------------------------------------------
class ContractRateRepository:

    @staticmethod
    def get_active_rate(session: Session, contract_id: int,
                         ref_date: date) -> Optional[ContractRateHistory]:
        return (
            session.query(ContractRateHistory)
            .filter(
                ContractRateHistory.contract_id == contract_id,
                ContractRateHistory.start_date <= ref_date,
                (ContractRateHistory.end_date == None) |  # noqa
                (ContractRateHistory.end_date >= ref_date),
            )
            .order_by(ContractRateHistory.start_date.desc())
            .first()
        )

    @staticmethod
    def get_all_by_contract(session: Session, contract_id: int) -> list[ContractRateHistory]:
        return (
            session.query(ContractRateHistory)
            .filter(ContractRateHistory.contract_id == contract_id)
            .order_by(ContractRateHistory.start_date.desc())
            .all()
        )

    @staticmethod
    def create(session: Session, contract_id: int, hour_rate: Decimal,
               start_date: date, end_date: Optional[date] = None) -> ContractRateHistory:
        rate = ContractRateHistory(contract_id=contract_id, hour_rate=hour_rate,
                                   start_date=start_date, end_date=end_date)
        session.add(rate)
        session.flush()
        return rate

    @staticmethod
    def close_current(session: Session, contract_id: int,
                       end_date: date) -> Optional[ContractRateHistory]:
        current = (
            session.query(ContractRateHistory)
            .filter(ContractRateHistory.contract_id == contract_id,
                    ContractRateHistory.end_date == None)  # noqa
            .first()
        )
        if current:
            current.end_date = end_date
        return current


# ---------------------------------------------------------------------------
class ProjectRepository:

    @staticmethod
    def get_all_by_contract(session: Session, contract_id: int) -> list[Project]:
        return (session.query(Project)
                .filter(Project.contract_id == contract_id)
                .order_by(Project.name).all())

    @staticmethod
    def create(session: Session, contract_id: int, name: str,
               description: Optional[str] = None) -> Project:
        obj = Project(contract_id=contract_id, name=name, description=description)
        session.add(obj)
        session.flush()
        return obj

    @staticmethod
    def delete(session: Session, project_id: int) -> bool:
        obj = session.get(Project, project_id)
        if obj:
            session.delete(obj)
            return True
        return False


# ---------------------------------------------------------------------------
class WorkLogRepository:

    @staticmethod
    def create(session: Session, **kwargs) -> WorkLog:
        obj = WorkLog(**kwargs)
        session.add(obj)
        session.flush()
        return obj

    @staticmethod
    def get_by_id(session: Session, wl_id: int) -> Optional[WorkLog]:
        return session.get(WorkLog, wl_id)

    @staticmethod
    def list_filtered(session: Session, contract_id: Optional[int] = None,
                       company_id: Optional[int] = None,
                       month: Optional[int] = None,
                       year: Optional[int] = None) -> list[WorkLog]:
        q = (session.query(WorkLog)
             .options(joinedload(WorkLog.contract).joinedload(Contract.company))
             .order_by(WorkLog.date.desc(), WorkLog.start_time.desc()))
        if contract_id:
            q = q.filter(WorkLog.contract_id == contract_id)
        elif company_id:
            contract_ids = [
                c.id for c in session.query(Contract.id)
                .filter(Contract.company_id == company_id).all()
            ]
            q = q.filter(WorkLog.contract_id.in_(contract_ids))
        if year:
            q = q.filter(extract("year", WorkLog.date) == year)
        if month:
            q = q.filter(extract("month", WorkLog.date) == month)
        return q.all()

    @staticmethod
    def list_by_contract_month(session: Session, contract_id: int,
                                year: int, month: int) -> list[WorkLog]:
        return (session.query(WorkLog)
                .filter(WorkLog.contract_id == contract_id,
                        extract("year",  WorkLog.date) == year,
                        extract("month", WorkLog.date) == month)
                .order_by(WorkLog.date).all())

    @staticmethod
    def get_months_with_logs(session: Session, contract_id: int, year: int) -> set[int]:
        rows = (session.query(extract("month", WorkLog.date).label("m"))
                .filter(WorkLog.contract_id == contract_id,
                        extract("year", WorkLog.date) == year)
                .distinct().all())
        return {int(r.m) for r in rows}

    @staticmethod
    def delete(session: Session, wl_id: int) -> bool:
        obj = session.get(WorkLog, wl_id)
        if obj:
            session.delete(obj)
            return True
        return False


# ---------------------------------------------------------------------------
class InvoiceRepository:

    @staticmethod
    def create(session: Session, **kwargs) -> Invoice:
        obj = Invoice(**kwargs)
        session.add(obj)
        session.flush()
        return obj

    @staticmethod
    def exists_by_number(session: Session, contract_id: int,
                          invoice_number: str,
                          exclude_id: Optional[int] = None) -> bool:
        q = (session.query(Invoice)
             .filter(Invoice.contract_id == contract_id,
                     Invoice.invoice_number == invoice_number.strip()))
        if exclude_id:
            q = q.filter(Invoice.id != exclude_id)
        return q.first() is not None

    @staticmethod
    def get_months_with_invoices(session: Session, contract_id: int, year: int) -> set[int]:
        rows = (session.query(extract("month", Invoice.issue_date).label("m"))
                .filter(Invoice.contract_id == contract_id,
                        extract("year", Invoice.issue_date) == year)
                .distinct().all())
        return {int(r.m) for r in rows}

    @staticmethod
    def list_filtered(session: Session, contract_id: Optional[int] = None,
                       company_id: Optional[int] = None,
                       month: Optional[int] = None,
                       year: Optional[int] = None) -> list[Invoice]:
        q = (session.query(Invoice)
             .options(joinedload(Invoice.contract).joinedload(Contract.company))
             .order_by(Invoice.issue_date.desc()))
        if contract_id:
            q = q.filter(Invoice.contract_id == contract_id)
        elif company_id:
            contract_ids = [
                c.id for c in session.query(Contract.id)
                .filter(Contract.company_id == company_id).all()
            ]
            q = q.filter(Invoice.contract_id.in_(contract_ids))
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


# ---------------------------------------------------------------------------
class HolidayRepository:

    @staticmethod
    def get_in_range(session: Session, start: date, end: date) -> set[date]:
        return {h.date for h in
                session.query(Holiday)
                .filter(Holiday.date >= start, Holiday.date <= end).all()}

    @staticmethod
    def get_all(session: Session) -> list[Holiday]:
        return session.query(Holiday).order_by(Holiday.date).all()

    @staticmethod
    def create(session: Session, date_: date, description: str,
               is_national: bool = True, is_optional: bool = False,
               observation: Optional[str] = None) -> Holiday:
        obj = Holiday(date=date_, description=description,
                      is_national=is_national, is_optional=is_optional,
                      observation=observation)
        session.add(obj)
        session.flush()
        return obj

    @staticmethod
    def delete(session: Session, holiday_id: int) -> bool:
        obj = session.get(Holiday, holiday_id)
        if obj:
            session.delete(obj)
            return True
        return False
