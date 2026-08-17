import logging
import os
import secrets
import sqlite3
from datetime import datetime

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "Mikhail7890").lstrip("@").lower()
DB_PATH = os.getenv("DB_PATH", "coolclass.db")
PORT = int(os.getenv("PORT", "10000"))
WEBHOOK_PATH = "/webhook"
PUBLIC_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET") or secrets.token_urlsafe(32)

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not PUBLIC_URL:
    raise RuntimeError("RENDER_EXTERNAL_URL is not available")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


class LeadForm(StatesGroup):
    parent_name = State()
    child_age = State()
    phone = State()
    interest = State()
    question_text = State()


class QuizState(StatesGroup):
    answering = State()
    child_name = State()
    phone = State()


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, parent_name TEXT, child_age TEXT, phone TEXT, interest TEXT, telegram_username TEXT, created_at TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS quiz_results (id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id TEXT, telegram_username TEXT, child_name TEXT, phone TEXT, score INTEGER, topic_scores TEXT, wrong_questions TEXT, created_at TEXT)")
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


def save_quiz_result(data: dict):
    conn = db()
    conn.execute(
        "INSERT INTO quiz_results(telegram_id,telegram_username,child_name,phone,score,topic_scores,wrong_questions,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (
            str(data.get("telegram_id", "")),
            data.get("username", ""),
            data.get("child_name", ""),
            data.get("phone", ""),
            int(data.get("score", 0)),
            "; ".join(f"{k}: {v}/2" for k, v in data.get("topic_scores", {}).items()),
            ", ".join(str(i + 1) for i in data.get("wrong_questions", [])) or "нет",
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    conn.close()


def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏫 О школе"), KeyboardButton(text="📚 Программа")],
            [KeyboardButton(text="🧠 Проверить математику"), KeyboardButton(text="🕘 Расписание")],
            [KeyboardButton(text="💰 Стоимость"), KeyboardButton(text="📍 Как нас найти")],
            [KeyboardButton(text="🎓 Записаться"), KeyboardButton(text="❓ Задать вопрос")],
        ],
        resize_keyboard=True,
    )


def contact_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить номер телефона", request_contact=True)], [KeyboardButton(text="↩️ Отмена")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def interest_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎓 Поступление"), KeyboardButton(text="🏫 Перевод в школу")],
            [KeyboardButton(text="👀 Экскурсия"), KeyboardButton(text="❓ Пока просто узнаю")],
        ],
        resize_keyboard=True,
    )


def quiz_phone_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить номер телефона", request_contact=True)], [KeyboardButton(text="Пропустить")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


async def register_admin(message: Message):
    username = (message.from_user.username or "").lower()
    if username == ADMIN_USERNAME:
        set_setting("admin_chat_id", str(message.chat.id))
        await message.answer("✅ Вы зарегистрированы как получатель заявок. Новые заявки будут приходить сюда.", reply_markup=main_menu())
        return True
    return False


async def notify_admin(text: str):
    admin_chat_id = get_setting("admin_chat_id")
    if not admin_chat_id:
        logger.warning("Admin chat is not registered. Ask @%s to send /start to the bot.", ADMIN_USERNAME)
        return False
    try:
        await bot.send_message(admin_chat_id, text)
        return True
    except Exception:
        logger.exception("Failed to notify admin")
        return False


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    if await register_admin(message):
        return
    await message.answer(
        "<b>Здравствуйте! Это CoolClass 👋</b>\n\n"
        "Семейная школа во Внуково для детей 1–5 классов. Небольшие классы, математический уклон, английский и спокойная домашняя атмосфера.\n\n"
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
        "• 1–5 классы\n• небольшие классы 7–9 детей\n• математика каждый день\n• английский язык\n• отдельное здание\n• закрытая территория\n• прогулки\n• домашняя атмосфера\n• трёхразовое питание включено\n\n"
        "Главная идея CoolClass — не только дать знания, но и научить ребёнка думать и становиться самостоятельным.",
        reply_markup=main_menu(),
    )


