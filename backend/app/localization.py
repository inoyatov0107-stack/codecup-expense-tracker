from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Literal
from pydantic import BaseModel, Field
from sqlalchemy import select
from .models import BotProfile

ZONES = ("UTC", "Asia/Dushanbe", "Europe/Kaliningrad", "Europe/Moscow",
         "Europe/Samara", "Asia/Yekaterinburg", "Asia/Omsk", "Asia/Krasnoyarsk",
         "Asia/Irkutsk", "Asia/Yakutsk", "Asia/Vladivostok", "Asia/Magadan", "Asia/Kamchatka")

class ProfileIn(BaseModel):
    language: Literal["ru", "tg"] | None = None
    timezone: str | None = None

class VersionIn(BaseModel):
    version: str = Field(min_length=1, max_length=32, pattern=r"^[a-zA-Z0-9._-]+$")

async def user_zone(session, user_id):
    value = await session.scalar(select(BotProfile.timezone).where(BotProfile.user_id == user_id))
    return value if value in ZONES else "UTC"

def period_starts(zone, now=None):
    now = now or datetime.now(timezone.utc)
    day = now.astimezone(ZoneInfo(zone)).replace(hour=0, minute=0, second=0, microsecond=0)
    return {key: start.astimezone(timezone.utc) for key, start in {
        "today": day, "week": day-timedelta(days=day.weekday()), "month": day.replace(day=1)}.items()}
