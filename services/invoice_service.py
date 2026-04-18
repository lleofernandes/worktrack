"""
invoice_service.py — Regras de negócio para notas fiscais.
Toda lógica fica aqui; o form (UI) apenas chama este service.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from database.models import Company, Invoice


# ---------------------------------------------------------------------------
# Consultas auxiliares
# ---------------------------------------------------------------------------

def get_all_companies(session: Session) -> list[Company]:
    return session.query(Company).order_by(Company.name).all()


def get_company_by_id(session: Session, company_id: int) -> Optional[Company]:
    return session.get(Company, company_id)


def invoice_number_exists(session: Session, company_id: int, invoice_number: str) -> bool:
    """Verifica unicidade do número de NF por empresa."""
    return (
        session.query(Invoice)
        .filter(
            Invoice.company_id == company_id,
            Invoice.invoice_number == invoice_number.strip(),
        )
        .first()
        is not None
    )


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
    """
    Valida campos da NF. Lança InvoiceValidationError se inválido.
    editing_id: quando não-None, ignora a própria NF na checagem de unicidade.
    """
    if not invoice_number or not invoice_number.strip():
        raise InvoiceValidationError("Número da NF é obrigatório.")

    if amount <= 0:
        raise InvoiceValidationError("O valor da NF deve ser maior que zero.")

    if notes and len(notes) > 255:
        raise InvoiceValidationError("Observações devem ter no máximo 255 caracteres.")

    # Unicidade: número de NF por empresa (ignora o próprio registro em edição)
    existing = (
        session.query(Invoice)
        .filter(
            Invoice.company_id == company_id,
            Invoice.invoice_number == invoice_number.strip(),
        )
        .first()
    )
    if existing and (editing_id is None or existing.id != editing_id):
        raise InvoiceValidationError(
            f"Número de NF '{invoice_number}' já existe para esta empresa."
        )


# ---------------------------------------------------------------------------
# Criação
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
    """Valida e persiste uma nova nota fiscal."""
    validate_invoice(session, company_id, invoice_number, amount, notes)

    invoice = Invoice(
        company_id=company_id,
        issue_date=issue_date,
        invoice_number=invoice_number.strip(),
        amount=Decimal(str(amount)),
        origin=origin.strip() if origin else None,
        notes=notes.strip() if notes else None,
    )
    session.add(invoice)
    session.flush()
    return invoice


# ---------------------------------------------------------------------------
# Listagem
# ---------------------------------------------------------------------------

def list_invoices(
    session: Session,
    company_id: Optional[int] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
) -> list[Invoice]:
    from sqlalchemy import extract

    q = session.query(Invoice).order_by(Invoice.issue_date.desc())

    if company_id:
        q = q.filter(Invoice.company_id == company_id)
    if year:
        q = q.filter(extract("year", Invoice.issue_date) == year)
    if month:
        q = q.filter(extract("month", Invoice.issue_date) == month)

    return q.all()


def delete_invoice(session: Session, invoice_id: int) -> bool:
    obj = session.get(Invoice, invoice_id)
    if obj:
        session.delete(obj)
        return True
    return False
