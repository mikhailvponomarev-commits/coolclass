import asyncio
import logging
import os
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "Mikhail7890").lstrip("@").lower()
DB_PATH = os.getenv("DB_PATH", "coolclass.db")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

class LeadForm(StatesGroup):
    parent_name = State()
    child_age = State()
    phone = State()
    interest = State()


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, parent_name TEXT, child_age TEXT, phone TEXT, interest TEXT, telegram_username TEXT, created_at TEXT)")
    conn.commit()
    return conn


def set_setting(key: str, value: str):
    conn = db()
    conn.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    conn.commit()
    conn.close()


def get_setting(key: str):
    conn = db()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row[0] if row else None


def save_lead(data: dict):
    conn = db()
    conn.execute(
        "INSERT INTO leads(parent_name,child_age,phone,interest,telegram_username,created_at) VALUES(?,?,?,?,?,?)",
        (data["parent_name"], data["child_age"], data["phone"], data["interest"], data.get("username", ""), datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()


def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🏫 О школе"), KeyboardButton(text="📚 Программа")],
        [KeyboardButton(text="🕘 Расписание"), KeyboardButton(text="💰 Стоимость")],
        [KeyboardButton(text="📍 Как нас найти"), KeyboardButton(text="🎓 Записаться")],
        [KeyboardButton(text="❓ Задать вопрос")],
    ], resize_keyboard=True)


def contact_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📱 Отправить номер телефона", request_contact=True)],
        [KeyboardButton(text="↩️ Отмена")],
    ], resize_keyboard=True, one_time_keyboard=True)


async def register_admin(message: Message):
    username = (message.from_user.username or "").lower()
    if username == ADMIN_USERNAME:
        set_setting("admin_chat_id", str(message.chat.id))
        await message.answer("✅ Вы зарегистрированы как получатель заявок. Новые заявки будут приходить сюда.", reply_markup=main_menu())
        return True
    return False


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    if await register_admin(message):
        return
    await message.answer(
        "<b>Здравствуйте! Это CoolClass 👋</b>\n\n"
        "Семейная школа во Внуково для детей 1–5 классов. "
        "Небольшие классы, математический уклон, английский и спокойная домашняя атмосфера.\n\n"
        "Выберите, что хотите узнать:",
        reply_markup=main_menu(),
    )


@dp.message(Command("cancel"))
@dp.message(F.text == "↩️ Отмена")
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Заявка отменена. Чем ещё могу помочь?", reply_markup=main_menu())


@dp.message(F.text == "🏫 О школе")
async def about(message: Message):
    await message.answer(
        "<b>CoolClass — семейная школа во Внуково</b> 🏫\n\n"
        "• 1–5 классы\n"
        "• небольшие классы 7–9 детей\n"
        "• математика каждый день\n"
        "• английский язык\n"
        "• отдельное здание\n"
        "• закрытая территория\n"
        "• прогулки\n"
        "• домашняя атмосфера\n"
        "• трёхразовое питание включено\n\n"
        "Главная идея CoolClass — не только дать знания, но и научить ребёнка думать и становиться самостоятельным.",
        reply_markup=main_menu(),
    )


@dp.message(F.text == "📚 Программа")
async def program(message: Message):
    await message.answer(
        "<b>Что изучают дети</b> 📚\n\n"
        "🧮 Математика — каждый день, с акцентом на понимание и умение рассуждать.\n"
        "🇬🇧 Английский язык.\n"
        "📖 Основные предметы начальной школы.\n"
        "🧠 Развитие самостоятельности и навыков планирования.\n\n"
        "Школа рассчитана на 1–5 классы.",
        reply_markup=main_menu(),
    )


@dp.message(F.text == "🕘 Расписание")
async def schedule(message: Message):
    await message.answer(
        "<b>Режим школы</b> 🕘\n\n"
        "Понедельник–пятница\n"
        "<b>09:00–18:00</b>\n\n"
        "В течение дня — занятия, питание, прогулки и дополнительные активности.",
        reply_markup=main_menu(),
    )


@dp.message(F.text == "💰 Стоимость")
async def price(message: Message):
    await message.answer(
        "<b>Стоимость обучения</b> 💰\n\n"
        "<b>65 000 ₽ в месяц</b>\n\n"
        "В стоимость включено всё необходимое в течение школьного дня, в том числе <b>трёхразовое питание</b>.\n\n"
        "Чтобы узнать подробности и подобрать класс для ребёнка, можно записаться на экскурсию.",
        reply_markup=main_menu(),
    )


