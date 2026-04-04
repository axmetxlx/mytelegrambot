import os
import logging
import aiosqlite
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ------------------- НАСТРОЙКА -------------------
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

ADMIN_CLASSES = {
    5199542672: "8A",
    7357106839: "9A"
}

bot = Bot(TOKEN)
dp = Dispatcher()
app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------- БАЗА -------------------
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

# ------------------- FSM -------------------
class AddHW(StatesGroup):
    choosing_day = State()
    waiting_for_text = State()

# ------------------- DAYS -------------------
DAY_NAMES = {
    "mon": "Дүйсенбі",
    "tue": "Сейсенбі",
    "wed": "Сәрсенбі",
    "thu": "Бейсенбі",
    "fri": "Жұма"
}

# ------------------- MENU -------------------
def main_menu():
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="7A", callback_data="class_7A")],
        [types.InlineKeyboardButton(text="8A", callback_data="class_8A"),
         types.InlineKeyboardButton(text="8Ә", callback_data="class_8AE")],
        [types.InlineKeyboardButton(text="8Б", callback_data="class_8B"),
         types.InlineKeyboardButton(text="9A", callback_data="class_9A")]
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

# ------------------- START -------------------
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Сәлем! 👋\nҚай сыныптың үй тапсырмасын көргің келеді? 👇",
        reply_markup=main_menu()
    )

# ------------------- HELP -------------------
@dp.message(Command("help"))
async def help_command(message: types.Message):
    await message.answer(
        "Командалар:\n"
        "/start - Ботты іске қосу\n"
        "/help - Командалар тізімі\n"
        "/admin - Админ панель, үй жұмысын қосу (тек админдерге)\n"
        "/id - Өзіңнің ID-ың"
    )

# ------------------- ID -------------------
@dp.message(Command("id"))
async def id_command(message: types.Message):
    await message.answer(f"Сенің ID-ың 👉: {message.from_user.id}")

# ------------------- ADMIN -------------------
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_CLASSES:
        return await message.answer("Сен админ емессің ❌")
    await message.answer("Админ панель 🔐", reply_markup=admin_menu())

# ------------------- CALLBACKS -------------------
# Back main
@dp.callback_query(F.data == "back_main")
async def back_main(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.edit_text(
        "Қай сыныптың үй тапсырмасын көргің келеді? 👇",
        reply_markup=main_menu()
    )
    await query.answer()

# Back admin
@dp.callback_query(F.data == "back_admin")
async def back_admin(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.edit_text("Админ панель 🔐", reply_markup=admin_menu())
    await query.answer()

# Add homework
@dp.callback_query(F.data == "add_hw")
async def add_hw(query: CallbackQuery):
    user_class = ADMIN_CLASSES.get(query.from_user.id)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=user_class, callback_data=f"hw_{user_class}")],
        [types.InlineKeyboardButton(text="⬅️ Артқа", callback_data="back_admin")]
    ])
    await query.message.edit_text("Класс 👇", reply_markup=kb)
    await query.answer()

# Choose class for adding
@dp.callback_query(F.data.startswith("hw_"))
async def choose_class(query: CallbackQuery, state: FSMContext):
    user_class = ADMIN_CLASSES.get(query.from_user.id)
    class_name = query.data.split("_")[1]
    if class_name != user_class:
        return await query.answer("Тек өз класың ❌", show_alert=True)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Дүйсенбі", callback_data="day_mon")],
        [types.InlineKeyboardButton(text="Сейсенбі", callback_data="day_tue")],
        [types.InlineKeyboardButton(text="Сәрсенбі", callback_data="day_wed")],
        [types.InlineKeyboardButton(text="Бейсенбі", callback_data="day_thu")],
        [types.InlineKeyboardButton(text="Жұма", callback_data="day_fri")],
        [types.InlineKeyboardButton(text="⬅️ Артқа", callback_data="back_add")]
    ])
    await state.update_data(class_name=class_name)
    await state.set_state(AddHW.choosing_day)
    await query.message.edit_text("Күн таңда 👇", reply_markup=kb)
    await query.answer()

