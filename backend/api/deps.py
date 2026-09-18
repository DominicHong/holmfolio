"""Dependencies for API endpoints."""

from fastapi import Depends, HTTPException
from sqlmodel import Session
from backend.db import get_session


def get_db_session():
    """Get database session dependency."""
    return get_session()


SessionDep = Depends(get_db_session)