@dp.message(F.text == "📍 Как нас найти")
async def location(message: Message):
    await message.answer(
        "<b>Адрес CoolClass</b> 📍\n\n"
        "Москва, ул. Плотинная, 28\n"
        "район Внуково\n\n"
        "📞 <a href=\"tel:+79296929208\">+7 929 692-92-08</a>",
        reply_markup=main_menu(),
    )


@dp.message(F.text == "🎓 Записаться")
async def begin_lead(message: Message, state: FSMContext):
    await state.set_state(LeadForm.parent_name)
    await message.answer("Отлично! Оставьте заявку — менеджер свяжется с вами.\n\n<b>Как вас зовут?</b>", reply_markup=ReplyKeyboardRemove())


@dp.message(LeadForm.parent_name)
async def lead_name(message: Message, state: FSMContext):
    if not message.text or len(message.text.strip()) < 2:
        await message.answer("Пожалуйста, напишите ваше имя.")
        return
    await state.update_data(parent_name=message.text.strip())
    await state.set_state(LeadForm.child_age)
    await message.answer("<b>Сколько лет ребёнку?</b> Можно написать возраст или класс, например: «7 лет» или «2 класс».")


@dp.message(LeadForm.child_age)
async def lead_age(message: Message, state: FSMContext):
    if not message.text or len(message.text.strip()) < 1:
        await message.answer("Укажите возраст или класс ребёнка.")
        return
    await state.update_data(child_age=message.text.strip())
    await state.set_state(LeadForm.phone)
    await message.answer("<b>Оставьте номер телефона</b>, чтобы менеджер мог связаться с вами.", reply_markup=contact_keyboard())


@dp.message(LeadForm.phone, F.contact)
async def lead_phone_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    await state.update_data(phone=phone)
    await state.set_state(LeadForm.interest)
    await message.answer("<b>Что вас сейчас интересует?</b>", reply_markup=ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎓 Поступление"), KeyboardButton(text="🏫 Перевод в школу")],
        [KeyboardButton(text="👀 Экскурсия"), KeyboardButton(text="❓ Пока просто узнаю")],
    ], resize_keyboard=True))


@dp.message(LeadForm.phone)
async def lead_phone_text(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if len(text) < 7:
        await message.answer("Пожалуйста, отправьте корректный номер телефона кнопкой ниже.", reply_markup=contact_keyboard())
        return
    await state.update_data(phone=text)
    await state.set_state(LeadForm.interest)
    await message.answer("<b>Что вас сейчас интересует?</b>", reply_markup=ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎓 Поступление"), KeyboardButton(text="🏫 Перевод в школу")],
        [KeyboardButton(text="👀 Экскурсия"), KeyboardButton(text="❓ Пока просто узнаю")],
    ], resize_keyboard=True))


@dp.message(LeadForm.interest)
async def lead_interest(message: Message, state: FSMContext):
    data = await state.get_data()
    data["interest"] = message.text or "Не указано"
    data["username"] = message.from_user.username or ""
    save_lead(data)

    admin_chat_id = get_setting("admin_chat_id")
    if admin_chat_id:
        username = f"@{data['username']}" if data.get("username") else "нет username"
        text = (
            "🔔 <b>Новая заявка CoolClass</b>\n\n"
            f"👤 Родитель: {data['parent_name']}\n"
            f"👧 Возраст/класс: {data['child_age']}\n"
            f"📞 Телефон: {data['phone']}\n"
            f"🎯 Интерес: {data['interest']}\n"
            f"💬 Telegram: {username}\n\n"
            "Источник: Telegram-бот"
        )
        try:
            await bot.send_message(admin_chat_id, text)
        except Exception:
            logger.exception("Failed to notify admin")
    else:
        logger.warning("Admin chat is not registered. Ask @%s to send /start to the bot.", ADMIN_USERNAME)

    await state.clear()
    await message.answer(
        "<b>Спасибо! Заявка принята ✅</b>\n\n"
        "Менеджер CoolClass свяжется с вами по указанному номеру.\n\n"
        "Если хотите, можете сразу посмотреть информацию о школе в меню.",
        reply_markup=main_menu(),
    )


@dp.message(F.text == "❓ Задать вопрос")
async def question(message: Message):
    await message.answer(
        "Напишите ваш вопрос одним сообщением — я передам его менеджеру.\n\n"
        "Также можно позвонить: +7 929 692-92-08",
        reply_markup=main_menu(),
    )


@dp.message()
async def fallback(message: Message):
    await message.answer(
        "Я могу рассказать о школе, программе, расписании и стоимости или принять заявку. Выберите пункт меню ниже.",
        reply_markup=main_menu(),
    )


async def main():
    db().close()
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("CoolClass bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
