from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

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

from components.dash_linechart import _render_monthly_evolution



# ---------------------------------------------------------------------------
# Bar chart — reutiliza metrics_list
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
        "Ordem":        d.date.toordinal(),
        "Horas":        float(d.worked_hours),
        "Receita (R$)": float(d.revenue),
    } for d in daily])
    
    df = df.sort_values("Ordem").drop(columns=["Ordem"])

    c1, c2 = st.columns(2)
    with c1:
        st.bar_chart(df.set_index("Data")["Horas"])
    with c2:
        st.bar_chart(df.set_index("Data")["Receita (R$)"])

    with st.expander("Ver tabela"):
        df2 = df.copy()
        df2["Horas"]        = df2["Horas"].apply(lambda x: f"{x:.2f}h")
        df2["Receita (R$)"] = df2["Receita (R$)"].apply(lambda x: f"R$ {x:,.2f}")
        st.dataframe(df2, width='stretch', hide_index=True)
        th = sum(d.worked_hours for d in daily)
        tr = sum(d.revenue      for d in daily)
        st.metric("Total horas",   f"{float(th):.2f}h")
        st.metric("Total receita", f"R$ {float(tr):,.2f}")