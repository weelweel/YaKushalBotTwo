import os
import time
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.executor import start_webhook

# ================== НАСТРОЙКИ ==================

BOT_TOKEN = os.getenv("BOT_TOKEN")

WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME")
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"https://{WEBHOOK_HOST}{WEBHOOK_PATH}"

WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = int(os.environ.get("PORT", 8000))

CLICK_LOCK_SECONDS = 3
DB_PATH = "bot.db"

PARENTS = {428857475, 666428090, 1482978536}
PARENT_NAMES = {
    428857475: "папа",
    666428090: "мама",
    1482978536: "бабушка"
}

# ================== БОТ ==================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

LAST_CLICK = {}
SESSION = {}

# ================== БАЗА ДАННЫХ ==================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS feedings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            children TEXT NOT NULL,
            author_id INTEGER NOT NULL,
            volume INTEGER
        )
    """)
    conn.commit()
    conn.close()

def add_feeding(ts, children, author_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO feedings (ts, children, author_id, volume) VALUES (?, ?, ?, NULL)",
        (ts, ",".join(children), author_id)
    )
    conn.commit()
    conn.close()

def set_volume_for_last(volume):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE feedings
        SET volume = ?
        WHERE id = (SELECT id FROM feedings ORDER BY id DESC LIMIT 1)
    """, (volume,))
    conn.commit()
    conn.close()

def get_last_feeding():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM feedings ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    return row

def get_all_feedings():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM feedings ORDER BY ts DESC")
    rows = c.fetchall()
    conn.close()
    return rows

# ================== ВСПОМОГАТЕЛЬНОЕ ==================

def locked(user_id):
    now = time.time()
    last = LAST_CLICK.get(user_id, 0)
    if now - last < CLICK_LOCK_SECONDS:
        return True
    LAST_CLICK[user_id] = now
    return False

def fmt_time(ts):
    return datetime.fromtimestamp(ts).strftime("%H:%M")

def ago(ts):
    delta = datetime.now() - datetime.fromtimestamp(ts)
    mins = int(delta.total_seconds() // 60)
    if mins < 60:
        return f"{mins} мин назад"
    hours = mins // 60
    mins %= 60
    return f"{hours} ч {mins} мин назад"

def child_with_icon(name):
    if name == "Саша":
        return "👶 Саша"
    if name == "Гриша":
        return "👶 Гриша"
    return name

def children_text(children_list):
    if set(children_list) == {"Саша", "Гриша"}:
        return "👶👶 Оба"
    return ", ".join(child_with_icon(c) for c in children_list)

# ================== КЛАВИАТУРЫ ==================

def main_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("Саша", callback_data="child:Саша"),
        InlineKeyboardButton("Гриша", callback_data="child:Гриша"),
        InlineKeyboardButton("Оба поели", callback_data="child:Оба")
    )
    kb.add(
        InlineKeyboardButton("Объём", callback_data="volume"),
        InlineKeyboardButton("История", callback_data="history")
    )
    kb.add(
        InlineKeyboardButton("Сумма", callback_data="sum")
    )
    return kb

def time_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("Сейчас", callback_data="time:0"),
        InlineKeyboardButton("15 минут назад", callback_data="time:15"),
        InlineKeyboardButton("30 минут назад", callback_data="time:30"),
        InlineKeyboardButton("1 час назад", callback_data="time:60")
    )
    kb.add(
        InlineKeyboardButton("⬅ Назад", callback_data="back")
    )
    return kb

def volume_keyboard():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("90", callback_data="vol:90"),
        InlineKeyboardButton("120", callback_data="vol:120"),
        InlineKeyboardButton("150", callback_data="vol:150"),
        InlineKeyboardButton("180", callback_data="vol:180")
    )
    kb.add(
        InlineKeyboardButton("⬅ Назад", callback_data="back")
    )
    return kb

# ================== РЕНДЕР ==================

def render_main():
    row = get_last_feeding()
    if not row:
        return "Последнее кормление:\n—\n\nКого покормили?", main_keyboard()

    _, ts, children_str, author_id, volume = row
    children_list = children_str.split(",")
    children = children_text(children_list)

    text = (
        "Последнее кормление:\n"
        f"{children} — {fmt_time(ts)} ({ago(ts)}), "
        f"{PARENT_NAMES.get(author_id, 'кто-то')}"
    )

    if volume is not None:
        text += f"\nОбъём: {volume} мл"

    text += "\n\nКого покормили?"
    return text, main_keyboard()

