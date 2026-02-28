import os
import datetime as dt
from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
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


def only_admin(user_id: int) -> bool:
    return True


def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="заполнить", callback_data="fill")],
        [InlineKeyboardButton(text="отмена", callback_data="cancel")],
    ])


def kb_date() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="сегодня", callback_data="date:today"),
            InlineKeyboardButton(text="вчера", callback_data="date:yday"),
        ],
        [InlineKeyboardButton(text="ввести вручную (ддммгг)", callback_data="date:manual")],
        [InlineKeyboardButton(text="отмена", callback_data="cancel")],
    ])


def fmt_ddmmyy(d: dt.date) -> str:
    return d.strftime("%d%m%y")


@dp.errors()
async def on_error(event, exception):
    # чтобы видеть причину в render logs
    print("AIROGRAM_ERROR:", repr(exception))
    return True


@dp.message(F.text == "/start")
async def start(m: Message):
    await m.answer(f"твой id = {m.from_user.id}")
        return
    await state.clear()
    await m.answer("ок. жми «заполнить»", reply_markup=kb_main())


@dp.callback_query(F.data == "fill")
async def fill(c: CallbackQuery, state: FSMContext):
    if not only_admin(c.from_user.id):
        return
    print("FILL_CLICKED from", c.from_user.id)  # <- увидишь в логах
    await state.clear()
    await state.set_state(Form.date)

    # 1) сообщение-пинг (чтобы ты видел, что хендлер точно сработал)
    await c.message.answer("вижу клик. выбирай дату:", reply_markup=kb_date())
    await c.answer()


@dp.callback_query(F.data.startswith("date:"))
async def pick_date(c: CallbackQuery, state: FSMContext):
    if not only_admin(c.from_user.id):
        return

    v = c.data.split(":", 1)[1]
    today = dt.date.today()

    if v == "today":
        date = fmt_ddmmyy(today)
        await state.update_data(date=date)
        await c.message.answer(f"ок дата: {date}")
    elif v == "yday":
        date = fmt_ddmmyy(today - dt.timedelta(days=1))
        await state.update_data(date=date)
        await c.message.answer(f"ок дата: {date}")
    else:
        await c.message.answer("введи дату в формате ддммгг (пример 050126)")

    await c.answer()


@dp.message(Form.date)
async def manual_date(m: Message, state: FSMContext):
    if not only_admin(m.from_user.id):
        return

    t = "".join(ch for ch in (m.text or "").strip() if ch.isdigit())
    if len(t) != 6:
        await m.answer("нужно 6 цифр: ддммгг (пример 050126).")
        return

    await state.update_data(date=t)
    await m.answer(f"ок дата: {t}")


@dp.callback_query(F.data == "cancel")
async def cancel(c: CallbackQuery, state: FSMContext):
    if only_admin(c.from_user.id):
        await state.clear()
        await c.message.answer("отменено.", reply_markup=kb_main())
    await c.answer()


async def on_startup(app: web.Application):
    if not WEBHOOK_URL:
        print("NO RENDER_EXTERNAL_URL - set it in env")
        return
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
    print(f"WEBHOOK_SET: {WEBHOOK_URL}")


async def on_shutdown(app: web.Application):
    await bot.delete_webhook(drop_pending_updates=True)


def main():
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    SimpleRequestHandler(dp, bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    port = int(os.environ.get("PORT", "10000"))
    web.run_app(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