# Back add
@dp.callback_query(F.data == "back_add")
async def back_add(query: CallbackQuery):
    user_class = ADMIN_CLASSES.get(query.from_user.id)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=user_class, callback_data=f"hw_{user_class}")],
        [types.InlineKeyboardButton(text="⬅️ Артқа", callback_data="back_admin")]
    ])
    await query.message.edit_text("Класс 👇", reply_markup=kb)
    await query.answer()

# Choose day
@dp.callback_query(F.data.startswith("day_"))
async def choose_day(query: CallbackQuery, state: FSMContext):
    day = query.data.split("_")[1]
    await state.update_data(day=day)
    await state.set_state(AddHW.waiting_for_text)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⬅️ Артқа", callback_data="back_days")]
    ])
    await query.message.edit_text(
        "✏️ Үй тапсырманы жаз:\n\nМысалы:\nМатематика - 56 бет, 7 тапсырма\nАғылшын тілі - 73 бет, 3 тапсырма\nФизика - 92 бет, 12 тапсырма\n...\n\n📌 Үй жұмысын толық әрі нақты жазған дұрыс.",
        reply_markup=kb
    )
    await query.answer()

# Back days
@dp.callback_query(F.data == "back_days")
async def back_days(query: CallbackQuery, state: FSMContext):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Дүйсенбі", callback_data="day_mon")],
        [types.InlineKeyboardButton(text="Сейсенбі", callback_data="day_tue")],
        [types.InlineKeyboardButton(text="Сәрсенбі", callback_data="day_wed")],
        [types.InlineKeyboardButton(text="Бейсенбі", callback_data="day_thu")],
        [types.InlineKeyboardButton(text="Жұма", callback_data="day_fri")],
        [types.InlineKeyboardButton(text="⬅️ Артқа", callback_data="back_add")]
    ])
    await state.set_state(AddHW.choosing_day)
    await query.message.edit_text("Күн таңда 👇", reply_markup=kb)
    await query.answer()

# Save homework
@dp.message(AddHW.waiting_for_text)
async def save_hw(message: types.Message, state: FSMContext):
    data = await state.get_data()
    class_name = data["class_name"]
    day = data["day"]
    text = message.text
    async with aiosqlite.connect("db.db") as db:
        await db.execute("DELETE FROM homework WHERE class=? AND day=?", (class_name, day))
        await db.execute("INSERT INTO homework (class, day, text) VALUES (?, ?, ?)", (class_name, day, text))
        await db.commit()
    await message.answer("Сақталды ✅", reply_markup=back_main_btn())
    await state.clear()

# Show homework
@dp.callback_query(F.data.startswith("class_"))
async def show_hw(query: CallbackQuery):
    class_name = query.data.split("_")[1]
    async with aiosqlite.connect("db.db") as db:
        cursor = await db.execute("SELECT day, text FROM homework WHERE class=?", (class_name,))
        rows = await cursor.fetchall()
    if not rows:
        return await query.message.edit_text("Үй тапсырмасы әлі қосылмаған ❌", reply_markup=back_main_btn())
    text = ""
    for day, hw in rows:
        text += f"📅 {DAY_NAMES.get(day)}:\n{hw}\n\n"
    await query.message.edit_text(text, reply_markup=back_main_btn())
    await query.answer()

# Delete menu
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

# Delete homework
@dp.callback_query(F.data.startswith("delete_"))
async def delete_hw(query: CallbackQuery):
    _, class_name, day = query.data.split("_")
    async with aiosqlite.connect("db.db") as db:
        await db.execute("DELETE FROM homework WHERE class=? AND day=?", (class_name, day))
        await db.commit()
    await query.message.edit_text("Өшірілді ✅", reply_markup=back_main_btn())
    await query.answer()

# Notify admins
async def notify_admins(bot: Bot):
    for admin_id in ADMIN_CLASSES.keys():
        try:
            await bot.send_message(admin_id, "⏰ Ескерту!\nҮй тапсырмасын толтыруды ұмытпа 📚")
        except:
            pass

# ------------------- WEBHOOK -------------------
@app.post("/api/bot")
async def webhook(request: Request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return {"ok": True}

# ------------------- STARTUP -------------------
@app.on_event("startup")
async def on_startup():
    await init_db()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(notify_admins, "cron", day_of_week="mon-fri", hour=19, minute=0, args=[bot])
    scheduler.start()