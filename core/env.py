import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

DEFAULT_SQLITE_URL = "sqlite:///./worktrack.db"


def get_app_env() -> str:
    return os.getenv("APP_ENV", "PROD").strip().upper()


def is_uat() -> bool:
    return get_app_env() == "UAT"


def _database_url_from_env() -> str | None:
    return os.getenv("DATABASE_URL")


def _database_url_from_secrets() -> str | None:
    try:
        if "DATABASE_URL" in st.secrets:
            return st.secrets["DATABASE_URL"]
    except Exception:
        pass

    try:
        if "database" in st.secrets and "url" in st.secrets["database"]:
            return st.secrets["database"]["url"]
    except Exception:
        pass

    return None


def get_database_url() -> str:
    if is_uat():
        return _database_url_from_env() or DEFAULT_SQLITE_URL

    url = _database_url_from_secrets() or _database_url_from_env()
    if url:
        return url

    raise ValueError(
        "DATABASE_URL não configurada. "
        "Defina DATABASE_URL ou database.url nos secrets do Streamlit Cloud."
    )
