from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Header, HTTPException, Depends
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from ..config import settings
from ..database import get_session
from ..models import Expense, User
from ..schemas import ExpenseIn

router = APIRouter(prefix="/bot", tags=["bot"])

async def bot_user(x_bot_token: str = Header(...), x_telegram_id: int = Header(...), x_telegram_name: str = Header("User"), session: AsyncSession = Depends(get_session)):
    if x_bot_token not in {settings.bot_api_token, settings.telegram_bot_token}: raise HTTPException(401, "Invalid bot credential")
    user = await session.scalar(select(User).where(User.telegram_id == x_telegram_id))
    if not user:
        user = User(telegram_id=x_telegram_id, first_name=x_telegram_name[:128]); session.add(user); await session.commit(); await session.refresh(user)
    return user

@router.post("/expenses")
async def create_expense(data: ExpenseIn, user: User = Depends(bot_user), session: AsyncSession = Depends(get_session)):
    item = Expense(user_id=user.id, **data.model_dump(exclude={"spent_at"}), spent_at=data.spent_at or datetime.now(timezone.utc))
    session.add(item); await session.commit(); return {"id": item.id}

@router.get("/summary")
async def summary(user: User = Depends(bot_user), session: AsyncSession = Depends(get_session)):
    now = datetime.now(timezone.utc); day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    starts = {"today": day, "week": day-timedelta(days=day.weekday()), "month": day.replace(day=1)}
    return {key: float((await session.scalar(select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.user_id == user.id, Expense.spent_at >= start))) or 0) for key, start in starts.items()}

@router.get("/expenses")
async def list_expenses(user: User = Depends(bot_user), session: AsyncSession = Depends(get_session)):
    rows = (await session.scalars(select(Expense).where(Expense.user_id == user.id).order_by(Expense.spent_at.desc()).limit(10))).all()
    return [{"id": x.id, "amount": float(x.amount), "category": x.category, "description": x.description} for x in rows]

@router.delete("/expenses/{expense_id}", status_code=204)
async def delete_expense(expense_id: int, user: User = Depends(bot_user), session: AsyncSession = Depends(get_session)):
    result = await session.execute(delete(Expense).where(Expense.id == expense_id, Expense.user_id == user.id))
    if not result.rowcount: raise HTTPException(404, "Expense not found")
    await session.commit()

@router.put("/expenses/{expense_id}")
async def update_expense(expense_id: int, data: ExpenseIn, user: User = Depends(bot_user), session: AsyncSession = Depends(get_session)):
    item = await session.scalar(select(Expense).where(Expense.id == expense_id, Expense.user_id == user.id))
    if not item: raise HTTPException(404, "Expense not found")
    for key, value in data.model_dump(exclude_none=True).items(): setattr(item, key, value)
    await session.commit(); return {"id": item.id}
