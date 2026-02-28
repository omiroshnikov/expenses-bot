import os
import json
from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])

BASE_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
WEBHOOK_PATH = "/tg"
WEBHOOK_URL = f"{BASE_URL}{WEBHOOK_PATH}" if BASE_URL else None
WEBAPP_URL = f"{BASE_URL}/app" if BASE_URL else None

bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


def only_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def kb_main():
    # одна кнопка, без "отмена" - чтоб не путать старые сообщения
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="заполнить", web_app=WebAppInfo(url=WEBAPP_URL))],
    ])


@dp.message(F.text == "/start")
async def start(m: Message):
    if not only_admin(m.from_user.id):
        return
    print("IN_MSG:", m.from_user.id, repr(m.text))
    await m.answer("ок. жми «заполнить»", reply_markup=kb_main())


@dp.message(F.web_app_data)
async def on_webapp_data(m: Message):
    if not only_admin(m.from_user.id):
        return

    raw = m.web_app_data.data or ""
    print("WEBAPP_DATA:", raw)

    try:
        payload = json.loads(raw or "{}")
    except Exception:
        await m.answer("ошибка: не смог прочитать данные формы")
        return

    await m.answer(
        "принято:\n"
        f"дата: {payload.get('date')}\n"
        f"наименование: {payload.get('name')}\n"
        f"сумма: {payload.get('amount')}\n"
        f"категория: {payload.get('category')}\n"
        f"откуда: {payload.get('payFrom')}\n"
        f"примечание: {payload.get('note')}"
    )


async def on_startup(app: web.Application):
    if not WEBHOOK_URL:
        print("NO WEBHOOK_URL (set RENDER_EXTERNAL_URL)")
        return

    await bot.set_webhook(
        WEBHOOK_URL,
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"],  # web_app_data прилетает как message
    )
    print("WEBHOOK_SET:", WEBHOOK_URL)
    print("WEBAPP_URL:", WEBAPP_URL)


def main():
    app = web.Application()
    app.on_startup.append(on_startup)

    async def app_page(_req: web.Request):
        return web.FileResponse("webapp.html")

    app.router.add_get("/app", app_page)

    SimpleRequestHandler(dp, bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    port = int(os.environ.get("PORT", "10000"))
    web.run_app(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
