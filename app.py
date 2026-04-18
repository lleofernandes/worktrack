"""
app.py — Entry point do Work Track (Streamlit).
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from database.connection import init_db

st.set_page_config(
    page_title="Work Track",
    page_icon="⏱️",
    layout="wide",
)

init_db()

with st.sidebar:
    st.title("⏱️ Work Track")
    st.caption("Controle de horas & faturamento")
    st.divider()
    page = st.radio(
        "Menu",
        options=["📊 Dashboard", "⏱️ Controle de Horas", "🧾 Notas Fiscais"],
        index=0,
    )
    st.divider()
    st.caption("v1.0.0 — Etapa 5")

if page == "⏱️ Controle de Horas":
    from ui.worklog_form import render_worklog_form
    render_worklog_form()

elif page == "🧾 Notas Fiscais":
    from ui.invoice_form import render_invoice_form
    render_invoice_form()

elif page == "📊 Dashboard":
    from ui.dashboard import render_dashboard
    render_dashboard()
