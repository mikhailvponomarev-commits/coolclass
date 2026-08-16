import logging
import os
import secrets
import sqlite3
from datetime import datetime

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

TOKEN = os.getenv("BOT_TOKEN", "").strip()
PORT = int(os.getenv("PORT", "10000"))
URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
SECRET = os.getenv("WEBHOOK_SECRET") or secrets.token_urlsafe(24)
ADMIN = os.getenv("ADMIN_USERNAME", "Mikhail7890").lstrip("@").lower()
DB = os.getenv("DB_PATH", "coolclass.db")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not URL:
    raise RuntimeError("RENDER_EXTERNAL_URL is not available")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("coolclass")

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


class Lead(StatesGroup):
    parent = State()
    child = State()
    phone = State()
    interest = State()
    question = State()


def conn():
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY,v TEXT NOT NULL)")
    c.commit()
    return c


def get(key):
    c = conn()
    row = c.execute("SELECT v FROM settings WHERE k=?", (key,)).fetchone()
    c.close()
    return row[0] if row else None


def put(key, value):
    c = conn()
    c.execute(
        "INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
        (key, value),
    )
    c.commit()
    c.close()


def menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏫 О школе"), KeyboardButton(text="📚 Программа")],
            [KeyboardButton(text="🕘 Расписание"), KeyboardButton(text="💰 Стоимость")],
            [KeyboardButton(text="📍 Как нас найти"), KeyboardButton(text="🎓 Записаться")],
            [KeyboardButton(text="❓ Задать вопрос")],
        ],
        resize_keyboard=True,
    )


def phone_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить номер телефона", request_contact=True)],
            [KeyboardButton(text="↩️ Отмена")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def interest_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎓 Поступление"), KeyboardButton(text="🏫 Перевод в школу")],
            [KeyboardButton(text="👀 Экскурсия"), KeyboardButton(text="❓ Пока просто узнаю")],
        ],
        resize_keyboard=True,
    )


async def notify_admin(text):
    chat_id = get("admin_chat_id")
    if not chat_id:
        log.warning("admin_chat_id is empty; owner must press /start in private chat")
        return
    try:
        await bot.send_message(chat_id, text)
    except Exception:
        log.exception("admin notification failed")


def is_group(message: Message):
    return message.chat.type in {"group", "supergroup"}


def normalized_command(text: str) -> str:
    text = (text or "").strip().lower()
    if not text:
        return ""
    first = text.split()[0]
    return first.split("@", 1)[0]


async def send_schedule(message: Message):
    await message.answer("🕘 <b>Расписание</b>\n\nПонедельник–пятница\n<b>09:00–18:00</b>")


async def send_price(message: Message):
    await message.answer(
        "💰 <b>Стоимость</b>\n\n<b>65 000 ₽ в месяц</b>\n\n"
        "Всё включено, в том числе <b>трёхразовое питание</b>."
    )


async def send_signup(message: Message):
    await message.answer(
        "🎓 <b>Заявка</b>\n\n"
        "Откройте личный чат с @CoolclassVnukovobot и нажмите Start.\n"
        "Телефон и данные ребёнка собираются только в личном чате."
    )


async def send_question_info(message: Message):
    await message.answer(
        "❓ Откройте личный чат с @CoolclassVnukovobot и задайте вопрос — "
        "контактные данные останутся приватными."
    )


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    log.info(
        "START chat_id=%s type=%s user=%s text=%r",
        message.chat.id,
        message.chat.type,
        message.from_user.id if message.from_user else None,
        message.text,
    )

    if is_group(message):
        await message.answer(
            "👋 <b>Добро пожаловать в группу CoolClass!</b>\n\n"
            "/расписание — расписание\n"
            "/стоимость — стоимость\n"
            "/записаться — заявка\n"
            "/вопрос — вопрос\n\n"
            "🔒 Телефон и данные ребёнка бот собирает только в личном чате."
        )
        return

    if (message.from_user.username or "").lower() == ADMIN:
        put("admin_chat_id", str(message.chat.id))
        await message.answer(
            "✅ Вы зарегистрированы. Новые заявки будут приходить сюда.",
            reply_markup=menu(),
        )
        return

    await message.answer(
        "<b>Здравствуйте! Это CoolClass 👋</b>\n\n"
        "Семейная школа во Внуково, 1–5 классы, группы 7–9 детей, математический уклон.\n\n"
        "Выберите раздел:",
        reply_markup=menu(),
    )


