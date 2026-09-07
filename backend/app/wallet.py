from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from .models import Expense, Income, MonthlyBudget, WalletSettings
from .localization import period_starts, user_zone

Currency = Literal["TJS", "RUB"]


class CurrencyIn(BaseModel):
    currency: Currency


class IncomeIn(CurrencyIn):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    description: str = Field(min_length=1, max_length=1000)


class BudgetIn(CurrencyIn):
    # Zero disables the budget without deleting any transactions.
    amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


async def selected_currency(session, user_id):
    return await session.scalar(select(WalletSettings.currency).where(WalletSettings.user_id == user_id)) or "TJS"


async def budget_status(session, user_id, currency):
    now = datetime.now(timezone.utc)
    zone = await user_zone(session, user_id)
    start = period_starts(zone, now)["month"]
    limit = await session.scalar(select(MonthlyBudget.amount).where(MonthlyBudget.user_id == user_id, MonthlyBudget.currency == currency))
    spent = await session.scalar(select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.user_id == user_id, Expense.currency == currency, Expense.spent_at >= start, Expense.spent_at <= now))
    return {"currency": currency, "timezone": zone, "limit": str(limit or 0), "spent": str(spent),
            "level": 100 if limit and spent >= limit else 80 if limit and spent >= limit * Decimal("0.8") else 0}


async def balance(session, user_id):
    result = []
    for currency in ("TJS", "RUB"):
        income = await session.scalar(select(func.coalesce(func.sum(Income.amount), 0)).where(Income.user_id == user_id, Income.currency == currency))
        expense = await session.scalar(select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.user_id == user_id, Expense.currency == currency))
        result.append({"currency": currency, "income": str(income), "expense": str(expense), "balance": str(income-expense)})
    return result
