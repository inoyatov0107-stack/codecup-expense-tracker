import asyncio, os, re, logging
from pathlib import Path
from aiogram.types import FSInputFile, LinkPreviewOptions
from weakref import WeakValueDictionary
from aiogram import BaseMiddleware
from bot_texts import t, labels, language
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
WELCOME_IMAGE = Path(__file__).with_name("welcome.png")
WELCOME_IMAGE_URL = "https://raw.githubusercontent.com/inoyatov0107-stack/codecup-expense-tracker/main/bot/welcome.png?v=robot-v4"
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

VERSION = "2026.09.07.2"
CURRENCIES = {"rub":"RUB","руб":"RUB","рубль":"RUB","рубля":"RUB","рублей":"RUB","р":"RUB","₽":"RUB","tjs":"TJS","сомони":"TJS","сомонӣ":"TJS"}
ZONES = [
 ("Asia/Dushanbe","Душанбе · UTC+5"),("Europe/Moscow","Москва · UTC+3"),
 ("Europe/Kaliningrad","Калининград · UTC+2"),("Europe/Samara","Самара · UTC+4"),
 ("Asia/Yekaterinburg","Екатеринбург · UTC+5"),("Asia/Omsk","Омск · UTC+6"),
 ("Asia/Krasnoyarsk","Красноярск · UTC+7"),("Asia/Irkutsk","Иркутск · UTC+8"),
 ("Asia/Yakutsk","Якутск · UTC+9"),("Asia/Vladivostok","Владивосток · UTC+10"),
 ("Asia/Magadan","Магадан · UTC+11"),("Asia/Kamchatka","Камчатка · UTC+12"),("UTC","UTC")]
def parse_money(text):
 m=PATTERN.match(text or "")
 if not m:return None
 amount,rest=m.groups(); words=rest.split(); currency=None
 if words and words[0].lower().rstrip(".") in CURRENCIES:
  currency=CURRENCIES[words.pop(0).lower().rstrip(".")]
 if words and words[-1].lower().rstrip(".") in CURRENCIES:
  if currency:return None
  currency=CURRENCIES[words.pop().lower().rstrip(".")]
 parsed=parse(amount+" "+" ".join(words))
 return (*parsed,currency) if parsed else None

async def api(path,message,method="GET",payload=None):
 async with api_slots, httpx.AsyncClient(timeout=15) as client:
  r=await client.request(method,f"{API}{path}",json=payload,headers={
   "X-Telegram-Id":str(message.from_user.id),
   "X-Telegram-Name-Encoded":quote(message.from_user.full_name,safe=""),
   "X-Telegram-Username":getattr(message.from_user,"username",None) or "",
   "X-Bot-Token":TOKEN})
  r.raise_for_status();return r.json() if r.content else None

def button(key,data):return InlineKeyboardButton(text=t(key),callback_data=data)
def menu():
 return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t(a)),KeyboardButton(text=t(b))] for a,b in
  (("expenses","balance"),("income","budget"),("currency","help"),("language","timezone"))],resize_keyboard=True,is_persistent=True)
def panel_button():return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t("panel"),url=PANEL_URL)]])
def undo_button(kind,item_id):return InlineKeyboardMarkup(inline_keyboard=[[button("undo",f"undo:{kind}:{item_id}")]])
def start_button():return InlineKeyboardMarkup(inline_keyboard=[[button("start","welcome")]])