# Group commands. These handlers intentionally do not use aiogram's Command filter,
# so that both /command and /command@CoolclassVnukovobot are accepted.
@dp.message(lambda m: is_group(m) and normalized_command(m.text) in {"/расписание", "/schedule"})
async def group_schedule(message: Message):
    log.info("GROUP schedule chat_id=%s text=%r", message.chat.id, message.text)
    await send_schedule(message)


@dp.message(lambda m: is_group(m) and normalized_command(m.text) in {"/стоимость", "/price"})
async def group_price(message: Message):
    log.info("GROUP price chat_id=%s text=%r", message.chat.id, message.text)
    await send_price(message)


@dp.message(lambda m: is_group(m) and normalized_command(m.text) in {"/записаться", "/signup"})
async def group_signup(message: Message):
    log.info("GROUP signup chat_id=%s text=%r", message.chat.id, message.text)
    await send_signup(message)


@dp.message(lambda m: is_group(m) and normalized_command(m.text) in {"/вопрос", "/question"})
async def group_question(message: Message):
    log.info("GROUP question chat_id=%s text=%r", message.chat.id, message.text)
    await send_question_info(message)


@dp.message(lambda m: is_group(m) and (m.text or "").strip().lower() in {"расписание", "стоимость", "записаться", "вопрос"})
async def group_plain_text(message: Message):
    text = (message.text or "").strip().lower()
    log.info("GROUP plain chat_id=%s text=%r", message.chat.id, text)
    handlers = {
        "расписание": send_schedule,
        "стоимость": send_price,
        "записаться": send_signup,
        "вопрос": send_question_info,
    }
    await handlers[text](message)


@dp.message(lambda m: is_group(m) and bool(m.text))
async def group_fallback(message: Message):
    log.info("GROUP fallback chat_id=%s text=%r", message.chat.id, message.text)
    await message.answer(
        "🤖 Я на связи. Используйте /расписание, /стоимость, /записаться или /вопрос"
    )


# Channel posts are a different Telegram update type. They are handled separately.
@dp.channel_post(lambda m: normalized_command(m.text) in {"/расписание", "/schedule"})
async def channel_schedule(message: Message):
    log.info("CHANNEL schedule chat_id=%s text=%r", message.chat.id, message.text)
    await send_schedule(message)


@dp.channel_post(lambda m: normalized_command(m.text) in {"/стоимость", "/price"})
async def channel_price(message: Message):
    log.info("CHANNEL price chat_id=%s text=%r", message.chat.id, message.text)
    await send_price(message)


@dp.channel_post(lambda m: normalized_command(m.text) in {"/записаться", "/signup"})
async def channel_signup(message: Message):
    log.info("CHANNEL signup chat_id=%s text=%r", message.chat.id, message.text)
    await send_signup(message)


@dp.channel_post(lambda m: normalized_command(m.text) in {"/вопрос", "/question"})
async def channel_question(message: Message):
    log.info("CHANNEL question chat_id=%s text=%r", message.chat.id, message.text)
    await send_question_info(message)


# Private chat menu.
@dp.message(lambda m: not is_group(m) and m.text == "🏫 О школе")
async def about(message: Message):
    await message.answer(
        "<b>CoolClass — семейная школа во Внуково</b> 🏫\n\n"
        "1–5 классы\nГруппы 7–9 детей\nМатематика каждый день\nАнглийский\n"
        "Отдельное здание\nЗакрытая территория\nПрогулки\nТрёхразовое питание включено",
        reply_markup=menu(),
    )


@dp.message(lambda m: not is_group(m) and m.text == "📚 Программа")
async def program(message: Message):
    await message.answer(
        "<b>Программа</b> 📚\n\n"
        "Математика каждый день, английский язык, основные предметы, развитие самостоятельности.\n\n"
        "1–5 классы.",
        reply_markup=menu(),
    )


@dp.message(lambda m: not is_group(m) and m.text == "🕘 Расписание")
async def private_schedule(message: Message):
    await send_schedule(message)


@dp.message(lambda m: not is_group(m) and m.text == "💰 Стоимость")
async def private_price(message: Message):
    await send_price(message)


@dp.message(lambda m: not is_group(m) and m.text == "📍 Как нас найти")
async def location(message: Message):
    await message.answer(
        "<b>CoolClass</b> 📍\n\nМосква, ул. Плотинная, 28\nВнуково\n📞 +7 929 692-92-08",
        reply_markup=menu(),
    )


