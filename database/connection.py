from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from core.env import get_database_url

DATABASE_URL = get_database_url()

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_session():
    return SessionLocal()


def init_db():
    from database.models import Company, WorkLog, Invoice  # noqa: F401
    Base.metadata.create_all(bind=engine)
