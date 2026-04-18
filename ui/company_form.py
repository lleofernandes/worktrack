"""
company_form.py — Cadastro, edição e contratos de empresas.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

import streamlit as st
from utils.toast_helper import set_toast, show_pending_toast

from database.connection import SessionLocal
from database.models import ContractType
from database.repository import CompanyRepository, ContractRateRepository


CONTRACT_TYPE_LABELS = {
    "WORK_HOUR":     "Por Hora (WORK_HOUR)",
    "PROJECT":       "Projeto Fechado (PROJECT)",
    "PROJECT_HOURS": "Projeto c/ Horas (PROJECT_HOURS)",
}


class CompanyValidationError(Exception):
    pass


def _validate(name: str, cnpj: Optional[str], hour_rate: float,
              session, editing_id=None):
    if not name.strip():
        raise CompanyValidationError("Razão Social é obrigatória.")
    if hour_rate <= 0:
        raise CompanyValidationError("Taxa/hora deve ser maior que zero.")
    if cnpj and cnpj.strip():
        existing = CompanyRepository.get_by_cnpj(session, cnpj.strip())
        if existing and (editing_id is None or existing.id != editing_id):
            raise CompanyValidationError(f"CNPJ '{cnpj}' já cadastrado para outra empresa.")


# ---------------------------------------------------------------------------

def render_company_form() -> None:
    st.header("🏢 Empresas")
    show_pending_toast()

    tab_list, tab_new, tab_edit, tab_holiday = st.tabs([
        "📋 Cadastros",
        "➕ Nova Empresa",
        "✏️ Editar / Contratos",
        "🗓️ Feriados",
    ])

    with tab_list:
        _render_list()
    with tab_new:
        _render_new()
    with tab_edit:
        _render_edit()
    with tab_holiday:
        _render_holidays()


# ---------------------------------------------------------------------------
# Listagem
# ---------------------------------------------------------------------------

def _render_list() -> None:
    session = SessionLocal()
    try:
        status_filter = st.radio(
            "Status do contrato",
            options=["Ativos", "Inativos", "Todos"],
            horizontal=True,
            key="company_status_filter",
        )
        active_map = {"Ativos": True, "Inativos": False, "Todos": None}
        active_only = active_map[status_filter]

        companies = CompanyRepository.get_all(session, active_only=active_only)

        if not companies:
            st.info("Nenhuma empresa encontrada para o filtro selecionado.")
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
                "Início Taxa": rate_obj.start_date.strftime("%d/%m/%Y") if rate_obj else "—",
                "Término Contrato": c.end_date.strftime("%d/%m/%Y") if c.end_date else "—",
                "Status": "🟢 Ativo" if c.is_active else "🔴 Inativo",
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"Total exibido: {len(companies)} empresa(s).")

    finally:
        session.close()


# ---------------------------------------------------------------------------
# Nova empresa
# ---------------------------------------------------------------------------

def _render_new() -> None:
    session = SessionLocal()
    try:
        with st.form("form_new_company", clear_on_submit=True):
            st.subheader("Dados da Empresa")
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Razão Social *")
            with col2:
                fantasy_name = st.text_input("Nome Fantasia")

            col3, col4 = st.columns(2)
            with col3:
                cnpj = st.text_input("CNPJ", placeholder="00.000.000/0001-00")
            with col4:
                contract_number = st.text_input("Nº Contrato")

            col5, col6 = st.columns(2)
            with col5:
                contract_type = st.selectbox(
                    "Tipo de Contrato *",
                    options=[ct.value for ct in ContractType],
                    format_func=lambda x: CONTRACT_TYPE_LABELS.get(x, x),
                )
            with col6:
                end_date = st.date_input(
                    "Término do Contrato (opcional)",
                    value=None,
                    format="DD/MM/YYYY",
                )

            st.divider()
            st.subheader("Taxa Inicial")
            rc1, rc2 = st.columns(2)
            with rc1:
                hour_rate = st.number_input("Taxa/hora (R$) *", min_value=0.01, value=85.00, step=5.0, format="%.2f")
            with rc2:
                rate_start = st.date_input("Vigente a partir de *", value=date.today(), format="DD/MM/YYYY")

            submitted = st.form_submit_button("💾 Cadastrar Empresa", type="primary", use_container_width=True)

        if submitted:
            try:
                _validate(name, cnpj, hour_rate, session)
                company = CompanyRepository.create(
                    session,
                    name=name.strip(),
                    fantasy_name=fantasy_name.strip() or None,
                    cnpj=cnpj.strip() or None,
                    contract_number=contract_number.strip() or None,
                    contract_type=ContractType(contract_type),
                    end_date=end_date if end_date else None,
                )
                ContractRateRepository.create(
                    session,
                    company_id=company.id,
                    hour_rate=Decimal(str(hour_rate)),
                    start_date=rate_start,
                    end_date=None,
                )
                session.commit()
                set_toast(f"✅ Empresa '{company.name}' cadastrada! ID #{company.id}")
                st.rerun()
            except CompanyValidationError as e:
                st.error(f"❌ {e}")
            except Exception as e:
                session.rollback()
                st.error(f"❌ Erro: {e}")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Editar empresa / gerenciar contratos e taxas
# ---------------------------------------------------------------------------

def _render_edit() -> None:
    session = SessionLocal()
    try:
        companies = CompanyRepository.get_all(session)
        if not companies:
            st.info("Nenhuma empresa cadastrada.")
            return

        company_options = {f"[{c.id}] {c.name} ({'Ativo' if c.is_active else 'Inativo'})": c.id
                           for c in companies}
        selected_label = st.selectbox("Selecione a empresa", options=list(company_options.keys()))
        company_id = company_options[selected_label]
        company = CompanyRepository.get_by_id(session, company_id)

        if not company:
            st.error("Empresa não encontrada.")
            return

        st.divider()

        # ── Dados cadastrais ─────────────────────────────────────────────
        with st.expander("✏️ Dados Cadastrais", expanded=True):
            with st.form(f"form_edit_data_{company_id}"):
                col1, col2 = st.columns(2)
                with col1:
                    new_name = st.text_input("Razão Social *", value=company.name)
                with col2:
                    new_fantasy = st.text_input("Nome Fantasia", value=company.fantasy_name or "")

                col3, col4 = st.columns(2)
                with col3:
                    new_cnpj = st.text_input("CNPJ", value=company.cnpj or "")
                with col4:
                    new_end_date = st.date_input(
                        "Término do Contrato (vazio = ativo)",
                        value=company.end_date if company.end_date else None,
                        format="DD/MM/YYYY",
                    )

                save_data = st.form_submit_button("💾 Salvar Dados Cadastrais", type="primary", use_container_width=True)

            if save_data:
                try:
                    _validate(new_name, new_cnpj, 1.0, session, editing_id=company_id)
                    company.name = new_name.strip()
                    company.fantasy_name = new_fantasy.strip() or None
                    company.cnpj = new_cnpj.strip() or None
                    company.end_date = new_end_date if new_end_date else None
                    session.commit()
                    set_toast("✅ Dados cadastrais atualizados!")
                    st.rerun()
                except CompanyValidationError as e:
                    st.error(f"❌ {e}")
                except Exception as e:
                    session.rollback()
                    st.error(f"❌ Erro: {e}")

        # ── Contrato (tipo + número) ─────────────────────────────────────
        with st.expander("📄 Dados do Contrato"):
            with st.form(f"form_edit_contract_{company_id}"):
                col1, col2 = st.columns(2)
                with col1:
                    new_contract_type = st.selectbox(
                        "Tipo de Contrato *",
                        options=[ct.value for ct in ContractType],
                        index=[ct.value for ct in ContractType].index(company.contract_type.value),
                        format_func=lambda x: CONTRACT_TYPE_LABELS.get(x, x),
                    )
                with col2:
                    new_contract_number = st.text_input("Nº Contrato", value=company.contract_number or "")

                save_contract = st.form_submit_button("💾 Salvar Contrato", use_container_width=True)

            if save_contract:
                try:
                    company.contract_type = ContractType(new_contract_type)
                    company.contract_number = new_contract_number.strip() or None
                    session.commit()
                    set_toast("✅ Dados do contrato atualizados!")
                    st.rerun()
                except Exception as e:
                    session.rollback()
                    st.error(f"❌ Erro: {e}")

        # ── Taxas ─────────────────────────────────────────────────────────
        with st.expander("💰 Taxas Horárias"):
            rates = ContractRateRepository.get_all_by_company(session, company_id)
            if rates:
                import pandas as pd
                st.dataframe(pd.DataFrame([{
                    "ID": r.id,
                    "Taxa/h": f"R$ {float(r.hour_rate):,.2f}",
                    "Início": r.start_date.strftime("%d/%m/%Y"),
                    "Término": r.end_date.strftime("%d/%m/%Y") if r.end_date else "Vigente",
                } for r in rates]), use_container_width=True, hide_index=True)
            else:
                st.info("Nenhuma taxa cadastrada.")

            st.caption("Adicionar nova taxa (fecha a vigente automaticamente):")
            with st.form(f"form_new_rate_{company_id}"):
                rc1, rc2 = st.columns(2)
                with rc1:
                    new_rate = st.number_input("Nova Taxa/hora (R$) *", min_value=0.01, value=85.00, step=5.0, format="%.2f")
                with rc2:
                    new_rate_start = st.date_input("Vigente a partir de *", value=date.today(), format="DD/MM/YYYY")
                save_rate = st.form_submit_button("💾 Adicionar Taxa", use_container_width=True)

            if save_rate:
                try:
                    if new_rate <= 0:
                        raise CompanyValidationError("Taxa deve ser maior que zero.")
                    ContractRateRepository.close_current_rate(
                        session, company_id, end_date=new_rate_start - timedelta(days=1)
                    )
                    ContractRateRepository.create(
                        session, company_id=company_id,
                        hour_rate=Decimal(str(new_rate)),
                        start_date=new_rate_start, end_date=None,
                    )
                    session.commit()
                    set_toast(f"✅ Taxa R$ {new_rate:,.2f}/h vigente a partir de {new_rate_start.strftime('%d/%m/%Y')}!")
                    st.rerun()
                except CompanyValidationError as e:
                    st.error(f"❌ {e}")
                except Exception as e:
                    session.rollback()
                    st.error(f"❌ Erro: {e}")

    finally:
        session.close()


# ---------------------------------------------------------------------------
# Feriados
# ---------------------------------------------------------------------------

def _render_holidays() -> None:
    from database.repository import HolidayRepository

    session = SessionLocal()
    try:
        tab_h_list, tab_h_new = st.tabs(["📋 Feriados Cadastrados", "➕ Novo Feriado"])

        with tab_h_list:
            holidays = HolidayRepository.get_all(session)
            if not holidays:
                st.info("Nenhum feriado cadastrado.")
            else:
                import pandas as pd
                rows = [{
                    "ID": h.id,
                    "Data": h.date.strftime("%d/%m/%Y"),
                    "Descrição": h.description,
                    "Nacional": "✅" if h.is_national else "—",
                    "Facultativo": "⚠️ Sim" if h.is_optional else "Não",
                    "Observação": h.observation or "—",
                } for h in holidays]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                with st.expander("🗑️ Remover feriado"):
                    del_id = st.number_input("ID do feriado", min_value=1, step=1, key="del_holiday_id")
                    if st.button("Remover feriado", type="secondary"):
                        found = HolidayRepository.delete(session, int(del_id))
                        if found:
                            session.commit()
                            st.success(f"Feriado #{del_id} removido.")
                            st.rerun()
                        else:
                            st.error(f"Feriado #{del_id} não encontrado.")

        with tab_h_new:
            with st.form("form_new_holiday", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    h_date = st.date_input("Data *", value=date.today(), format="DD/MM/YYYY")
                with col2:
                    h_desc = st.text_input("Descrição *", placeholder="Ex: Tiradentes")

                col3, col4 = st.columns(2)
                with col3:
                    h_national = st.checkbox("Feriado Nacional", value=True)
                with col4:
                    h_optional = st.checkbox("Facultativo", value=False,
                                             help="Marque se for feriado facultativo (ponto opcional)")

                h_obs = st.text_input(
                    "Observação",
                    placeholder="Ex: Ponto facultativo para servidores federais",
                    max_chars=255,
                )

                submitted = st.form_submit_button("💾 Cadastrar Feriado", type="primary", use_container_width=True)

            if submitted:
                try:
                    if not h_desc.strip():
                        st.error("❌ Descrição é obrigatória.")
                    else:
                        HolidayRepository.create(
                            session,
                            date_=h_date,
                            description=h_desc.strip(),
                            is_national=h_national,
                            is_optional=h_optional,
                            observation=h_obs.strip() or None,
                        )
                        session.commit()
                        tipo = "Facultativo" if h_optional else ("Nacional" if h_national else "Local")
                        set_toast(f"✅ Feriado '{h_desc}' ({tipo}) cadastrado para {h_date.strftime('%d/%m/%Y')}!")
                        st.rerun()
                except Exception as e:
                    session.rollback()
                    st.error(f"❌ Erro: {e}")

    finally:
        session.close()
