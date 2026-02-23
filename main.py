import os
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])

# render обычно даёт это сам. если нет - добавишь руками в env
BASE_URL = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
WEBHOOK_PATH = "/tg"
WEBHOOK_URL = f"{BASE_URL}{WEBHOOK_PATH}" if BASE_URL else None

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

def only_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="заполнить", callback_data="fill")],
        [InlineKeyboardButton(text="отмена", callback_data="cancel")],
    ])

@dp.message(F.text == "/start")
async def start(m: Message):
    if not only_admin(m.from_user.id):
        return
    await m.answer("ок. жми «заполнить» или пиши строкой через ;", reply_markup=kb_main())

@dp.callback_query(F.data == "fill")
async def fill(c: CallbackQuery):
    if not only_admin(c.from_user.id):
        return
    await c.message.answer("ок, дальше сделаем шаги формы (дата/наименование/сумма/...).")
    await c.answer()

@dp.callback_query(F.data == "cancel")
async def cancel(c: CallbackQuery):
    if only_admin(c.from_user.id):
        await c.message.answer("отменено.", reply_markup=kb_main())
    await c.answer()

async def on_startup(app: web.Application):
    if not WEBHOOK_URL:
        print("no RENDER_EXTERNAL_URL - set it in env")
        return
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
    print(f"webhook set: {WEBHOOK_URL}")

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
