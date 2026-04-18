"""
Fonte: tabela invoices (amount > 0) — independente de filtros e contratos.
"""
from __future__ import annotations

from decimal import Decimal
from collections import defaultdict

import plotly.graph_objects as go
import streamlit as st

from database.models import Invoice, Contract


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


def render_annual_charts(session) -> None:
    data_year, data_client = _get_invoice_data(session)

    if not data_year:
        st.info("Sem dados de faturamento para exibir.")
        return
            
    st.subheader("🏢 Faturamento por Cliente")

    # Ordena do maior para o menor    
    clients = sorted(data_client, key=lambda c: data_client[c], reverse=False)
    values  = [float(data_client[c]) for c in clients]

    colors = [
        "#4f98a3", "#e8af34", "#6daa45",
        "#a86fdf", "#dd6974", "#fdab43",
    ]

    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        x=values,
        y=clients,
        orientation="h",
        marker_color=[colors[i % len(colors)] for i in range(len(clients))],
        text=[f"R$ {v:,.0f}" for v in values],
        textposition="outside",
        textfont=dict(size=11),
        hovertemplate="%{y}<br>Total: R$ %{x:,.2f}<extra></extra>",
    ))

    fig_bar.update_layout(
        xaxis=dict(
            title="Receita (R$)",
            tickprefix="R$ ",
            tickformat=",.0f",
            gridcolor="rgba(255,255,255,0.08)",
        ),
        yaxis=dict(
            gridcolor="rgba(255,255,255,0.08)",
            automargin=True,
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cdccca"),
        margin=dict(t=40, b=40, l=10, r=80),
        showlegend=False,
    )
    st.plotly_chart(fig_bar, width="stretch")