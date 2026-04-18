import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from datetime import date
from decimal import Decimal
from collections import defaultdict

from database.models import Contract
from services.analytics_service import (    
    get_monthly_evolution,
    get_monthly_metrics,
)
from database.repository import ContractRepository
from database.models import Invoice, Contract

#-- global variables
today = date.today()
# years_range = list(range(today.year - 2, today.year + 1))
years_range = list(range(2021, today.year + 1))


def _get_invoice_data(session):    
    rows = (
        session.query(Invoice, Contract)
        .join(Contract, Invoice.contract_id == Contract.id)
        .filter(Invoice.amount > 0)
        .all()
    )

    by_year:   dict[int, Decimal]  = defaultdict(Decimal)
    by_client: dict[str, Decimal]  = defaultdict(Decimal)

    for inv, ct in rows:
        yr      = inv.issue_date.year
        client  = (
            ct.company.fantasy_name or ct.company.name 
            if ct.company else f"Contrato #{ct.id}"
        )
        by_year[yr]      += inv.amount
        by_client[client] += inv.amount

    return dict(by_year), dict(by_client)




# Line chart — evolução mensal
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
        

#----------------------------------------------------
"""
dash_linechart_annual.py — Evolução anual de receita por empresa (sem vínculo com filtros).
"""

def _get_annual_revenue_by_company(session) -> dict[str, dict[int, Decimal]]:
    """
    Considera todos os contratos (ativos e inativos).
    """
    contracts = ContractRepository.get_all(session, active_only=None)    
    years     = years_range

    # Agrupa por empresa → ano → receita
    data: dict[str, dict[int, Decimal]] = {}

    for ct in contracts:
        company = ct.company.name if ct.company else f"Contrato #{ct.id}"
        if company not in data:
            data[company] = {yr: Decimal("0") for yr in years}

        for yr in years:
            for mo in range(1, 13):
                if date(yr, mo, 1) > today:
                    break
                m = get_monthly_metrics(session, ct.id, yr, mo)
                data[company][yr] += m.actual_revenue

    # DEBUG — remover depois
    # print(f"[DEBUG] Total contratos carregados: {len(contracts)}")
    # for ct in contracts:
    #     print(f"  → id={ct.id} | {ct.contract_number} | end_date={ct.end_date} | empresa={ct.company.name if ct.company else '?'}")
    
    return data


def render_annual_revenue_linechart(session) -> None:
    data_year, data_client = _get_invoice_data(session)
    
    st.subheader("📈 Total Faturado por Ano")

    years  = sorted(data_year.keys())
    y_vals = [float(data_year[yr]) for yr in years]

    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(
        x=years,
        y=y_vals,
        mode="lines+markers+text",
        line=dict(color="#4f98a3", width=2.5),
        marker=dict(size=9, color="#4f98a3"),
        text=[f"R$ {v:,.0f}" for v in y_vals],
        textposition="top center",
        textfont=dict(size=11),
        hovertemplate="Ano: %{x}<br>Total: R$ %{y:,.2f}<extra></extra>",
    ))

    fig_line.update_layout(
        xaxis=dict(
            tickvals=years,
            ticktext=[str(y) for y in years],
            title="Ano",
            gridcolor="rgba(255,255,255,0.08)",
        ),
        yaxis=dict(
            title="Receita (R$)",
            tickprefix="R$ ",
            tickformat=",.0f",
            gridcolor="rgba(255,255,255,0.08)",
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cdccca"),
        margin=dict(t=40, b=40, l=10, r=10),
        showlegend=False,
    )
    st.plotly_chart(fig_line, width="stretch")