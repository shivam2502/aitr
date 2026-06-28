"""
database.py — Async SQLAlchemy engine and session factory.
Import `get_db` as a FastAPI dependency in route files.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# Load .env from the backend directory
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set — check backend/.env")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,        # set True to log SQL queries during development
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    """FastAPI dependency — yields an AsyncSession and closes it after the request."""
    async with SessionLocal() as session:
        yield session


async def create_tables():
    """Call once on startup to create all tables if they don't exist."""
    # Import models so Base.metadata knows about them
    import backend.db.models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
