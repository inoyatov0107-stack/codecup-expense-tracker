import asyncio, os, re, logging
from decimal import Decimal
from urllib.parse import quote
import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardMarkup, ErrorEvent

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
API = os.getenv("API_INTERNAL_URL", "http://api:8000/api")
PANEL_URL = "https://dynamic-cat-production.up.railway.app/"
dp = Dispatcher()
api_slots = asyncio.Semaphore(20)

@dp.errors()
async def handle_error(event: ErrorEvent):
 logging.error("Bot handler failed: %s", type(event.exception).__name__)
 if event.update.message:
  if isinstance(event.exception, httpx.HTTPStatusError) and event.exception.response.status_code == 422:
   text = "Проверьте сумму и описание: сумма должна быть больше нуля, максимум 2 знака после запятой."
  else:
   text = "Не удалось подтвердить операцию. Проверьте /list перед повтором, чтобы не записать трату дважды. Попробуйте позже."
  await event.update.message.answer(text)
 return True
PATTERN = re.compile(r"^\s*(\d+(?:[.,]\d{1,2})?)\s+(.+?)\s*$")
KEYWORDS = {
 "Еда": ("кафе","ресторан","обед","продукт","магазин","кофе","еда","хӯрок","хурок","мағоза","қаҳва"),
 "Транспорт": ("такси","таксӣ","бензин","автобус","транспорт","нақлиёт","заправка"),
 "Авто и запчасти": ("запчаст","қисм","шина","масло","фильтр","аккумулятор","автосервис"),
 "Одежда": ("одежд","либос","куртка","обув","пойафзол","футболка","брюк","плать"),
 "Ремонт": ("ремонт","таъмир","почин","мастер","сервис"),
 "Дом": ("аренда","иҷора","квартира","хона","коммунал"),
 "Здоровье": ("аптека","дорухона","врач","табиб","лекарств","дору"),
 "Связь": ("телефон","мобильн","сим","интернет","алоқа","связь"),
 "Обучение": ("курс","книга","учеб","школ","мактаб","университет","таълим"),
 "Дети": ("ребен","кӯдак","детск","садик","игрушк"),
 "Животные": ("кот","кошка","собак","ҳайвон","ветеринар","корм"),
 "Развлечения": ("кино","игра","бозӣ","концерт","развлеч","спортзал"),
 "Подарки": ("подар","тӯҳфа","цветы","сувенир"),
 "Подписки": ("подписк","обуна","netflix","spotify","icloud"),
 "Путешествия": ("отель","билет","сафар","путешеств","авиабилет"),
 "Налоги и платежи": ("налог","андоз","штраф","госпошлин","страховк"),
}
def parse(text):
 m=PATTERN.match(text)
 if not m:return None
 amount,rest=m.groups(); category=None
 if " #" in rest: rest,category=rest.rsplit(" #",1); category=category.strip().title()
 category=category or next((name for name,words in KEYWORDS.items() if any(word in rest.lower() for word in words)),"Другое")
 amount = Decimal(amount.replace(",","."))
 if not 0 < amount < Decimal("10000000000") or not rest.strip() or len(rest)>1000 or not category or len(category)>64:return None
 return amount,rest,category
async def api(path,message,method="GET",payload=None):
 async with api_slots, httpx.AsyncClient(timeout=15) as client:
  r=await client.request(method,f"{API}{path}",json=payload,headers={"X-Telegram-Id":str(message.from_user.id),"X-Telegram-Name-Encoded":quote(message.from_user.full_name, safe=""),"X-Bot-Token":TOKEN})
  r.raise_for_status();return r.json() if r.content else None
def panel_button(): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📊 Открыть мои расходы",url=PANEL_URL)]])
def menu(): return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📊 Мои расходы"),KeyboardButton(text="💰 Баланс")],[KeyboardButton(text="➕ Доход"),KeyboardButton(text="🎯 Бюджет")],[KeyboardButton(text="💱 Валюта"),KeyboardButton(text="❓ Помощь")]],resize_keyboard=True,is_persistent=True)
HELP = ("Трата: 45 такси\nДоход: /income 5000 зарплата\n/balance — доходы, расходы и остаток отдельно по валютам\n/currency — сомони или рубли для новых записей\n/budget 3000 — месячный бюджет в выбранной валюте\n/budget 0 — отключить бюджет\n/today /week /month — расходы в выбранной валюте\n/list — последние расходы\n/edit ID сумма описание — исправить трату\n/delete ID — удалить трату\n/incomes — последние доходы\n/delete_income ID — удалить доход\n\nВалюта старых записей не меняется. Конвертации нет. Бюджет повторяется каждый месяц, периоды считаются по UTC.")
@dp.message(Command("start"))
async def start(message:Message):
 await message.answer("Привет! Отправь трату: «45 такси» или «120 обед #Еда».\nПо умолчанию — сомони (TJS). Рубли можно выбрать через /currency.\n\n"+HELP,reply_markup=menu())