@dp.message(F.text == "📚 Программа")
async def program(message: Message):
    await message.answer(
        "<b>Что изучают дети</b> 📚\n\n"
        "🧮 Математика — каждый день, с акцентом на понимание и умение рассуждать.\n"
        "🇬🇧 Английский язык.\n📖 Основные предметы начальной школы.\n🧠 Развитие самостоятельности и навыков планирования.\n\n"
        "Школа рассчитана на 1–5 классы.",
        reply_markup=main_menu(),
    )


@dp.message(F.text == "🕘 Расписание")
async def schedule(message: Message):
    await message.answer("<b>Режим школы</b> 🕘\n\nПонедельник–пятница\n<b>09:00–18:00</b>\n\nВ течение дня — занятия, питание, прогулки и дополнительные активности.", reply_markup=main_menu())


@dp.message(F.text == "💰 Стоимость")
async def price(message: Message):
    await message.answer("<b>Стоимость обучения</b> 💰\n\n<b>60 000 ₽ в месяц</b>\n\nВ стоимость включено всё необходимое в течение школьного дня, в том числе <b>трёхразовое питание</b>.\n\nЧтобы узнать подробности и подобрать класс для ребёнка, можно записаться на экскурсию.", reply_markup=main_menu())


@dp.message(F.text == "📍 Как нас найти")
async def location(message: Message):
    await message.answer("<b>Адрес CoolClass</b> 📍\n\nМосква, ул. Плотинная, 28\nрайон Внуково\n\n📞 <a href=\"tel:+79296929208\">+7 929 692-92-08</a>", reply_markup=main_menu())


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
    if not message.text or not message.text.strip():
        await message.answer("Укажите возраст или класс ребёнка.")
        return
    await state.update_data(child_age=message.text.strip())
    await state.set_state(LeadForm.phone)
    await message.answer("<b>Оставьте номер телефона</b>, чтобы менеджер мог связаться с вами.", reply_markup=contact_keyboard())


@dp.message(LeadForm.phone, F.contact)
async def lead_phone_contact(message: Message, state: FSMContext):
    await state.update_data(phone=message.contact.phone_number)
    await state.set_state(LeadForm.interest)
    await message.answer("<b>Что вас сейчас интересует?</b>", reply_markup=interest_keyboard())


