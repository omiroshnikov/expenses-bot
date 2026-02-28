import os
from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])  # твой телеграм id

BASE_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
WEBHOOK_PATH = "/tg"
WEBHOOK_URL = f"{BASE_URL}{WEBHOOK_PATH}" if BASE_URL else None

bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


def only_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="заполнить", callback_data="fill")],
        [InlineKeyboardButton(text="отмена", callback_data="cancel")],
    ])


@dp.message()
async def any_message(m: Message):
    txt = (m.text or "").strip()
    print("IN_MSG:", m.from_user.id, repr(txt))

    if not only_admin(m.from_user.id):
        # молча игнорим всех, кроме тебя
        return

    if txt == "/start":
        await m.answer("ок. жми «заполнить»", reply_markup=kb_main())
        return

    # на всё остальное просто подтверждаем "alive"
    await m.answer("alive.")


@dp.callback_query()
async def any_callback(c: CallbackQuery):
    print("IN_CB:", c.from_user.id, c.data)

    if not only_admin(c.from_user.id):
        await c.answer()
        return

    if c.data == "fill":
        await c.message.answer("вижу клик. дальше докрутим форму.")
        await c.answer()
        return

    if c.data == "cancel":
        await c.answer("ок", show_alert=False)
        return

    await c.answer()


async def on_startup(app: web.Application):
    if not WEBHOOK_URL:
        print("NO WEBHOOK_URL (set RENDER_EXTERNAL_URL)")
        return
    await bot.set_webhook(
        WEBHOOK_URL,
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"],
    )
    print("WEBHOOK_SET:", WEBHOOK_URL)


def main():
    app = web.Application()
    app.on_startup.append(on_startup)

    SimpleRequestHandler(dp, bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    port = int(os.environ.get("PORT", "10000"))
    web.run_app(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
