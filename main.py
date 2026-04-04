import logging
import os
import aiosqlite
from datetime import datetime
from dotenv import load_dotenv

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ------------------- Настройка -------------------
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(TOKEN)
dp = Dispatcher()
app = FastAPI()

logging.basicConfig(level=logging.INFO)

# Админдердің ID-лары мен сыныптар
ADMIN_CLASSES = {
    5199542672: "8A",
    7357106839: "9A"
}

# ------------------- Дни недели -------------------
DAY_NAMES = {
    "mon": "Дүйсенбі",
    "tue": "Сейсенбі",
    "wed": "Сәрсенбі",
    "thu": "Бейсенбі",
    "fri": "Жұма"
}

# ------------------- FSM -------------------
class AddHW(StatesGroup):
    choosing_day = State()
    waiting_for_text = State()

# ------------------- Клавиатуры -------------------
def main_menu():
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="7A", callback_data="class_7A")],
        [types.InlineKeyboardButton(text="8A", callback_data="class_8A"),
         types.InlineKeyboardButton(text="8Ә", callback_data="class_8AE")],
        [types.InlineKeyboardButton(text="8Б", callback_data="class_8B"),
         types.InlineKeyboardButton(text="9A", callback_data="class_9A")],
    ])

def admin_menu():
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📚 Қосу / Өзгерту", callback_data="add_hw")],
        [types.InlineKeyboardButton(text="🗑 Өшіру", callback_data="delete_menu")],
        [types.InlineKeyboardButton(text="⬅️ Меню", callback_data="back_main")]
    ])

def back_main_btn():
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⬅️ Меню", callback_data="back_main")]
    ])

# ------------------- База данных -------------------
async def init_db():
    async with aiosqlite.connect("db.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS homework (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class TEXT,
            day TEXT,
            text TEXT
        )
        """)
        await db.commit()

# ------------------- Старт / Хелп -------------------
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Сәлем! 👋\nҚай сыныптың үй тапсырмасын көргің келеді? 👇",
        reply_markup=main_menu()
    )

@dp.message(Command("help"))
async def help_command(message: types.Message):
    await message.answer(
        "Командалар:\n"
        "/start - Ботты іске қосу\n"
        "/help - Командалар тізімі\n"
        "/admin - Админ панель, үй жұмысын қосу (тек админдерге)\n"
        "/id - Өзіңнің ID-ыңды алу"
    )

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_CLASSES:
        return await message.answer("Сен админ емессің ❌")
    await message.answer("Админ панель 🔐", reply_markup=admin_menu())

# ------------------- Навигация -------------------
@dp.callback_query(F.data == "back_main")
async def back_main(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.edit_text(
        "Қай сыныптың үй тапсырмасын көргің келеді? 👇",
        reply_markup=main_menu()
    )
    await query.answer()

# ------------------- Показать домашку -------------------
@dp.callback_query(F.data.startswith("class_"))
async def show_hw(query: CallbackQuery):
    class_name = query.data.split("_")[1]
    async with aiosqlite.connect("db.db") as db:
        cursor = await db.execute("SELECT day, text FROM homework WHERE class=?", (class_name,))
        rows = await cursor.fetchall()

    if not rows:
        return await query.message.edit_text(
            "Үй тапсырмасы әлі қосылмаған ❌",
            reply_markup=back_main_btn()
        )

    text = ""
    for day, hw in rows:
        text += f"📅 {DAY_NAMES.get(day)}:\n{hw}\n\n"

    await query.message.edit_text(text, reply_markup=back_main_btn())
    await query.answer()

# ------------------- Добавление / Удаление -------------------
@dp.callback_query(F.data == "add_hw")
async def add_hw_start(query: CallbackQuery, state: FSMContext):
    await state.set_state(AddHW.choosing_day)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=name, callback_data=key)] for key, name in DAY_NAMES.items()
    ])
    await query.message.edit_text("Күнді таңдаңыз:", reply_markup=kb)
    await query.answer()

@dp.callback_query(F.data.in_(DAY_NAMES.keys()))
async def choose_day(query: CallbackQuery, state: FSMContext):
    await state.update_data(day=query.data)
    await state.set_state(AddHW.waiting_for_text)
    await query.message.edit_text("Үй тапсырмасын енгізіңіз:")
    await query.answer()

@dp.message(AddHW.waiting_for_text)
async def save_hw(message: types.Message, state: FSMContext):
    data = await state.get_data()
    day = data["day"]
    class_name = "8A"  # Пример, можно расширить для выбора класса
    async with aiosqlite.connect("db.db") as db:
        await db.execute("INSERT INTO homework (class, day, text) VALUES (?, ?, ?)", (class_name, day, message.text))
        await db.commit()
    await state.clear()
    await message.answer("Үй тапсырмасы қосылды ✅", reply_markup=back_main_btn())

# ------------------- Scheduler и уведомления -------------------
scheduler = AsyncIOScheduler()

async def notify_homework():
    async with aiosqlite.connect("db.db") as db:
        cursor = await db.execute("SELECT class, day, text FROM homework")
        rows = await cursor.fetchall()
    today = datetime.today().strftime("%a").lower()
    for class_name, day, text in rows:
        if day == today:
            # Отправка уведомления всем пользователям (пример)
            logging.info(f"Уведомление для {class_name}: {text}")

scheduler.add_job(notify_homework, "cron", hour=8, minute=0)  # каждый день в 8:00

# ------------------- Webhook для Vercel -------------------
@app.post("/api/bot")
async def webhook(request: Request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return {"ok": True}

# ------------------- Startup -------------------
@app.on_event("startup")
async def on_startup():
    await init_db()
    scheduler.start()