import sys
import os
from app import neon_dbapi

# Patch psycopg2 with our HTTP-based DBAPI before SQLAlchemy loads the dialect.
# Avoids binary psycopg2 dependency in serverless environments (Vercel).
if "psycopg2" not in sys.modules:
    sys.modules["psycopg2"] = neon_dbapi
    sys.modules["psycopg2.extras"] = neon_dbapi.extras
    sys.modules["psycopg2.extensions"] = neon_dbapi.extensions

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import StaticPool
from dotenv import load_dotenv

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