@dp.message(Command("help"))
@dp.message(F.text=="❓ Помощь")
async def help_message(message:Message):
 await message.answer(HELP,reply_markup=menu())
@dp.message(F.text=="📊 Мои расходы")
async def dashboard(message:Message):
 await message.answer("Нажмите кнопку — откроется ваша личная панель.",reply_markup=panel_button())
@dp.message(Command("today","week","month"))
async def report(message:Message):
 data=await api("/bot/summary",message);period=message.text.split()[0][1:].split("@")[0];await message.answer(f"{period.capitalize()}: {data[period]:.2f} {data['currency']}")
@dp.message(Command("list"))
async def list_items(message:Message):
 rows=await api("/bot/expenses",message)
 if not rows:await message.answer("Трат пока нет");return
 chunk=""
 for x in rows:
  line=f"#{x['id']} · {x['amount']:.2f} {x['currency']} · {x['category']} — {x['description']}\n"
  if len(chunk)+len(line)>3500:await message.answer(chunk);chunk=""
  chunk+=line
 if chunk:await message.answer(chunk)
@dp.message(Command("delete"))
async def delete_item(message:Message,command:CommandObject):
 if not command.args or not command.args.isdigit():await message.answer("Формат: /delete ID. Номер видно в /list");return
 try:await api(f"/bot/expenses/{command.args}",message,"DELETE")
 except httpx.HTTPStatusError as exc:
  if exc.response.status_code!=404:raise
  await message.answer("Трата не найдена");return
 await message.answer("Трата удалена")
@dp.message(Command("edit"))
async def edit_item(message:Message,command:CommandObject):
 parts=(command.args or "").split(maxsplit=1)
 if len(parts)!=2 or not parts[0].isdigit() or not (parsed:=parse(parts[1])):await message.answer("Формат: /edit ID сумма описание #Категория");return
 amount,description,category=parsed
 try:
  item=await api(f"/bot/expenses/{parts[0]}",message)
  await api(f"/bot/expenses/{parts[0]}",message,"PUT",{"amount":str(amount),"currency":item['currency'],"category":category,"description":description})
 except httpx.HTTPStatusError as exc:
  if exc.response.status_code!=404:raise
  await message.answer("Трата не найдена");return
 await message.answer("Трата изменена")
 await show_budget_warning(message,item['currency'])

