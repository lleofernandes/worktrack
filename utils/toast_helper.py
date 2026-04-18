"""
toast_helper.py — Exibe toasts persistentes entre reruns via session_state.
"""
import streamlit as st


def set_toast(message: str, icon: str = "✅") -> None:
    """Registra um toast para ser exibido após o próximo rerun."""
    st.session_state["_pending_toast"] = {"message": message, "icon": icon}


def show_pending_toast() -> None:
    """Chama no topo de cada página para exibir toast pendente."""
    key = "_pending_toast"
    if key in st.session_state:
        data = st.session_state.pop(key)
        st.toast(data["message"], icon=data["icon"])
