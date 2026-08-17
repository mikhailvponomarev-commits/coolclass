import sqlite3
from datetime import datetime

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

from bot import DB_PATH, db, dp, main_menu, notify_admin


QUIZ_BUTTON = "🧠 Проверить математику"


class QuizState(StatesGroup):
    answering = State()
    child_name = State()
    phone = State()


QUESTIONS = [
    {
        "topic": "Счёт",
        "text": "🧮 Посчитай быстрее калькулятора:\n\n47 + 38 = ?",
        "options": ["75", "85", "95", "83"],
        "answer": 1,
        "hint": "Попробуй сложить десятки и единицы отдельно.",
    },
    {
        "topic": "Счёт",
        "text": "🧮 Сколько будет:\n\n6 × 7 + 18 = ?",
        "options": ["60", "58", "65", "52"],
        "answer": 0,
        "hint": "Сначала выполни умножение, затем сложение.",
    },
    {
        "topic": "Задачи",
        "text": "📖 Внимательно прочитай:\n\nУ Маши было 3 яблока. Она дала 1 яблоко Пете, а потом папа дал ей ещё 5 яблок. Сколько яблок стало у Маши?",
        "options": ["6", "7", "8", "5"],
        "answer": 1,
        "hint": "Сначала убери яблоко, которое Маша отдала, затем прибавь полученные яблоки.",
    },
    {
        "topic": "Задачи",
        "text": "📖 Задача-ловушка:\n\nНа столе лежало 10 груш. 5 груш съели. Сколько груш осталось на столе?",
        "options": ["5", "4", "6", "3"],
        "answer": 0,
        "hint": "Если груши съели, их больше нет на столе.",
    },
    {
        "topic": "Дроби",
        "text": "🍕 Пиццу разрезали на 8 кусков. Съели 3 куска. Какая часть пиццы осталась?",
        "options": ["3/8", "5/8", "8/3", "1/2"],
        "answer": 1,
        "hint": "Из 8 частей осталось 8 − 3.",
    },
    {
        "topic": "Дроби",
        "text": "🧩 Что больше?\n\n2/3 или 4/6?",
        "options": ["2/3 больше", "4/6 больше", "Они равны", "Не знаю"],
        "answer": 2,
        "hint": "Приведи дроби к одному знаменателю или сократи 4/6.",
    },
    {
        "topic": "Геометрия",
        "text": "📐 Найди периметр:\n\nУ квадрата сторона = 4 см. Чему равен периметр?",
        "options": ["8 см", "12 см", "16 см", "4 см"],
        "answer": 2,
        "hint": "У квадрата четыре одинаковые стороны.",
    },
    {
        "topic": "Геометрия",
        "text": "🔺 Какая фигура лишняя?\n\n1. Квадрат\n2. Круг\n3. Треугольник\n4. Прямоугольник",
        "options": ["Квадрат", "Круг", "Треугольник", "Прямоугольник"],
        "answer": 1,
        "hint": "У всех фигур, кроме одной, есть углы.",
    },
    {
        "topic": "Логика",
        "text": "🧠 Продолжи ряд:\n\n2, 4, 8, 16, ?",
        "options": ["18", "20", "32", "24"],
        "answer": 2,
        "hint": "Каждое следующее число в 2 раза больше предыдущего.",
    },
    {
        "topic": "Логика",
        "text": "🎯 Сколько концов у 3 палок?\n\nУ каждой палки по два конца.",
        "options": ["6 концов", "3 конца", "4 конца", "5 концов"],
        "answer": 0,
        "hint": "Посчитай по два конца для каждой из трёх палок.",
    },
]


RESULTS = [
    (9, 10, "🏆 Математический гений!", "Видно, что с логикой и базовыми вычислениями всё отлично. Можно переходить к задачам повышенной сложности и олимпиадным заданиям."),
    (7, 8, "🌟 Уверенный ученик!", "Отличный результат. База в целом крепкая, но несколько тем стоит потренировать, чтобы знания стали устойчивыми."),
    (5, 6, "📖 Нужна поддержка", "Ребёнок старался. Результат показывает несколько зон, где спокойная регулярная практика поможет почувствовать себя увереннее."),
    (0, 4, "🔔 Нужна дополнительная помощь", "Тест показал заметные пробелы. Важно начать с понятного ребёнку уровня и постепенно восстановить базу без давления."),
]


def quiz_keyboard(index: int) -> InlineKeyboardMarkup:
    question = QUESTIONS[index]
    buttons = [
        [InlineKeyboardButton(text=f"{chr(65 + i)}) {option}", callback_data=f"quiz:{index}:{i}")]
        for i, option in enumerate(question["options"])
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def result_for_score(score: int):
    for low, high, title, text in RESULTS:
        if low <= score <= high:
            return title, text
    return RESULTS[-1][2], RESULTS[-1][3]


def init_quiz_db():
    conn = db()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS quiz_results (id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id TEXT, telegram_username TEXT, child_name TEXT, phone TEXT, score INTEGER, topic_scores TEXT, wrong_questions TEXT, created_at TEXT)"
    )
    conn.commit()
    conn.close()


def save_quiz_result(data: dict):
    conn = sqlite3.connect(DB_PATH)
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


