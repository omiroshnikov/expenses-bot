import os
import json
from aiohttp import web, ClientSession

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
WEBAPP_URL = f"{BASE_URL}/testapp?v=1" if BASE_URL else None

GAS_EXEC_URL = os.environ.get("GAS_EXEC_URL", "").strip()

bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


def only_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="заполнить", web_app=WebAppInfo(url=WEBAPP_URL))],
    ])


def ymd_to_ddmmyy(ymd: str) -> str:
    # "2026-02-27" -> "270226"
    try:
        yyyy, mm, dd = ymd.split("-")
        return f"{dd}{mm}{yyyy[-2:]}"
    except Exception:
        return ""


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

    if not GAS_EXEC_URL:
        await m.answer("ошибка: не задан GAS_EXEC_URL в render env")
        return

    ddmmyy = ymd_to_ddmmyy(payload.get("date") or "")
    name = (payload.get("name") or "").strip()
    amount = (payload.get("amount") or "").strip()
    category = (payload.get("category") or "").strip()
    pay_from = (payload.get("payFrom") or "").strip()
    note = (payload.get("note") or "").strip()

    if not name:
        await m.answer("ошибка: пустое наименование")
        return

    line = ";".join([ddmmyy, name, amount, category, pay_from, note]).rstrip(";")

    update = {
        "message": {
            "message_id": m.message_id,
            "text": line,
            "chat": {"id": m.chat.id},
            "from": {
                "id": m.from_user.id,
                "username": m.from_user.username,
                "first_name": m.from_user.first_name,
                "last_name": m.from_user.last_name,
            },
        }
    }

    try:
        async with ClientSession() as http:
            async with http.post(
                GAS_EXEC_URL,
                data=json.dumps(update),
                headers={"Content-Type": "application/json"},
                timeout=20,
            ) as resp:
                body = await resp.text()
                print("GAS_RESP:", resp.status, body[:200])
                if resp.status != 200:
                    await m.answer(f"ошибка: gas вернул {resp.status}")
                    return
    except Exception as e:
        await m.answer(f"ошибка: не достучался до gas: {e}")
        return

    await m.answer(f"ок. отправил в таблицу: {line}")


async def on_startup(app: web.Application):
    if not WEBHOOK_URL:
        print("NO WEBHOOK_URL (set RENDER_EXTERNAL_URL)")
        return

    await bot.set_webhook(
        WEBHOOK_URL,
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query", "web_app_data"],
    )
    print("WEBHOOK_SET:", WEBHOOK_URL)
    print("WEBAPP_URL:", WEBAPP_URL)


def main():
    app = web.Application()
    app.on_startup.append(on_startup)

    async def app_page(_req: web.Request):
        return web.FileResponse("webapp.html")

   app.router.add_get("/testapp", app_page)

    SimpleRequestHandler(dp, bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    port = int(os.environ.get("PORT", "10000"))
    web.run_app(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
