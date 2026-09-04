from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from ..auth import current_user
from ..database import get_session
from ..models import Expense, User

router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/summary")
async def summary(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    now = datetime.now(timezone.utc); today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    starts = {"today": today, "week": today - timedelta(days=today.weekday()), "month": today.replace(day=1)}
    result = {}
    for name, start in starts.items():
        result[name] = float((await session.scalar(select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.user_id == user.id, Expense.spent_at >= start))) or 0)
    return result

@router.get("/breakdown")
async def breakdown(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    by_day = await session.execute(select(func.date(Expense.spent_at), func.sum(Expense.amount)).where(Expense.user_id == user.id, Expense.spent_at >= start).group_by(func.date(Expense.spent_at)).order_by(func.date(Expense.spent_at)))
    by_category = await session.execute(select(Expense.category, func.sum(Expense.amount)).where(Expense.user_id == user.id, Expense.spent_at >= start).group_by(Expense.category).order_by(func.sum(Expense.amount).desc()))
    return {"days": [{"date": str(d), "amount": float(a)} for d, a in by_day], "categories": [{"category": c, "amount": float(a)} for c, a in by_category]}
