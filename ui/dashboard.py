"""
dashboard.py — Dashboard analítico (por contrato).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

import pandas as pd
import streamlit as st

from database.connection import SessionLocal
from database.models import Contract
from database.repository import (
    ContractRepository,
    InvoiceRepository,
    WorkLogRepository,
)
from services.analytics_service import (
    get_all_contracts_metrics,
    get_daily_revenue,
    get_monthly_evolution,
    get_monthly_metrics,
)
from utils.calculations import calc_productivity
from utils.toast_helper import show_pending_toast


_STATUS_MAP = {"Todos": None, "Ativo": True, "Inativo": False}


def render_dashboard() -> None:
    st.header("📊 Dashboard Analítico")
    show_pending_toast()

    session = SessionLocal()
    try:
        with st.container(border=True):
            fc1, fc2, fc3, fc4 = st.columns(4)

            with fc1:
                status_sel    = st.selectbox("Status Contrato", list(_STATUS_MAP.keys()), key="dash_status")
                filter_active = _STATUS_MAP[status_sel]

            with fc2:
                month_opts = {"Todos": None}
                month_opts.update({
                    date(2021, m, 1).strftime("%B").capitalize(): m
                    for m in range(1, 13)
                })
                month_labels    = list(month_opts.keys())
                cur_month_label = date(2021, date.today().month, 1).strftime("%B").capitalize()
                month_sel       = st.selectbox("Mês", month_labels,
                                               index=month_labels.index(cur_month_label),
                                               key="dash_month")
                filter_month = month_opts[month_sel]

            with fc3:
                year_opts = ["Todos"] + list(range(date.today().year - 2, date.today().year + 1))
                year_sel  = st.selectbox("Ano", year_opts,
                                         index=year_opts.index(date.today().year),
                                         key="dash_year")
                filter_year = None if year_sel == "Todos" else int(year_sel)

            with fc4:
                contracts = sorted(
                    ContractRepository.get_all(session, active_only=filter_active),
                    key=lambda c: c.id, reverse=True,
                )
                ct_opts = {"Todos": None}
                ct_opts.update({
                    f"[{ct.id}] {ct.company.name if ct.company else '?'}  — {ct.contract_number or 'S/N'}": ct.id
                    for ct in contracts
                })
                sel = st.selectbox("Contrato", list(ct_opts.keys()), key="dash_contract")
                filter_contract_id = ct_opts[sel]

        if not contracts:
            st.warning("Nenhum contrato encontrado para o status selecionado.")
            st.stop()

        years_range  = _resolve_years(filter_year)
        months_range = _resolve_months(filter_month)

        st.divider()

        for yr in years_range:
            _render_nf_alert(session, contracts, yr, filter_contract_id)
        st.divider()

        # ── Coleta métricas UMA ÚNICA VEZ com active_only correto ────────
        metrics_list = []
        for yr in years_range:
            for mo in months_range:
                if filter_contract_id:
                    metrics_list.append(
                        get_monthly_metrics(session, filter_contract_id, yr, mo)
                    )
                else:
                    metrics_list.extend(
                        get_all_contracts_metrics(
                            session, yr, mo, active_only=filter_active
                        )
                    )

        period_label = _period_label(filter_year, filter_month)
        st.caption(f"📅 Período: **{period_label}**")
        _render_kpi_cards(metrics_list)
        st.divider()

        col_bar, col_line = st.columns(2)
        with col_bar:
            # Reutiliza metrics_list — sem nova chamada ao service/banco
            _render_hours_by_contract_from_metrics(metrics_list)
        with col_line:
            target_id = filter_contract_id or (contracts[0].id if contracts else None)
            if target_id:
                evo_year = filter_year or date.today().year
                _render_monthly_evolution(session, target_id, evo_year)

        if filter_contract_id and filter_year and filter_month:
            st.divider()
            _render_daily_detail(session, filter_contract_id, filter_year, filter_month)

    finally:
        session.close()


# ---------------------------------------------------------------------------
# Helpers de período
# ---------------------------------------------------------------------------

def _resolve_years(filter_year) -> list[int]:
    if filter_year:
        return [filter_year]
    today = date.today()
    return list(range(today.year - 2, today.year + 1))


def _resolve_months(filter_month) -> list[int]:
    return [filter_month] if filter_month else list(range(1, 13))


def _period_label(filter_year, filter_month) -> str:
    if filter_year and filter_month:
        return date(filter_year, filter_month, 1).strftime("%B/%Y").capitalize()
    if filter_year:
        return f"Ano {filter_year} (todos os meses)"
    if filter_month:
        return f"{date(2021, filter_month, 1).strftime('%B').capitalize()} (todos os anos)"
    return "Todos os períodos"


# ---------------------------------------------------------------------------
# Alerta NF Pendente
# ---------------------------------------------------------------------------

def _render_nf_alert(session, contracts, year: int, filter_contract_id) -> None:
    target = (
        [c for c in contracts if c.id == filter_contract_id]
        if filter_contract_id else contracts
    )

    pendentes, em_andamento = [], []
    today = date.today()

    for ct in target:
        months_logs = WorkLogRepository.get_months_with_logs(session, ct.id, year)
        months_nf   = InvoiceRepository.get_months_with_invoices(session, ct.id, year)
        label       = f"{ct.company.name if ct.company else '?'} — {ct.contract_number or 'S/N'}"

        for m in sorted(months_logs):
            if m not in months_nf:
                is_current = (year == today.year and m == today.month)
                item = {
                    "Contrato": label,
                    "Mês/Ano": date(year, m, 1).strftime("%B/%Y").capitalize(),
                    "Status": "🔄 Em andamento" if is_current else "⚠️ NF Pend. de Envio",
                }
                (em_andamento if is_current else pendentes).append(item)

    if not pendentes and not em_andamento:
        st.success(f"✅ Todas as NFs de {year} estão em dia!")
        return

    if pendentes:
        st.warning(f"⚠️ **{len(pendentes)} NF(s) pendente(s) — {year}**")
        st.dataframe(pd.DataFrame(pendentes), use_container_width=True, hide_index=True)

    if em_andamento:
        with st.expander(f"🔄 {len(em_andamento)} mês(es) em andamento em {year} (NF ainda não emitida — normal)"):
            st.dataframe(pd.DataFrame(em_andamento), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# KPI Cards
# ---------------------------------------------------------------------------

def _render_kpi_cards(metrics_list) -> None:
    if not metrics_list:
        st.info("Sem dados para o período.")
        return

    total_worked   = sum(m.worked_hours     for m in metrics_list)
    total_expected = sum(m.expected_hours   for m in metrics_list)
    total_actual   = sum(m.actual_revenue   for m in metrics_list)
    total_exp_rev  = sum(m.expected_revenue for m in metrics_list)
    total_remain   = sum(m.remaining_hours  for m in metrics_list)
    rev_diff       = total_actual - total_exp_rev
    prod           = float(calc_productivity(total_worked, total_expected))
    biz_days       = sum(m.business_days for m in metrics_list)
    worked_days    = sum(m.worked_days   for m in metrics_list)

    st.subheader("⏱️ Horas")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Dias Úteis",        f"{biz_days}")
    c2.metric("Dias Trabalhados",  f"{worked_days}")
    c3.metric("Horas Esperadas",   f"{float(total_expected):.1f}h")
    c4.metric("Horas Trabalhadas", f"{float(total_worked):.1f}h",
              delta=f"{float(total_worked - total_expected):.1f}h")
    c5.metric("Horas Restantes",   f"{float(total_remain):.1f}h")

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
    st.caption(f"{icon} Produtividade consolidada: {prod:.1f}%")
    st.progress(min(prod / 100, 1.0))


# ---------------------------------------------------------------------------
# Bar chart — reutiliza metrics_list, zero chamadas extras ao banco
# ---------------------------------------------------------------------------

def _render_hours_by_contract_from_metrics(metrics_list) -> None:
    st.subheader("📊 Horas por Contrato")

    totals: dict[str, dict] = defaultdict(lambda: {"Horas": 0.0, "Receita (R$)": 0.0})

    for m in metrics_list:
        if float(m.worked_hours) > 0:
            totals[m.company_name]["Horas"]        += float(m.worked_hours)
            totals[m.company_name]["Receita (R$)"] += float(m.actual_revenue)

    if not totals:
        st.info("Sem dados no período.")
        return

    df = (
        pd.DataFrame([{"Contrato": k, **v} for k, v in totals.items()]).sort_values("Horas", ascending=False)
    )

    t1, t2 = st.tabs(["Receita", "Horas"])
    with t1:
        st.bar_chart(df.set_index("Contrato")["Receita (R$)"])
    with t2:
        st.bar_chart(df.set_index("Contrato")["Horas"])
        


# ---------------------------------------------------------------------------
# Line chart — evolução mensal
# ---------------------------------------------------------------------------

def _render_monthly_evolution(session, contract_id: int, year: int) -> None:
    ct    = session.get(Contract, contract_id)
    label = (
        f"{ct.company.name if ct and ct.company else '?'} — {ct.contract_number or 'S/N'}"
        if ct else f"#{contract_id}"
    )
    st.subheader(f"📈 Evolução por Mês/Ano") # — {label}")

    ev = get_monthly_evolution(session, contract_id, year)
    if not ev:
        st.info("Sem dados de evolução.")
        return

    df = pd.DataFrame([{
        "Mês":               date(e.year, e.month, 1).strftime("%b/%Y"),
        "Horas Trabalhadas": float(e.worked_hours),
        "Horas Esperadas":   float(e.expected_hours),
        "Receita Realizada": float(e.actual_revenue),
        "Receita Esperada":  float(e.expected_revenue),
        "Produtividade (%)": float(e.productivity),
    } for e in ev])

    t1, t2, t3 = st.tabs(["Horas", "Receita", "Produtividade"])
    with t1:
        st.line_chart(df.set_index("Mês")[["Horas Trabalhadas", "Horas Esperadas"]])
    with t2:
        st.line_chart(df.set_index("Mês")[["Receita Realizada", "Receita Esperada"]])
    with t3:
        st.line_chart(df.set_index("Mês")["Produtividade (%)"])
        st.caption("🔴 < 100% abaixo da meta | 🟢 ≥ 100% acima da meta")


# ---------------------------------------------------------------------------
# Detalhe diário
# ---------------------------------------------------------------------------

def _render_daily_detail(session, contract_id: int, year: int, month: int) -> None:
    ct    = session.get(Contract, contract_id)
    label = f"{ct.company.name if ct and ct.company else '?'}" if ct else f"#{contract_id}"
    st.subheader(
        f"📅 Detalhe Diário — {label} ({date(year, month, 1).strftime('%B/%Y').capitalize()})"
    )

    daily = get_daily_revenue(session, contract_id, year, month)
    if not daily:
        st.info("Sem apontamentos no período.")
        return

    df = pd.DataFrame([{
        "Data":         d.date.strftime("%d/%m/%Y"),
        "Horas":        float(d.worked_hours),
        "Receita (R$)": float(d.revenue),
    } for d in daily])

    c1, c2 = st.columns(2)
    with c1:
        st.bar_chart(df.set_index("Data")["Horas"])
    with c2:
        st.bar_chart(df.set_index("Data")["Receita (R$)"])

    with st.expander("Ver tabela"):
        df2 = df.copy()
        df2["Horas"]        = df2["Horas"].apply(lambda x: f"{x:.2f}h")
        df2["Receita (R$)"] = df2["Receita (R$)"].apply(lambda x: f"R$ {x:,.2f}")
        st.dataframe(df2, use_container_width=True, hide_index=True)
        th = sum(d.worked_hours for d in daily)
        tr = sum(d.revenue      for d in daily)
        st.metric("Total horas",   f"{float(th):.2f}h")
        st.metric("Total receita", f"R$ {float(tr):,.2f}")
