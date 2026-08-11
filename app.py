import logging
import os
import secrets
from datetime import datetime
import sqlite3
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "Mikhail7890").lstrip("@").lower()
PORT = int(os.getenv("PORT", "10000"))
PUBLIC_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
WEBHOOK_PATH = "/webhook"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET") or secrets.token_urlsafe(32)
DB_PATH = os.getenv("DB_PATH", "coolclass.db")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not PUBLIC_URL:
    raise RuntimeError("RENDER_EXTERNAL_URL is not available")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

class LeadForm(StatesGroup):
    parent_name = State(); child_age = State(); phone = State(); interest = State(); question = State()

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT,parent_name TEXT,child_age TEXT,phone TEXT,interest TEXT,telegram_username TEXT,created_at TEXT)")
    conn.commit()
    return conn

def setting(key):
    conn=db(); row=conn.execute("SELECT value FROM settings WHERE key=?",(key,)).fetchone(); conn.close(); return row[0] if row else None

def set_setting(key,value):
    conn=db(); conn.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,value)); conn.commit(); conn.close()

def save_lead(d):
    conn=db(); conn.execute("INSERT INTO leads(parent_name,child_age,phone,interest,telegram_username,created_at) VALUES(?,?,?,?,?,?)",(d['parent_name'],d['child_age'],d['phone'],d['interest'],d.get('username',''),datetime.now().isoformat(timespec='seconds'))); conn.commit(); conn.close()

def menu():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='🏫 О школе'),KeyboardButton(text='📚 Программа')],[KeyboardButton(text='🕘 Расписание'),KeyboardButton(text='💰 Стоимость')],[KeyboardButton(text='📍 Как нас найти'),KeyboardButton(text='🎓 Записаться')],[KeyboardButton(text='❓ Задать вопрос')]],resize_keyboard=True)

def contact_menu(): return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='📱 Отправить номер телефона',request_contact=True)],[KeyboardButton(text='↩️ Отмена')]],resize_keyboard=True,one_time_keyboard=True)
def interest_menu(): return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='🎓 Поступление'),KeyboardButton(text='🏫 Перевод в школу')],[KeyboardButton(text='👀 Экскурсия'),KeyboardButton(text='❓ Пока просто узнаю')]],resize_keyboard=True)

async def notify_admin(text):
    chat_id=setting('admin_chat_id')
    if not chat_id:
        logger.warning('Admin has not started bot')
        return
    try: await bot.send_message(chat_id,text)
    except Exception: logger.exception('Could not notify admin')

@dp.message(CommandStart())
async def start(message:Message,state:FSMContext):
    await state.clear()
    if (message.from_user.username or '').lower()==ADMIN_USERNAME:
        set_setting('admin_chat_id',str(message.chat.id)); await message.answer('✅ Вы зарегистрированы как получатель заявок. Новые заявки будут приходить сюда.',reply_markup=menu()); return
    await message.answer('<b>Здравствуйте! Это CoolClass 👋</b>\n\nСемейная школа во Внуково для детей 1–5 классов. Небольшие классы 7–9 детей, математический уклон, английский и домашняя атмосфера.\n\nВыберите, что хотите узнать:',reply_markup=menu())

@dp.message(Command('cancel'))
@dp.message(F.text=='↩️ Отмена')
async def cancel(message:Message,state:FSMContext): await state.clear(); await message.answer('Заявка отменена.',reply_markup=menu())
@dp.message(F.text=='🏫 О школе')
async def about(message:Message): await message.answer('<b>CoolClass — семейная школа во Внуково</b> 🏫\n\n• 1–5 классы\n• классы 7–9 детей\n• математика каждый день\n• английский язык\n• отдельное здание\n• закрытая территория\n• прогулки\n• домашняя атмосфера\n• трёхразовое питание включено\n\nУчимся думать, а не просто заучивать, и развиваем самостоятельность.',reply_markup=menu())
@dp.message(F.text=='📚 Программа')
async def program(message:Message): await message.answer('<b>Программа</b> 📚\n\n🧮 Математика — каждый день, с акцентом на понимание и рассуждение.\n🇬🇧 Английский язык.\n📖 Основные предметы начальной школы.\n🧠 Самостоятельность и навыки планирования.\n\n1–5 классы.',reply_markup=menu())
@dp.message(F.text=='🕘 Расписание')
async def schedule(message:Message): await message.answer('<b>Расписание</b> 🕘\n\nПонедельник–пятница\n<b>09:00–18:00</b>\n\nЗанятия, питание, прогулки и дополнительные активности.',reply_markup=menu())
@dp.message(F.text=='💰 Стоимость')
async def price(message:Message): await message.answer('<b>Стоимость</b> 💰\n\n<b>60 000 ₽ в месяц</b>\n\nВсё включено, в том числе <b>трёхразовое питание</b>.',reply_markup=menu())
@dp.message(F.text=='📍 Как нас найти')
async def location(message:Message): await message.answer('<b>CoolClass</b> 📍\n\nМосква, ул. Плотинная, 28\nВнуково\n\n📞 <a href="tel:+79296929208">+7 929 692-92-08</a>',reply_markup=menu())
@dp.message(F.text=='🎓 Записаться')
async def begin(message:Message,state:FSMContext): await state.set_state(LeadForm.parent_name); await message.answer('Оставьте заявку — менеджер свяжется с вами.\n\n<b>Как вас зовут?</b>',reply_markup=ReplyKeyboardRemove())
@dp.message(LeadForm.parent_name)
async def name(message:Message,state:FSMContext):
    if not message.text or len(message.text.strip())<2: return await message.answer('Пожалуйста, напишите ваше имя.')
    await state.update_data(parent_name=message.text.strip()); await state.set_state(LeadForm.child_age); await message.answer('<b>Сколько лет ребёнку?</b> Например: «7 лет» или «2 класс».')
