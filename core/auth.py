import hashlib
import hmac
import os
import warnings
from datetime import datetime, timedelta, timezone

import jwt
import streamlit as st
import streamlit.components.v1 as components

from core.env import is_uat

_COOKIE_NAME = "wt_session"
_SESSION_HOURS = 8


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def _jwt_secret() -> str:
    """Deriva uma chave de 64 chars (32 bytes) via SHA-256 para satisfazer RFC 7518."""
    raw = os.getenv("SESSION_SECRET") or os.getenv("APP_PASSWORD") or "dev-only-secret"
    return hashlib.sha256(raw.encode()).hexdigest()


def _generate_token() -> str:
    payload = {
        "auth": True,
        "exp": datetime.now(tz=timezone.utc) + timedelta(hours=_SESSION_HOURS),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm="HS256")


def _verify_token(token: str) -> bool:
    try:
        jwt.decode(token, _jwt_secret(), algorithms=["HS256"])
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------

def _read_cookie() -> str | None:
    try:
        return st.context.cookies.get(_COOKIE_NAME)
    except Exception:
        return None


def _inject_js(script: str) -> None:
    """Injeta JS via iframe (mesmo domínio). Suprime o aviso de deprecação de
    st.components.v1.html: st.iframe só aceita src URL e data: URIs são
    cross-origin, impossibilitando acesso a window.parent."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        components.html(f"<script>{script}</script>", height=0)


def _cookie_js(name: str, value: str, max_age: int) -> str:
    """Gera JS que define o cookie de forma robusta em HTTP e HTTPS.

    - Usa SameSite=Lax (compatível com HTTPS sem precisar do flag Strict)
    - Adiciona Secure automaticamente quando servido via HTTPS (PROD)
    - Tenta document.cookie (iframe same-origin) e window.parent como fallback
    """
    return f"""
(function() {{
    var c = "{name}={value}; max-age={max_age}; path=/; SameSite=Lax";
    if (window.location.protocol === "https:") c += "; Secure";
    document.cookie = c;
    try {{ window.parent.document.cookie = c; }} catch(e) {{}}
}})();
"""


def _write_cookie(token: str) -> None:
    """Grava o cookie de sessão no run em que NÃO há st.rerun() pendente."""
    _inject_js(_cookie_js(_COOKIE_NAME, token, _SESSION_HOURS * 3600))


def _clear_cookie() -> None:
    _inject_js(_cookie_js(_COOKIE_NAME, "", 0))


# ---------------------------------------------------------------------------
# Password resolution
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_password() -> bool:
    # — Executa ações de cookie pendentes do run anterior (sem st.rerun ativo) —
    # Gravar ou limpar o cookie aqui garante que o JS é renderizado num run
    # estável, sem ser descartado por um rerun imediato.
    action = st.session_state.pop("_cookie_action", None)
    if action == "write":
        _write_cookie(_generate_token())
    elif action == "clear":
        _clear_cookie()

    # 1. Sessão já autenticada neste run
    if st.session_state.get("password_correct", False):
        return True

    # 2. Cookie válido → restaura sessão sem exigir senha
    token = _read_cookie()
    if token and _verify_token(token):
        st.session_state["password_correct"] = True
        return True

    # 3. Exibe formulário de login
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
            # Agenda a gravação do cookie para o próximo run (após o rerun abaixo)
            st.session_state["_cookie_action"] = "write"
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
        # Agenda a limpeza do cookie para o próximo run
        st.session_state["_cookie_action"] = "clear"
        st.rerun()
