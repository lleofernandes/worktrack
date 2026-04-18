"""
config.py — Configuração central da aplicação Work Track.
Troca de banco: basta alterar a env var DATABASE_URL.
"""
import os

# SQLite (local, padrão MVP)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///worktrack.db")

# Exemplos para outros bancos (setar a env var DATABASE_URL):
#   PostgreSQL:  postgresql://user:pass@host:5432/worktrack
#   SQL Server:  mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+17+for+SQL+Server
#   MySQL:       mysql+pymysql://user:pass@host:3306/worktrack

APP_NAME = "Work Track"
APP_VERSION = "0.1.0"

# Horas máximas permitidas por registro (validação)
MAX_HOURS_PER_DAY = 24

# Horas esperadas por dia útil
HOURS_PER_BUSINESS_DAY = 8
