import os
from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

BOT_TOKEN = os.environ["BOT_TOKEN"]

BASE_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
WEBHOOK_PATH = "/tg"
WEBHOOK_URL = f"{BASE_URL}{WEBHOOK_PATH}" if BASE_URL else None

bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="заполнить", callback_data="fill")],
    ])


@dp.message()
async def any_message(m: Message):
    # это должно быть видно в render logs
    print("IN_MSG:", m.from_user.id, repr(m.text))
    if (m.text or "").strip() == "/start":
        await m.answer("alive. жми «заполнить»", reply_markup=kb_main())
    else:
        await m.answer("alive.")


@dp.callback_query()
async def any_callback(c: CallbackQuery):
    print("IN_CB:", c.from_user.id, c.data)
    await c.answer("alive_cb", show_alert=False)


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