@dp.message(LeadForm.phone)
async def lead_phone_text(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if len(text) < 7:
        await message.answer("Пожалуйста, отправьте корректный номер телефона кнопкой ниже.", reply_markup=contact_keyboard())
        return
    await state.update_data(phone=text)
    await state.set_state(LeadForm.interest)
    await message.answer("<b>Что вас сейчас интересует?</b>", reply_markup=interest_keyboard())


@dp.message(LeadForm.interest)
async def lead_interest(message: Message, state: FSMContext):
    data = await state.get_data()
    data["interest"] = message.text or "Не указано"
    data["username"] = message.from_user.username or ""
    save_lead(data)
    username = f"@{data['username']}" if data.get("username") else "нет username"
    await notify_admin(
        "🔔 <b>Новая заявка CoolClass</b>\n\n"
        f"👤 Родитель: {data['parent_name']}\n👧 Возраст/класс: {data['child_age']}\n📞 Телефон: {data['phone']}\n"
        f"🎯 Интерес: {data['interest']}\n💬 Telegram: {username}\n🕐 Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n\nИсточник: Telegram-бот"
    )
    await state.clear()
    await message.answer("<b>Спасибо! Заявка принята ✅</b>\n\nМенеджер CoolClass свяжется с вами по указанному номеру.", reply_markup=main_menu())


@dp.message(F.text == "❓ Задать вопрос")
async def question_start(message: Message, state: FSMContext):
    await state.set_state(LeadForm.question_text)
    await message.answer("Напишите ваш вопрос одним сообщением — я передам его менеджеру.", reply_markup=ReplyKeyboardRemove())


@dp.message(LeadForm.question_text)
async def question_receive(message: Message, state: FSMContext):
    question_text = (message.text or "").strip()
    if not question_text:
        await message.answer("Пожалуйста, напишите вопрос текстом.")
        return
    username = f"@{message.from_user.username}" if message.from_user.username else "нет username"
    await notify_admin("❓ <b>Вопрос от посетителя CoolClass</b>\n\n" f"💬 Telegram: {username}\n👤 Имя: {message.from_user.full_name}\n\nВопрос:\n{question_text}")
    await state.clear()
    await message.answer("Спасибо! Вопрос передан менеджеру CoolClass. Вам ответят в ближайшее время.", reply_markup=main_menu())


# -------------------- МАТЕМАТИЧЕСКАЯ ДИАГНОСТИКА --------------------

QUESTIONS = [
    {"topic": "Счёт", "text": "🧮 Посчитай быстрее калькулятора:\n\n47 + 38 = ?", "options": ["75", "85", "95", "83"], "answer": 1, "hint": "Попробуй сложить десятки и единицы отдельно."},
    {"topic": "Счёт", "text": "🧮 Сколько будет:\n\n6 × 7 + 18 = ?", "options": ["60", "58", "65", "52"], "answer": 0, "hint": "Сначала выполни умножение, затем сложение."},
    {"topic": "Задачи", "text": "📖 Внимательно прочитай:\n\nУ Маши было 3 яблока. Она дала 1 яблоко Пете, а потом папа дал ей ещё 5 яблок. Сколько яблок стало у Маши?", "options": ["6", "7", "8", "5"], "answer": 1, "hint": "Сначала убери яблоко, которое Маша отдала, затем прибавь полученные яблоки."},
    {"topic": "Задачи", "text": "📖 Задача-ловушка:\n\nНа столе лежало 10 груш. 5 груш съели. Сколько груш осталось на столе?", "options": ["5", "4", "6", "3"], "answer": 0, "hint": "Если груши съели, их больше нет на столе."},
    {"topic": "Дроби", "text": "🍕 Пиццу разрезали на 8 кусков. Съели 3 куска. Какая часть пиццы осталась?", "options": ["3/8", "5/8", "8/3", "1/2"], "answer": 1, "hint": "Из 8 частей осталось 8 − 3."},
    {"topic": "Дроби", "text": "🧩 Что больше?\n\n2/3 или 4/6?", "options": ["2/3 больше", "4/6 больше", "Они равны", "Не знаю"], "answer": 2, "hint": "Приведи дроби к одному знаменателю или сократи 4/6."},
    {"topic": "Геометрия", "text": "📐 Найди периметр:\n\nУ квадрата сторона = 4 см. Чему равен периметр?", "options": ["8 см", "12 см", "16 см", "4 см"], "answer": 2, "hint": "У квадрата четыре одинаковые стороны."},
    {"topic": "Геометрия", "text": "🔺 Какая фигура лишняя?\n\n1. Квадрат\n2. Круг\n3. Треугольник\n4. Прямоугольник", "options": ["Квадрат", "Круг", "Треугольник", "Прямоугольник"], "answer": 1, "hint": "У всех фигур, кроме одной, есть углы."},
    {"topic": "Логика", "text": "🧠 Продолжи ряд:\n\n2, 4, 8, 16, ?", "options": ["18", "20", "32", "24"], "answer": 2, "hint": "Каждое следующее число в 2 раза больше предыдущего."},
    {"topic": "Логика", "text": "🎯 Сколько концов у 3 палок?\n\nУ каждой палки по два конца.", "options": ["6 концов", "3 конца", "4 конца", "5 концов"], "answer": 0, "hint": "Посчитай по два конца для каждой из трёх палок."},
]

RESULTS = [
    (9, 10, "🏆 Математический гений!", "Видно, что с логикой и базовыми вычислениями всё отлично. Можно переходить к задачам повышенной сложности и олимпиадным заданиям."),
    (7, 8, "🌟 Уверенный ученик!", "Отличный результат. База в целом крепкая, но несколько тем стоит потренировать, чтобы знания стали устойчивыми."),
    (5, 6, "📖 Нужна поддержка", "Ребёнок старался. Результат показывает несколько зон, где спокойная регулярная практика поможет почувствовать себя увереннее."),
    (0, 4, "🔔 Нужна дополнительная помощь", "Тест показал заметные пробелы. Важно начать с понятного ребёнку уровня и постепенно восстановить базу без давления."),
]


def quiz_keyboard(index: int):
    question = QUESTIONS[index]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{chr(65 + i)}) {option}", callback_data=f"quiz:{index}:{i}")]
        for i, option in enumerate(question["options"])
    ])


