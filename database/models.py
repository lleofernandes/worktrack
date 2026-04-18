"""
models.py — Mapeamento ORM de todas as entidades do Work Track.
Sem SQL hardcoded. Compatível com SQLite / PostgreSQL / SQL Server / MySQL.
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


# ---------------------------------------------------------------------------
# ENUM — Tipo de contrato
# ---------------------------------------------------------------------------

class ContractType(str, enum.Enum):
    WORK_HOUR      = "WORK_HOUR"       # Hora a hora
    PROJECT        = "PROJECT"         # Projeto fechado (valor fixo)
    PROJECT_HOURS  = "PROJECT_HOURS"   # Projeto com controle de horas


# ---------------------------------------------------------------------------
# 3.1 companies
# ---------------------------------------------------------------------------

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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relacionamentos
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

    def __repr__(self) -> str:
        return f"<Company id={self.id} name={self.name!r}>"


# ---------------------------------------------------------------------------
# 3.2 contract_rates_history
# ---------------------------------------------------------------------------

class ContractRateHistory(Base):
    __tablename__ = "contract_rates_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    hour_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # None = vigente

    company: Mapped["Company"] = relationship("Company", back_populates="rate_history")

    def __repr__(self) -> str:
        return (
            f"<ContractRateHistory company_id={self.company_id} "
            f"rate={self.hour_rate} from={self.start_date}>"
        )


# ---------------------------------------------------------------------------
# 3.3 projects
# ---------------------------------------------------------------------------

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    company: Mapped["Company"] = relationship("Company", back_populates="projects")
    work_logs: Mapped[list["WorkLog"]] = relationship(
        "WorkLog", back_populates="project"
    )

    def __repr__(self) -> str:
        return f"<Project id={self.id} name={self.name!r}>"


# ---------------------------------------------------------------------------
# 3.4 work_logs
# ---------------------------------------------------------------------------

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
    extra_partner_hours: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    company: Mapped["Company"] = relationship("Company", back_populates="work_logs")
    project: Mapped["Project | None"] = relationship("Project", back_populates="work_logs")

    def __repr__(self) -> str:
        return f"<WorkLog id={self.id} date={self.date} company_id={self.company_id}>"


# ---------------------------------------------------------------------------
# 3.5 invoices
# ---------------------------------------------------------------------------

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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("company_id", "invoice_number", name="uq_invoice_company"),
    )

    company: Mapped["Company"] = relationship("Company", back_populates="invoices")

    def __repr__(self) -> str:
        return f"<Invoice id={self.id} number={self.invoice_number!r} company_id={self.company_id}>"


# ---------------------------------------------------------------------------
# 3.6 holidays
# ---------------------------------------------------------------------------

class Holiday(Base):
    __tablename__ = "holidays"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    is_national: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<Holiday date={self.date} description={self.description!r}>"
