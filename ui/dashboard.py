"""
dashboard.py — Dashboard analítico (por contrato).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd
import streamlit as st

from database.connection import SessionLocal
from database.models import Contract
from database.repository import (
    CompanyRepository, ContractRepository,
    InvoiceRepository, WorkLogRepository,
)
from services.analytics_service import (
    get_all_contracts_metrics,
    get_company_bar_data,
    get_daily_revenue,
    get_monthly_evolution,
    get_monthly_metrics,
)
from utils.calculations import calc_productivity
from utils.toast_helper import show_pending_toast


def render_dashboard() -> None:
    st.header("📊 Dashboard Analítico")
    show_pending_toast()

    session = SessionLocal()
    try:
        contracts = ContractRepository.get_all(session)
        if not contracts:
            st.warning("Nenhum contrato cadastrado.")
            return

        # ── Filtros ──────────────────────────────────────────────────────
        with st.container(border=True):
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                year = st.selectbox("Ano",
                                     list(range(date.today().year - 2, date.today().year + 1)),
                                     index=2, key="dash_year")
            with fc2:
                month = st.selectbox("Mês", list(range(1, 13)),
                                      index=date.today().month - 1,
                                      format_func=lambda m: date(2000, m, 1).strftime("%B").capitalize(),
                                      key="dash_month")
            with fc3:
                ct_opts = {"Todos": None}
                ct_opts.update({
                    f"[{ct.id}] {ct.company.name if ct.company else '?'} — {ct.contract_number or 'S/N'}": ct.id
                    for ct in contracts
                })
                sel = st.selectbox("Contrato", list(ct_opts.keys()), key="dash_contract")
                filter_contract_id = ct_opts[sel]

        st.divider()

        # ── Alerta NF Pendente ───────────────────────────────────────────
        _render_nf_alert(session, contracts, year, filter_contract_id)
        st.divider()

        # ── KPI Cards ────────────────────────────────────────────────────
        if filter_contract_id:
            metrics_list = [get_monthly_metrics(session, filter_contract_id, year, month)]
        else:
            metrics_list = get_all_contracts_metrics(session, year, month)

        _render_kpi_cards(metrics_list)
        st.divider()

        # ── Gráficos ─────────────────────────────────────────────────────
        col_bar, col_line = st.columns(2)
        with col_bar:
            _render_hours_by_contract(session, year, month)
        with col_line:
            target_id = filter_contract_id or (contracts[0].id if contracts else None)
            if target_id:
                _render_monthly_evolution(session, target_id, year)

        # ── Detalhe diário ───────────────────────────────────────────────
        if filter_contract_id:
            st.divider()
            _render_daily_detail(session, filter_contract_id, year, month)

    finally:
        session.close()


# ---------------------------------------------------------------------------
# Alerta NF Pendente
# ---------------------------------------------------------------------------

def _render_nf_alert(session, contracts, year: int, filter_contract_id) -> None:
    target = ([c for c in contracts if c.id == filter_contract_id]
              if filter_contract_id else contracts)

    pendentes, em_andamento = [], []
    today = date.today()

    for ct in target:
        months_logs = WorkLogRepository.get_months_with_logs(session, ct.id, year)
        months_nf   = InvoiceRepository.get_months_with_invoices(session, ct.id, year)
        label       = f"{ct.company.name if ct.company else '?'} — {ct.contract_number or 'S/N'}"

        for m in sorted(months_logs):
            if m not in months_nf:
                is_current = (year == today.year and m == today.month)
                item = {"Contrato": label,
                        "Mês/Ano": date(year, m, 1).strftime("%B/%Y").capitalize(),
                        "Status": "🔄 Em andamento" if is_current else "⚠️ NF Pend. de Envio"}
                (em_andamento if is_current else pendentes).append(item)

    if not pendentes and not em_andamento:
        st.success(f"✅ Todas as NFs do ano {year} estão em dia!")
        return

    if pendentes:
        st.warning(f"⚠️ **{len(pendentes)} NF(s) pendente(s) de envio** — meses com horas sem NF emitida.")
        st.dataframe(pd.DataFrame(pendentes), use_container_width=True, hide_index=True)

    if em_andamento:
        with st.expander(f"🔄 {len(em_andamento)} mês(es) em andamento (NF ainda não emitida — normal)"):
            st.dataframe(pd.DataFrame(em_andamento), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# KPI Cards
# ---------------------------------------------------------------------------

def _render_kpi_cards(metrics_list) -> None:
    if not metrics_list:
        st.info("Sem dados para o período.")
        return

    total_worked   = sum(m.worked_hours for m in metrics_list)
    total_expected = sum(m.expected_hours for m in metrics_list)
    total_actual   = sum(m.actual_revenue for m in metrics_list)
    total_exp_rev  = sum(m.expected_revenue for m in metrics_list)
    total_remain   = sum(m.remaining_hours for m in metrics_list)
    rev_diff       = total_actual - total_exp_rev
    prod           = float(calc_productivity(total_worked, total_expected))
    biz_days       = max((m.business_days for m in metrics_list), default=0)
    worked_days    = max((m.worked_days   for m in metrics_list), default=0)

    st.subheader("⏱️ Horas")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Dias Úteis",       f"{biz_days}")
    c2.metric("Dias Trabalhados", f"{worked_days}")
    c3.metric("Horas Esperadas",  f"{float(total_expected):.1f}h")
    c4.metric("Horas Trabalhadas", f"{float(total_worked):.1f}h",
              delta=f"{float(total_worked - total_expected):.1f}h")
    c5.metric("Horas Restantes",  f"{float(total_remain):.1f}h")

    st.divider()
    st.subheader("💰 Receita & Produtividade")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Receita Esperada",  f"R$ {float(total_exp_rev):,.2f}")
    r2.metric("Receita Realizada", f"R$ {float(total_actual):,.2f}",
              delta=f"R$ {float(rev_diff):,.2f}",
              delta_color="normal" if rev_diff >= 0 else "inverse")
    r3.metric("Diferença",         f"R$ {float(rev_diff):,.2f}",
              delta_color="normal" if rev_diff >= 0 else "inverse")
    r4.metric("Produtividade",     f"{prod:.1f}%",
              delta=f"{prod - 100:.1f}%")

    icon = "🟢" if prod >= 100 else "🔴"
    st.caption(f"{icon} Produtividade: {prod:.1f}%")
    st.progress(min(prod / 100, 1.0))


# ---------------------------------------------------------------------------
# Bar chart
# ---------------------------------------------------------------------------

def _render_hours_by_contract(session, year: int, month: int) -> None:
    st.subheader("📊 Horas por Contrato")
    bar_data = get_company_bar_data(session, year, month)
    if not bar_data:
        st.info("Sem dados no período.")
        return

    df = pd.DataFrame([
        {"Contrato": b.company_name,
         "Horas": float(b.worked_hours),
         "Receita (R$)": float(b.actual_revenue)}
        for b in bar_data
    ]).sort_values("Horas", ascending=False)

    t1, t2 = st.tabs(["Horas", "Receita"])
    with t1: st.bar_chart(df.set_index("Contrato")["Horas"])
    with t2: st.bar_chart(df.set_index("Contrato")["Receita (R$)"])


# ---------------------------------------------------------------------------
# Line chart
# ---------------------------------------------------------------------------

def _render_monthly_evolution(session, contract_id: int, year: int) -> None:
    ct = session.get(Contract, contract_id)
    label = f"{ct.company.name if ct and ct.company else '?'} — {ct.contract_number or 'S/N'}" if ct else f"#{contract_id}"
    st.subheader(f"📈 Evolução — {label}")

    ev = get_monthly_evolution(session, contract_id, year)
    if not ev:
        st.info("Sem dados de evolução.")
        return

    df = pd.DataFrame([{
        "Mês": date(e.year, e.month, 1).strftime("%b/%Y"),
        "Horas Trabalhadas": float(e.worked_hours),
        "Horas Esperadas":   float(e.expected_hours),
        "Receita Realizada": float(e.actual_revenue),
        "Receita Esperada":  float(e.expected_revenue),
        "Produtividade (%)": float(e.productivity),
    } for e in ev])

    t1, t2, t3 = st.tabs(["Horas", "Receita", "Produtividade"])
    with t1: st.line_chart(df.set_index("Mês")[["Horas Trabalhadas", "Horas Esperadas"]])
    with t2: st.line_chart(df.set_index("Mês")[["Receita Realizada", "Receita Esperada"]])
    with t3:
        st.line_chart(df.set_index("Mês")["Produtividade (%)"])
        st.caption("🔴 < 100% abaixo da meta | 🟢 ≥ 100% acima da meta")


# ---------------------------------------------------------------------------
# Detalhe diário
# ---------------------------------------------------------------------------

def _render_daily_detail(session, contract_id: int, year: int, month: int) -> None:
    ct = session.get(Contract, contract_id)
    label = f"{ct.company.name if ct and ct.company else '?'}" if ct else f"#{contract_id}"
    st.subheader(f"📅 Detalhe Diário — {label} ({date(year, month, 1).strftime('%B/%Y').capitalize()})")

    daily = get_daily_revenue(session, contract_id, year, month)
    if not daily:
        st.info("Sem apontamentos no período.")
        return

    df = pd.DataFrame([{"Data": d.date.strftime("%d/%m/%Y"),
                         "Horas": float(d.worked_hours),
                         "Receita (R$)": float(d.revenue)} for d in daily])

    c1, c2 = st.columns(2)
    with c1: st.bar_chart(df.set_index("Data")["Horas"])
    with c2: st.bar_chart(df.set_index("Data")["Receita (R$)"])

    with st.expander("Ver tabela"):
        df2 = df.copy()
        df2["Horas"]        = df2["Horas"].apply(lambda x: f"{x:.2f}h")
        df2["Receita (R$)"] = df2["Receita (R$)"].apply(lambda x: f"R$ {x:,.2f}")
        st.dataframe(df2, use_container_width=True, hide_index=True)
        th = sum(d.worked_hours for d in daily)
        tr = sum(d.revenue for d in daily)
        st.metric("Total horas",   f"{float(th):.2f}h")
        st.metric("Total receita", f"R$ {float(tr):,.2f}")
