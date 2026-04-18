"""
connection.py — Gerenciamento de conexão via SQLAlchemy.
Suporta: SQLite, PostgreSQL, SQL Server, MySQL.
Preparado para Alembic (migrations futuras).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import DATABASE_URL


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str = DATABASE_URL):
    """
    Cria o engine SQLAlchemy.
    connect_args com check_same_thread apenas para SQLite.
    """
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}

    return create_engine(
        database_url,
        connect_args=connect_args,
        echo=False,  # Altere para True para debug de SQL
    )


engine = build_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def get_session():
    """
    Context manager de sessão.

    Uso:
        with get_session() as session:
            session.add(obj)
            session.commit()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """
    Cria todas as tabelas no banco (idempotente).
    Em produção, substituir por Alembic migrations.
    """
    from database import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
