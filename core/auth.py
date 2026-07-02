import hmac
import os

import streamlit as st

from core.env import is_uat


def _password_from_secrets():
    try:
        if "APP_PASSWORD" in st.secrets:
            return st.secrets["APP_PASSWORD"]
    except Exception:
        pass

    try:
        if "auth" in st.secrets and "APP_PASSWORD" in st.secrets["auth"]:
            return st.secrets["auth"]["APP_PASSWORD"]
    except Exception:
        pass

    return None


def _password_from_env():
    return os.getenv("APP_PASSWORD")


def _get_app_password():
    if is_uat():
        return _password_from_env() or _password_from_secrets()

    return _password_from_secrets() or _password_from_env()


def check_password() -> bool:
    if st.session_state.get("password_correct", False):
        return True

    expected = _get_app_password()
    if not expected:
        st.error(
            "❌ APP_PASSWORD não configurada. "
            "Em UAT: defina APP_ENV=UAT e APP_PASSWORD no .env. "
            "Em PROD: configure nos secrets do Streamlit Cloud."
        )
        return False

    st.subheader("🔐 Acesso restrito")

    with st.form("login_form", clear_on_submit=False):
        st.text_input("Senha", type="password", key="password")
        submitted = st.form_submit_button("Entrar")

    if submitted:
        password = st.session_state.get("password", "")
        if hmac.compare_digest(password, expected):
            st.session_state["password_correct"] = True
            if "password" in st.session_state:
                del st.session_state["password"]
            st.rerun()
        else:
            st.session_state["password_correct"] = False
            st.error("❌ Senha incorreta")

    return False


def logout_button() -> None:
    if st.button("Sair"):
        st.session_state["password_correct"] = False
        st.rerun()