@dp.message(Command("currency"))
@dp.message(F.text=="💱 Валюта")
async def currency_menu(message:Message):
 current=(await api("/bot/settings",message))["currency"]
 await message.answer(f"Сейчас: {current}. Выберите валюту новых записей. Старые суммы не меняются.",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🇹🇯 Сомони · TJS",callback_data="currency:TJS"),InlineKeyboardButton(text="🇷🇺 Рубли · RUB",callback_data="currency:RUB")]]))

@dp.callback_query(F.data.startswith("currency:"))
async def choose_currency(query:CallbackQuery):
 currency=query.data.split(":")[1]
 if currency not in ("TJS","RUB"):await query.answer("Неизвестная валюта");return
 await query.answer()
 try:await api("/bot/settings",query,"PUT",{"currency":currency})
 except httpx.HTTPError:
  await query.message.answer("Не удалось подтвердить смену валюты. Проверьте /currency.");return
 await query.message.answer(f"Валюта новых записей: {currency}. Старые записи сохранены.")

def undo_button(kind, item_id):
 return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ Отменить эту запись",callback_data=f"undo:{kind}:{item_id}")]])

@dp.callback_query(F.data.startswith("undo:"))
async def undo(query:CallbackQuery):
 await query.answer()
 parts=query.data.split(":")
 if len(parts)!=3 or parts[1] not in ("expenses","incomes") or not parts[2].isdigit():return
 try:await api(f"/bot/{parts[1]}/{parts[2]}",query,"DELETE")
 except httpx.HTTPStatusError as exc:
  await query.message.answer("Запись уже удалена или недоступна." if exc.response.status_code==404 else "Не удалось подтвердить отмену. Проверьте /list или /incomes.");return
 except httpx.HTTPError:
  await query.message.answer("Не удалось подтвердить отмену. Проверьте /list или /incomes.");return
 await query.message.edit_reply_markup(reply_markup=None)
 await query.message.answer("Запись отменена. Баланс и бюджет пересчитаны.")

@dp.message(Command("income"))
@dp.message(F.text=="➕ Доход")
async def income(message:Message):
 parts=message.text.split(maxsplit=1)
 parsed=parse(parts[1]) if message.text.startswith("/income") and len(parts)==2 else None
 if not parsed:await message.answer("Введите доход: /income 5000 зарплата\nВалюта — выбранная в /currency.");return
 amount,description,_=parsed
 currency=(await api("/bot/settings",message))["currency"]
 item=await api("/bot/incomes",message,"POST",{"amount":str(amount),"description":description,"currency":currency})
 await message.answer(f"Доход записан: {amount} {currency} · {description}",reply_markup=undo_button("incomes",item['id']))

@dp.message(Command("incomes"))
async def income_list(message:Message):
 rows=await api("/bot/incomes",message)
 if not rows:await message.answer("Доходов пока нет. Добавить: /income 5000 зарплата");return
 for x in rows:
  await message.answer(f"Доход #{x['id']} · {x['amount']} {x['currency']} · {x['description']}",reply_markup=undo_button("incomes",x['id']))

@dp.message(Command("delete_income"))
async def delete_income(message:Message,command:CommandObject):
 if not command.args or not command.args.isdigit():await message.answer("Формат: /delete_income ID. Номер видно в /incomes");return
 try:await api(f"/bot/incomes/{command.args}",message,"DELETE")
 except httpx.HTTPStatusError as exc:
  if exc.response.status_code!=404:raise
  await message.answer("Доход не найден");return
 await message.answer("Доход удалён")

@dp.message(Command("balance"))
@dp.message(F.text=="💰 Баланс")
async def balance(message:Message):
 rows=await api("/bot/balance",message)
 await message.answer("Баланс по всем введённым записям:\n\n"+"\n\n".join(f"{x['currency']}\nДоходы: {x['income']}\nРасходы: {x['expense']}\nОстаток: {x['balance']}" for x in rows)+"\n\nЭто учётный остаток, не баланс банковского счёта. Валюты не складываются.")

def budget_text(data):
 limit=Decimal(data['limit']);spent=Decimal(data['spent']);currency=data['currency']
 if not limit:return f"Бюджет {currency} не установлен. Например: /budget 3000"
 prefix="🚨 Бюджет исчерпан или превышен." if data['level']==100 else "⚠️ Израсходовано не менее 80% бюджета." if data['level']==80 else "🎯 Месячный бюджет"
 return f"{prefix}\nПотрачено: {spent:.2f} из {limit:.2f} {currency}\nОстаток: {limit-spent:.2f} {currency}"

async def show_budget_warning(message,currency):
 try:data=await api(f"/bot/budget?currency={currency}",message)
 except httpx.HTTPError:
  await message.answer("Запись сохранена, но бюджет проверить не удалось. Откройте /budget позже.");return
 if data['level']:await message.answer(budget_text(data))

@dp.message(Command("budget"))
@dp.message(F.text=="🎯 Бюджет")
async def budget(message:Message):
 parts=message.text.split(maxsplit=1)
 if message.text.startswith("/budget") and len(parts)==2:
  value=parts[1].replace(",",".")
  if not re.fullmatch(r"\d{1,10}(?:\.\d{1,2})?",value) or Decimal(value)>=Decimal("10000000000"):
   await message.answer("Формат: /budget 3000. Для отключения: /budget 0");return
  currency=(await api("/bot/settings",message))["currency"]
  data=await api("/bot/budget",message,"PUT",{"currency":currency,"amount":value})
 else:data=await api("/bot/budget",message)
 await message.answer(budget_text(data)+"\nПериод: календарный месяц по UTC. Лимит действует и в следующих месяцах.")

@dp.message(F.text)
async def expense(message:Message):
 data=parse(message.text or "")
 if not data:await message.answer("Формат: «сумма описание», например: 45 такси или 120 обед #Еда");return
 amount,description,category=data
 currency=(await api("/bot/settings",message))["currency"]
 item=await api("/bot/expenses",message,"POST",{"amount":str(amount),"currency":currency,"category":category,"description":description})
 await message.answer(f"Записал: {amount} {currency} · {category} · {description}",reply_markup=undo_button("expenses",item['id']))
 await show_budget_warning(message,currency)
async def main():await dp.start_polling(Bot(TOKEN))
if __name__=="__main__":asyncio.run(main())
