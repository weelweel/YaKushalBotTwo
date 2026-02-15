import json
import time
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================== НАСТРОЙКИ ==================

TOKEN = "8323281304:AAG3b970DlCfR63W4tFghAkWBzNexDAV1V0"

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

DATA_FILE = "events.json"
CLICK_LOCK_SECONDS = 3

PARENTS = {
    428857475,
    666428090,
    1482978536
}

PARENT_NAMES = {
    428857475: "папа",
    666428090: "мама",
    1482978536: "бабушка"
}

# ================== СОСТОЯНИЕ ==================

EVENTS = []
LAST_CLICK = {}
SESSION = {}

# ================== ХРАНЕНИЕ ==================

def load_events():
    global EVENTS
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            EVENTS = json.load(f)
    except FileNotFoundError:
        EVENTS = []

def save_events():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(EVENTS, f, ensure_ascii=False, indent=2)

# ================== ВСПОМОГАТЕЛЬНОЕ ==================

def locked(user_id: int) -> bool:
    now = time.time()
    last = LAST_CLICK.get(user_id, 0)
    if now - last < CLICK_LOCK_SECONDS:
        return True
    LAST_CLICK[user_id] = now
    return False

def fmt_time(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%H:%M")

def ago(ts: int) -> str:
    delta = datetime.now() - datetime.fromtimestamp(ts)
    mins = int(delta.total_seconds() // 60)
    if mins < 60:
        return f"{mins} мин назад"
    hours = mins // 60
    mins = mins % 60
    return f"{hours} ч {mins} мин назад"

def child_with_icon(name: str) -> str:
    if name == "Саша":
        return "👶 Саша"
    if name == "Гриша":
        return "🧒 Гриша"
    return name

def children_text(children: list) -> str:
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
    if not EVENTS:
        text = "Последнее кормление:\n—\n\nКого покормили?"
        return text, main_keyboard()

    last = EVENTS[-1]
    children = children_text(last["children"])
    t = fmt_time(last["ts"])
    who = PARENT_NAMES.get(last["author_id"], "кто-то")

    text = (
        "Последнее кормление:\n"
        f"{children} — {t} ({ago(last['ts'])}), {who}"
    )

    if last.get("volume") is not None:
        text += f"\nОбъём: {last['volume']} мл"

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
    uid = cb.from_user.id
    if locked(uid):
        await cb.answer("Подожди секунду")
        return

    choice = cb.data.split(":")[1]

    if choice == "Оба":
        children = ["Саша", "Гриша"]
    else:
        children = [choice]

    SESSION[uid] = {
        "children": children,
        "msg_id": cb.message.message_id
    }

    await cb.message.edit_text(
        "Когда поели?",
        reply_markup=time_keyboard()
    )
    await cb.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("time:"))
async def choose_time(cb: types.CallbackQuery):
    uid = cb.from_user.id
    if locked(uid):
        await cb.answer("Подожди секунду")
        return

    minutes = int(cb.data.split(":")[1])
    sess = SESSION.get(uid)
    if not sess:
        await cb.answer("Сессия устарела")
        return

    ts = int(time.time() - minutes * 60)

    EVENTS.append({
        "ts": ts,
        "children": sess["children"],
        "author_id": uid,
        "volume": None
    })

    save_events()

    await cb.message.edit_text(
        "Сколько дали смеси?",
        reply_markup=volume_keyboard()
    )
    await cb.answer()

@dp.callback_query_handler(lambda c: c.data == "volume")
async def volume_menu(cb: types.CallbackQuery):
    if not EVENTS:
        await cb.answer("Нет кормлений")
        return

    last = EVENTS[-1]
    text = "Сколько дали смеси?"

    if last.get("volume") is not None:
        text = f"Текущий объём: {last['volume']} мл\nИзменить?"

    await cb.message.edit_text(
        text,
        reply_markup=volume_keyboard()
    )
    await cb.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("vol:"))
async def set_volume(cb: types.CallbackQuery):
    uid = cb.from_user.id
    if locked(uid):
        await cb.answer("Подожди секунду")
        return

    if not EVENTS:
        await cb.answer()
        return

    volume = int(cb.data.split(":")[1])
    EVENTS[-1]["volume"] = volume
    save_events()

    text, kb = render_main()
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@dp.callback_query_handler(lambda c: c.data == "history")
async def history(cb: types.CallbackQuery):
    if not EVENTS:
        await cb.answer("Истории пока нет")
        return

    lines = []
    current_day = None

    for e in reversed(EVENTS):
        day = datetime.fromtimestamp(e["ts"]).date()

        if day != current_day:
            if day == datetime.now().date():
                lines.append("\nСегодня:")
            elif day == datetime.now().date() - timedelta(days=1):
                lines.append("\nВчера:")
            else:
                lines.append(f"\n{day.strftime('%d.%m.%Y')}:")
            current_day = day

        child_text = children_text(e["children"])
        line = f"— {child_text} {fmt_time(e['ts'])}"

        if e.get("volume") is not None:
            line += f" — {e['volume']} мл"

        lines.append(line)

    text = "История кормлений:\n" + "\n".join(lines)

    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("⬅ Назад", callback_data="back")
    )

    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()

@dp.callback_query_handler(lambda c: c.data == "sum")
async def daily_sum(cb: types.CallbackQuery):
    today = datetime.now().date()
    sums = {}

    for e in EVENTS:
        day = datetime.fromtimestamp(e["ts"]).date()
        if day != today:
            continue
        if e.get("volume") is None:
            continue

        for child in e["children"]:
            sums[child] = sums.get(child, 0) + e["volume"]

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

# ================== ЗАПУСК ==================

if __name__ == "__main__":
    load_events()
    executor.start_polling(dp, skip_updates=True)