def result_for_score(score: int):
    for low, high, title, text in RESULTS:
        if low <= score <= high:
            return title, text
    return RESULTS[-1][2], RESULTS[-1][3]


async def show_question(message: Message, index: int):
    question = QUESTIONS[index]
    await message.answer(
        f"<b>Вопрос {index + 1} из 10</b> · {question['topic']}\n\n"
        f"{question['text']}\n\nВыбери один вариант ответа 👇",
        reply_markup=quiz_keyboard(index),
    )


@dp.message(F.text == "🧠 Проверить математику")
async def quiz_start(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(
        index=0,
        score=0,
        attempts=0,
        topic_scores={"Счёт": 0, "Задачи": 0, "Дроби": 0, "Геометрия": 0, "Логика": 0},
        wrong_questions=[],
        telegram_id=message.from_user.id,
        username=message.from_user.username or "",
    )
    await state.set_state(QuizState.answering)
    await message.answer(
        "<b>🧠 Математическая диагностика CoolClass</b>\n\n"
        "10 вопросов · 5 тем · примерно 5 минут.\n\n"
        "Это не школьная контрольная — здесь важно понять, какие темы ребёнок уже знает уверенно, а где нужна практика.\n\n"
        "За каждый вопрос можно получить подсказку. Начинаем! 🚀"
    )
    await show_question(message, 0)


@dp.callback_query(F.data.startswith("quiz:"), QuizState.answering)
async def quiz_answer(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    try:
        _, index_raw, answer_raw = callback.data.split(":")
        index = int(index_raw)
        answer = int(answer_raw)
    except (ValueError, AttributeError):
        return

    data = await state.get_data()
    if index != data.get("index"):
        return

    question = QUESTIONS[index]
    if answer == question["answer"]:
        score = int(data.get("score", 0)) + 1
        topic_scores = dict(data.get("topic_scores", {}))
        topic_scores[question["topic"]] = int(topic_scores.get(question["topic"], 0)) + 1
        await state.update_data(score=score, topic_scores=topic_scores, attempts=0)
        await callback.message.edit_text("✅ <b>Правильно!</b> Отлично, идём дальше.")
    else:
        attempts = int(data.get("attempts", 0)) + 1
        if attempts < 2:
            await state.update_data(attempts=attempts)
            await callback.message.edit_text(
                f"🤔 Пока не угадал. Попробуй ещё раз!\n\n💡 Подсказка: {question['hint']}",
                reply_markup=quiz_keyboard(index),
            )
            return
        wrong = list(data.get("wrong_questions", []))
        wrong.append(index)
        await state.update_data(attempts=0, wrong_questions=wrong)
        await callback.message.edit_text(
            f"❌ В этот раз не получилось. Правильный ответ: <b>{chr(65 + question['answer'])}) {question['options'][question['answer']]}</b>\n\n💡 {question['hint']}"
        )

    next_index = index + 1
    await state.update_data(index=next_index)
    if next_index < 10:
        await show_question(callback.message, next_index)
    else:
        await finish_quiz(callback.message, state)


async def finish_quiz(message: Message, state: FSMContext):
    data = await state.get_data()
    score = int(data.get("score", 0))
    title, description = result_for_score(score)
    topic_scores = data.get("topic_scores", {})
    weak_topics = [topic for topic, value in topic_scores.items() if int(value) < 2]

    lines = ["<b>🎉 Диагностика завершена!</b>", "", f"Результат: <b>{score} из 10</b>", title, "", description, "", "<b>По темам:</b>"]
    for topic in ["Счёт", "Задачи", "Дроби", "Геометрия", "Логика"]:
        value = int(topic_scores.get(topic, 0))
        icon = "🟢" if value == 2 else "🟡" if value == 1 else "🔴"
        lines.append(f"{icon} {topic}: {value}/2")
    if weak_topics:
        lines.extend(["", f"<b>Что стоит потренировать:</b> {', '.join(weak_topics)}."])
    else:
        lines.extend(["", "🔥 Все пять тем пройдены без ошибок — отличный результат!"])
    lines.extend(["", "Хотите получить персональные рекомендации и передать результат специалисту CoolClass?"])

    await state.set_state(QuizState.child_name)
    await message.answer(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Получить рекомендации", callback_data="quiz_lead")],
            [InlineKeyboardButton(text="🏫 Узнать о CoolClass", callback_data="quiz_school")],
        ]),
    )


