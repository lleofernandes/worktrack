# pip install sqlalchemy psycopg2-binary
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


DATABASE_URL = st.secrets["DATABASE_URL"]

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_session():
    return SessionLocal()


def init_db():
    from database.models import Company, WorkLog, Invoice
    Base.metadata.create_all(bind=engine)