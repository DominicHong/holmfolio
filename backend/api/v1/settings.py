"""Settings API endpoints."""

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select

from backend.db import get_session
from backend.db.models import Settings
from backend.api.models import SettingsResponse

router = APIRouter()


@router.get("/{key}", response_model=SettingsResponse)
def get_setting(key: str, session: Session = Depends(get_session)):
    """Get a specific setting by key."""
    setting = session.exec(select(Settings).where(Settings.key == key)).first()
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")
    return setting


@router.post("/", response_model=SettingsResponse)
def create_or_update_setting(setting: Settings, session: Session = Depends(get_session)):
    """Create or update a setting."""
    existing_setting = session.exec(
        select(Settings).where(Settings.key == setting.key)
    ).first()

    if existing_setting:
        existing_setting.value = setting.value
        existing_setting.description = setting.description
        existing_setting.updated_at = datetime.now(timezone.utc)
        session.add(existing_setting)
        session.commit()
        session.refresh(existing_setting)
        return existing_setting
    else:
        setting.created_at = datetime.now(timezone.utc)
        setting.updated_at = datetime.now(timezone.utc)
        session.add(setting)
        session.commit()
        session.refresh(setting)
        return setting


@router.get("/", response_model=list[SettingsResponse])
def get_all_settings(session: Session = Depends(get_session)):
    """Get all settings."""
    settings = session.exec(select(Settings)).all()
    return settings
