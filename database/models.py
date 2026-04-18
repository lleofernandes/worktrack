"""
models.py — Mapeamento ORM completo do Work Track.
Arquitetura: Company → Contract → ContractRateHistory
             WorkLog e Invoice referenciam Contract (+ Company por conveniência)
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
    WORK_HOUR     = "WORK_HOUR"
    PROJECT       = "PROJECT"
    PROJECT_HOURS = "PROJECT_HOURS"


# ---------------------------------------------------------------------------
# Company — dados cadastrais da empresa (sem contrato)
# ---------------------------------------------------------------------------
class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int]          = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str]        = mapped_column(String(255), nullable=False)
    fantasy_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cnpj: Mapped[str | None] = mapped_column(String(18),  nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    contracts: Mapped[list["Contract"]] = relationship(
        "Contract", back_populates="company", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Company id={self.id} name={self.name!r}>"


# ---------------------------------------------------------------------------
# Contract — vínculo contratual entre empresa e prestador
# ---------------------------------------------------------------------------
class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    contract_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contract_type: Mapped[ContractType] = mapped_column(
        Enum(ContractType, name="contract_type_enum"),
        nullable=False,
        default=ContractType.WORK_HOUR,
    )
    start_date: Mapped[date]       = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None]  = mapped_column(Date, nullable=True)   # None = vigente
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime]   = mapped_column(DateTime, nullable=False, server_default=func.now())

    company: Mapped["Company"] = relationship("Company", back_populates="contracts")
    rate_history: Mapped[list["ContractRateHistory"]] = relationship(
        "ContractRateHistory", back_populates="contract", cascade="all, delete-orphan"
    )
    work_logs: Mapped[list["WorkLog"]] = relationship(
        "WorkLog", back_populates="contract", cascade="all, delete-orphan"
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice", back_populates="contract", cascade="all, delete-orphan"
    )

    @property
    def is_active(self) -> bool:
        return self.end_date is None or self.end_date >= date.today()

    @property
    def current_rate(self) -> "ContractRateHistory | None":
        today = date.today()
        actives = [
            r for r in self.rate_history
            if r.start_date <= today and (r.end_date is None or r.end_date >= today)
        ]
        return sorted(actives, key=lambda r: r.start_date, reverse=True)[0] if actives else None

    def __repr__(self) -> str:
        return f"<Contract id={self.id} company_id={self.company_id} type={self.contract_type}>"


# ---------------------------------------------------------------------------
# ContractRateHistory — histórico de taxas por contrato
# ---------------------------------------------------------------------------
class ContractRateHistory(Base):
    __tablename__ = "contract_rates_history"

    id: Mapped[int]         = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    hour_rate: Mapped[Decimal]     = mapped_column(Numeric(12, 2), nullable=False)
    start_date: Mapped[date]       = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None]  = mapped_column(Date, nullable=True)

    contract: Mapped["Contract"] = relationship("Contract", back_populates="rate_history")

    def __repr__(self) -> str:
        return f"<ContractRateHistory contract_id={self.contract_id} rate={self.hour_rate}>"


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------
class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int]         = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str]              = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime]   = mapped_column(DateTime, nullable=False, server_default=func.now())

    contract: Mapped["Contract"] = relationship("Contract")
    work_logs: Mapped[list["WorkLog"]] = relationship("WorkLog", back_populates="project")

    def __repr__(self) -> str:
        return f"<Project id={self.id} name={self.name!r}>"


# ---------------------------------------------------------------------------
# WorkLog
# ---------------------------------------------------------------------------
class WorkLog(Base):
    __tablename__ = "work_logs"

    id: Mapped[int]          = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    date: Mapped[date]             = mapped_column(Date, nullable=False)
    # WORK_HOUR
    start_time: Mapped[time | None]  = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None]    = mapped_column(Time, nullable=True)
    break_minutes: Mapped[int]       = mapped_column(Integer, nullable=False, default=0)
    extra_partner_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    # PROJECT_HOURS
    total_hours: Mapped[Decimal | None]  = mapped_column(Numeric(6, 2), nullable=True)
    # PROJECT
    progress_pct: Mapped[int | None]     = mapped_column(Integer, nullable=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime]    = mapped_column(DateTime, nullable=False, server_default=func.now())

    contract: Mapped["Contract"] = relationship("Contract", back_populates="work_logs")
    project: Mapped["Project | None"] = relationship("Project", back_populates="work_logs")

    def __repr__(self) -> str:
        return f"<WorkLog id={self.id} date={self.date}>"


# ---------------------------------------------------------------------------
# Invoice
# ---------------------------------------------------------------------------
class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int]          = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    issue_date: Mapped[date]       = mapped_column(Date, nullable=False)
    invoice_number: Mapped[str]    = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal]        = mapped_column(Numeric(14, 2), nullable=False)
    origin: Mapped[str | None]     = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None]      = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime]   = mapped_column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("contract_id", "invoice_number", name="uq_invoice_contract"),
    )

    contract: Mapped["Contract"] = relationship("Contract", back_populates="invoices")

    def __repr__(self) -> str:
        return f"<Invoice id={self.id} number={self.invoice_number!r}>"


# ---------------------------------------------------------------------------
# Holiday
# ---------------------------------------------------------------------------
class Holiday(Base):
    __tablename__ = "holidays"

    id: Mapped[int]        = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date]     = mapped_column(Date, nullable=False, unique=True)
    description: Mapped[str]    = mapped_column(String(255), nullable=False)
    is_national: Mapped[bool]   = mapped_column(Boolean, nullable=False, default=True)
    is_optional: Mapped[bool]   = mapped_column(Boolean, nullable=False, default=False)
    observation: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<Holiday date={self.date} description={self.description!r}>"
