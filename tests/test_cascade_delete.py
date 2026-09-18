"""Tests for cascade delete behavior of Asset, Tag, and TagCategory."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import event
from sqlmodel import create_engine, SQLModel, Session, select

from backend.db.base import enable_sqlite_fk
from backend.db.models import (
    Asset,
    AssetTag,
    Portfolio,
    Position,
    Price,
    StockInfo,
    Tag,
    TagCategory,
    Transaction,
)


def _add_asset_children(session: Session, asset: Asset, portfolio: Portfolio) -> None:
    """Attach one AssetTag, Price, Position, and StockInfo to an asset."""
    tag = Tag(name="CascadeTag")
    session.add(tag)
    session.flush()

    session.add(AssetTag(asset_id=asset.id, tag_id=tag.id, weight=Decimal("100")))
    session.add(
        Price(
            asset_id=asset.id,
            price_date=date(2024, 1, 2),
            price=Decimal("10.5"),
            price_type="historical",
        )
    )
    session.add(
        Position(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            position_date=date(2024, 1, 2),
            quantity=Decimal("100"),
            average_cost=Decimal("9"),
        )
    )
    session.add(
        StockInfo(
            asset_id=asset.id,
            symbol=asset.symbol,
            report_date=date(2024, 1, 2),
        )
    )
    session.commit()


def test_delete_asset_cascades_children(test_db):
    portfolio = test_db._test_portfolio
    asset = test_db._test_assets["600036.SH"]
    _add_asset_children(test_db, asset, portfolio)

    test_db.delete(asset)
    test_db.commit()

    assert test_db.get(Asset, asset.id) is None
    assert test_db.exec(select(AssetTag).where(AssetTag.asset_id == asset.id)).first() is None
    assert test_db.exec(select(Price).where(Price.asset_id == asset.id)).first() is None
    assert test_db.exec(select(Position).where(Position.asset_id == asset.id)).first() is None
    assert test_db.exec(select(StockInfo).where(StockInfo.asset_id == asset.id)).first() is None


def test_delete_asset_blocked_by_transactions(test_db):
    portfolio = test_db._test_portfolio
    asset = test_db._test_assets["600036.SH"]

    test_db.add(
        Transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            action="buy",
            trade_date=date(2024, 1, 2),
            quantity=Decimal("10"),
            price=Decimal("10"),
            amount=Decimal("100"),
            currency_id=asset.currency_id,
        )
    )
    test_db.commit()

    with pytest.raises(Exception):
        test_db.delete(asset)
        test_db.commit()
    test_db.rollback()

    assert test_db.get(Asset, asset.id) is not None


def test_delete_tag_cascades_asset_tags(test_db):
    asset = test_db._test_assets["600036.SH"]
    tag = Tag(name="LinkedTag")
    test_db.add(tag)
    test_db.flush()
    test_db.add(AssetTag(asset_id=asset.id, tag_id=tag.id, weight=Decimal("100")))
    test_db.commit()

    test_db.delete(tag)
    test_db.commit()

    assert test_db.get(Tag, tag.id) is None
    assert test_db.exec(select(AssetTag).where(AssetTag.tag_id == tag.id)).first() is None
    assert test_db.get(Asset, asset.id) is not None


def test_delete_tag_category_detaches_tags(test_db):
    category = TagCategory(name="CascadeCategory")
    test_db.add(category)
    test_db.flush()
    tag = Tag(name="CategorizedTag", category_id=category.id)
    test_db.add(tag)
    test_db.commit()

    test_db.delete(category)
    test_db.commit()

    assert test_db.get(TagCategory, category.id) is None
    detached = test_db.get(Tag, tag.id)
    assert detached is not None
    assert detached.category_id is None


def test_database_level_ondelete_cascade():
    """FK ON DELETE CASCADE works on a fresh database with FK pragma enabled."""
    import tempfile
    import os

    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    try:
        engine = create_engine(f"sqlite:///{db_path}")
        event.listen(engine, "connect", enable_sqlite_fk)
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            from backend.db.models import Currency

            cny = Currency(code="CNY", name="Yuan", symbol="¥", is_primary=True)
            session.add(cny)
            session.flush()
            portfolio = Portfolio(name="P", base_currency_id=cny.id)
            session.add(portfolio)
            session.flush()
            asset = Asset(symbol="X", name="X", type="stock", currency_id=cny.id)
            session.add(asset)
            session.flush()
            session.add(
                Price(
                    asset_id=asset.id,
                    price_date=date(2024, 1, 2),
                    price=Decimal("1"),
                    price_type="historical",
                )
            )
            session.commit()

            session.delete(asset)
            session.commit()

            assert session.exec(select(Price)).first() is None
    finally:
        engine.dispose()
        os.close(db_fd)
        os.unlink(db_path)
