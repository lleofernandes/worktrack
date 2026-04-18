"""
company_form.py — UI Streamlit para cadastro e edição de empresas.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

import streamlit as st

from database.connection import SessionLocal
from database.models import ContractType
from database.repository import CompanyRepository, ContractRateRepository


# ---------------------------------------------------------------------------
# Validações
# ---------------------------------------------------------------------------

class CompanyValidationError(Exception):
    pass


def _validate_company(name: str, cnpj: Optional[str], hour_rate: float, start_date: date, session, editing_id=None):
    if not name.strip():
        raise CompanyValidationError("Razão Social é obrigatória.")
    if hour_rate <= 0:
        raise CompanyValidationError("Taxa/hora deve ser maior que zero.")
    if cnpj and cnpj.strip():
        existing = CompanyRepository.get_by_cnpj(session, cnpj.strip())
        if existing and (editing_id is None or existing.id != editing_id):
            raise CompanyValidationError(f"CNPJ '{cnpj}' já cadastrado para outra empresa.")


# ---------------------------------------------------------------------------
# Render principal
# ---------------------------------------------------------------------------

def render_company_form() -> None:
    st.header("🏢 Empresas")

    tab_list, tab_new, tab_edit = st.tabs(["📋 Cadastros", "➕ Nova Empresa", "✏️ Editar Empresa"])

    with tab_list:
        _render_list()

    with tab_new:
        _render_new()

    with tab_edit:
        _render_edit()


# ---------------------------------------------------------------------------
# Listagem
# ---------------------------------------------------------------------------

def _render_list() -> None:
    session = SessionLocal()
    try:
        companies = CompanyRepository.get_all(session)

        if not companies:
            st.info("Nenhuma empresa cadastrada.")
            return

        import pandas as pd

        rows = []
        for c in companies:
            rate_obj = ContractRateRepository.get_active_rate(session, c.id, date.today())
            rows.append({
                "ID": c.id,
                "Razão Social": c.name,
                "Nome Fantasia": c.fantasy_name or "—",
                "CNPJ": c.cnpj or "—",
                "Tipo Contrato": c.contract_type.value,
                "Nº Contrato": c.contract_number or "—",
                "Taxa/h Vigente": f"R$ {float(rate_obj.hour_rate):,.2f}" if rate_obj else "—",
                "Desde": rate_obj.start_date.strftime("%d/%m/%Y") if rate_obj else "—",
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"Total: {len(companies)} empresa(s) cadastrada(s).")

    finally:
        session.close()


# ---------------------------------------------------------------------------
# Cadastro de nova empresa
# ---------------------------------------------------------------------------

def _render_new() -> None:
    session = SessionLocal()
    try:
        with st.form("form_new_company", clear_on_submit=True):
            st.subheader("Dados da Empresa")

            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Razão Social *", placeholder="Ex: iMaps Tecnologia Ltda")
            with col2:
                fantasy_name = st.text_input("Nome Fantasia", placeholder="Ex: iMaps")

            col3, col4 = st.columns(2)
            with col3:
                cnpj = st.text_input("CNPJ", placeholder="00.000.000/0001-00")
            with col4:
                contract_number = st.text_input("Nº Contrato", placeholder="Ex: CT-2026-001")

            contract_type = st.selectbox(
                "Tipo de Contrato *",
                options=[ct.value for ct in ContractType],
                format_func=lambda x: {
                    "WORK_HOUR": "Por Hora (WORK_HOUR)",
                    "PROJECT": "Projeto Fechado (PROJECT)",
                    "PROJECT_HOURS": "Projeto c/ Horas (PROJECT_HOURS)",
                }.get(x, x),
            )

            st.divider()
            st.subheader("Taxa Inicial")

            col5, col6 = st.columns(2)
            with col5:
                hour_rate = st.number_input(
                    "Taxa/hora (R$) *", min_value=0.01, value=85.00, step=5.0, format="%.2f"
                )
            with col6:
                rate_start = st.date_input(
                    "Vigente a partir de *", value=date.today(), format="DD/MM/YYYY"
                )

            submitted = st.form_submit_button("💾 Cadastrar Empresa", type="primary", use_container_width=True)

        if submitted:
            try:
                _validate_company(name, cnpj, hour_rate, rate_start, session)
                company = CompanyRepository.create(
                    session,
                    name=name.strip(),
                    fantasy_name=fantasy_name.strip() or None,
                    cnpj=cnpj.strip() or None,
                    contract_number=contract_number.strip() or None,
                    contract_type=ContractType(contract_type),
                )
                ContractRateRepository.create(
                    session,
                    company_id=company.id,
                    hour_rate=Decimal(str(hour_rate)),
                    start_date=rate_start,
                    end_date=None,
                )
                session.commit()
                st.success(f"✅ Empresa '{company.name}' cadastrada com sucesso! ID #{company.id}")
                st.rerun()
            except CompanyValidationError as e:
                st.error(f"❌ {e}")
            except Exception as e:
                session.rollback()
                st.error(f"❌ Erro ao cadastrar: {e}")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Edição de empresa existente
# ---------------------------------------------------------------------------

def _render_edit() -> None:
    session = SessionLocal()
    try:
        companies = CompanyRepository.get_all(session)

        if not companies:
            st.info("Nenhuma empresa cadastrada para editar.")
            return

        company_options = {f"[{c.id}] {c.name}": c.id for c in companies}
        selected_label = st.selectbox("Selecione a empresa", options=list(company_options.keys()))
        company_id = company_options[selected_label]
        company = CompanyRepository.get_by_id(session, company_id)

        if not company:
            st.error("Empresa não encontrada.")
            return

        st.divider()

        # ── Dados cadastrais ─────────────────────────────────────────────
        with st.expander("✏️ Editar dados cadastrais", expanded=True):
            with st.form(f"form_edit_company_{company_id}"):
                col1, col2 = st.columns(2)
                with col1:
                    new_name = st.text_input("Razão Social *", value=company.name)
                with col2:
                    new_fantasy = st.text_input("Nome Fantasia", value=company.fantasy_name or "")

                col3, col4 = st.columns(2)
                with col3:
                    new_cnpj = st.text_input("CNPJ", value=company.cnpj or "")
                with col4:
                    new_contract_number = st.text_input("Nº Contrato", value=company.contract_number or "")

                new_contract_type = st.selectbox(
                    "Tipo de Contrato *",
                    options=[ct.value for ct in ContractType],
                    index=[ct.value for ct in ContractType].index(company.contract_type.value),
                    format_func=lambda x: {
                        "WORK_HOUR": "Por Hora (WORK_HOUR)",
                        "PROJECT": "Projeto Fechado (PROJECT)",
                        "PROJECT_HOURS": "Projeto c/ Horas (PROJECT_HOURS)",
                    }.get(x, x),
                )

                save_data = st.form_submit_button("💾 Salvar Dados", type="primary", use_container_width=True)

            if save_data:
                try:
                    _validate_company(new_name, new_cnpj, 1.0, date.today(), session, editing_id=company_id)
                    company.name = new_name.strip()
                    company.fantasy_name = new_fantasy.strip() or None
                    company.cnpj = new_cnpj.strip() or None
                    company.contract_number = new_contract_number.strip() or None
                    company.contract_type = ContractType(new_contract_type)
                    session.commit()
                    st.success("✅ Dados cadastrais atualizados com sucesso!")
                    st.rerun()
                except CompanyValidationError as e:
                    st.error(f"❌ {e}")
                except Exception as e:
                    session.rollback()
                    st.error(f"❌ Erro ao salvar: {e}")

        # ── Histórico de taxas ───────────────────────────────────────────
        with st.expander("💰 Histórico de Taxas / Nova Taxa"):
            rates = ContractRateRepository.get_all_by_company(session, company_id)

            if rates:
                import pandas as pd
                rate_rows = [{
                    "ID": r.id,
                    "Taxa/h": f"R$ {float(r.hour_rate):,.2f}",
                    "Início": r.start_date.strftime("%d/%m/%Y"),
                    "Término": r.end_date.strftime("%d/%m/%Y") if r.end_date else "Vigente",
                } for r in rates]
                st.dataframe(pd.DataFrame(rate_rows), use_container_width=True, hide_index=True)
            else:
                st.info("Nenhuma taxa cadastrada.")

            st.caption("Adicionar nova taxa (a taxa vigente atual será encerrada automaticamente):")

            with st.form(f"form_new_rate_{company_id}"):
                rc1, rc2 = st.columns(2)
                with rc1:
                    new_rate = st.number_input(
                        "Nova Taxa/hora (R$) *", min_value=0.01, value=85.00, step=5.0, format="%.2f"
                    )
                with rc2:
                    new_rate_start = st.date_input(
                        "Vigente a partir de *", value=date.today(), format="DD/MM/YYYY"
                    )

                save_rate = st.form_submit_button("💾 Adicionar Taxa", use_container_width=True)

            if save_rate:
                try:
                    if new_rate <= 0:
                        raise CompanyValidationError("Taxa deve ser maior que zero.")
                    # Fecha rate atual
                    from datetime import timedelta
                    ContractRateRepository.close_current_rate(
                        session, company_id,
                        end_date=new_rate_start - timedelta(days=1)
                    )
                    # Cria nova
                    ContractRateRepository.create(
                        session,
                        company_id=company_id,
                        hour_rate=Decimal(str(new_rate)),
                        start_date=new_rate_start,
                        end_date=None,
                    )
                    session.commit()
                    st.success(f"✅ Nova taxa R$ {new_rate:,.2f}/h vigente a partir de {new_rate_start.strftime('%d/%m/%Y')}!")
                    st.rerun()
                except CompanyValidationError as e:
                    st.error(f"❌ {e}")
                except Exception as e:
                    session.rollback()
                    st.error(f"❌ Erro ao salvar taxa: {e}")

    finally:
        session.close()
