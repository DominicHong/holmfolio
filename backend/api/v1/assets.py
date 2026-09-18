"""Asset API endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select

from backend.db import get_session
from backend.db.models import Asset, Transaction, AssetTag
from backend.api.models import AssetTagResponse

router = APIRouter()


@router.get("/", response_model=list[Asset])
def get_assets(session: Session = Depends(get_session)):
    """Get all assets."""
    assets = session.exec(select(Asset)).all()
    return assets


@router.post("/", response_model=Asset)
def create_asset(asset: Asset, session: Session = Depends(get_session)):
    """Create a new asset."""
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


@router.get("/{asset_id}", response_model=Asset)
def get_asset(asset_id: int, session: Session = Depends(get_session)):
    """Get a specific asset."""
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.put("/{asset_id}", response_model=Asset)
def update_asset(asset_id: int, asset: Asset, session: Session = Depends(get_session)):
    """Update an existing asset."""
    db_asset = session.get(Asset, asset_id)
    if not db_asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    db_asset.symbol = asset.symbol
    db_asset.name = asset.name
    db_asset.type = asset.type
    db_asset.isin = asset.isin
    db_asset.currency_id = asset.currency_id

    session.add(db_asset)
    session.commit()
    session.refresh(db_asset)
    return db_asset


@router.delete("/{asset_id}")
def delete_asset(asset_id: int, session: Session = Depends(get_session)):
    """Delete an asset."""
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    transactions = session.exec(
        select(Transaction).where(Transaction.asset_id == asset_id)
    ).all()
    if transactions:
        raise HTTPException(
            status_code=409, detail="Cannot delete asset: it has associated transactions"
        )

    session.delete(asset)
    session.commit()
    return {"message": "Asset deleted successfully"}


@router.get("/{asset_id}/tags", response_model=list[AssetTagResponse])
def get_asset_tags_by_asset(asset_id: int, session: Session = Depends(get_session)):
    """Get all tags assigned to a specific asset."""
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    statement = select(AssetTag).where(AssetTag.asset_id == asset_id)
    asset_tags = session.exec(statement).all()

    result = []
    for at in asset_tags:
        at_dict = {
            "id": at.id,
            "asset_id": at.asset_id,
            "tag_id": at.tag_id,
            "weight": float(at.weight),
            "notes": at.notes,
            "tag": at.tag,
            "asset": at.asset
        }
        result.append(at_dict)

    return result