@dp.message(LeadForm.child_age)
async def age(message:Message,state:FSMContext):
    if not message.text: return await message.answer('Укажите возраст или класс ребёнка.')
    await state.update_data(child_age=message.text.strip()); await state.set_state(LeadForm.phone); await message.answer('<b>Оставьте номер телефона</b>.',reply_markup=contact_menu())
@dp.message(LeadForm.phone,F.contact)
async def phone_contact(message:Message,state:FSMContext): await state.update_data(phone=message.contact.phone_number); await state.set_state(LeadForm.interest); await message.answer('<b>Что вас сейчас интересует?</b>',reply_markup=interest_menu())
@dp.message(LeadForm.phone)
async def phone_text(message:Message,state:FSMContext):
    text=(message.text or '').strip()
    if len(text)<7: return await message.answer('Отправьте корректный номер кнопкой ниже.',reply_markup=contact_menu())
    await state.update_data(phone=text); await state.set_state(LeadForm.interest); await message.answer('<b>Что вас сейчас интересует?</b>',reply_markup=interest_menu())
@dp.message(LeadForm.interest)
async def interest(message:Message,state:FSMContext):
    d=await state.get_data(); d['interest']=message.text or 'Не указано'; d['username']=message.from_user.username or ''; save_lead(d); u=f"@{d['username']}" if d['username'] else 'нет username'
    await notify_admin('🔔 <b>Новая заявка CoolClass</b>\n\n'+f"👤 Родитель: {d['parent_name']}\n👧 Возраст/класс: {d['child_age']}\n📞 Телефон: {d['phone']}\n🎯 Интерес: {d['interest']}\n💬 Telegram: {u}\n🕐 {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    await state.clear(); await message.answer('<b>Спасибо! Заявка принята ✅</b>\n\nМенеджер CoolClass свяжется с вами.',reply_markup=menu())
@dp.message(F.text=='❓ Задать вопрос')
async def qstart(message:Message,state:FSMContext): await state.set_state(LeadForm.question); await message.answer('Напишите ваш вопрос одним сообщением.',reply_markup=ReplyKeyboardRemove())
@dp.message(LeadForm.question)
async def question(message:Message,state:FSMContext):
    text=(message.text or '').strip()
    if not text: return await message.answer('Напишите вопрос текстом.')
    u=f"@{message.from_user.username}" if message.from_user.username else 'нет username'; await notify_admin(f'❓ <b>Вопрос от посетителя CoolClass</b>\n\n💬 Telegram: {u}\n👤 {message.from_user.full_name}\n\n{text}'); await state.clear(); await message.answer('Спасибо! Вопрос передан менеджеру.',reply_markup=menu())
@dp.message()
async def fallback(message:Message): await message.answer('Выберите пункт меню ниже.',reply_markup=menu())

async def health(request): return web.json_response({'status':'ok','service':'coolclass-telegram-bot'})

async def on_startup(bot_instance: Bot):
    db().close()
    info = await bot_instance.get_me()
    logger.info('Telegram bot authenticated: @%s', info.username)
    await bot_instance.set_webhook(url=f'{PUBLIC_URL}{WEBHOOK_PATH}', secret_token=WEBHOOK_SECRET, drop_pending_updates=False)
    webhook = await bot_instance.get_webhook_info()
    logger.info('Webhook registered: %s pending=%s', webhook.url, webhook.pending_update_count)

async def on_shutdown(bot_instance: Bot):
    logger.info('CoolClass bot shutting down')

async def startup(app: web.Application):
    await on_startup(bot)

async def shutdown(app: web.Application):
    await on_shutdown(bot)
    await bot.session.close()

def create_app():
    app=web.Application()
    app.router.add_get('/',health)
    app.router.add_get('/health',health)
    handler=SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET, handle_in_background=True)
    handler.register(app,path=WEBHOOK_PATH)
    app.on_startup.append(startup)
    app.on_cleanup.append(shutdown)
    return app

if __name__=='__main__':
    web.run_app(create_app(),host='0.0.0.0',port=PORT)
