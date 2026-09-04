import hashlib, hmac, time
from urllib.parse import parse_qsl
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .config import settings
from .database import get_session
from .models import User

async def current_user(authorization: str = Header(...), session: AsyncSession = Depends(get_session)) -> User:
    if not authorization.startswith("tma "):
        raise HTTPException(401, "Telegram authorization required")
    raw = authorization[4:]
    pairs = dict(parse_qsl(raw, keep_blank_values=True))
    supplied = pairs.pop("hash", "")
    if not supplied or not pairs.get("auth_date") or time.time() - int(pairs["auth_date"]) > 86400:
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
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if user is None:
        user = User(telegram_id=telegram_id, first_name=telegram.get("first_name", "User"), username=telegram.get("username"))
        session.add(user); await session.commit(); await session.refresh(user)
    return user
