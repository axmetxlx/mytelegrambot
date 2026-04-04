import os
import logging
import asyncio
import aiosqlite
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ---------------- НАСТРОЙКА ----------------
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(TOKEN)
dp = Dispatcher()
app = FastAPI()

logging.basicConfig(level=logging.INFO)

DB_PATH = "db.db"

ADMIN_IDS = [5199542672, 7357106839]

DAY_NAMES = {
    "mon": "Дүйсенбі",
    "tue": "Сейсенбі",
    "wed": "Сәрсенбі",
    "thu": "Бейсенбі",
    "fri": "Жұма"
}

# ---------------- DATABASE ----------------
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
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
    choosing_class = State()
    choosing_day = State()
    waiting_for_text = State()

# ---------------- Keyboards ----------------
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("7A", callback_data="class_7A")],
        [InlineKeyboardButton("8A", callback_data="class_8A"),
         InlineKeyboardButton("8Б", callback_data="class_8B")],
        [InlineKeyboardButton("9A", callback_data="class_9A")]
    ])

def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("📚 Қосу / Өзгерту", callback_data="add_hw")],
        [InlineKeyboardButton("🗑 Өшіру", callback_data="delete_menu")],
        [InlineKeyboardButton("⬅️ Меню", callback_data="back_main")]
    ])

def back_main_btn():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("⬅️ Меню", callback_data="back_main")]
    ])

def day_buttons():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("Дүйсенбі", callback_data="day_mon"),
         InlineKeyboardButton("Сейсенбі", callback_data="day_tue")],
        [InlineKeyboardButton("Сәрсенбі", callback_data="day_wed"),
         InlineKeyboardButton("Бейсенбі", callback_data="day_thu")],
        [InlineKeyboardButton("Жұма", callback_data="day_fri")]
    ])

# ---------------- HANDLERS ----------------
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Сәлем! 👋\nҚай сыныптың үй тапсырмасын көргің келеді? 👇",
                         reply_markup=main_menu())

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("Сен админ емессің ❌")
    await message.answer("Админ панель 🔐", reply_markup=admin_menu())

@dp.callback_query(F.data == "back_main")
async def back_main(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.edit_text("Қай сыныптың үй тапсырмасын көргің келеді? 👇",
                                 reply_markup=main_menu())
    await query.answer()

@dp.callback_query(F.data.startswith("class_"))
async def show_hw(query: CallbackQuery):
    class_name = query.data.split("_")[1]
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT day, text FROM homework WHERE class=?", (class_name,))
        rows = await cursor.fetchall()

    if not rows:
        return await query.message.edit_text("Үй тапсырмасы әлі қосылмаған ❌",
                                             reply_markup=back_main_btn())

    text = "".join([f"📅 {DAY_NAMES.get(day)}:\n{hw}\n\n" for day, hw in rows])
    await query.message.edit_text(text, reply_markup=back_main_btn())
    await query.answer()

# ---------------- ADD HW ----------------
@dp.callback_query(F.data == "add_hw")
async def add_hw_start(query: CallbackQuery, state: FSMContext):
    await state.set_state(AddHW.choosing_class)
    await query.message.edit_text("Қай сыныпқа қосасың?", reply_markup=main_menu())
    await query.answer()

@dp.callback_query(F.data.startswith("class_"), state=AddHW.choosing_class)
async def add_hw_class(query: CallbackQuery, state: FSMContext):
    class_name = query.data.split("_")[1]
    await state.update_data(class_name=class_name)
    await state.set_state(AddHW.choosing_day)
    await query.message.edit_text("Қай күнге үй тапсырмасын қосасың?", reply_markup=day_buttons())
    await query.answer()

@dp.callback_query(F.data.startswith("day_"), state=AddHW.choosing_day)
async def add_hw_day(query: CallbackQuery, state: FSMContext):
    day = query.data.split("_")[1]
    await state.update_data(day=day)
    await state.set_state(AddHW.waiting_for_text)
    await query.message.edit_text("Үй тапсырмасын мәтін түрінде жіберіңіз:")
    await query.answer()

@dp.message(state=AddHW.waiting_for_text)
async def add_hw_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    class_name = data["class_name"]
    day = data["day"]
    text = message.text
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO homework(class, day, text) VALUES (?, ?, ?)", (class_name, day, text))
        await db.commit()
    await state.clear()
    await message.answer("✅ Үй тапсырмасы қосылды!", reply_markup=admin_menu())

# ---------------- DELETE HW ----------------
@dp.callback_query(F.data == "delete_menu")
async def delete_menu(query: CallbackQuery):
    await query.message.edit_text("Өшіру үшін сыныпты таңда:", reply_markup=main_menu())
    await query.answer()

@dp.callback_query(F.data.startswith("class_"), state=None)
async def delete_hw(query: CallbackQuery):
    class_name = query.data.split("_")[1]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM homework WHERE class=?", (class_name,))
        await db.commit()
    await query.message.edit_text(f"✅ {class_name} сыныбындағы барлық үй тапсырмасы өшірілді!", reply_markup=back_main_btn())
    await query.answer()

# ---------------- SCHEDULER / NOTIFY ----------------
async def notify():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT class, day, text FROM homework")
        rows = await cursor.fetchall()
    for class_name, day, text in rows:
        for admin_id in ADMIN_IDS:  # Мысалы, хабарландыру тек админдерге
            await bot.send_message(admin_id, f"📅 {DAY_NAMES.get(day)}:\n{text}")

async def start_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: asyncio.create_task(notify()), 'cron', hour=7, minute=0)
    scheduler.start()

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
    asyncio.create_task(start_scheduler())