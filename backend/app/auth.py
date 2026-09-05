import hashlib, hmac, time
from urllib.parse import parse_qsl
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from .config import settings
from .database import get_session
from .models import User

async def get_or_create_user(session, telegram_id, first_name="User", username=None):
    if not 0 < telegram_id < 2**63:
        raise HTTPException(401, "Invalid Telegram user")
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if user is not None:
        return user
    user = User(telegram_id=telegram_id, first_name=str(first_name or "User")[:128],
                username=str(username)[:128] if username else None)
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
        if user is None:
            raise
    return user

async def current_user(authorization: str = Header(...), session: AsyncSession = Depends(get_session)) -> User:
    if not authorization.startswith("tma "):
        raise HTTPException(401, "Telegram authorization required")
    raw = authorization[4:]
    pairs = dict(parse_qsl(raw, keep_blank_values=True))
    supplied = pairs.pop("hash", "")
    try:
        age = time.time() - int(pairs.get("auth_date", ""))
    except (ValueError, TypeError):
        raise HTTPException(401, "Invalid Telegram authorization date")
    if not supplied or not -60 <= age <= 86400:
        raise HTTPException(401, "Expired Telegram authorization")
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hashlib.sha256(settings.telegram_bot_token.encode()).digest()
    expected = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, supplied):
        raise HTTPException(401, "Invalid Telegram authorization")
    try:
        import json
        telegram = json.loads(pairs["user"]) if "user" in pairs else {"id": pairs["id"], "first_name": pairs.get("first_name", "User"), "username": pairs.get("username")}
        telegram_id = int(telegram["id"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(401, "Invalid Telegram user")
    return await get_or_create_user(session, telegram_id, telegram.get("first_name"), telegram.get("username"))