class PrivateSession(BaseMiddleware):
 def __init__(self):self.locks=WeakValueDictionary()
 async def __call__(self,handler,event,data):
  target=event.message if isinstance(event,CallbackQuery) else event
  if target is None:return
  if target.chat.type!="private":
   if isinstance(event,CallbackQuery):await event.answer()
   else:await target.answer(t("private"))
   return
  lock=self.locks.setdefault(event.from_user.id,asyncio.Lock())
  async with lock:
   token=None
   try:
    profile=await api("/bot/visit",event,"POST")
    token=language.set(profile["language"])
    is_start=(getattr(event,"text","") or "").split()[0:1] in (["/start"],["/help"])
    is_start=is_start or (isinstance(event,CallbackQuery) and event.data=="welcome")
    if not is_start and profile["seen_version"]!=VERSION:
     await target.answer(t("release"),reply_markup=start_button())
     await api("/bot/profile/seen",event,"PUT",{"version":VERSION})
    return await handler(event,data)
   except Exception as exc:
    logging.error("Private handler failed: %s",type(exc).__name__)
    key="invalid" if isinstance(exc,httpx.HTTPStatusError) and exc.response.status_code==422 else "network"
    await target.answer(t(key))
   finally:
    if token is not None:language.reset(token)
session_middleware=PrivateSession()
dp.message.outer_middleware(session_middleware)
dp.callback_query.outer_middleware(session_middleware)

async def welcome(actor,target,show_image=False):
 # A text message keeps the full help text beyond the 1024-character photo caption limit.
 preview = LinkPreviewOptions(url=WELCOME_IMAGE_URL,prefer_large_media=True,show_above_text=True) if show_image else LinkPreviewOptions(is_disabled=True)
 await target.answer(t("welcome")+t("help_text"),reply_markup=menu(),link_preview_options=preview)
 await target.answer(t("language_hint"),reply_markup=InlineKeyboardMarkup(inline_keyboard=[
  [InlineKeyboardButton(text="Русский",callback_data="language:ru"),InlineKeyboardButton(text="Тоҷикӣ",callback_data="language:tg")],
  [button("timezone","timezone_menu"),button("currency","currency_menu")],
  *([[button("original_image","welcome_original")]] if show_image else [])]))
 await api("/bot/profile/seen",actor,"PUT",{"version":VERSION})

@dp.message(Command("start","help"))
@dp.message(F.text.in_(labels("help")))
async def start(message:Message):
 await welcome(message,message,show_image=(message.text or "").split()[0].split("@")[0]=="/start")
help_message=start
@dp.callback_query(F.data=="welcome")
async def start_callback(query:CallbackQuery):
 await query.answer();await welcome(query,query.message,show_image=True)
@dp.callback_query(F.data=="welcome_original")
async def welcome_original(query:CallbackQuery):
 await query.answer()
 await query.message.answer_document(FSInputFile(WELCOME_IMAGE,filename="CodeCup-original.png"))
@dp.message(Command("updates"))
async def updates(message:Message):
 await message.answer(t("release"),reply_markup=start_button())
@dp.message(Command("myid"))
async def myid(message:Message):
 await message.answer(f"Telegram ID: {message.from_user.id}")
@dp.message(F.text.in_(labels("expenses")))
async def dashboard(message:Message):
 await message.answer(t("panel_hint"),reply_markup=panel_button())
MONTH_NAMES = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
def month_keyboard(year):
 return InlineKeyboardMarkup(inline_keyboard=[
  [InlineKeyboardButton(text=MONTH_NAMES[m-1],callback_data=f"history:{year}:{m}") for m in range(first,first+3)] for first in (1,4,7,10)
 ]+[[InlineKeyboardButton(text=f"‹ {year-1}",callback_data=f"history_year:{year-1}"),InlineKeyboardButton(text=f"{year+1} ›",callback_data=f"history_year:{year+1}")]])

@dp.message(Command("month"))
async def choose_month(message:Message):
 from datetime import datetime
 from zoneinfo import ZoneInfo
 data=await api("/bot/summary",message)
 year=datetime.now(ZoneInfo(data["timezone"])).year
 await message.answer(f"{t('month')}: {data['month']:.2f} {data['currency']}\nВыберите месяц · {year}",reply_markup=month_keyboard(year))

@dp.callback_query(F.data.startswith("history_year:"))
async def history_year(query:CallbackQuery):
 year=int(query.data.split(":")[1])
 if not 2<=year<=9997:await query.answer();return
 await query.answer()
 await query.message.edit_text(f"Выберите месяц · {year}",reply_markup=month_keyboard(year))

