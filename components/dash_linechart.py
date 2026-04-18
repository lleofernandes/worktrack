import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from datetime import date

from database.models import Contract
from services.analytics_service import (
    get_all_contracts_metrics,
    get_daily_revenue,
    get_monthly_evolution,
    get_monthly_metrics,
)

# ---------------------------------------------------------------------------
# Line chart — evolução mensal
# ---------------------------------------------------------------------------

def _render_monthly_evolution(session, contract_id: int, year: int) -> None:
    ct    = session.get(Contract, contract_id)
    st.subheader("📈 Evolução por Mês/Ano")

    ev = get_monthly_evolution(session, contract_id, year)
    if not ev:
        st.info("Sem dados de evolução.")
        return

    ev_sorted = sorted(ev, key=lambda e: (e.year, e.month))

    df = pd.DataFrame([{
        "Mês":               date(e.year, e.month, 1).strftime("%b/%Y"),
        "Horas Trabalhadas": float(e.worked_hours),
        "Horas Esperadas":   float(e.expected_hours),
        "Receita Realizada": float(e.actual_revenue),
        "Receita Esperada":  float(e.expected_revenue),
        "Produtividade (%)": float(e.productivity),
    } for e in ev_sorted])

    t1, t2, t3 = st.tabs(["Receita", "Horas", "Produtividade"])

    with t1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["Mês"], y=df["Receita Realizada"], name="Receita Realizada", mode="lines+markers+text", text=df["Receita Realizada"], textposition="top center", texttemplate="%{y:,.0f}"))
        fig.add_trace(go.Scatter(x=df["Mês"], y=df["Receita Esperada"],  name="Receita Esperada",  mode="lines+markers+text", text=df["Receita Esperada"],  textposition="bottom center", texttemplate="%{y:,.0f}"))
        fig.update_layout(xaxis={"categoryorder": "array", "categoryarray": df["Mês"].tolist()})        
        st.plotly_chart(fig, width='stretch')

    with t2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["Mês"], y=df["Horas Trabalhadas"], name="Horas Trabalhadas", mode="lines+markers"))
        fig.add_trace(go.Scatter(x=df["Mês"], y=df["Horas Esperadas"],   name="Horas Esperadas",   mode="lines+markers"))
        fig.update_layout(xaxis={"categoryorder": "array", "categoryarray": df["Mês"].tolist()})
        st.plotly_chart(fig, width='stretch')

    with t3:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["Mês"], y=df["Produtividade (%)"], name="Produtividade (%)", mode="lines+markers"))
        fig.update_layout(xaxis={"categoryorder": "array", "categoryarray": df["Mês"].tolist()})
        st.plotly_chart(fig, width='stretch')
        st.caption("🔴 < 100% abaixo da meta | 🟢 ≥ 100% acima da meta")