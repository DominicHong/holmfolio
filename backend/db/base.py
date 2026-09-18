"""Database base configuration and session management."""

from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import event
import os

# Database setup - ROOT_PATH is backend/ directory
ROOT_PATH = os.path.dirname(os.path.dirname(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(ROOT_PATH, 'portfolio.db')}"

# Data directory - project root data/ folder
DATA_PATH = os.path.join(os.path.dirname(ROOT_PATH), "data")

# Singleton engine instance
_engine = None


def enable_sqlite_fk(dbapi_connection, connection_record):
    """Enable foreign key enforcement for SQLite connections.

    SQLite does not enforce foreign keys unless this pragma is set
    on every new connection.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_engine():
    """Get the singleton database engine instance."""
    global _engine
    if _engine is None:
        _engine = create_engine(DATABASE_URL, echo=False)
        event.listen(_engine, "connect", enable_sqlite_fk)
    return _engine


def create_db_and_tables():
    """Create database and tables."""
    SQLModel.metadata.create_all(get_engine())


def drop_db_and_tables():
    """Drop database and tables."""
    SQLModel.metadata.drop_all(get_engine())


def get_session():
    """Get database session."""
    with Session(get_engine()) as session:
        yield session
