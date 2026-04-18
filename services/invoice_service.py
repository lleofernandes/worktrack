"""
invoice_service.py — Regras de negócio para notas fiscais.
Queries delegadas ao InvoiceRepository / CompanyRepository.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from database.models import Company, Invoice
from database.repository import CompanyRepository, InvoiceRepository


# ---------------------------------------------------------------------------
# Consultas auxiliares (facades para UI)
# ---------------------------------------------------------------------------

def get_all_companies(session: Session) -> list[Company]:
    return CompanyRepository.get_all(session)


def get_company_by_id(session: Session, company_id: int) -> Optional[Company]:
    return CompanyRepository.get_by_id(session, company_id)


# ---------------------------------------------------------------------------
# Validações
# ---------------------------------------------------------------------------

class InvoiceValidationError(Exception):
    pass


def validate_invoice(
    session: Session,
    company_id: int,
    invoice_number: str,
    amount: float,
    notes: Optional[str],
    editing_id: Optional[int] = None,
) -> None:
    if not invoice_number or not invoice_number.strip():
        raise InvoiceValidationError("Número da NF é obrigatório.")

    if amount <= 0:
        raise InvoiceValidationError("O valor da NF deve ser maior que zero.")

    if notes and len(notes) > 255:
        raise InvoiceValidationError("Observações devem ter no máximo 255 caracteres.")

    if InvoiceRepository.exists_by_number(
        session, company_id, invoice_number, exclude_id=editing_id
    ):
        raise InvoiceValidationError(
            f"Número de NF '{invoice_number}' já existe para esta empresa."
        )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def create_invoice(
    session: Session,
    company_id: int,
    issue_date: date,
    invoice_number: str,
    amount: float,
    origin: Optional[str],
    notes: Optional[str],
) -> Invoice:
    validate_invoice(session, company_id, invoice_number, amount, notes)

    return InvoiceRepository.create(
        session,
        company_id=company_id,
        issue_date=issue_date,
        invoice_number=invoice_number.strip(),
        amount=Decimal(str(amount)),
        origin=origin.strip() if origin else None,
        notes=notes.strip() if notes else None,
    )


def list_invoices(
    session: Session,
    company_id: Optional[int] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
) -> list[Invoice]:
    return InvoiceRepository.list_filtered(session, company_id, month, year)


def delete_invoice(session: Session, invoice_id: int) -> bool:
    return InvoiceRepository.delete(session, invoice_id)