@dp.callback_query(F.data.startswith("history:"))
async def history_month(query:CallbackQuery):
 _,year,month=query.data.split(":")
 await query.answer()
 data=await api(f"/bot/month?year={year}&month={month}",query)
 totals="\n".join(f"{Decimal(data['totals'].get(c,'0')):.2f} {c}" for c in ("RUB","TJS"))
 text=f"{MONTH_NAMES[int(month)-1]} {year}\nРасходы:\n{totals}\n{data['timezone']}"
 if query.message.text==text:return
 from aiogram.exceptions import TelegramBadRequest
 try:
  await query.message.edit_text(text,reply_markup=month_keyboard(int(year)))
 except TelegramBadRequest as exc:
  if "message is not modified" not in str(exc).lower():raise

@dp.message(Command("today","week"))
async def report(message:Message):
 data=await api("/bot/summary",message);period=message.text.split()[0][1:].split("@")[0]
 await message.answer(f"{t(period)}: {data[period]:.2f} {data['currency']}\n{data['timezone']}")
@dp.message(Command("list"))
async def list_items(message:Message):
 rows=await api("/bot/expenses",message)
 if not rows:await message.answer(t("empty"));return
 chunk=""
 for x in rows:
  line=f"#{x['id']} · {x['amount']:.2f} {x['currency']} · {x['category']} — {x['description']}\n"
  if len(chunk)+len(line)>3500:await message.answer(chunk);chunk=""
  chunk+=line
 if chunk:await message.answer(chunk)

async def remove(actor,target,kind,item_id,undoing=False):
 try:await api(f"/bot/{kind}/{item_id}",actor,"DELETE")
 except httpx.HTTPStatusError as exc:
  if exc.response.status_code!=404:raise
  await target.answer(t("already" if undoing else "missing"));return False
 await target.answer(t("undone" if undoing else "removed"));return True
@dp.message(Command("delete"))
async def delete_item(message:Message,command:CommandObject):
 if not command.args or not command.args.isdigit():
  await message.answer(t("delete_format",command="delete",listing="list"));return
 await remove(message,message,"expenses",command.args)
@dp.message(Command("delete_income"))
async def delete_income(message:Message,command:CommandObject):
 if not command.args or not command.args.isdigit():
  await message.answer(t("delete_format",command="delete_income",listing="incomes"));return
 await remove(message,message,"incomes",command.args)
@dp.callback_query(F.data.startswith("undo:"))
async def undo(query:CallbackQuery):
 await query.answer();parts=query.data.split(":")
 if len(parts)!=3 or parts[1] not in ("expenses","incomes") or not parts[2].isdigit():return
 if await remove(query,query.message,parts[1],parts[2],True):
  await query.message.edit_reply_markup(reply_markup=None)

@dp.message(Command("edit"))
async def edit_item(message:Message,command:CommandObject):
 parts=(command.args or "").split(maxsplit=1)
 if len(parts)!=2 or not parts[0].isdigit() or not (parsed:=parse_money(parts[1])):
  await message.answer(t("edit_format"));return
 amount,description,category,currency=parsed
 try:
  item=await api(f"/bot/expenses/{parts[0]}",message)
  if currency and currency!=item["currency"]:
   await message.answer(t("edit_currency"));return
  await api(f"/bot/expenses/{parts[0]}",message,"PUT",{"amount":str(amount),"currency":item["currency"],"category":category,"description":description})
 except httpx.HTTPStatusError as exc:
  if exc.response.status_code!=404:raise
  await message.answer(t("missing"));return
 await message.answer(t("edited"));await show_budget_warning(message,item["currency"])

