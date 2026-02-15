import os
import json
import time
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.executor import start_webhook

# ================== НАСТРОЙКИ ==================

BOT_TOKEN = os.getenv("BOT_TOKEN")

WEBHOOK_HOST = os.getenv("RAILWAY_STATIC_URL")
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"https://{WEBHOOK_HOST}{WEBHOOK_PATH}"

WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = int(os.environ.get("PORT", 8000))

DATA_FILE = "events.json"
CLICK_LOCK_SECONDS = 3

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# ================== ДАННЫЕ ==================

EVENTS = []
LAST_CLICK = {}
SESSION = {}

PARENTS = {428857475, 666428090, 1482978536}
PARENT_NAMES = {
    428857475: "папа",
    666428090: "мама",
    1482978536: "бабушка"
}

# ================== ХРАНЕНИЕ ==================

def load_events():
    global EVENTS
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            EVENTS = json.load(f)
    except:
        EVENTS = []

def save_events():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(EVENTS, f, ensure_ascii=False, indent=2)

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
        return "🧒 Гриша"
    return name

def children_text(children):
    if set(children) == {"Саша", "Гриша"}:
        return "👶👶 Оба"
    return ", ".join(child_with_icon(c) for c in children)

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

# (дальше твоя логика хендлеров остаётся прежней — я сократил здесь ради длины ответа)

# ================== WEBHOOK ==================

async def on_startup(dp):
    load_events()
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
