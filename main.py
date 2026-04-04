import logging
import os
import aiosqlite

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

# ---------------- НАСТРОЙКА ----------------
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(TOKEN)
dp = Dispatcher()
app = FastAPI()

logging.basicConfig(level=logging.INFO)

ADMIN_CLASSES = {
    5199542672: "8A",
    7357106839: "9A"
}

# ---------------- БАЗА ----------------
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


# ---------------- FSM ----------------
class AddHW(StatesGroup):
    choosing_day = State()
    waiting_for_text = State()


# ---------------- DAYS ----------------
DAY_NAMES = {
    "mon": "Дүйсенбі",
    "tue": "Сейсенбі",
    "wed": "Сәрсенбі",
    "thu": "Бейсенбі",
    "fri": "Жұма"
}


# ---------------- MENU ----------------
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


# ---------------- START ----------------
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Сәлем! 👋\nҚай сыныптың үй тапсырмасын көргің келеді? 👇",
        reply_markup=main_menu()
    )


# HELP
@dp.message(Command("help"))
async def help_command(message: types.Message):
    await message.answer(
        "Командалар:\n"
        "/start - Ботты іске қосу\n"
        "/help - Командалар тізімі\n"
        "/admin - Админ панель, үй жұмысын қосу (тек админдерге)\n"
        "/id - Өзіңнің ID-ынды алу"
    )


# ---------------- ADMIN ----------------
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_CLASSES:
        return await message.answer("Сен админ емессің ❌")

    await message.answer("Админ панель 🔐", reply_markup=admin_menu())


# ---------------- BACK ----------------
@dp.callback_query(F.data == "back_main")
async def back_main(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.edit_text(
        "Қай сыныптың үй тапсырмасын көргің келеді? 👇",
        reply_markup=main_menu()
    )
    await query.answer()


# ---------------- SHOW ----------------
@dp.callback_query(F.data.startswith("class_"))
async def show_hw(query: CallbackQuery):
    class_name = query.data.split("_")[1]

    async with aiosqlite.connect("db.db") as db:
        cursor = await db.execute(
            "SELECT day, text FROM homework WHERE class=?",
            (class_name,)
        )
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


# ---------------- WEBHOOK ----------------
@app.post("/api/bot")
async def webhook(request: Request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return {"ok": True}


# ---------------- STARTUP ----------------
@app.on_event("startup")
async def on_startup():
    await init_db()