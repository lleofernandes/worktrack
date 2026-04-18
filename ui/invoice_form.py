"""
invoice_form.py — Controle de Notas Fiscais (por contrato).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import streamlit as st
import pandas as pd

from database.connection import SessionLocal
from database.models import ContractType
from database.repository import (
    ContractRepository, ContractRateRepository, InvoiceRepository,
)
from utils.toast_helper import set_toast, show_pending_toast

CONTRACT_LABELS = {
    "WORK_HOUR":     "Por Hora",
    "PROJECT":       "Projeto Fechado",
    "PROJECT_HOURS": "Projeto c/ Horas",
}


def render_invoice_form() -> None:
    st.header("🧾 Notas Fiscais")
    show_pending_toast()

    session = SessionLocal()
    try:
        tab_hist, tab_new = st.tabs(["📋 Histórico", "➕ Nova NF"])
        with tab_hist:
            _render_history(session)
        
        with tab_new:
            _render_new(session)
        
    finally:
        session.close()


# ---------------------------------------------------------------------------

def _render_new(session) -> None:
    contracts = sorted(ContractRepository.get_all(session, active_only=True), key=lambda c: c.id, reverse=True)
    if not contracts:
        st.warning("Nenhum contrato ativo cadastrado.")
        return

    ct_opts = {
        f"[{ct.id}] {ct.company.name if ct.company else '?'} — {ct.contract_number or 'S/N'}": ct.id
        for ct in contracts
    }
    selected_label = st.selectbox("Contrato *", list(ct_opts.keys()), key="inv_contract")
    contract_id    = ct_opts[selected_label]
    contract       = ContractRepository.get_by_id(session, contract_id)

    # Auto-fill dados do contrato/empresa
    if contract and contract.company:
        with st.container(border=True):
            i1, i2, i3 = st.columns(3)
            # i1.metric("Empresa",    contract.company.name)
            # i2.metric("Fantasia",   contract.company.fantasy_name or "—")
            # i3.metric("CNPJ",       contract.company.cnpj or "—")
            # i4.metric("Tipo",       CONTRACT_LABELS.get(contract.contract_type.value, "—"))
            
            def field(label, value):
                st.markdown(f"""
                    <div style="line-height:2.1">
                        <div style="font-size:14px; text-align: center; color:gray; padding: 0;">{label}</div>
                        <div style="font-size:18px; text-align: center; padding: 0 0 5px 0; ">{value}</div>
                    </div>
                """, unsafe_allow_html=True)

            with i1:
                field("Empresa", contract.company.fantasy_name or "—")

            with i2:
                field("CNPJ", contract.company.cnpj or "—")

            with i3:
                field("Tipo", CONTRACT_LABELS.get(contract.contract_type.value, "—"))

    with st.form("form_new_invoice", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            issue_date     = st.date_input("Data de Emissão *", value=date.today(), format="DD/MM/YYYY")
        with col2:
            invoice_number = st.text_input("Número da NF *")

        col3, col4 = st.columns(2)
        with col3:
            amount = st.number_input("Valor (R$) *", min_value=0.0, step=100.0, format="%.2f")
        with col4:
            origin = st.text_input("Origem / Referência", placeholder="Ex: Competência Mar/2025")

        notes = st.text_input("Observações", max_chars=255, value="Serviços prestados de Analista de Dados")
        submitted = st.form_submit_button("💾 Salvar NF", type="primary", width='stretch')

    if submitted:
        if not invoice_number.strip():
            st.error("❌ Número da NF é obrigatório.")
            return
        if amount <= 0:
            st.error("❌ Valor deve ser maior que zero.")
            return
        if InvoiceRepository.exists_by_number(session, contract_id, invoice_number.strip(), origin.strip()):
            st.error(f"❌ NF '{invoice_number}' já lançada para este contrato.")
            return
        try:
            inv = InvoiceRepository.create(
                session,
                contract_id=contract_id,
                issue_date=issue_date,
                invoice_number=invoice_number.strip(),
                amount=Decimal(str(amount)),
                origin=origin.strip() or None,
                notes=notes.strip() or None,
            )
            session.commit()
            empresa = contract.company.name if contract and contract.company else "—"
            set_toast(f"✅ NF #{inv.invoice_number} salva! {empresa} — R$ {float(inv.amount):,.2f}")
            st.rerun()
        except Exception as e:
            session.rollback()
            st.error(f"❌ Erro: {e}")


# ---------------------------------------------------------------------------

def _render_history(session) -> None:
    from database.repository import CompanyRepository
    companies = CompanyRepository.get_all(session)
    co_opts = {"Todas": None}
    co_opts.update({c.name: c.id for c in companies})

    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        sel = st.selectbox("Empresa", list(co_opts.keys()), key="inv_hist_company")
        filter_company = co_opts[sel]
    with fc2:
        mo = {"Todos": None,
              **{date(2021, m, 1).strftime("%B").capitalize(): m for m in range(1, 13)}}
        ml = st.selectbox("Mês", list(mo.keys()),
                           index=list(mo.keys()).index(
                               date(2021, date.today().month, 1).strftime("%B").capitalize()),
                           key="inv_hist_month")
        filter_month = mo[ml]
    with fc3:            
        
        yo = {"Todos": None,
            **{str(y): y for y in range(2021, date.today().year + 1)}
        }

        yl = st.selectbox(
            "Ano",
            list(yo.keys()),
            index=list(yo.keys()).index(str(date.today().year)),
            key="inv_hist_year"
        )

        filter_year = yo[yl]

    invoices = InvoiceRepository.list_filtered(
        session, company_id=filter_company, month=filter_month, year=filter_year
    )

    st.divider()
    
    if not invoices:
        st.info("Nenhuma NF encontrada.")
        return

    rows = [{
        "ID":         inv.id,
        "Emissão":    inv.issue_date.strftime("%d/%m/%Y"),
        "NF":         inv.invoice_number,
        "Empresa":    inv.contract.company.name if inv.contract and inv.contract.company else "—",
        "Contrato":   inv.contract.contract_number or "S/N" if inv.contract else "—",
        "Valor":      f"R$ {float(inv.amount):,.2f}",
        "Origem":     inv.origin or "—",
        "Observação": inv.notes or "—",
    } for inv in invoices]

    total = sum(float(inv.amount) for inv in invoices)
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.write("")
    
    with c2:
        st.markdown(
            f"""
            <div style="text-align:right">                 
                <div style="font-size:22px; font-weight:600;">Total faturado: R$ {total:,.2f}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        # st.metric("Total faturado no período", f"R$ {total:,.2f}")            
        
    st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)
    
    

    with st.expander("🗑️ Remover NF"):
        del_id = st.number_input("ID da NF", min_value=1, step=1, key="del_inv_id")
        if st.button("Remover NF", type="secondary"):
            found = InvoiceRepository.delete(session, int(del_id))
            if found:
                session.commit()
                set_toast(f"✅ NF #{del_id} removida.")
                st.rerun()
            else:
                st.error(f"ID #{del_id} não encontrado.")