def lead_phone_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить номер телефона", request_contact=True)],
            [KeyboardButton(text="Пропустить")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


async def show_question(message: Message, state: FSMContext, index: int, edit: bool = False):
    question = QUESTIONS[index]
    text = (
        f"<b>Вопрос {index + 1} из {len(QUESTIONS)}</b> · {question['topic']}\n\n"
        f"{question['text']}\n\n"
        "Выбери один вариант ответа 👇"
    )
    if edit:
        await message.edit_text(text, reply_markup=quiz_keyboard(index))
    else:
        await message.answer(text, reply_markup=quiz_keyboard(index))


@dp.message(F.text == QUIZ_BUTTON)
async def quiz_start(message: Message, state: FSMContext):
    init_quiz_db()
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
    await show_question(message, state, 0)


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
        await state.update_data(score=score, topic_scores=topic_scores)
        await callback.message.edit_text("✅ <b>Правильно!</b> Отлично, идём дальше.")
        await next_question(callback.message, state, index)
        return

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
        f"❌ В этот раз не получилось. Правильный ответ: <b>{chr(65 + question['answer'])}) {question['options'][question['answer']]}</b>\n\n"
        f"💡 {question['hint']}"
    )
    await next_question(callback.message, state, index)


async def next_question(message: Message, state: FSMContext, current_index: int):
    next_index = current_index + 1
    await state.update_data(index=next_index, attempts=0)
    if next_index >= len(QUESTIONS):
        await finish_quiz(message, state)
        return
    await show_question(message, state, next_index)


async def finish_quiz(message: Message, state: FSMContext):
    data = await state.get_data()
    score = int(data.get("score", 0))
    title, description = result_for_score(score)
    topic_scores = data.get("topic_scores", {})
    weak_topics = [topic for topic, value in topic_scores.items() if int(value) < 2]
    strong_topics = [topic for topic, value in topic_scores.items() if int(value) == 2]

    lines = [
        "<b>🎉 Диагностика завершена!</b>",
        "",
        f"Результат: <b>{score} из 10</b>",
        f"{title}",
        "",
        description,
        "",
        "<b>По темам:</b>",
    ]
    for topic in ["Счёт", "Задачи", "Дроби", "Геометрия", "Логика"]:
        value = int(topic_scores.get(topic, 0))
        icon = "🟢" if value == 2 else "🟡" if value == 1 else "🔴"
        lines.append(f"{icon} {topic}: {value}/2")

    if weak_topics:
        lines.extend(["", f"<b>Что стоит потренировать:</b> {', '.join(weak_topics)}."])
    else:
        lines.extend(["", "🔥 Все пять тем пройдены без ошибок — отличный результат!"])

    lines.extend([
        "",
        "Хотите получить персональные рекомендации и передать результат специалисту CoolClass?",
    ])
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Получить рекомендации", callback_data="quiz_lead")],
        [InlineKeyboardButton(text="🏫 Узнать о CoolClass", callback_data="quiz_school")],
    ])
    await state.set_state(QuizState.child_name)
    await message.answer("\n".join(lines), reply_markup=keyboard)


@dp.callback_query(F.data == "quiz_school")
async def quiz_school(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "<b>CoolClass — семейная школа во Внуково</b> 🏫\n\n"
        "• 7–9 детей в группе\n"
        "• математика каждый день\n"
        "• английский язык\n"
        "• понедельник–пятница, 09:00–18:00\n"
        "• отдельное здание и закрытая территория\n"
        "• питание включено\n\n"
        "📍 Москва, ул. Плотинная, 28\n"
        "📞 +7 929 692-92-08",
        reply_markup=main_menu(),
    )


@dp.callback_query(F.data == "quiz_lead", QuizState.child_name)
async def quiz_lead_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(QuizState.child_name)
    await callback.message.answer(
        "Отлично. Напишите <b>имя ребёнка</b>, чтобы рекомендации были персональными.",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(QuizState.child_name)
async def quiz_child_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Напишите, пожалуйста, имя ребёнка.")
        return
    await state.update_data(child_name=name)
    await state.set_state(QuizState.phone)
    await message.answer(
        "Теперь можно оставить номер телефона — специалист CoolClass сможет связаться с вами по результату диагностики.\n\n"
        "Если пока не хотите оставлять номер, нажмите «Пропустить».",
        reply_markup=lead_phone_keyboard(),
    )


async def complete_quiz_lead(message: Message, state: FSMContext, phone: str = ""):
    data = await state.get_data()
    data["phone"] = phone
    save_quiz_result(data)
    weak_topics = [topic for topic, value in data.get("topic_scores", {}).items() if int(value) < 2]
    topic_text = ", ".join(weak_topics) if weak_topics else "нет"
    username = f"@{data['username']}" if data.get("username") else "нет username"
    admin_text = (
        "🧠 <b>Новая заявка из математической диагностики</b>\n\n"
        f"👧 Ребёнок: {data.get('child_name', 'не указано')}\n"
        f"📊 Результат: {data.get('score', 0)}/10\n"
        f"📚 Темы для практики: {topic_text}\n"
        f"📞 Телефон: {phone or 'не указан'}\n"
        f"💬 Telegram: {username}\n"
        f"🕐 Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    )
    await notify_admin(admin_text)
    await state.clear()
    await message.answer(
        "<b>Готово ✅</b>\n\n"
        "Результат диагностики сохранён. Специалист CoolClass сможет учесть сильные и слабые стороны ребёнка.\n\n"
        "Если оставили номер телефона — мы свяжемся с вами.",
        reply_markup=main_menu(),
    )


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
        await message.answer("Отправьте номер кнопкой ниже или нажмите «Пропустить».", reply_markup=lead_phone_keyboard())
        return
    await complete_quiz_lead(message, state, text)


# Register the quiz database table when the module is imported.
init_quiz_db()
