"""
worklog_form.py — UI Streamlit para apontamento de horas.
Sem regras de negócio aqui — tudo delegado ao worklog_service.
"""
from __future__ import annotations

from datetime import date, datetime, time

import streamlit as st

from database.connection import SessionLocal
from services.worklog_service import (
    WorkLogValidationError,
    create_worklog,
    delete_worklog,
    get_active_rate,
    get_all_companies,
    get_projects_by_company,
    list_worklogs,
)
from utils.calculations import calc_worked_hours


def render_worklog_form() -> None:
    st.header("⏱️ Controle de Horas")

    tab_new, tab_history = st.tabs(["➕ Novo Apontamento", "📋 Histórico"])

    with tab_new:
        _render_new_form()

    with tab_history:
        _render_history()


# ---------------------------------------------------------------------------
# Formulário de novo apontamento
# ---------------------------------------------------------------------------

def _render_new_form() -> None:
    session = SessionLocal()
    try:
        companies = get_all_companies(session)

        if not companies:
            st.warning("Nenhuma empresa cadastrada. Cadastre uma empresa antes de apontar horas.")
            return

        # ── Linha 1: Data + Empresa ──────────────────────────────────────
        col1, col2 = st.columns([1, 2])

        with col1:
            selected_date = st.date_input(
                "Data *",
                value=date.today(),
                format="DD/MM/YYYY",
            )

        with col2:
            company_options = {c.name: c for c in companies}
            company_name = st.selectbox("Empresa *", options=list(company_options.keys()))
            company = company_options[company_name]

        # ── Info da empresa (read-only) ───────────────────────────────────
        active_rate = get_active_rate(session, company.id, selected_date)

        with st.container(border=True):
            ic1, ic2, ic3 = st.columns(3)
            ic1.metric("Tipo de Contrato", company.contract_type.value)
            ic2.metric(
                "Taxa/Hora Vigente",
                f"R$ {active_rate.hour_rate:,.2f}" if active_rate else "—",
            )
            ic3.metric(
                "Nº Contrato",
                company.contract_number or "—",
            )

        # ── Linha 2: Horários ─────────────────────────────────────────────
        col3, col4, col5, col6 = st.columns(4)

        with col3:
            start_time = st.time_input("Início *", value=time(9, 0), step=300)
        with col4:
            end_time = st.time_input("Término *", value=time(18, 0), step=300)
        with col5:
            break_minutes = st.number_input(
                "Intervalo (min)",
                min_value=0,
                max_value=480,
                value=60,
                step=5,
            )
        with col6:
            extra_partner_hours = st.number_input(
                "Horas extras parceiro",
                min_value=0.0,
                max_value=24.0,
                value=0.0,
                step=0.25,
                format="%.2f",
            )

        # ── Preview das horas calculadas ──────────────────────────────────
        try:
            preview_hours = calc_worked_hours(start_time, end_time, break_minutes, extra_partner_hours)
            preview_revenue = (
                float(preview_hours) * float(active_rate.hour_rate)
                if active_rate
                else None
            )
            ph1, ph2 = st.columns(2)
            ph1.info(f"⏱️ **Horas calculadas:** {float(preview_hours):.2f}h")
            if preview_revenue is not None:
                ph2.info(f"💰 **Receita estimada:** R$ {preview_revenue:,.2f}")
        except (ValueError, Exception):
            st.warning("⚠️ Verifique os horários para calcular o preview.")

        # ── Linha 3: Projeto + Descrição ──────────────────────────────────
        projects = get_projects_by_company(session, company.id)
        project_options = {"— Nenhum —": None}
        project_options.update({p.name: p.id for p in projects})

        project_label = st.selectbox("Projeto (opcional)", options=list(project_options.keys()))
        project_id = project_options[project_label]

        description = st.text_area(
            "Descrição",
            placeholder="Descreva as atividades realizadas...",
            height=80,
        )

        # ── Submit ────────────────────────────────────────────────────────
        submitted = st.button("💾 Salvar Apontamento", type="primary", use_container_width=True)

        if submitted:
            try:
                worklog = create_worklog(
                    session=session,
                    company_id=company.id,
                    date_=selected_date,
                    start_time=start_time,
                    end_time=end_time,
                    break_minutes=int(break_minutes),
                    extra_partner_hours=float(extra_partner_hours),
                    description=description,
                    project_id=project_id,
                )
                session.commit()
                st.success(f"✅ Apontamento salvo! ID #{worklog.id} — {float(preview_hours):.2f}h registradas.")
                st.rerun()
            except WorkLogValidationError as e:
                st.error(f"❌ {e}")
            except Exception as e:
                session.rollback()
                st.error(f"❌ Erro ao salvar: {e}")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Histórico de apontamentos
