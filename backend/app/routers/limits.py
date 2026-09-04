from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..auth import current_user
from ..database import get_session
from ..models import CategoryLimit, User
from ..schemas import LimitIn

router = APIRouter(prefix="/limits", tags=["limits"])

@router.get("")
async def list_limits(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    return (await session.scalars(select(CategoryLimit).where(CategoryLimit.user_id == user.id))).all()

@router.put("")
async def upsert_limit(data: LimitIn, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    limit = await session.scalar(select(CategoryLimit).where(CategoryLimit.user_id == user.id, CategoryLimit.category == data.category, CategoryLimit.period == data.period))
    if limit: limit.amount = data.amount
    else: limit = CategoryLimit(user_id=user.id, **data.model_dump()); session.add(limit)
    await session.commit(); await session.refresh(limit)
    return {"id": limit.id, "category": limit.category, "amount": float(limit.amount), "period": limit.period}