async def show_currency(actor,target):
 current=(await api("/bot/settings",actor))["currency"]
 await target.answer(t("currency_hint",currency=current),reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
  InlineKeyboardButton(text="🇹🇯 Сомонӣ · TJS",callback_data="currency:TJS"),InlineKeyboardButton(text="🇷🇺 Рубли · RUB",callback_data="currency:RUB")]]))
@dp.message(Command("currency"))
@dp.message(F.text.in_(labels("currency")))
async def currency_menu(message:Message):await show_currency(message,message)
@dp.callback_query(F.data=="currency_menu")
async def currency_callback(query:CallbackQuery):
 await query.answer();await show_currency(query,query.message)
@dp.callback_query(F.data.startswith("currency:"))
async def choose_currency(query:CallbackQuery):
 await query.answer();currency=query.data.split(":")[1]
 if currency not in ("TJS","RUB"):return
 await api("/bot/settings",query,"PUT",{"currency":currency})
 await query.message.answer(t("currency_saved",currency=currency))

@dp.message(Command("language"))
@dp.message(F.text.in_(labels("language")))
async def language_menu(message:Message):
 await message.answer(t("language_hint"),reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
  InlineKeyboardButton(text="Русский",callback_data="language:ru"),InlineKeyboardButton(text="Тоҷикӣ",callback_data="language:tg")]]))
@dp.callback_query(F.data.startswith("language:"))
async def choose_language(query:CallbackQuery):
 await query.answer();value=query.data.split(":")[1]
 if value not in ("ru","tg"):return
 await api("/bot/profile",query,"PUT",{"language":value})
 token=language.set(value)
 try:await welcome(query,query.message)
 finally:language.reset(token)
async def show_timezone(actor,target):
 profile=await api("/bot/profile",actor)
 await target.answer(t("timezone_hint",zone=profile["timezone"]),reply_markup=InlineKeyboardMarkup(inline_keyboard=[
  [InlineKeyboardButton(text=label,callback_data=f"zone:{zone}")] for zone,label in ZONES]))
@dp.message(Command("timezone"))
@dp.message(F.text.in_(labels("timezone")))
async def timezone_menu(message:Message):await show_timezone(message,message)
@dp.callback_query(F.data=="timezone_menu")
async def timezone_callback(query:CallbackQuery):
 await query.answer();await show_timezone(query,query.message)
@dp.callback_query(F.data.startswith("zone:"))
async def choose_timezone(query:CallbackQuery):
 await query.answer();zone=query.data.split(":",1)[1]
 if zone not in dict(ZONES):return
 await api("/bot/profile",query,"PUT",{"timezone":zone})
 await query.message.answer(t("timezone_saved",zone=zone))

@dp.message(Command("income"))
@dp.message(F.text.in_(labels("income")))
async def income(message:Message):
 parts=message.text.split(maxsplit=1)
 parsed=parse_money(parts[1]) if message.text.startswith("/income") and len(parts)==2 else None
 if not parsed:await message.answer(t("income_format"));return
 amount,description,_,currency=parsed
 currency=currency or (await api("/bot/settings",message))["currency"]
 item=await api("/bot/incomes",message,"POST",{"amount":str(amount),"description":description,"currency":currency})
 await message.answer(t("income_saved",amount=amount,currency=currency,description=description),reply_markup=undo_button("incomes",item["id"]))
@dp.message(Command("incomes"))
async def income_list(message:Message):
 rows=await api("/bot/incomes",message)
 if not rows:await message.answer(t("empty_income"));return
 for x in rows:
  await message.answer(f"#{x['id']} · {x['amount']} {x['currency']} · {x['description']}",reply_markup=undo_button("incomes",x["id"]))
@dp.message(Command("balance"))
@dp.message(F.text.in_(labels("balance")))
async def balance(message:Message):
 rows=await api("/bot/balance",message)
 await message.answer(t("balance_intro")+"\n\n"+"\n\n".join(t("balance_row",**x) for x in rows)+"\n\n"+t("balance_note"))

