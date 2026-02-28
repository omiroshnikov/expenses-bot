import os
import datetime as dt
from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])

BASE_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
WEBHOOK_PATH = "/tg"
WEBHOOK_URL = f"{BASE_URL}{WEBHOOK_PATH}" if BASE_URL else None

bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


class Form(StatesGroup):
    date = State()
    name = State()


def only_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def fmt_ddmmyy(d: dt.date) -> str:
    return d.strftime("%d%m%y")


def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="заполнить", callback_data="fill")],
        [InlineKeyboardButton(text="отмена", callback_data="cancel")],
    ])


def kb_date():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="сегодня", callback_data="date:today"),
            InlineKeyboardButton(text="вчера", callback_data="date:yday"),
        ],
        [InlineKeyboardButton(text="ввести вручную (ддммгг)", callback_data="date:manual")],
        [InlineKeyboardButton(text="отмена", callback_data="cancel")],
    ])


@dp.message(F.text == "/start")
async def start(m: Message, state: FSMContext):
    if not only_admin(m.from_user.id):
        return
    await state.clear()
    await m.answer("ок. жми «заполнить»", reply_markup=kb_main())


@dp.callback_query(F.data == "fill")
async def fill(c: CallbackQuery, state: FSMContext):
    if not only_admin(c.from_user.id):
        await c.answer()
        return
    await state.clear()
    await state.set_state(Form.date)
    await c.message.answer("дата расхода?", reply_markup=kb_date())
    await c.answer()


@dp.callback_query(F.data.startswith("date:"))
async def pick_date(c: CallbackQuery, state: FSMContext):
    if not only_admin(c.from_user.id):
        await c.answer()
        return

    v = c.data.split(":", 1)[1]
    today = dt.date.today()

    if v == "today":
        date = fmt_ddmmyy(today)
    elif v == "yday":
        date = fmt_ddmmyy(today - dt.timedelta(days=1))
    else:
        await c.message.answer("введи дату в формате ддммгг (пример 050126)")
        await c.answer()
        return

    await state.update_data(date=date)
    await state.set_state(Form.name)
    await c.message.answer(f"дата: {date}\nвведи наименование (например: падел)")
    await c.answer()


@dp.message(Form.date)
async def manual_date(m: Message, state: FSMContext):
    if not only_admin(m.from_user.id):
        return

    txt = "".join(ch for ch in (m.text or "") if ch.isdigit())
    if len(txt) != 6:
        await m.answer("нужно 6 цифр: ддммгг (пример 050126)")
        return

    await state.update_data(date=txt)
    await state.set_state(Form.name)
    await m.answer(f"дата: {txt}\nвведи наименование")


@dp.message(Form.name)
async def get_name(m: Message, state: FSMContext):
    if not only_admin(m.from_user.id):
        return

    name = (m.text or "").strip()
    if not name:
        await m.answer("наименование не может быть пустым.")
        return

    data = await state.get_data()
    date = data.get("date")

    await state.update_data(name=name)

    await m.answer(f"дата: {date}\nнаименование: {name}\n(дальше добавим сумму)")
    # пока не переходим дальше — тестируем


@dp.callback_query(F.data == "cancel")
async def cancel(c: CallbackQuery, state: FSMContext):
    if not only_admin(c.from_user.id):
        await c.answer()
        return
    await state.clear()
    await c.message.answer("отменено.", reply_markup=kb_main())
    await c.answer()


async def on_startup(app: web.Application):
    if not WEBHOOK_URL:
        return
    await bot.set_webhook(
        WEBHOOK_URL,
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"],
    )


def main():
    app = web.Application()
    app.on_startup.append(on_startup)

    SimpleRequestHandler(dp, bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    port = int(os.environ.get("PORT", "10000"))
    web.run_app(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
