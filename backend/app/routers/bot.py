from datetime import datetime, timedelta, timezone
from urllib.parse import unquote
from fastapi import APIRouter, Header, HTTPException, Depends
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from ..config import settings
from ..database import get_session
from ..models import Expense, User, Income, WalletSettings, MonthlyBudget
from ..wallet import Currency, CurrencyIn, IncomeIn, BudgetIn, selected_currency, budget_status, balance
from ..schemas import ExpenseIn
from ..auth import get_or_create_user

router = APIRouter(prefix="/bot", tags=["bot"])

async def bot_user(x_bot_token: str = Header(...), x_telegram_id: int = Header(...), x_telegram_name: str = Header("User"), session: AsyncSession = Depends(get_session), x_telegram_name_encoded: str | None = Header(None)):
    if x_bot_token not in {settings.bot_api_token, settings.telegram_bot_token}: raise HTTPException(401, "Invalid bot credential")
    name = unquote(x_telegram_name_encoded) if x_telegram_name_encoded is not None else x_telegram_name
    return await get_or_create_user(session, x_telegram_id, name)

@router.post("/expenses")
async def create_expense(data: ExpenseIn, user: User = Depends(bot_user), session: AsyncSession = Depends(get_session)):
    item = Expense(user_id=user.id, **data.model_dump(exclude={"spent_at"}), spent_at=data.spent_at or datetime.now(timezone.utc))
    session.add(item); await session.commit(); return {"id": item.id}

@router.get("/summary")
async def summary(user: User = Depends(bot_user), session: AsyncSession = Depends(get_session)):
    currency = await selected_currency(session, user.id)
    now = datetime.now(timezone.utc); day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    starts = {"today": day, "week": day-timedelta(days=day.weekday()), "month": day.replace(day=1)}
    return {"currency": currency, **{key: float((await session.scalar(select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.user_id == user.id, Expense.currency == currency, Expense.spent_at >= start, Expense.spent_at <= now))) or 0) for key, start in starts.items()}}

@router.get("/expenses")
async def list_expenses(user: User = Depends(bot_user), session: AsyncSession = Depends(get_session)):
    rows = (await session.scalars(select(Expense).where(Expense.user_id == user.id).order_by(Expense.spent_at.desc()).limit(10))).all()
    return [{"id": x.id, "amount": float(x.amount), "currency": x.currency, "category": x.category, "description": x.description} for x in rows]

@router.get("/expenses/{expense_id}")
async def get_expense(expense_id: int, user: User = Depends(bot_user), session: AsyncSession = Depends(get_session)):
    item = await session.scalar(select(Expense).where(Expense.id == expense_id, Expense.user_id == user.id))
    if not item: raise HTTPException(404, "Expense not found")
    return {"id": item.id, "currency": item.currency}

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


@router.get("/settings")
async def settings_get(user: User = Depends(bot_user), session: AsyncSession = Depends(get_session)):
    return {"currency": await selected_currency(session, user.id)}


@router.put("/settings")
async def settings_put(data: CurrencyIn, user: User = Depends(bot_user), session: AsyncSession = Depends(get_session)):
    # Serialize writes for the same account; leave all existing transactions intact.
    await session.scalar(select(User.id).where(User.id == user.id).with_for_update())
    item = await session.get(WalletSettings, user.id)
    if item: item.currency = data.currency
    else: session.add(WalletSettings(user_id=user.id, currency=data.currency))
    await session.commit()
    return data.model_dump()


@router.post("/incomes", status_code=201)
async def add_income(data: IncomeIn, user: User = Depends(bot_user), session: AsyncSession = Depends(get_session)):
    item = Income(user_id=user.id, **data.model_dump())
    session.add(item); await session.commit()
    return {"id": item.id}


@router.get("/incomes")
async def incomes(user: User = Depends(bot_user), session: AsyncSession = Depends(get_session)):
    rows = (await session.scalars(select(Income).where(Income.user_id == user.id).order_by(Income.id.desc()).limit(10))).all()
    return [{"id": x.id, "amount": str(x.amount), "currency": x.currency, "description": x.description} for x in rows]


@router.delete("/incomes/{income_id}", status_code=204)
async def remove_income(income_id: int, user: User = Depends(bot_user), session: AsyncSession = Depends(get_session)):
    result = await session.execute(delete(Income).where(Income.id == income_id, Income.user_id == user.id))
    if not result.rowcount: raise HTTPException(404, "Income not found")
    await session.commit()


@router.get("/balance")
async def get_balance(user: User = Depends(bot_user), session: AsyncSession = Depends(get_session)):
    return await balance(session, user.id)


@router.get("/budget")
async def get_budget(currency: Currency | None = None, user: User = Depends(bot_user), session: AsyncSession = Depends(get_session)):
    return await budget_status(session, user.id, currency or await selected_currency(session, user.id))


@router.put("/budget")
async def put_budget(data: BudgetIn, user: User = Depends(bot_user), session: AsyncSession = Depends(get_session)):
    await session.scalar(select(User.id).where(User.id == user.id).with_for_update())
    item = await session.get(MonthlyBudget, (user.id, data.currency))
    if item: item.amount = data.amount
    else: session.add(MonthlyBudget(user_id=user.id, **data.model_dump()))
    await session.commit()
    return await budget_status(session, user.id, data.currency)
