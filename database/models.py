"""
models.py — Mapeamento ORM de todas as entidades do Work Track.
"""
import enum
from datetime import datetime, date, time
from decimal import Decimal

from sqlalchemy import (
    Boolean, Date, DateTime, Enum, ForeignKey,
    Integer, Numeric, String, Text, Time,
    UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.connection import Base


class ContractType(str, enum.Enum):
    WORK_HOUR      = "WORK_HOUR"
    PROJECT        = "PROJECT"
    PROJECT_HOURS  = "PROJECT_HOURS"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    fantasy_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cnpj: Mapped[str | None] = mapped_column(String(18), nullable=True, unique=True)
    contract_type: Mapped[ContractType] = mapped_column(
        Enum(ContractType, name="contract_type_enum"),
        nullable=False,
        default=ContractType.WORK_HOUR,
    )
    contract_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # None = ativo
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    rate_history: Mapped[list["ContractRateHistory"]] = relationship(
        "ContractRateHistory", back_populates="company", cascade="all, delete-orphan"
    )
    projects: Mapped[list["Project"]] = relationship(
        "Project", back_populates="company", cascade="all, delete-orphan"
    )
    work_logs: Mapped[list["WorkLog"]] = relationship(
        "WorkLog", back_populates="company", cascade="all, delete-orphan"
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice", back_populates="company", cascade="all, delete-orphan"
    )

    @property
    def is_active(self) -> bool:
        return self.end_date is None

    def __repr__(self) -> str:
        return f"<Company id={self.id} name={self.name!r}>"


class ContractRateHistory(Base):
    __tablename__ = "contract_rates_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    hour_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    company: Mapped["Company"] = relationship("Company", back_populates="rate_history")

    def __repr__(self) -> str:
        return f"<ContractRateHistory company_id={self.company_id} rate={self.hour_rate}>"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    company: Mapped["Company"] = relationship("Company", back_populates="projects")
    work_logs: Mapped[list["WorkLog"]] = relationship("WorkLog", back_populates="project")

    def __repr__(self) -> str:
        return f"<Project id={self.id} name={self.name!r}>"


class WorkLog(Base):
    __tablename__ = "work_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extra_partner_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    company: Mapped["Company"] = relationship("Company", back_populates="work_logs")
    project: Mapped["Project | None"] = relationship("Project", back_populates="work_logs")

    def __repr__(self) -> str:
        return f"<WorkLog id={self.id} date={self.date}>"


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    origin: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("company_id", "invoice_number", name="uq_invoice_company"),
    )

    company: Mapped["Company"] = relationship("Company", back_populates="invoices")

    def __repr__(self) -> str:
        return f"<Invoice id={self.id} number={self.invoice_number!r}>"


class Holiday(Base):
    __tablename__ = "holidays"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    is_national: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_optional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # facultativo
    observation: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<Holiday date={self.date} description={self.description!r}>"
