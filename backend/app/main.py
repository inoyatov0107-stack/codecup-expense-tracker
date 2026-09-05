from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database import engine
from .models import Base
from .routers import bot, expenses, reports, limits

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

app = FastAPI(title="CodeCup Expense Tracker API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[settings.web_origin], allow_credentials=False, allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Authorization", "Content-Type"])
app.include_router(expenses.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(limits.router, prefix="/api")
app.include_router(bot.router, prefix="/api")

@app.get("/health")
async def health():
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, "Database unavailable")
    return {"status": "ok"}
