"""
company_form.py — Empresas (cadastro) e Contratos (separado) e Feriados.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

import streamlit as st
import pandas as pd

from database.connection import SessionLocal
from database.models import ContractType
from database.repository import (
    CompanyRepository, ContractRepository,
    ContractRateRepository, HolidayRepository,
)
from utils.toast_helper import set_toast, show_pending_toast

CONTRACT_LABELS = {
    "WORK_HOUR":     "Por Hora (WORK_HOUR)",
    "PROJECT":       "Projeto Fechado (PROJECT)",
    "PROJECT_HOURS": "Projeto c/ Horas (PROJECT_HOURS)",
}


def render_company_form() -> None:
    st.header("🗂️ Cadastros")
    show_pending_toast()

    tab_companies, tab_contracts, tab_holidays = st.tabs([
        "🏢 Empresas",
        "📄 Contratos",
        "🗓️ Feriados",
    ])

    with tab_companies:
        _render_companies()
    with tab_contracts:
        _render_contracts()
    with tab_holidays:
        _render_holidays()


# ===========================================================================
# EMPRESAS
# ===========================================================================

def _render_companies() -> None:
    session = SessionLocal()
    try:
        sub_list, sub_new, sub_edit = st.tabs(["📋 Lista", "➕ Nova", "✏️ Editar"])
        with sub_list:
            _company_list(session)
        with sub_new:
            _company_new(session)
        with sub_edit:
            _company_edit(session)
    finally:
        session.close()


def _company_list(session) -> None:
    companies = CompanyRepository.get_all(session)
    if not companies:
        st.info("Nenhuma empresa cadastrada.")
        return

    rows = []
    for c in companies:
        contracts = ContractRepository.get_by_company(session, c.id)
        active_contracts = [ct for ct in contracts if ct.is_active]
        rows.append({
            "ID": c.id,
            "Razão Social": c.name,
            "Nome Fantasia": c.fantasy_name or "—",
            "CNPJ": c.cnpj or "—",
            "Contratos": len(contracts),
            "Ativos": len(active_contracts),
            "Cadastrado em": c.created_at.strftime("%d/%m/%Y"),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _company_new(session) -> None:
    with st.form("form_new_company", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Razão Social *")
        with col2:
            fantasy_name = st.text_input("Nome Fantasia")
        cnpj = st.text_input("CNPJ", placeholder="00.000.000/0001-00")
        submitted = st.form_submit_button("💾 Cadastrar Empresa", type="primary", use_container_width=True)

    if submitted:
        if not name.strip():
            st.error("❌ Razão Social é obrigatória.")
            return
        if cnpj.strip():
            existing = CompanyRepository.get_by_cnpj(session, cnpj.strip())
            if existing:
                st.error(f"❌ CNPJ já cadastrado para '{existing.name}'.")
                return
        try:
            company = CompanyRepository.create(
                session,
                name=name.strip(),
                fantasy_name=fantasy_name.strip() or None,
                cnpj=cnpj.strip() or None,
            )
            session.commit()
            set_toast(f"✅ Empresa '{company.name}' cadastrada! ID #{company.id}")
            st.rerun()
        except Exception as e:
            session.rollback()
            st.error(f"❌ Erro: {e}")


def _company_edit(session) -> None:
    companies = CompanyRepository.get_all(session)
    if not companies:
        st.info("Nenhuma empresa cadastrada.")
        return

    options = {f"[{c.id}] {c.name}": c.id for c in companies}
    label = st.selectbox("Empresa", list(options.keys()), key="edit_company_sel")
    company = CompanyRepository.get_by_id(session, options[label])
    if not company:
        return

    with st.form(f"form_edit_company_{company.id}"):
        col1, col2 = st.columns(2)
        with col1:
            new_name = st.text_input("Razão Social *", value=company.name)
        with col2:
            new_fantasy = st.text_input("Nome Fantasia", value=company.fantasy_name or "")
        new_cnpj = st.text_input("CNPJ", value=company.cnpj or "")
        saved = st.form_submit_button("💾 Salvar", type="primary", use_container_width=True)

    if saved:
        if not new_name.strip():
            st.error("❌ Razão Social obrigatória.")
            return
        if new_cnpj.strip():
            existing = CompanyRepository.get_by_cnpj(session, new_cnpj.strip())
            if existing and existing.id != company.id:
                st.error(f"❌ CNPJ já cadastrado para '{existing.name}'.")
                return
        try:
            company.name = new_name.strip()
            company.fantasy_name = new_fantasy.strip() or None
            company.cnpj = new_cnpj.strip() or None
            session.commit()
            set_toast("✅ Empresa atualizada!")
            st.rerun()
        except Exception as e:
            session.rollback()
            st.error(f"❌ Erro: {e}")


# ===========================================================================
# CONTRATOS
# ===========================================================================

def _render_contracts() -> None:
    session = SessionLocal()
    try:
        sub_list, sub_new, sub_edit = st.tabs(["📋 Lista", "➕ Novo Contrato", "✏️ Editar / Taxas"])
        with sub_list:
            _contract_list(session)
        with sub_new:
            _contract_new(session)
        with sub_edit:
            _contract_edit(session)
    finally:
        session.close()


def _contract_list(session) -> None:
    status_filter = st.radio("Status", ["Ativos", "Inativos", "Todos"],
                              horizontal=True, key="contract_status")
    active_map = {"Ativos": True, "Inativos": False, "Todos": None}
    contracts = ContractRepository.get_all(session, active_only=active_map[status_filter])

    if not contracts:
        st.info("Nenhum contrato encontrado.")
        return

    rows = []
    for ct in contracts:
        rate = ContractRateRepository.get_active_rate(session, ct.id, date.today())
        rows.append({
            "ID": ct.id,
            "Empresa": ct.company.name if ct.company else "—",
            "Nº Contrato": ct.contract_number or "—",
            "Tipo": CONTRACT_LABELS.get(ct.contract_type.value, ct.contract_type.value),
            "Início": ct.start_date.strftime("%d/%m/%Y"),
            "Término": ct.end_date.strftime("%d/%m/%Y") if ct.end_date else "Vigente",
            "Taxa/h Atual": f"R$ {float(rate.hour_rate):,.2f}" if rate else "—",
            "Status": "🟢 Ativo" if ct.is_active else "🔴 Encerrado",
            "Descrição": ct.description or "—",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption(f"{len(contracts)} contrato(s) encontrado(s).")


def _contract_new(session) -> None:
    companies = CompanyRepository.get_all(session)
    if not companies:
        st.warning("Cadastre uma empresa primeiro.")
        return

    company_options = {f"[{c.id}] {c.name}": c.id for c in companies}

    with st.form("form_new_contract", clear_on_submit=True):
        selected = st.selectbox("Empresa *", list(company_options.keys()), key="new_ct_company")
        company_id = company_options[selected]

        col1, col2 = st.columns(2)
        with col1:
            contract_number = st.text_input("Nº do Contrato")
        with col2:
            contract_type = st.selectbox(
                "Tipo de Contrato *",
                [ct.value for ct in ContractType],
                format_func=lambda x: CONTRACT_LABELS.get(x, x),
            )

        col3, col4 = st.columns(2)
        with col3:
            start_date = st.date_input("Início da Vigência *", value=date.today(), format="DD/MM/YYYY")
        with col4:
            end_date = st.date_input("Término da Vigência (vazio = aberto)", value=None, format="DD/MM/YYYY")

        description = st.text_input("Descrição / Objeto do Contrato", max_chars=255)

        st.divider()
        st.caption("Taxa Hora Inicial")
        rc1, rc2 = st.columns(2)
        with rc1:
            hour_rate = st.number_input("Taxa/hora (R$) *", min_value=0.01, value=85.00, step=5.0, format="%.2f")
        with rc2:
            rate_start = st.date_input("Vigente a partir de *", value=date.today(), format="DD/MM/YYYY")

        submitted = st.form_submit_button("💾 Cadastrar Contrato", type="primary", use_container_width=True)

    if submitted:
        if hour_rate <= 0:
            st.error("❌ Taxa/hora deve ser maior que zero.")
            return
        if end_date and end_date < start_date:
            st.error("❌ Término não pode ser anterior ao início.")
            return
        try:
            contract = ContractRepository.create(
                session,
                company_id=company_id,
                contract_number=contract_number.strip() or None,
                contract_type=ContractType(contract_type),
                start_date=start_date,
                end_date=end_date if end_date else None,
                description=description.strip() or None,
            )
            ContractRateRepository.create(
                session,
                contract_id=contract.id,
                hour_rate=Decimal(str(hour_rate)),
                start_date=rate_start,
                end_date=None,
            )
            session.commit()
            set_toast(f"✅ Contrato #{contract.id} cadastrado para {companies[0].name if companies else ''}!")
            st.rerun()
        except Exception as e:
            session.rollback()
            st.error(f"❌ Erro: {e}")


def _contract_edit(session) -> None:
    contracts = ContractRepository.get_all(session)
    if not contracts:
        st.info("Nenhum contrato cadastrado.")
        return

    options = {
        f"[{ct.id}] {ct.company.name if ct.company else '?'} — {ct.contract_number or 'S/N'} ({ct.start_date.strftime('%d/%m/%Y')})": ct.id
        for ct in contracts
    }
    label = st.selectbox("Contrato", list(options.keys()), key="edit_ct_sel")
    contract = ContractRepository.get_by_id(session, options[label])
    if not contract:
        return

    with st.expander("✏️ Dados do Contrato", expanded=True):
        with st.form(f"form_edit_ct_{contract.id}"):
            col1, col2 = st.columns(2)
            with col1:
                new_number = st.text_input("Nº Contrato", value=contract.contract_number or "")
            with col2:
                new_type = st.selectbox(
                    "Tipo", [ct.value for ct in ContractType],
                    index=[ct.value for ct in ContractType].index(contract.contract_type.value),
                    format_func=lambda x: CONTRACT_LABELS.get(x, x),
                )
            col3, col4 = st.columns(2)
            with col3:
                new_start = st.date_input("Início", value=contract.start_date, format="DD/MM/YYYY")
            with col4:
                new_end = st.date_input("Término (vazio = aberto)",
                                         value=contract.end_date if contract.end_date else None,
                                         format="DD/MM/YYYY")
            new_desc = st.text_input("Descrição", value=contract.description or "")
            saved = st.form_submit_button("💾 Salvar Contrato", type="primary", use_container_width=True)

        if saved:
            try:
                contract.contract_number = new_number.strip() or None
                contract.contract_type   = ContractType(new_type)
                contract.start_date      = new_start
                contract.end_date        = new_end if new_end else None
                contract.description     = new_desc.strip() or None
                session.commit()
                set_toast("✅ Contrato atualizado!")
                st.rerun()
            except Exception as e:
                session.rollback()
                st.error(f"❌ Erro: {e}")

    with st.expander("💰 Histórico de Taxas"):
        rates = ContractRateRepository.get_all_by_contract(session, contract.id)
        if rates:
            st.dataframe(pd.DataFrame([{
                "ID": r.id, "Taxa/h": f"R$ {float(r.hour_rate):,.2f}",
                "Início": r.start_date.strftime("%d/%m/%Y"),
                "Término": r.end_date.strftime("%d/%m/%Y") if r.end_date else "Vigente",
            } for r in rates]), use_container_width=True, hide_index=True)
        else:
            st.info("Sem taxas cadastradas.")

        with st.form(f"form_new_rate_{contract.id}"):
            rc1, rc2 = st.columns(2)
            with rc1:
                new_rate = st.number_input("Nova Taxa/h (R$) *", min_value=0.01, value=85.0, step=5.0, format="%.2f")
            with rc2:
                new_rate_start = st.date_input("Vigente a partir de *", value=date.today(), format="DD/MM/YYYY")
            add_rate = st.form_submit_button("💾 Adicionar Taxa", use_container_width=True)

        if add_rate:
            try:
                ContractRateRepository.close_current(
                    session, contract.id,
                    end_date=new_rate_start - timedelta(days=1)
                )
                ContractRateRepository.create(
                    session, contract_id=contract.id,
                    hour_rate=Decimal(str(new_rate)),
                    start_date=new_rate_start, end_date=None,
                )
                session.commit()
                set_toast(f"✅ Nova taxa R$ {new_rate:,.2f}/h a partir de {new_rate_start.strftime('%d/%m/%Y')}!")
                st.rerun()
            except Exception as e:
                session.rollback()
                st.error(f"❌ Erro: {e}")


# ===========================================================================
# FERIADOS
# ===========================================================================

def _render_holidays() -> None:
    session = SessionLocal()
    try:
        sub_list, sub_new = st.tabs(["📋 Cadastrados", "➕ Novo Feriado"])
        with sub_list:
            holidays = HolidayRepository.get_all(session)
            if not holidays:
                st.info("Nenhum feriado cadastrado.")
            else:
                st.dataframe(pd.DataFrame([{
                    "ID": h.id, "Data": h.date.strftime("%d/%m/%Y"),
                    "Descrição": h.description,
                    "Nacional": "✅" if h.is_national else "—",
                    "Facultativo": "⚠️ Sim" if h.is_optional else "Não",
                    "Observação": h.observation or "—",
                } for h in holidays]), use_container_width=True, hide_index=True)

                with st.expander("🗑️ Remover"):
                    del_id = st.number_input("ID do feriado", min_value=1, step=1, key="del_hol")
                    if st.button("Remover", type="secondary"):
                        found = HolidayRepository.delete(session, int(del_id))
                        if found:
                            session.commit()
                            set_toast(f"✅ Feriado #{del_id} removido.")
                            st.rerun()
                        else:
                            st.error("ID não encontrado.")

        with sub_new:
            with st.form("form_new_holiday", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    h_date = st.date_input("Data *", value=date.today(), format="DD/MM/YYYY")
                with col2:
                    h_desc = st.text_input("Descrição *")
                col3, col4 = st.columns(2)
                with col3:
                    h_nat = st.checkbox("Nacional", value=True)
                with col4:
                    h_opt = st.checkbox("Facultativo", value=False)
                h_obs = st.text_input("Observação", max_chars=255)
                submitted = st.form_submit_button("💾 Cadastrar", type="primary", use_container_width=True)

            if submitted:
                if not h_desc.strip():
                    st.error("❌ Descrição obrigatória.")
                else:
                    try:
                        HolidayRepository.create(
                            session, date_=h_date, description=h_desc.strip(),
                            is_national=h_nat, is_optional=h_opt,
                            observation=h_obs.strip() or None,
                        )
                        session.commit()
                        tipo = "Facultativo" if h_opt else ("Nacional" if h_nat else "Local")
                        set_toast(f"✅ Feriado '{h_desc}' ({tipo}) — {h_date.strftime('%d/%m/%Y')}!")
                        st.rerun()
                    except Exception as e:
                        session.rollback()
                        st.error(f"❌ Erro: {e}")
    finally:
        session.close()
