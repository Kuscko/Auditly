"""Database layer for RapidRMF."""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# Declarative base for all ORM models
Base = declarative_base()

# Session factories (lazy-loaded in config)
_async_engine = None
_async_session_factory = None
_sync_engine = None
_sync_session_factory = None


async def get_async_session() -> AsyncSession:
    """Get an async database session."""
    global _async_session_factory
    if _async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    async with _async_session_factory() as session:
        yield session


def get_sync_session():
    """Get a sync database session."""
    global _sync_session_factory
    if _sync_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db_sync() first.")
    return _sync_session_factory()


def init_db_async(database_url: str):
    """Initialize async database engine and session factory."""
    global _async_engine, _async_session_factory
    _async_engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)
    _async_session_factory = sessionmaker(_async_engine, class_=AsyncSession, expire_on_commit=False)


def init_db_sync(database_url: str):
    """Initialize sync database engine and session factory."""
    global _sync_engine, _sync_session_factory
    _sync_engine = create_engine(database_url, echo=False, pool_pre_ping=True)
    _sync_session_factory = sessionmaker(_sync_engine)


def get_async_engine():
    """Get the async engine."""
    global _async_engine
    if _async_engine is None:
        raise RuntimeError("Async database not initialized. Call init_db_async() first.")
    return _async_engine


def get_sync_engine():
    """Get the sync engine."""
    global _sync_engine
    if _sync_engine is None:
        raise RuntimeError("Sync database not initialized. Call init_db_sync() first.")
    return _sync_engine
