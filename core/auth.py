import hmac
import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

def check_password():
    if st.session_state.get("password_correct", False):
        return True

    def password_entered():
        password = st.session_state.get("password", "")
        expected = os.getenv("APP_PWRD", "")

        if expected and hmac.compare_digest(password, expected):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    st.subheader("🔐 Acesso restrito")
    st.caption("Uso pessoal")

    with st.form("login_form", clear_on_submit=False):
        st.text_input("Senha", type="password", key="password")
        submitted = st.form_submit_button("Entrar")
        if submitted:
            password_entered()

    if st.session_state.get("password_correct", False):
        return True

    if "password_correct" in st.session_state:
        st.error("Senha incorreta")

    return False


def logout_button():
    if st.button("Sair"):
        st.session_state["password_correct"] = False
        st.rerun()