"""Price service for price management."""

from datetime import date
from sqlmodel import select
from backend.db.models import Asset, Price
from backend.services.base import BaseService
from decimal import Decimal


class PriceService(BaseService):
    """Service for price management."""

    def get_latest_price(
        self, asset_id: int, as_of_date: date = None
    ) -> Price | None:
        """Get the latest price for an asset."""
        if as_of_date is None:
            as_of_date = date.today()

        # Check if this is a cash asset
        asset = self.session.get(Asset, asset_id)
        if asset and asset.type == "cash":
            # Cash assets always have a price of 1.0
            return Price(
                asset_id=asset_id,
                price_date=as_of_date,
                price=Decimal("1.0"),
                price_type="real_time",
                source="system",
            )

        price = self.session.exec(
            select(Price)
            .where(Price.asset_id == asset_id)
            .where(Price.price_date <= as_of_date)
            .order_by(Price.price_date.desc())
        ).first()

        return price

    def get_latest_prices(
        self, asset_ids: list[int], as_of_date: date = None
    ) -> dict[int, Price | None]:
        """Batch fetch latest prices for multiple assets.

        Returns a dict mapping asset_id to its latest Price (or None).
        Cash assets always return a synthetic Price with price=1.0.
        """
        if as_of_date is None:
            as_of_date = date.today()

        result: dict[int, Price | None] = {}

        # Batch fetch assets to identify cash types
        assets_map = self.get_asset_map(asset_ids)

        non_cash_ids: list[int] = []
        for asset_id, asset in assets_map.items():
            if asset.type == "cash":
                result[asset_id] = Price(
                    asset_id=asset.id,
                    price_date=as_of_date,
                    price=Decimal("1.0"),
                    price_type="real_time",
                    source="system",
                )
            else:
                non_cash_ids.append(asset.id)

        if not non_cash_ids:
            return result

        from sqlalchemy import func

        subq = (
            select(Price.asset_id, func.max(Price.price_date).label("max_date"))
            .where(Price.asset_id.in_(non_cash_ids))
            .where(Price.price_date <= as_of_date)
            .group_by(Price.asset_id)
            .subquery()
        )

        prices = self.session.exec(
            select(Price)
            .join(
                subq,
                (Price.asset_id == subq.c.asset_id)
                & (Price.price_date == subq.c.max_date),
            )
        ).all()

        for price in prices:
            result[price.asset_id] = price

        for aid in non_cash_ids:
            if aid not in result:
                result[aid] = None

        return result

    def get_price_history(
        self, asset_id: int, start_date: date, end_date: date
    ) -> list[Price]:
        """Get price history for an asset."""
        prices = self.session.exec(
            select(Price)
            .where(Price.asset_id == asset_id)
            .where(Price.price_date >= start_date)
            .where(Price.price_date <= end_date)
            .order_by(Price.price_date)
        ).all()

        return prices
