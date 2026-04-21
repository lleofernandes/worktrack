"""
connection.py — Gerenciamento de conexão via SQLAlchemy.
Suporte atual: PostgreSQL.
Preparado para Alembic (migrations futuras).
"""

from __future__ import annotations
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

from core.config import DATABASE_URL


def build_engine(database_url: str = DATABASE_URL):
    if not database_url:
        raise ValueError("DATABASE_URL não foi definida.")

    if not database_url.startswith("postgresql"):
        raise ValueError(
            "DATABASE_URL inválida para este projeto. "
            "Use uma URL PostgreSQL, por exemplo: "
            "postgresql+psycopg2://user:password@host:5432/database"
        )

    return create_engine(
        database_url,
        pool_pre_ping=True,
        future=True,
        echo=False,
    )


engine = build_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    future=True,
)

Base = declarative_base()


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def test_connection() -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def init_db():
    """
    Cria todas as tabelas no PostgreSQL (idempotente).
    Em produção, substituir por Alembic migrations.
    """
    from database import models  # noqa: F401
    Base.metadata.create_all(bind=engine)