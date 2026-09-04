import asyncio, os, re
from decimal import Decimal
import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
API = os.getenv("API_INTERNAL_URL", "http://api:8000/api")
dp = Dispatcher()
PATTERN = re.compile(r"^\s*(\d+(?:[.,]\d{1,2})?)\s+(.+?)\s*$")

def parse(text: str):
    match = PATTERN.match(text)
    if not match: return None
    amount, rest = match.groups(); category = None
    if " #" in rest:
        rest, category = rest.rsplit(" #", 1); category = category.strip().title()
    category = category or next((c for word, c in {"такси":"Транспорт", "кафе":"Еда", "аптека":"Здоровье", "аренда":"Дом"}.items() if word in rest.lower()), "Другое")
    return Decimal(amount.replace(",", ".")), rest, category

async def api(path, message, method="GET", payload=None):
    async with httpx.AsyncClient() as client:
        response = await client.request(method, f"{API}{path}", json=payload, headers={"X-Telegram-Id": str(message.from_user.id), "X-Telegram-Name": message.from_user.full_name, "X-Bot-Token": os.environ["BOT_API_TOKEN"]})
        response.raise_for_status(); return response.json() if response.content else None

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("Привет! Отправь трату одной строкой: «45 такси» или «120 обед #Еда».\nКоманды: /today, /week, /month, /list, /delete ID, /edit ID сумма описание #Категория")

@dp.message(Command("today", "week", "month"))
async def report(message: Message):
    data = await api("/bot/summary", message)
    period = message.text[1:]
    await message.answer(f"{period.capitalize()}: {data[period]:.2f} TJS")

@dp.message(Command("list"))
async def list_items(message: Message):
    rows = await api("/bot/expenses", message)
    await message.answer("\n".join(f"#{x['id']} · {x['amount']:.2f} TJS · {x['category']} — {x['description']}" for x in rows) or "Трат пока нет")

@dp.message(Command("delete"))
async def delete_item(message: Message, command: CommandObject):
    if not command.args or not command.args.isdigit():
        await message.answer("Формат: /delete ID. Номер видно в /list"); return
    try: await api(f"/bot/expenses/{command.args}", message, "DELETE")
    except httpx.HTTPStatusError: await message.answer("Трата не найдена"); return
    await message.answer("Трата удалена")

@dp.message(Command("edit"))
async def edit_item(message: Message, command: CommandObject):
    parts = (command.args or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[0].isdigit() or not (parsed := parse(parts[1])):
        await message.answer("Формат: /edit ID сумма описание #Категория"); return
    amount, description, category = parsed
    try: await api(f"/bot/expenses/{parts[0]}", message, "PUT", {"amount": str(amount), "currency":"TJS", "category":category, "description":description})
    except httpx.HTTPStatusError: await message.answer("Трата не найдена"); return
    await message.answer("Трата изменена")

@dp.message(F.text)
async def expense(message: Message):
    data = parse(message.text or "")
    if not data:
        await message.answer("Формат: «сумма описание», например: 45 такси или 120 обед #Еда")
        return
    amount, description, category = data
    await api("/bot/expenses", message, "POST", {"amount": str(amount), "currency": "TJS", "category": category, "description": description})
    await message.answer(f"Записал: {amount} TJS · {category} · {description}")

async def main():
    await dp.start_polling(Bot(TOKEN))

if __name__ == "__main__": asyncio.run(main())
