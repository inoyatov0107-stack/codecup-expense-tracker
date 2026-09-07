from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from ..auth import current_user
from ..database import get_session
from ..models import Expense, User
from ..wallet import Currency
from ..localization import period_starts, user_zone
from zoneinfo import ZoneInfo
from collections import defaultdict
from decimal import Decimal

router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/summary")
async def summary(currency: Currency = "TJS", user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    now = datetime.now(timezone.utc)
    starts = period_starts(await user_zone(session, user.id), now)
    result = {}
    for name, start in starts.items():
        result[name] = float((await session.scalar(select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.user_id == user.id, Expense.currency == currency, Expense.spent_at >= start, Expense.spent_at <= now))) or 0)
    return result

@router.get("/breakdown")
async def breakdown(currency: Currency = "TJS", user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    now = datetime.now(timezone.utc)
    zone = await user_zone(session, user.id)
    start = period_starts(zone, now)["month"]
    days, categories = defaultdict(Decimal), defaultdict(Decimal)
    rows = await session.stream(select(Expense.spent_at, Expense.amount, Expense.category).where(Expense.user_id == user.id, Expense.currency == currency, Expense.spent_at >= start, Expense.spent_at <= now))
    async for when, amount, category in rows:
        if when.tzinfo is None: when = when.replace(tzinfo=timezone.utc)
        days[when.astimezone(ZoneInfo(zone)).date().isoformat()] += amount
        categories[category] += amount
    return {"timezone": zone, "days": [{"date": d, "amount": float(a)} for d, a in sorted(days.items())], "categories": [{"category": c, "amount": float(a)} for c, a in sorted(categories.items(), key=lambda x: x[1], reverse=True)]}
