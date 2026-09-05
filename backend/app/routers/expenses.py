import csv, io
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from ..auth import current_user
from ..database import get_session
from ..models import Expense, User
from ..schemas import ExpenseIn, ExpenseOut

router = APIRouter(prefix="/expenses", tags=["expenses"])

def csv_text(value):
    # Prevent spreadsheet formula execution in user-supplied text cells.
    value = str(value)
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")) else value

@router.get("", response_model=list[ExpenseOut])
async def list_expenses(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    return (await session.scalars(select(Expense).where(Expense.user_id == user.id).order_by(Expense.spent_at.desc()))).all()

@router.post("", response_model=ExpenseOut, status_code=201)
async def create_expense(data: ExpenseIn, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    expense = Expense(user_id=user.id, **data.model_dump(exclude={"spent_at"}), spent_at=data.spent_at or datetime.now(timezone.utc))
    session.add(expense); await session.commit(); await session.refresh(expense); return expense

@router.put("/item/{expense_id}", response_model=ExpenseOut)
async def update_expense(expense_id: int, data: ExpenseIn, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    expense = await session.scalar(select(Expense).where(Expense.id == expense_id, Expense.user_id == user.id))
    if expense is None: raise HTTPException(404, "Expense not found")
    for key, value in data.model_dump(exclude_none=True).items(): setattr(expense, key, value)
    await session.commit(); await session.refresh(expense); return expense

@router.delete("/item/{expense_id}", status_code=204)
async def delete_expense(expense_id: int, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    result = await session.execute(delete(Expense).where(Expense.id == expense_id, Expense.user_id == user.id))
    if not result.rowcount: raise HTTPException(404, "Expense not found")
    await session.commit(); return Response(status_code=204)

@router.get("/export/csv")
async def export_csv(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    rows = (await session.scalars(select(Expense).where(Expense.user_id == user.id).order_by(Expense.spent_at.desc()))).all()
    out = io.StringIO(); writer = csv.writer(out); writer.writerow(["id", "amount", "currency", "category", "description", "spent_at"])
    writer.writerows([[x.id, x.amount, csv_text(x.currency), csv_text(x.category), csv_text(x.description), x.spent_at.isoformat()] for x in rows])
    return Response(out.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=expenses.csv"})
