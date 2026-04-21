from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from database.models import Contract

from services.analytics_service import (
    get_daily_revenue,

)



# ---------------------------------------------------------------------------
# Bar chart — reutiliza metrics_list
# ---------------------------------------------------------------------------

def _render_hours_by_contract_from_metrics(metrics_list) -> None:
    st.subheader("📊 Horas por Contrato")

    totals: dict[str, dict] = defaultdict(lambda: {"Horas": 0.0, "Receita": 0.0})

    for m in metrics_list:
        if float(m.worked_hours) > 0:
            totals[m.company_name]["Horas"]   += float(m.worked_hours)
            totals[m.company_name]["Receita"] += float(m.actual_revenue)

    if not totals:
        st.info("Sem dados no período.")
        return

    df = (
        pd.DataFrame([{"Contrato": k, **v} for k, v in totals.items()])
        .sort_values("Horas", ascending=False)
    )

    colors = [
        "#4f98a3", "#e8af34", "#6daa45",
        "#a86fdf", "#dd6974", "#fdab43",
    ]
    bar_colors = [colors[i % len(colors)] for i in range(len(df))]

    def _make_bar(col, prefix, fmt):
        fig = go.Figure(go.Bar(
            x=df["Contrato"],
            y=df[col],
            marker_color=bar_colors,
            text=[f"{prefix}{v:{fmt}}" for v in df[col]],
            textposition="outside",
            textfont=dict(size=11),
            hovertemplate=f"%{{x}}<br>{col}: {prefix}%{{y:{fmt}}}<extra></extra>",
        ))
        fig.update_layout(
            xaxis=dict(gridcolor="rgba(255,255,255,0.08)"),
            yaxis=dict(
                gridcolor="rgba(255,255,255,0.08)",
                tickprefix=prefix,
                tickformat=fmt,
            ),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#cdccca"),
            margin=dict(t=40, b=40, l=10, r=10),
            showlegend=False,
        )
        return fig

    t1, t2 = st.tabs(["Receita", "Horas"])
    with t1:
        st.plotly_chart(_make_bar("Receita", "R$ ", ",.0f"), width="stretch")
    with t2:
        st.plotly_chart(_make_bar("Horas", "", ".1f"), width="stretch")
        
        

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