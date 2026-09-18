"""Base service class with common functionality."""

from collections.abc import Iterable
from sqlmodel import Session, select
from backend.db import get_engine
from backend.db.models import Asset


class BaseService:
    """Base service class with session management."""

    def __init__(self, session: Session | None = None):
        """Initialize service with optional session.

        Args:
            session: Optional database session. If not provided, a new session will be created.
        """
        self._own_session = session is None
        self.session = session or Session(get_engine())

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with automatic commit/rollback."""
        if self._own_session:
            if exc_type:
                self.session.rollback()
            else:
                self.session.commit()
            self.session.close()

    def commit(self):
        """Commit current transaction."""
        self.session.commit()

    def rollback(self):
        """Rollback current transaction."""
        self.session.rollback()

    def refresh(self, obj):
        """Refresh object from database."""
        self.session.refresh(obj)

    def get_asset_map(self, asset_ids: Iterable[int]) -> dict[int, Asset]:
        """Batch fetch assets by id list, returning an {id: Asset} map.

        Avoids N+1 queries when multiple assets need to be looked up.
        Returns an empty dict when asset_ids is empty.
        """
        ids = list(asset_ids)
        if not ids:
            return {}
        assets = self.session.exec(
            select(Asset).where(Asset.id.in_(ids))
        ).all()
        return {a.id: a for a in assets}