@dp.message(lambda m: not is_group(m) and m.text == "🎓 Записаться")
async def begin_signup(message: Message, state: FSMContext):
    await state.set_state(Lead.parent)
    await message.answer("Оставьте заявку.\n\n<b>Как вас зовут?</b>", reply_markup=ReplyKeyboardRemove())


@dp.message(Lead.parent)
async def lead_parent(message: Message, state: FSMContext):
    await state.update_data(parent=message.text or "")
    await state.set_state(Lead.child)
    await message.answer("<b>Возраст или класс ребёнка?</b>")


@dp.message(Lead.child)
async def lead_child(message: Message, state: FSMContext):
    await state.update_data(child=message.text or "")
    await state.set_state(Lead.phone)
    await message.answer("<b>Номер телефона:</b>", reply_markup=phone_menu())


@dp.message(Lead.phone)
async def lead_phone(message: Message, state: FSMContext):
    phone = message.contact.phone_number if message.contact else (message.text or "").strip()
    if len(phone) < 7:
        await message.answer("Пожалуйста, отправьте номер телефона кнопкой ниже.", reply_markup=phone_menu())
        return
    await state.update_data(phone=phone)
    await state.set_state(Lead.interest)
    await message.answer("<b>Что вас интересует?</b>", reply_markup=interest_menu())


@dp.message(Lead.interest)
async def lead_interest(message: Message, state: FSMContext):
    data = await state.get_data()
    data["interest"] = message.text or ""
    username = "@" + message.from_user.username if message.from_user.username else "нет username"
    await notify_admin(
        "🔔 <b>Новая заявка CoolClass</b>\n\n"
        f"👤 {data.get('parent', '')}\n"
        f"👧 {data.get('child', '')}\n"
        f"📞 {data.get('phone', '')}\n"
        f"🎯 {data.get('interest', '')}\n"
        f"💬 {username}\n"
        f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    )
    await state.clear()
    await message.answer("✅ <b>Заявка принята!</b> Менеджер свяжется с вами.", reply_markup=menu())


@dp.message(lambda m: not is_group(m) and m.text == "❓ Задать вопрос")
async def question_start(message: Message, state: FSMContext):
    await state.set_state(Lead.question)
    await message.answer("Напишите ваш вопрос.", reply_markup=ReplyKeyboardRemove())


@dp.message(Lead.question)
async def lead_question(message: Message, state: FSMContext):
    username = "@" + message.from_user.username if message.from_user.username else "нет username"
    await notify_admin(f"❓ <b>Вопрос</b>\n\n{username}\n{message.text or ''}")
    await state.clear()
    await message.answer("Спасибо! Вопрос передан менеджеру.", reply_markup=menu())


async def health(request):
    return web.json_response({"status": "ok", "bot": "CoolClass"})


async def startup(*args, **kwargs):
    conn().close()
    me = await bot.get_me()
    log.info("BOT OK @%s id=%s", me.username, me.id)

    # Telegram Bot API command names must be latin lowercase/digits/underscores.
    # Russian commands are still accepted by the group handlers as plain text.
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Начать"),
            BotCommand(command="schedule", description="Расписание"),
            BotCommand(command="price", description="Стоимость"),
            BotCommand(command="signup", description="Оставить заявку"),
            BotCommand(command="question", description="Задать вопрос"),
        ]
    )

    webhook_url = URL + "/webhook"
    await bot.set_webhook(
        url=webhook_url,
        secret_token=SECRET,
        drop_pending_updates=False,
        allowed_updates=["message", "channel_post"],
    )
    info = await bot.get_webhook_info()
    log.info(
        "WEBHOOK=%s pending=%s allowed=%s",
        info.url,
        info.pending_update_count,
        info.allowed_updates,
    )


async def shutdown(*args, **kwargs):
    try:
        await bot.delete_webhook(drop_pending_updates=False)
    finally:
        await bot.session.close()


app = web.Application()
app.router.add_get("/", health)
app.router.add_get("/health", health)

handler = SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=SECRET)
handler.register(app, path="/webhook")

# Register lifecycle callbacks before setup_application so startup/shutdown are deterministic.
dp.startup.register(startup)
dp.shutdown.register(shutdown)
setup_application(app, dp, bot=bot)


if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
