"""
app.py — Entry point do Work Track (Streamlit).
"""
import sys, os
import streamlit as st
from database.connection import init_db
from ui.styles import inject_styles

#--- Page configuration -----------------
st.set_page_config(
    page_title="Work Track",
    page_icon="⏱️",
    layout="wide",
    initial_sidebar_state="expanded",
)

#--- Initialize db when connect -----------------
init_db()
inject_styles()
sys.path.insert(0, os.path.dirname(__file__))

#--- Sidebar -----------------
with st.sidebar:
    st.title("⏱️ Work Track")
    st.caption("Controle de Horas & Faturamento")
    st.divider() 
    
    st.markdown("""
        <style>
        div[data-baseweb="tag"] {
            display: block !important;
            width: 100% !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    page = st.pills(
        "Navegação",
        [
            "📊 Dashboard",
            "⏱️ Controle de Horas",
            "🧾 Notas Fiscais",
            "🗂️ Cadastros",
        ],
        label_visibility="collapsed",
        default="📊 Dashboard",
    )
    
    st.divider()                
    
    st.markdown(
        """
        <div style="position: fixed; bottom: 20px; width: 250px;">                        
            <p style="font-size: 12px;">Powered by LF Analytics © 2026</p>
        </div>
        """,
        unsafe_allow_html=True
    )


#--- Page routing -----------------
if page is None or page == "📊 Dashboard":
    from ui.dashboard import render_dashboard
    render_dashboard()

elif page == "⏱️ Controle de Horas":
    from ui.worklog_form import render_worklog_form
    render_worklog_form()

elif page == "🧾 Notas Fiscais":
    from ui.invoice_form import render_invoice_form
    render_invoice_form()

elif page == "🗂️ Cadastros":
    from ui.company_form import render_company_form
    render_company_form()
