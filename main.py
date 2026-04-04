import logging
import os
import aiosqlite

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import CallbackQuery, Update
from aiogram.filters import Command

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

# FSM орнына
user_data = {}

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


# ---------------- HELP ----------------
@dp.message(Command("help"))
async def help_command(message: types.Message):
    await message.answer("Командалар:\n/start\n/help\n/admin\n/id")


# ---------------- ID ----------------
@dp.message(Command("id"))
async def id_command(message: types.Message):
    await message.answer(f"ID 👉 {message.from_user.id}")


# ---------------- ADMIN ----------------
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_CLASSES:
        return await message.answer("Сен админ емессің ❌")

    await message.answer("Админ панель 🔐", reply_markup=admin_menu())


# ---------------- BACK ----------------
@dp.callback_query(F.data == "back_main")
async def back_main(query: CallbackQuery):
    await query.message.edit_text(
        "Қай сыныпты таңдайсың? 👇",
        reply_markup=main_menu()
    )
    await query.answer()


@dp.callback_query(F.data == "back_admin")
async def back_admin(query: CallbackQuery):
    await query.message.edit_text("Админ панель 🔐", reply_markup=admin_menu())
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
        await query.message.edit_text(
            "Үй тапсырмасы әлі жоқ ❌",
            reply_markup=back_main_btn()
        )
        await query.answer()
        return

    text = ""
    for day, hw in rows:
        text += f"📅 {DAY_NAMES.get(day)}:\n{hw}\n\n"

    await query.message.edit_text(text, reply_markup=back_main_btn())
    await query.answer()


# ---------------- ADD ----------------
@dp.callback_query(F.data == "add_hw")
async def add_hw(query: CallbackQuery):
    user_class = ADMIN_CLASSES.get(query.from_user.id)

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=user_class, callback_data=f"hw_{user_class}")],
        [types.InlineKeyboardButton(text="⬅️ Артқа", callback_data="back_admin")]
    ])

    await query.message.edit_text("Класс 👇", reply_markup=kb)
    await query.answer()


@dp.callback_query(F.data.startswith("hw_"))
async def choose_class(query: CallbackQuery):
    class_name = query.data.split("_")[1]

    user_data[query.from_user.id] = {"class": class_name}

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Дүйсенбі", callback_data="day_mon")],
        [types.InlineKeyboardButton(text="Сейсенбі", callback_data="day_tue")],
        [types.InlineKeyboardButton(text="Сәрсенбі", callback_data="day_wed")],
        [types.InlineKeyboardButton(text="Бейсенбі", callback_data="day_thu")],
        [types.InlineKeyboardButton(text="Жұма", callback_data="day_fri")],
        [types.InlineKeyboardButton(text="⬅️ Артқа", callback_data="back_admin")]
    ])

    await query.message.edit_text("Күн таңда 👇", reply_markup=kb)
    await query.answer()


@dp.callback_query(F.data.startswith("day_"))
async def choose_day(query: CallbackQuery):
    day = query.data.split("_")[1]

    user_data[query.from_user.id]["day"] = day

    await query.message.edit_text("✏️ Үй тапсырманы жаз:")
    await query.answer()


@dp.message()
async def save_hw(message: types.Message):
    data = user_data.get(message.from_user.id)

    if not data:
        return

    class_name = data["class"]
    day = data["day"]

    async with aiosqlite.connect("db.db") as db:
        await db.execute(
            "DELETE FROM homework WHERE class=? AND day=?",
            (class_name, day)
        )
        await db.execute(
            "INSERT INTO homework (class, day, text) VALUES (?, ?, ?)",
            (class_name, day, message.text)
        )
        await db.commit()

    await message.answer("Сақталды ✅")
    user_data.pop(message.from_user.id)


# ---------------- DELETE ----------------
@dp.callback_query(F.data == "delete_menu")
async def delete_menu(query: CallbackQuery):
    user_class = ADMIN_CLASSES.get(query.from_user.id)

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Дүйсенбі", callback_data=f"delete_{user_class}_mon")],
        [types.InlineKeyboardButton(text="Сейсенбі", callback_data=f"delete_{user_class}_tue")],
        [types.InlineKeyboardButton(text="Сәрсенбі", callback_data=f"delete_{user_class}_wed")],
        [types.InlineKeyboardButton(text="Бейсенбі", callback_data=f"delete_{user_class}_thu")],
        [types.InlineKeyboardButton(text="Жұма", callback_data=f"delete_{user_class}_fri")],
        [types.InlineKeyboardButton(text="⬅️ Артқа", callback_data="back_admin")]
    ])

    await query.message.edit_text("Қай күнді өшіреміз?", reply_markup=kb)
    await query.answer()


@dp.callback_query(F.data.startswith("delete_"))
async def delete_hw(query: CallbackQuery):
    _, class_name, day = query.data.split("_")

    async with aiosqlite.connect("db.db") as db:
        await db.execute(
            "DELETE FROM homework WHERE class=? AND day=?",
            (class_name, day)
        )
        await db.commit()

    await query.message.edit_text("Өшірілді ✅", reply_markup=back_main_btn())
    await query.answer()


# ---------------- WEBHOOK ----------------
@app.post("/api/bot")
async def webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)

    await dp.feed_update(bot, update)
    return {"ok": True}


# ---------------- STARTUP ----------------
@app.on_event("startup")
async def on_startup():
    await init_db()