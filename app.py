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

from ui.styles import inject_styles
inject_styles()

with st.sidebar:
    st.title("⏱️ Work Track")
    st.caption("Controle de Horas & Faturamento")
    st.divider()
    # page = st.radio(
    #     "Menu",
    #     options=[
    #         "📊 Dashboard",
    #         "⏱️ Controle de Horas",
    #         "🧾 Notas Fiscais",
    #         "🗂️ Cadastros",
    #     ],
    #     index=0,                
    # )
    
    st.markdown("""
        <style>
        div[data-baseweb="tag"] {
            display: block !important;
            width: 100% !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    page = st.pills(
        "",
        [
            "📊 Dashboard",
            "⏱️ Controle de Horas",
            "🧾 Notas Fiscais",
            "🗂️ Cadastros",
        ]
    )

    
    st.divider()            
    
    st.caption("v1.0.0")
    
    st.markdown(
        """
        <div style="position: fixed; bottom: 20px; width: 250px;">                        
            <p style="font-size: 12px;">© 2026 LF Analytics</p>
        </div>
        """,
        unsafe_allow_html=True
    )

if page == "⏱️ Controle de Horas":
    from ui.worklog_form import render_worklog_form
    render_worklog_form()

elif page == "🧾 Notas Fiscais":
    from ui.invoice_form import render_invoice_form
    render_invoice_form()

elif page == "📊 Dashboard":
    from ui.dashboard import render_dashboard
    render_dashboard()

elif page == "🗂️ Cadastros":
    from ui.company_form import render_company_form
    render_company_form()