# ================== ХЕНДЛЕРЫ ==================

@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    if msg.from_user.id not in PARENTS:
        return
    text, kb = render_main()
    await msg.answer(text, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("child:"))
async def choose_child(cb: types.CallbackQuery):
    if locked(cb.from_user.id):
        await cb.answer("Подожди секунду")
        return

    choice = cb.data.split(":")[1]
    children = ["Саша", "Гриша"] if choice == "Оба" else [choice]

    SESSION[cb.from_user.id] = children

    await cb.message.edit_text("Когда поели?", reply_markup=time_keyboard())
    await cb.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("time:"))
async def choose_time(cb: types.CallbackQuery):
    if locked(cb.from_user.id):
        await cb.answer("Подожди секунду")
        return

    minutes = int(cb.data.split(":")[1])
    children = SESSION.get(cb.from_user.id)
    if not children:
        await cb.answer()
        return

    ts = int(time.time() - minutes * 60)
    add_feeding(ts, children, cb.from_user.id)

    await cb.message.edit_text("Сколько дали смеси?", reply_markup=volume_keyboard())
    await cb.answer()

@dp.callback_query_handler(lambda c: c.data == "volume")
async def volume_menu(cb: types.CallbackQuery):
    row = get_last_feeding()
    if not row:
        await cb.answer("Нет кормлений")
        return

    volume = row[4]
    text = "Сколько дали смеси?" if volume is None else f"Текущий объём: {volume} мл\nИзменить?"

    await cb.message.edit_text(text, reply_markup=volume_keyboard())
    await cb.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("vol:"))
async def set_volume(cb: types.CallbackQuery):
    if locked(cb.from_user.id):
        await cb.answer("Подожди секунду")
        return

    volume = int(cb.data.split(":")[1])
    set_volume_for_last(volume)

    text, kb = render_main()
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@dp.callback_query_handler(lambda c: c.data == "history")
async def history(cb: types.CallbackQuery):
    rows = get_all_feedings()
    if not rows:
        await cb.answer("Истории пока нет")
        return

    lines = []
    current_day = None

    for row in rows:
        _, ts, children_str, _, volume = row
        day = datetime.fromtimestamp(ts).date()

        if day != current_day:
            if day == datetime.now().date():
                lines.append("\nСегодня:")
            elif day == datetime.now().date() - timedelta(days=1):
                lines.append("\nВчера:")
            else:
                lines.append(f"\n{day.strftime('%d.%m.%Y')}:")
            current_day = day

        children = children_text(children_str.split(","))
        line = f"— {children} {fmt_time(ts)}"
        if volume is not None:
            line += f" — {volume} мл"

        lines.append(line)

    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("⬅ Назад", callback_data="back")
    )

    await cb.message.edit_text("История кормлений:\n" + "\n".join(lines), reply_markup=kb)
    await cb.answer()

@dp.callback_query_handler(lambda c: c.data == "sum")
async def daily_sum(cb: types.CallbackQuery):
    rows = get_all_feedings()
    today = datetime.now().date()
    sums = {}

    for row in rows:
        _, ts, children_str, _, volume = row
        if volume is None:
            continue
        if datetime.fromtimestamp(ts).date() != today:
            continue

        for child in children_str.split(","):
            sums[child] = sums.get(child, 0) + volume

    if not sums:
        text = "Сегодня объёмов нет."
    else:
        lines = ["Сегодня:"]
        for child in ["Саша", "Гриша"]:
            if child in sums:
                lines.append(f"{child} — {sums[child]} мл")
        text = "\n".join(lines)

    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("⬅ Назад", callback_data="back")
    )

    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@dp.callback_query_handler(lambda c: c.data == "back")
async def back(cb: types.CallbackQuery):
    text, kb = render_main()
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

# ================== WEBHOOK ==================

async def on_startup(dp):
    init_db()
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(dp):
    await bot.delete_webhook()

if __name__ == "__main__":
    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        host=WEBAPP_HOST,
        port=WEBAPP_PORT,
    )
