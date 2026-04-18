"""
dashboard.py — Dashboard analítico do Work Track.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import streamlit as st
import pandas as pd

from database.connection import SessionLocal
from services.analytics_service import (
    get_all_companies_metrics,
    get_company_bar_data,
    get_daily_revenue,
    get_monthly_evolution,
    get_monthly_metrics,
)
from services.worklog_service import get_all_companies
from database.repository import InvoiceRepository, WorkLogRepository


def render_dashboard() -> None:
    st.header("📊 Dashboard Analítico")

    session = SessionLocal()
    try:
        companies = get_all_companies(session)
        if not companies:
            st.warning("Nenhuma empresa cadastrada.")
            return

        # ── Filtros globais ──────────────────────────────────────────────
        with st.container(border=True):
            fc1, fc2, fc3 = st.columns(3)

            with fc1:
                year = st.selectbox(
                    "Ano",
                    options=list(range(date.today().year - 2, date.today().year + 1)),
                    index=2,
                    key="dash_year",
                )

            with fc2:
                month = st.selectbox(
                    "Mês",
                    options=list(range(1, 13)),
                    index=date.today().month - 1,
                    format_func=lambda m: date(2000, m, 1).strftime("%B").capitalize(),
                    key="dash_month",
                )

            with fc3:
                company_options = {"Todas": None}
                company_options.update({c.name: c.id for c in companies})
                selected_company = st.selectbox(
                    "Empresa",
                    options=list(company_options.keys()),
                    key="dash_company",
                )
                company_id = company_options[selected_company]

        st.divider()

        # ── Alerta de NFs pendentes ──────────────────────────────────────
        _render_nf_alert(session, companies, year, month, company_id)

        st.divider()

        # ── KPI Cards ────────────────────────────────────────────────────
        if company_id:
            metrics_list = [get_monthly_metrics(session, company_id, year, month)]
        else:
            metrics_list = get_all_companies_metrics(session, year, month)

        _render_kpi_cards(metrics_list)

        st.divider()

        # ── Gráficos ─────────────────────────────────────────────────────
        col_bar, col_line = st.columns([1, 1])

        with col_bar:
            _render_hours_by_company(session, year, month)

        with col_line:
            target_id = company_id or (companies[0].id if companies else None)
            if target_id:
                _render_monthly_evolution(session, target_id, year)

        # ── Detalhe diário ───────────────────────────────────────────────
        if company_id:
            st.divider()
            _render_daily_detail(session, company_id, year, month)

    finally:
        session.close()


# ---------------------------------------------------------------------------
# Alerta de NFs Pendentes
# ---------------------------------------------------------------------------

def _render_nf_alert(session, companies, year: int, month: int, company_id_filter) -> None:
    """
    Cruza meses com horas lançadas vs meses com NF emitida por empresa.
    Se um mês tem horas mas não tem NF → NF Pendente de Envio.
    """
    target_companies = (
        [c for c in companies if c.id == company_id_filter]
        if company_id_filter
        else companies
    )

    pendentes = []

    for company in target_companies:
        months_with_logs = WorkLogRepository.get_months_with_logs(
            session, company.id, year
        )
        months_with_invoices = InvoiceRepository.get_months_with_invoices(
            session, company.id, year
        )

        for m in sorted(months_with_logs):
            # Só alerta meses já encerrados (não o mês atual em andamento)
            ref = date(year, m, 1)
            today = date.today()
            is_current_month = (ref.year == today.year and ref.month == today.month)

            if m not in months_with_invoices:
                pendentes.append({
                    "Empresa": company.name,
                    "Mês/Ano": date(year, m, 1).strftime("%B/%Y").capitalize(),
                    "Status": "🔄 Em andamento" if is_current_month else "⚠️ NF Pend. de Envio",
                    "_is_current": is_current_month,
                    "_month": m,
                })

    if not pendentes:
        st.success(f"✅ Todas as NFs do ano {year} estão em dia!")
        return

    # Separa pendentes reais vs mês em andamento
    pendentes_reais = [p for p in pendentes if not p["_is_current"]]
    em_andamento    = [p for p in pendentes if p["_is_current"]]

    if pendentes_reais:
        st.warning(
            f"⚠️ **{len(pendentes_reais)} NF(s) pendente(s) de envio** — "
            f"meses com horas lançadas sem nota fiscal emitida."
        )
        df = pd.DataFrame([
            {"Empresa": p["Empresa"], "Mês/Ano": p["Mês/Ano"], "Status": p["Status"]}
            for p in pendentes_reais
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)

    if em_andamento:
        with st.expander(f"🔄 {len(em_andamento)} mês(es) em andamento (sem NF ainda — normal)"):
            df2 = pd.DataFrame([
                {"Empresa": p["Empresa"], "Mês/Ano": p["Mês/Ano"], "Status": p["Status"]}
                for p in em_andamento
            ])
            st.dataframe(df2, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# KPI Cards
# ---------------------------------------------------------------------------

def _render_kpi_cards(metrics_list) -> None:
    if not metrics_list:
        st.info("Sem dados para o período selecionado.")
        return

    total_worked       = sum(m.worked_hours for m in metrics_list)
    total_expected     = sum(m.expected_hours for m in metrics_list)
    total_actual_rev   = sum(m.actual_revenue for m in metrics_list)
    total_expected_rev = sum(m.expected_revenue for m in metrics_list)
    total_remaining    = sum(m.remaining_hours for m in metrics_list)
    revenue_diff       = total_actual_rev - total_expected_rev

    from utils.calculations import calc_productivity
    productivity = calc_productivity(total_worked, total_expected)
    prod_val = float(productivity)

    st.subheader("⏱️ Horas")
    h1, h2, h3, h4, h5 = st.columns(5)
    h1.metric("Dias Úteis", f"{max(m.business_days for m in metrics_list)}")
    h2.metric("Dias Trabalhados", f"{max(m.worked_days for m in metrics_list)}")
    h3.metric("Horas Esperadas", f"{float(total_expected):.1f}h")
    hours_diff = total_worked - total_expected
    h4.metric(
        "Horas Trabalhadas",
        f"{float(total_worked):.1f}h",
        delta=f"{float(hours_diff):.1f}h",
        delta_color="normal",
    )
    h5.metric("Horas Restantes", f"{float(total_remaining):.1f}h")

    st.divider()

    st.subheader("💰 Receita & Produtividade")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Receita Esperada", f"R$ {float(total_expected_rev):,.2f}")

    rev_color = "normal" if revenue_diff >= 0 else "inverse"
    r2.metric(
        "Receita Realizada",
        f"R$ {float(total_actual_rev):,.2f}",
        delta=f"R$ {float(revenue_diff):,.2f}",
        delta_color=rev_color,
    )
    r3.metric(
        "Diferença",
        f"R$ {float(revenue_diff):,.2f}",
        delta_color=rev_color,
    )
    r4.metric(
        "Produtividade",
        f"{prod_val:.1f}%",
        delta=f"{prod_val - 100:.1f}%",
        delta_color="normal",
    )

    progress = min(prod_val / 100, 1.0)
    bar_color = "🟢" if prod_val >= 100 else "🔴"
    st.caption(f"{bar_color} Produtividade: {prod_val:.1f}% da meta mensal")
    st.progress(progress)


# ---------------------------------------------------------------------------
# Bar chart — horas por empresa
# ---------------------------------------------------------------------------

def _render_hours_by_company(session, year: int, month: int) -> None:
    st.subheader("📊 Horas por Empresa")
    bar_data = get_company_bar_data(session, year, month)

    if not bar_data:
        st.info("Sem dados no período.")
        return

    df = pd.DataFrame([
        {"Empresa": b.company_name, "Horas": float(b.worked_hours), "Receita (R$)": float(b.actual_revenue)}
        for b in bar_data
    ]).sort_values("Horas", ascending=False)

    tab1, tab2 = st.tabs(["Horas", "Receita"])
    with tab1:
        st.bar_chart(df.set_index("Empresa")["Horas"])
    with tab2:
        st.bar_chart(df.set_index("Empresa")["Receita (R$)"])

    with st.expander("Ver tabela"):
        df_display = df.copy()
        df_display["Receita (R$)"] = df_display["Receita (R$)"].apply(lambda x: f"R$ {x:,.2f}")
        df_display["Horas"] = df_display["Horas"].apply(lambda x: f"{x:.2f}h")
        st.dataframe(df_display, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Line chart — evolução mensal
# ---------------------------------------------------------------------------

def _render_monthly_evolution(session, company_id: int, year: int) -> None:
    from database.models import Company
    company = session.get(Company, company_id)
    label = company.name if company else f"Empresa #{company_id}"

    st.subheader(f"📈 Evolução Mensal — {label}")
    evolution = get_monthly_evolution(session, company_id, year, months=12)

    if not evolution:
        st.info("Sem dados de evolução.")
        return

    df = pd.DataFrame([
        {
            "Mês": date(e.year, e.month, 1).strftime("%b/%Y"),
            "Horas Trabalhadas": float(e.worked_hours),
            "Horas Esperadas": float(e.expected_hours),
            "Receita Realizada": float(e.actual_revenue),
            "Receita Esperada": float(e.expected_revenue),
            "Produtividade (%)": float(e.productivity),
        }
        for e in evolution
    ])

    tab1, tab2, tab3 = st.tabs(["Horas", "Receita", "Produtividade"])
    with tab1:
        st.line_chart(df.set_index("Mês")[["Horas Trabalhadas", "Horas Esperadas"]])
    with tab2:
        st.line_chart(df.set_index("Mês")[["Receita Realizada", "Receita Esperada"]])
    with tab3:
        st.line_chart(df.set_index("Mês")["Produtividade (%)"])
        st.caption("🔴 < 100% = abaixo da meta | 🟢 ≥ 100% = acima da meta")


# ---------------------------------------------------------------------------
# Detalhe diário
# ---------------------------------------------------------------------------

def _render_daily_detail(session, company_id: int, year: int, month: int) -> None:
    from database.models import Company
    company = session.get(Company, company_id)
    label = company.name if company else f"Empresa #{company_id}"

    st.subheader(f"📅 Detalhe Diário — {label} ({date(year, month, 1).strftime('%B/%Y').capitalize()})")
    daily = get_daily_revenue(session, company_id, year, month)

    if not daily:
        st.info("Sem apontamentos no período.")
        return

    df = pd.DataFrame([
        {"Data": d.date.strftime("%d/%m/%Y"), "Horas": float(d.worked_hours), "Receita (R$)": float(d.revenue)}
        for d in daily
    ])

    col1, col2 = st.columns(2)
    with col1:
        st.bar_chart(df.set_index("Data")["Horas"])
    with col2:
        st.bar_chart(df.set_index("Data")["Receita (R$)"])

    with st.expander("Ver tabela diária"):
        df_display = df.copy()
        df_display["Horas"] = df_display["Horas"].apply(lambda x: f"{x:.2f}h")
        df_display["Receita (R$)"] = df_display["Receita (R$)"].apply(lambda x: f"R$ {x:,.2f}")
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        total_h = sum(d.worked_hours for d in daily)
        total_r = sum(d.revenue for d in daily)
        c1, c2 = st.columns(2)
        c1.metric("Total horas", f"{float(total_h):.2f}h")
        c2.metric("Total receita", f"R$ {float(total_r):,.2f}")
