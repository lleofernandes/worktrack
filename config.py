"""
config.py — Configuração central da aplicação Work Track.
# Exemplos para outros bancos:
#   PostgreSQL:  postgresql+psycopg2://user:pass@host:5432/worktrack
#   SQL Server:  mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+17+for+SQL+Server
#   MySQL:       mysql+pymysql://user:pass@host:3306/worktrack
"""

import os
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()

APP_NAME = "Work Track"
APP_VERSION = "1.1.0"

MAX_HOURS_PER_DAY = 24
HOURS_PER_BUSINESS_DAY = 8

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
# DB_PASSWORD = quote_plus(os.getenv("DB_PASSWORD", ""))
DB_DRIVER = os.getenv("DB_DRIVER", "postgresql+psycopg2")

required_vars = {
    "DB_HOST": DB_HOST,
    "DB_PORT": DB_PORT,
    "DB_NAME": DB_NAME,
    "DB_USER": DB_USER,
    "DB_PASSWORD": DB_PASSWORD,
}

missing_vars = [k for k, v in required_vars.items() if not v]
if missing_vars:
    raise ValueError(
        f"Variáveis obrigatórias do PostgreSQL não definidas: {', '.join(missing_vars)}"
    )

DATABASE_URL = f"{DB_DRIVER}://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"