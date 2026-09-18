"""Tag API endpoints."""

from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select

from backend.db import get_session
from backend.db.models import Tag, TagCategory, AssetTag, Asset
from backend.api.models import AssetTagCreate, AssetTagResponse
from backend.services import TagService

router = APIRouter()
category_router = APIRouter()


# Tag Category endpoints
@category_router.get("/", response_model=list[TagCategory])
def get_tag_categories(session: Session = Depends(get_session)):
    """Get all tag categories ordered by display_order."""
    with TagService(session) as service:
        return service.get_all_categories()


@category_router.post("/", response_model=TagCategory)
def create_tag_category(category: TagCategory, session: Session = Depends(get_session)):
    """Create a new tag category."""
    try:
        with TagService(session) as service:
            return service.create_category(
                name=category.name,
                description=category.description,
                display_order=category.display_order
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@category_router.put("/{category_id}", response_model=TagCategory)
def update_tag_category(category_id: int, category: TagCategory, session: Session = Depends(get_session)):
    """Update a tag category."""
    db_category = session.get(TagCategory, category_id)
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")

    category_data = category.model_dump(exclude_unset=True)
    for key, value in category_data.items():
        setattr(db_category, key, value)

    session.add(db_category)
    session.commit()
    session.refresh(db_category)
    return db_category


@category_router.delete("/{category_id}")
def delete_tag_category(category_id: int, session: Session = Depends(get_session)):
    """Delete a tag category."""
    category = session.get(TagCategory, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    session.delete(category)
    session.commit()
    return {"message": "Category deleted successfully"}


# Tag endpoints
@router.get("/", response_model=list[Tag])
def get_tags(category_id: int | None = None, session: Session = Depends(get_session)):
    """Get all tags, optionally filtered by category."""
    if category_id:
        statement = select(Tag).where(Tag.category_id == category_id)
    else:
        statement = select(Tag)
    return session.exec(statement).all()


@router.post("/", response_model=Tag)
def create_tag(tag: Tag, session: Session = Depends(get_session)):
    """Create a new tag."""
    try:
        with TagService(session) as service:
            category_name = None
            if tag.category_id:
                category = session.get(TagCategory, tag.category_id)
                if category:
                    category_name = category.name
            return service.create_tag(
                name=tag.name,
                category_name=category_name,
                description=tag.description,
                color=tag.color
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{tag_id}", response_model=Tag)
def update_tag(tag_id: int, tag: Tag, session: Session = Depends(get_session)):
    """Update a tag."""
    db_tag = session.get(Tag, tag_id)
    if not db_tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    tag_data = tag.model_dump(exclude_unset=True)
    for key, value in tag_data.items():
        setattr(db_tag, key, value)

    session.add(db_tag)
    session.commit()
    session.refresh(db_tag)
    return db_tag


@router.delete("/{tag_id}")
def delete_tag(tag_id: int, session: Session = Depends(get_session)):
    """Delete a tag."""
    tag = session.get(Tag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    session.delete(tag)
    session.commit()
    return {"message": "Tag deleted successfully"}


# Asset Tag endpoints
@router.get("/asset-tags/", response_model=list[AssetTagResponse])
def get_asset_tags(
    asset_id: int | None = None,
    tag_id: int | None = None,
    session: Session = Depends(get_session)
):
    """Get asset tags, optionally filtered by asset or tag."""
    statement = select(AssetTag)
    if asset_id:
        statement = statement.where(AssetTag.asset_id == asset_id)
    if tag_id:
        statement = statement.where(AssetTag.tag_id == tag_id)

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


@router.post("/asset-tags/", response_model=AssetTagResponse)
def create_asset_tag(asset_tag: AssetTagCreate, session: Session = Depends(get_session)):
    """Assign a tag to an asset with weight."""
    try:
        asset = session.get(Asset, asset_tag.asset_id)
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        tag = session.get(Tag, asset_tag.tag_id)
        if not tag:
            raise HTTPException(status_code=404, detail="Tag not found")

        with TagService(session) as service:
            asset_tag_obj = service.assign_tag_to_asset(
                asset_symbol=asset.symbol,
                tag_name=tag.name,
                weight=Decimal(str(asset_tag.weight)),
                notes=asset_tag.notes,
                validate=False
            )

            return {
                "id": asset_tag_obj.id,
                "asset_id": asset_tag_obj.asset_id,
                "tag_id": asset_tag_obj.tag_id,
                "weight": float(asset_tag_obj.weight),
                "notes": asset_tag_obj.notes,
                "tag": asset_tag_obj.tag,
                "asset": asset_tag_obj.asset
            }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/asset-tags/{asset_tag_id}", response_model=AssetTagResponse)
def update_asset_tag(asset_tag_id: int, asset_tag: AssetTagCreate, session: Session = Depends(get_session)):
    """Update an asset tag assignment."""
    db_asset_tag = session.get(AssetTag, asset_tag_id)
    if not db_asset_tag:
        raise HTTPException(status_code=404, detail="Asset tag not found")

    try:
        db_asset_tag.weight = Decimal(str(asset_tag.weight))
        db_asset_tag.notes = asset_tag.notes
        session.add(db_asset_tag)
        session.commit()
        session.refresh(db_asset_tag)

        return {
            "id": db_asset_tag.id,
            "asset_id": db_asset_tag.asset_id,
            "tag_id": db_asset_tag.tag_id,
            "weight": float(db_asset_tag.weight),
            "notes": db_asset_tag.notes,
            "tag": db_asset_tag.tag,
            "asset": db_asset_tag.asset
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/asset-tags/{asset_tag_id}")
def delete_asset_tag(asset_tag_id: int, session: Session = Depends(get_session)):
    """Remove a tag from an asset."""
    asset_tag = session.get(AssetTag, asset_tag_id)
    if not asset_tag:
        raise HTTPException(status_code=404, detail="Asset tag not found")

    session.delete(asset_tag)
    session.commit()
    return {"message": "Asset tag deleted successfully"}


@router.get("/portfolio/{portfolio_id}/statistics")
def get_portfolio_tag_statistics(
    portfolio_id: int,
    position_date: str,
    category_name: str | None = None,
    session: Session = Depends(get_session)
):
    """Get tag-based statistics for a portfolio on a specific date."""
    try:
        pos_date = datetime.strptime(position_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    with TagService(session) as service:
        return service.get_portfolio_tag_statistics(portfolio_id, pos_date, category_name)


@router.get("/summary")
def get_tag_summary(session: Session = Depends(get_session)):
    """Get summary of all tags and their usage."""
    with TagService(session) as service:
        return service.get_tag_summary()