@dp.callback_query(F.data == "quiz_school")
async def quiz_school(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "<b>CoolClass — семейная школа во Внуково</b> 🏫\n\n"
        "• 7–9 детей в группе\n• математика каждый день\n• английский язык\n• понедельник–пятница, 09:00–18:00\n• отдельное здание и закрытая территория\n• питание включено\n\n"
        "📍 Москва, ул. Плотинная, 28\n📞 +7 929 692-92-08",
        reply_markup=main_menu(),
    )


@dp.callback_query(F.data == "quiz_lead", QuizState.child_name)
async def quiz_lead_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Отлично. Напишите <b>имя ребёнка</b>, чтобы рекомендации были персональными.", reply_markup=ReplyKeyboardRemove())


@dp.message(QuizState.child_name)
async def quiz_child_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Напишите, пожалуйста, имя ребёнка.")
        return
    await state.update_data(child_name=name)
    await state.set_state(QuizState.phone)
    await message.answer("Теперь можно оставить номер телефона — специалист CoolClass сможет связаться с вами по результату диагностики.\n\nЕсли пока не хотите оставлять номер, нажмите «Пропустить».", reply_markup=quiz_phone_keyboard())


async def complete_quiz_lead(message: Message, state: FSMContext, phone: str = ""):
    data = await state.get_data()
    data["phone"] = phone
    save_quiz_result(data)
    weak_topics = [topic for topic, value in data.get("topic_scores", {}).items() if int(value) < 2]
    topic_text = ", ".join(weak_topics) if weak_topics else "нет"
    username = f"@{data['username']}" if data.get("username") else "нет username"
    await notify_admin(
        "🧠 <b>Новая заявка из математической диагностики</b>\n\n"
        f"👧 Ребёнок: {data.get('child_name', 'не указано')}\n📊 Результат: {data.get('score', 0)}/10\n"
        f"📚 Темы для практики: {topic_text}\n📞 Телефон: {phone or 'не указан'}\n💬 Telegram: {username}\n"
        f"🕐 Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    )
    await state.clear()
    await message.answer("<b>Готово ✅</b>\n\nРезультат диагностики сохранён. Специалист CoolClass сможет учесть сильные и слабые стороны ребёнка.\n\nЕсли оставили номер телефона — мы свяжемся с вами.", reply_markup=main_menu())


@dp.message(QuizState.phone, F.contact)
async def quiz_phone_contact(message: Message, state: FSMContext):
    await complete_quiz_lead(message, state, message.contact.phone_number)


@dp.message(QuizState.phone)
async def quiz_phone_text(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text.lower() == "пропустить":
        await complete_quiz_lead(message, state, "")
        return
    if len(text) < 7:
        await message.answer("Отправьте номер кнопкой ниже или нажмите «Пропустить».", reply_markup=quiz_phone_keyboard())
        return
    await complete_quiz_lead(message, state, text)


@dp.message()
async def fallback(message: Message):
    await message.answer("Я могу рассказать о школе, программе, расписании и стоимости или принять заявку. Выберите пункт меню ниже.", reply_markup=main_menu())


async def health(request: web.Request):
    return web.json_response({"status": "ok", "service": "coolclass-telegram-bot"})


async def on_startup(bot_instance: Bot):
    db().close()
    webhook_url = f"{PUBLIC_URL}{WEBHOOK_PATH}"
    await bot_instance.set_webhook(url=webhook_url, secret_token=WEBHOOK_SECRET, drop_pending_updates=False)
    logger.info("CoolClass bot started with webhook: %s", webhook_url)


async def on_shutdown(bot_instance: Bot):
    try:
        await bot_instance.delete_webhook(drop_pending_updates=False)
    except Exception:
        logger.exception("Failed to delete webhook on shutdown")


def create_app():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET, handle_in_background=True)
    webhook_handler.register(app, path=WEBHOOK_PATH)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    setup_application(app, dp, bot=bot)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=PORT)
