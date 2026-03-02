import os
import json
import logging
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

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])

BASE_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
WEBHOOK_PATH = "/tg"
WEBHOOK_URL = f"{BASE_URL}{WEBHOOK_PATH}" if BASE_URL else None

GAS_EXEC_URL = os.environ.get("GAS_EXEC_URL", "").strip()
WEBAPP_KEY = os.environ.get("WEBAPP_KEY", "").strip()

WEBAPP_URL = f"{BASE_URL}/testapp?v=2&k={WEBAPP_KEY}" if BASE_URL else None

bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


def only_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="заполнить", web_app=WebAppInfo(url=WEBAPP_URL))],
    ])


def ymd_to_ddmmyy(ymd: str) -> str:
    try:
        yyyy, mm, dd = ymd.split("-")
        return f"{dd}{mm}{yyyy[-2:]}"
    except Exception:
        return ""


async def forward_to_gas(line: str, chat_id: int, message_id: int, from_user):
    if not GAS_EXEC_URL:
        return 500, "no GAS_EXEC_URL"

    update = {
        "message": {
            "message_id": message_id,
            "text": line,
            "chat": {"id": chat_id},
            "from": {
                "id": getattr(from_user, "id", None),
                "username": getattr(from_user, "username", None),
                "first_name": getattr(from_user, "first_name", None),
                "last_name": getattr(from_user, "last_name", None),
            },
        }
    }

    async with ClientSession() as http:
        async with http.post(GAS_EXEC_URL, json=update, timeout=25) as resp:
            body = await resp.text()
            return resp.status, body[:400]


@dp.message(F.text == "/start")
async def start(m: Message):
    if not only_admin(m.from_user.id):
        return
    logging.info("IN_MSG: %s %s", m.from_user.id, repr(m.text))
    await m.answer("ок. жми «заполнить»", reply_markup=kb_main())


# оставляем (если вдруг web_app_data оживёт - тоже будет писать)
@dp.message(F.web_app_data)
async def on_webapp_data(m: Message):
    if not only_admin(m.from_user.id):
        return

    raw = (m.web_app_data.data or "").strip()
    logging.info("WEBAPP_DATA raw: %s", raw[:500])

    try:
        payload = json.loads(raw or "{}")
    except Exception:
        await m.answer("ошибка: данные формы не json")
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

    status, body = await forward_to_gas(line, m.chat.id, m.message_id, m.from_user)
    logging.info("GAS_RESP: %s %s", status, body)

    if status != 200:
        await m.answer(f"ошибка: gas {status}: {body}")
        return

    await m.answer(f"ок. отправил в таблицу: {line}")


async def on_startup(app: web.Application):
    if WEBHOOK_URL:
        await bot.set_webhook(
            WEBHOOK_URL,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
        )
        logging.info("WEBHOOK_SET: %s", WEBHOOK_URL)

    logging.info("WEBAPP_URL: %s", WEBAPP_URL)
    logging.info("GAS_EXEC_URL set: %s", bool(GAS_EXEC_URL))
    logging.info("WEBAPP_KEY set: %s", bool(WEBAPP_KEY))


def main():
    app = web.Application()
    app.on_startup.append(on_startup)

    async def app_page(_req: web.Request):
        return web.FileResponse("webapp.html")

    async def submit(req: web.Request):
        # защита "только для меня": проверяем ключ из url
        k = req.query.get("k", "")
        if not WEBAPP_KEY or k != WEBAPP_KEY:
            return web.json_response({"ok": False, "error": "bad key"}, status=403)

        try:
            payload = await req.json()
        except Exception:
            return web.json_response({"ok": False, "error": "bad json"}, status=400)

        ddmmyy = ymd_to_ddmmyy(str(payload.get("date", "")))
        name = str(payload.get("name", "")).strip()
        amount = str(payload.get("amount", "")).strip()
        category = str(payload.get("category", "")).strip()
        pay_from = str(payload.get("payFrom", "")).strip()
        note = str(payload.get("note", "")).strip()

        if not name:
            return web.json_response({"ok": False, "error": "empty name"}, status=400)

        line = ";".join([ddmmyy, name, amount, category, pay_from, note]).rstrip(";")
        logging.info("SUBMIT line: %s", line)

        # пишем в sheet через gas, chat_id/message_id берём "виртуальные"
        status, body = await forward_to_gas(line, ADMIN_ID, int(payload.get("_mid", 1)), None)
        logging.info("GAS_RESP(submit): %s %s", status, body)

        if status != 200:
            return web.json_response({"ok": False, "error": f"gas {status}", "body": body}, status=502)

        return web.json_response({"ok": True, "line": line})

    app.router.add_get("/testapp", app_page)
    app.router.add_post("/submit", submit)

    SimpleRequestHandler(dp, bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    port = int(os.environ.get("PORT", "10000"))
    web.run_app(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