def budget_text(data):
 limit=Decimal(data["limit"]);spent=Decimal(data["spent"]);currency=data["currency"]
 if not limit:return t("budget_none",currency=currency)
 key="budget_100" if data["level"]==100 else "budget_80" if data["level"]==80 else "budget_title"
 return t(key)+"\n"+t("budget_row",spent=f"{spent:.2f}",limit=f"{limit:.2f}",remaining=f"{limit-spent:.2f}",currency=currency)
async def show_budget_warning(message,currency):
 try:data=await api(f"/bot/budget?currency={currency}",message)
 except httpx.HTTPError:
  await message.answer(t("budget_failed"));return
 if data["level"]:await message.answer(budget_text(data))
@dp.message(Command("budget"))
@dp.message(F.text.in_(labels("budget")))
async def budget(message:Message):
 parts=message.text.split(maxsplit=1)
 if message.text.startswith("/budget") and len(parts)==2:
  value=parts[1].replace(",",".")
  if not re.fullmatch(r"\d{1,10}(?:\.\d{1,2})?",value) or Decimal(value)>=Decimal("10000000000"):
   await message.answer(t("budget_format"));return
  currency=(await api("/bot/settings",message))["currency"]
  data=await api("/bot/budget",message,"PUT",{"currency":currency,"amount":value})
 else:data=await api("/bot/budget",message)
 await message.answer(budget_text(data)+"\n"+t("budget_period",zone=data["timezone"]))

async def show_users(actor,target,page=1):
 try:data=await api(f"/bot/admin/users?page={page}",actor)
 except httpx.HTTPStatusError as exc:
  if exc.response.status_code!=403:raise
  await target.answer(t("admin_denied"));return
 lines=[t("admin_title",**{k:data[k] for k in ("total","page","pages")})]
 for x in data["users"]:
  name=" ".join(x["name"].split())[:128]
  username="@"+x["username"][:32] if x["username"] else t("no_username")
  lines.append(f"• {name} · {username}")
 buttons=[]
 if page>1:buttons.append(button("previous",f"users:{page-1}"))
 if page<data["pages"]:buttons.append(button("next",f"users:{page+1}"))
 await target.answer("\n".join(lines),reply_markup=InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None)
@dp.message(Command("users","stats"))
async def users(message:Message):await show_users(message,message)
@dp.callback_query(F.data.startswith("users:"))
async def users_page(query:CallbackQuery):
 await query.answer();page=query.data.split(":")[1]
 if page.isdigit() and 1<=int(page)<=1000000:await show_users(query,query.message,int(page))

@dp.message(F.text)
async def expense(message:Message):
 data=parse_money(message.text or "")
 if not data:await message.answer(t("format"));return
 amount,description,category,currency=data
 currency=currency or (await api("/bot/settings",message))["currency"]
 item=await api("/bot/expenses",message,"POST",{"amount":str(amount),"currency":currency,"category":category,"description":description})
 await message.answer(t("saved",amount=amount,currency=currency,category=category,description=description),reply_markup=undo_button("expenses",item["id"]))
 await show_budget_warning(message,currency)
async def main():
 bot=Bot(TOKEN)
 try:
  me=await bot.get_me()
  photos=await bot.get_user_profile_photos(me.id,limit=1)
  if photos.total_count==0:
   import json
   with Path(__file__).with_name("avatar.jpg").open("rb") as photo:
    async with httpx.AsyncClient(timeout=30) as client:
     response=await client.post(f"https://api.telegram.org/bot{TOKEN}/setMyProfilePhoto",data={"photo":json.dumps({"type":"static","photo":"attach://avatar"})},files={"avatar":("avatar.jpg",photo,"image/jpeg")})
     success=response.json().get("ok",False)
     logging.warning("Initial bot avatar installed: %s",success)
 except Exception as exc:
  logging.warning("Avatar setup failed: %s",type(exc).__name__)
 await dp.start_polling(bot)
if __name__=="__main__":asyncio.run(main())