# ---------------------------------------------------------------------------

def _render_history() -> None:
    session = SessionLocal()
    try:
        companies = get_all_companies(session)

        # Filtros
        fc1, fc2, fc3 = st.columns(3)

        with fc1:
            filter_company_options = {"Todas": None}
            filter_company_options.update({c.name: c.id for c in companies})
            filter_company = st.selectbox(
                "Filtrar por empresa",
                options=list(filter_company_options.keys()),
                key="hist_company",
            )

        with fc2:
            filter_month = st.selectbox(
                "Mês",
                options=list(range(1, 13)),
                index=date.today().month - 1,
                format_func=lambda m: date(2000, m, 1).strftime("%B").capitalize(),
                key="hist_month",
            )

        with fc3:
            filter_year = st.selectbox(
                "Ano",
                options=list(range(date.today().year - 2, date.today().year + 1)),
                index=2,
                key="hist_year",
            )

        worklogs = list_worklogs(
            session,
            company_id=filter_company_options[filter_company],
            month=filter_month,
            year=filter_year,
        )

        if not worklogs:
            st.info("Nenhum apontamento encontrado para os filtros selecionados.")
            return

        # Monta tabela de exibição
        from utils.calculations import calc_worked_hours as cwh

        rows = []
        for w in worklogs:
            try:
                hours = float(cwh(w.start_time, w.end_time, w.break_minutes, float(w.extra_partner_hours)))
            except Exception:
                hours = 0.0

            # Busca rate vigente na data do log
            rate_obj = get_active_rate(session, w.company_id, w.date)
            rate = float(rate_obj.hour_rate) if rate_obj else 0.0
            revenue = hours * rate

            rows.append({
                "ID": w.id,
                "Data": w.date.strftime("%d/%m/%Y"),
                "Empresa": w.company.name if w.company else "—",
                "Projeto": w.project.name if w.project else "—",
                "Início": w.start_time.strftime("%H:%M"),
                "Término": w.end_time.strftime("%H:%M"),
                "Intervalo": f"{w.break_minutes}min",
                "Horas": f"{hours:.2f}h",
                "Receita": f"R$ {revenue:,.2f}",
                "_revenue_raw": revenue,
                "Descrição": (w.description or "")[:60],
            })

        import pandas as pd
        df = pd.DataFrame([{k: v for k, v in r.items() if k != "_revenue_raw"} for r in rows])
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Totais
        total_hours = sum(float(r["Horas"].replace("h", "")) for r in rows)  # já é string segura
        total_revenue = sum(r["_revenue_raw"] for r in rows)

        t1, t2, t3 = st.columns(3)
        t1.metric("Total de registros", len(rows))
        t2.metric("Total de horas", f"{total_hours:.2f}h")
        t3.metric("Receita total", f"R$ {total_revenue:,.2f}")

        # Delete
        with st.expander("🗑️ Remover apontamento"):
            del_id = st.number_input("ID do apontamento", min_value=1, step=1, key="del_id")
            if st.button("Remover", type="secondary"):
                found = delete_worklog(session, int(del_id))
                if found:
                    session.commit()
                    st.success(f"Apontamento #{del_id} removido.")
                    st.rerun()
                else:
                    st.error(f"Apontamento #{del_id} não encontrado.")
    finally:
        session.close()