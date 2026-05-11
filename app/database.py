from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import StaticPool
from dotenv import load_dotenv
import os
from app import neon_dbapi

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def _neon_creator():
    return neon_dbapi.connect(DATABASE_URL)


engine = create_engine(
    "postgresql+psycopg2://localhost/neondb",
    creator=_neon_creator,
    poolclass=StaticPool,
    echo=False,
)

# Strip all psycopg2-specific on_connect hooks (UUID/hstore registration, etc.)
engine.pool.dispatch.connect.clear()

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
