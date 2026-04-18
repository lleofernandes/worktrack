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

st.title("⏱️ Work Track")
st.success("✅ Banco de dados inicializado com sucesso.")
st.info("Etapa 1 concluída — models e conexão prontos.")
