from datetime import datetime, timedelta, timezone
from urllib.parse import unquote
from fastapi import APIRouter, Header, HTTPException, Depends, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from ..config import settings
from ..database import get_session
from ..models import Expense, User, Income, WalletSettings, MonthlyBudget, BotProfile
from ..localization import ProfileIn, VersionIn, ZONES, period_starts, user_zone
from ..wallet import Currency, CurrencyIn, IncomeIn, BudgetIn, selected_currency, budget_status, balance
from ..schemas import ExpenseIn
from ..auth import get_or_create_user
from zoneinfo import ZoneInfo

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
    now = datetime.now(timezone.utc)
    zone = await user_zone(session, user.id)
    starts = period_starts(zone, now)
    return {"currency": currency, "timezone": zone, **{key: float((await session.scalar(select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.user_id == user.id, Expense.currency == currency, Expense.spent_at >= start, Expense.spent_at <= now))) or 0) for key, start in starts.items()}}

@router.get("/month")
async def month_report(year: int = Query(ge=1, le=9998), month: int = Query(ge=1, le=12), user: User = Depends(bot_user), session: AsyncSession = Depends(get_session)):
    zone = await user_zone(session, user.id)
    start = datetime(year, month, 1, tzinfo=ZoneInfo(zone)).astimezone(timezone.utc)
    end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=ZoneInfo(zone)).astimezone(timezone.utc)
    rows = (await session.execute(select(Expense.currency, func.sum(Expense.amount)).where(Expense.user_id == user.id, Expense.spent_at >= start, Expense.spent_at < end).group_by(Expense.currency))).all()
    return {"year": year, "month": month, "timezone": zone, "totals": {currency: str(amount) for currency, amount in rows}}

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


async def locked_profile(session, user):
    await session.scalar(select(User.id).where(User.id == user.id).with_for_update())
    item = await session.get(BotProfile, user.id)
    if item is None:
        item = BotProfile(user_id=user.id, language="ru", timezone="UTC", seen_version="")
        session.add(item)
    return item


def profile_data(item):
    return {"language": item.language, "timezone": item.timezone, "seen_version": item.seen_version}


@router.post("/visit")
async def visit(user: User = Depends(bot_user), session: AsyncSession = Depends(get_session),
                x_telegram_username: str = Header(""), x_telegram_name_encoded: str | None = Header(None)):
    item = await locked_profile(session, user)
    # Only the authenticated bot supplies this metadata; usernames are not authority.
    user.username = x_telegram_username[:128] or None
    if x_telegram_name_encoded is not None:
        user.first_name = unquote(x_telegram_name_encoded)[:128]
    item.last_seen = datetime.now(timezone.utc)
    await session.commit()
    return profile_data(item)


@router.get("/profile")
async def profile_get(user: User = Depends(bot_user), session: AsyncSession = Depends(get_session)):
    item = await session.get(BotProfile, user.id)
    return profile_data(item) if item else {"language": "ru", "timezone": "UTC", "seen_version": ""}


@router.put("/profile")
async def profile_put(data: ProfileIn, user: User = Depends(bot_user), session: AsyncSession = Depends(get_session)):
    if data.timezone is not None and data.timezone not in ZONES:
        raise HTTPException(422, "Unsupported timezone")
    item = await locked_profile(session, user)
    if data.language is not None: item.language = data.language
    if data.timezone is not None: item.timezone = data.timezone
    await session.commit()
    return profile_data(item)


@router.put("/profile/seen")
async def seen(data: VersionIn, user: User = Depends(bot_user), session: AsyncSession = Depends(get_session)):
    item = await locked_profile(session, user)
    item.seen_version = data.version
    await session.commit()
    return {"ok": True}


@router.get("/admin/users")
async def admin_users(page: int = Query(1, ge=1, le=1000000), user: User = Depends(bot_user), session: AsyncSession = Depends(get_session)):
    if settings.bot_owner_id <= 0 or user.telegram_id != settings.bot_owner_id:
        raise HTTPException(403, "Owner only")
    total = await session.scalar(select(func.count(User.id)))
    rows = (await session.scalars(select(User).order_by(User.id).offset((page-1)*20).limit(20))).all()
    return {"total": total, "page": page, "pages": max(1, (total+19)//20),
            "users": [{"name": x.first_name, "username": x.username} for x in rows]}
