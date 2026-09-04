from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field

class ExpenseIn(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="TJS", min_length=3, max_length=3)
    category: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=1000)
    spent_at: datetime | None = None

class ExpenseOut(ExpenseIn):
    id: int
    spent_at: datetime
    model_config = {"from_attributes": True}

class LimitIn(BaseModel):
    category: str = Field(min_length=1, max_length=64)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    period: str = "month"
