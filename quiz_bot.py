import asyncio
import logging
import os
import sqlite3
from datetime import datetime

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "Mikhail7890").lstrip("@").lower()
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "").strip()
DB_PATH = os.getenv("DB_PATH", "coolclass_quiz.db")
PORT = int(os.getenv("PORT", "10000"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "coolclass-quiz")
PUBLIC_URL = (os.getenv("PUBLIC_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

bot = Bot(TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class QuizState(StatesGroup):
    answering = State()
    child_name = State()
    phone = State()

QUESTIONS = [
    ("Счёт", "🧮 Посчитай быстрее калькулятора:\n\n47 + 38 = ?", ["75", "85", "95", "83"], 1, "Сложи десятки и единицы отдельно."),
    ("Счёт", "🧮 Сколько будет:\n\n6 × 7 + 18 = ?", ["60", "58", "65", "52"], 0, "Сначала умножение, затем сложение."),
    ("Задачи", "📖 У Маши было 3 яблока. Она дала 1 яблоко Пете, а потом папа дал ей ещё 5 яблок. Сколько яблок стало у Маши?", ["6", "7", "8", "5"], 1, "Сначала убери 1 яблоко, затем прибавь 5."),
    ("Задачи", "📖 На столе лежало 10 груш. 5 груш съели. Сколько груш осталось на столе?", ["5", "4", "6", "3"], 0, "Съеденные груши больше не лежат на столе."),
    ("Дроби", "🍕 Пиццу разрезали на 8 кусков. Съели 3 куска. Какая часть пиццы осталась?", ["3/8", "5/8", "8/3", "1/2"], 1, "Из 8 частей осталось 8 − 3."),
    ("Дроби", "🧩 Что больше?\n\n2/3 или 4/6?", ["2/3 больше", "4/6 больше", "Они равны", "Не знаю"], 2, "Сократи 4/6 или приведи дроби к общему знаменателю."),
    ("Геометрия", "📐 У квадрата сторона = 4 см. Чему равен периметр?", ["8 см", "12 см", "16 см", "4 см"], 2, "У квадрата четыре одинаковые стороны."),
    ("Геометрия", "🔺 Какая фигура лишняя?\n\n1. Квадрат\n2. Круг\n3. Треугольник\n4. Прямоугольник", ["Квадрат", "Круг", "Треугольник", "Прямоугольник"], 1, "У всех остальных фигур есть углы."),
    ("Логика", "🧠 Продолжи ряд:\n\n2, 4, 8, 16, ?", ["18", "20", "32", "24"], 2, "Каждое следующее число в 2 раза больше предыдущего."),
    ("Логика", "🎯 Сколько концов у 3 палок?\n\nУ каждой палки по два конца.", ["6 концов", "3 конца", "4 конца", "5 концов"], 0, "У каждой из трёх палок по два конца."),
]

RESULTS = [
    (9, "🏆 Математический гений!", "Отличный результат. Можно переходить к задачам повышенной сложности и олимпиадным заданиям."),
    (7, "🌟 Уверенный ученик!", "База в целом крепкая, но несколько тем стоит потренировать, чтобы знания стали устойчивыми."),
    (5, "📖 Нужна поддержка", "Несколько зон требуют спокойной регулярной практики — так ребёнок станет увереннее."),
    (0, "🔔 Нужна дополнительная помощь", "Есть заметные пробелы. Важно начать с понятного ребёнку уровня и постепенно восстановить базу без давления."),
]

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS admins (username TEXT PRIMARY KEY, chat_id TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS quiz_results (id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id TEXT, telegram_username TEXT, child_name TEXT, phone TEXT, score INTEGER, topic_scores TEXT, wrong_questions TEXT, created_at TEXT)")
    conn.commit()
    return conn

def save_result(data):
    conn = db()
    conn.execute("INSERT INTO quiz_results(telegram_id,telegram_username,child_name,phone,score,topic_scores,wrong_questions,created_at) VALUES(?,?,?,?,?,?,?,?)", (str(data.get("telegram_id", "")), data.get("username", ""), data.get("child_name", ""), data.get("phone", ""), int(data.get("score", 0)), "; ".join(f"{k}: {v}/2" for k, v in data.get("topic_scores", {}).items()), ", ".join(str(i + 1) for i in data.get("wrong_questions", [])) or "нет", datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()

def register_admin(username, chat_id):
    if not username or username.lower() != ADMIN_USERNAME:
        return
    conn = db()
    conn.execute("INSERT INTO admins(username,chat_id) VALUES(?,?) ON CONFLICT(username) DO UPDATE SET chat_id=excluded.chat_id", (username.lower(), str(chat_id)))
    conn.commit()
    conn.close()

def get_admin_chat_id():
    if ADMIN_CHAT_ID:
        return ADMIN_CHAT_ID
    conn = db()
    row = conn.execute("SELECT chat_id FROM admins WHERE username=?", (ADMIN_USERNAME,)).fetchone()
    conn.close()
    return row[0] if row else None

def answer_keyboard(index):
    q = QUESTIONS[index]
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{chr(65+i)}) {q[2][i]}", callback_data=f"quiz:{index}:{i}")] for i in range(4)])

def lead_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📱 Отправить номер телефона", request_contact=True)], [KeyboardButton(text="Пропустить")]], resize_keyboard=True, one_time_keyboard=True)

async def show_question(message, index):
    topic, text, _, _, _ = QUESTIONS[index]
    await message.answer(f"<b>Вопрос {index+1} из 10</b> · {topic}\n\n{text}\n\nВыбери один вариант ответа 👇", reply_markup=answer_keyboard(index))

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    register_admin(message.from_user.username or "", message.chat.id)
    await state.clear()
    await message.answer("<b>🧠 Математическая диагностика CoolClass</b>\n\n10 вопросов · 5 тем · примерно 5 минут.\n\nЭто не контрольная. Мы хотим понять, какие темы ребёнок уже знает уверенно, а где нужна практика.\n\nЗа каждый вопрос можно получить подсказку. Начинаем! 🚀", reply_markup=ReplyKeyboardRemove())
    await state.update_data(index=0, score=0, attempts=0, topic_scores={"Счёт":0,"Задачи":0,"Дроби":0,"Геометрия":0,"Логика":0}, wrong_questions=[], telegram_id=message.from_user.id, username=message.from_user.username or "")
    await state.set_state(QuizState.answering)
    await show_question(message, 0)

@dp.callback_query(F.data.startswith("quiz:"), QuizState.answering)
async def answer(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    try:
        _, index_s, answer_s = callback.data.split(":")
        index, selected = int(index_s), int(answer_s)
    except Exception:
        return
    data = await state.get_data()
    if index != int(data.get("index", -1)):
        return
    topic, text, options, correct, hint = QUESTIONS[index]
    if selected == correct:
        topics = dict(data["topic_scores"])
        topics[topic] += 1
        await state.update_data(score=int(data["score"])+1, topic_scores=topics, attempts=0)
        await callback.message.edit_text("✅ <b>Правильно!</b> Отлично, идём дальше.")
        await next_question(callback.message, state, index)
        return
    attempts = int(data.get("attempts", 0)) + 1
    if attempts < 2:
        await state.update_data(attempts=attempts)
        await callback.message.edit_text(f"🤔 Пока не угадал. Попробуй ещё раз!\n\n💡 Подсказка: {hint}", reply_markup=answer_keyboard(index))
        return
    wrong = list(data.get("wrong_questions", [])); wrong.append(index)
    await state.update_data(attempts=0, wrong_questions=wrong)
    await callback.message.edit_text(f"❌ В этот раз не получилось. Правильный ответ: <b>{chr(65+correct)}) {options[correct]}</b>\n\n💡 {hint}")
    await next_question(callback.message, state, index)

async def next_question(message, state, current):
    nxt = current + 1
    if nxt >= 10:
        await finish(message, state); return
    await state.update_data(index=nxt, attempts=0)
    await show_question(message, nxt)

async def finish(message, state):
    data = await state.get_data(); score = int(data["score"]); topics = data["topic_scores"]
    result = RESULTS[0]
    for minimum, title, description in RESULTS:
        if score >= minimum:
            result = (minimum, title, description); break
    weak = [k for k,v in topics.items() if v < 2]
    lines = ["<b>🎉 Диагностика завершена!</b>", "", f"Результат: <b>{score} из 10</b>", result[1], "", result[2], "", "<b>По темам:</b>"]
    for topic in ["Счёт","Задачи","Дроби","Геометрия","Логика"]:
        value = topics[topic]; icon = "🟢" if value == 2 else "🟡" if value == 1 else "🔴"; lines.append(f"{icon} {topic}: {value}/2")
    lines += ["", f"<b>Что стоит потренировать:</b> {', '.join(weak)}." if weak else "🔥 Все пять тем пройдены без ошибок — отличный результат!", "", "Хотите получить персональные рекомендации от CoolClass?"]
    await state.update_data(score=score, topic_scores=topics)
    await state.set_state(QuizState.child_name)
    await message.answer("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📋 Получить рекомендации", callback_data="quiz_lead")]]))

@dp.callback_query(F.data == "quiz_lead")
async def lead_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(QuizState.child_name)
    await callback.message.answer("Как зовут ребёнка?", reply_markup=ReplyKeyboardRemove())

@dp.message(QuizState.child_name)
async def child_name(message: Message, state: FSMContext):
    await state.update_data(child_name=(message.text or "").strip())
    await state.set_state(QuizState.phone)
    await message.answer("Оставьте номер телефона родителя — мы передадим результат специалисту CoolClass.", reply_markup=lead_keyboard())

@dp.message(QuizState.phone)
async def phone(message: Message, state: FSMContext):
    data = await state.get_data()
    phone = message.contact.phone_number if message.contact else (message.text or "").strip()
    if phone == "Пропустить": phone = "не указан"
    data["phone"] = phone
    save_result(data)
    admin_id = get_admin_chat_id()
    report = f"🔔 <b>Новая диагностика CoolClass</b>\n\n👧 Ребёнок: {data.get('child_name','')}\n📞 Телефон: {phone}\n📊 Результат: <b>{data.get('score',0)}/10</b>\n🧩 Темы: " + "; ".join(f"{k}: {v}/2" for k,v in data.get("topic_scores",{}).items()) + f"\n💬 @{data.get('username') or 'нет'}"
    if admin_id:
        try: await bot.send_message(admin_id, report)
        except Exception: pass
    await state.clear()
    await message.answer("✅ Спасибо! Результат диагностики сохранён и передан специалисту CoolClass. Мы свяжемся с вами.", reply_markup=ReplyKeyboardRemove())

async def health(request):
    return web.json_response({"status":"ok","bot":"CoolClassTest"})

async def on_startup(app):
    db().close()
    if not PUBLIC_URL:
        logger.error("Webhook URL is empty: PUBLIC_URL and RENDER_EXTERNAL_URL are not set")
        return
    webhook_url = f"{PUBLIC_URL}/webhook"
    try:
        me = await bot.get_me()
        logger.info("Telegram bot: @%s (%s)", me.username, me.id)
        await bot.set_webhook(webhook_url, secret_token=WEBHOOK_SECRET, drop_pending_updates=False)
        info = await bot.get_webhook_info()
        logger.info("Webhook configured: url=%s pending=%s last_error=%s", info.url, info.pending_update_count, info.last_error_message)
    except Exception:
        logger.exception("Failed to configure Telegram webhook")

async def on_shutdown(app):
    await bot.delete_webhook(drop_pending_updates=False)
    await bot.session.close()

app = web.Application()
app.router.add_get("/", health)
app.router.add_get("/health", health)
handler = SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET)
handler.register(app, path="/webhook")
setup_application(app, dp, bot=bot)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
