# -*- coding: utf-8 -*-
import os
import datetime as dt

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

PAY_FROM = [
    "Сбер Gold",
    "Сбер 7650",
    "Тинькофф",
    "ИП Рахматуллаев",
    "ИП Саяпина",
    "Сбер ИП Урумчи",
    "Счет Сбер физ. лица",
    "Сбер разные счета",
    "Наличные",
]
DEFAULT_PAY_FROM = "Сбер 7650"

CATEGORIES = [
    "Кафе","Продукты","Спорт","Красота/Здоровье","Транспорт","Развлечения","Авто","Подарки",
    "Квартира","Алименты","Кредит","Инвестиции","Прочее","Тел. + инет + подписки",
    "Банк. комиссия","Дети","Плутон","Одежда","Путешествия","Отдал Жене","Книги","Ozon","Обучение",
]

class Form(StatesGroup):
    date = State()
    # дальше добавим name/amount/category/payfrom/note/confirm

def only_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="заполнить", callback_data="fill")],
        [InlineKeyboardButton(text="отмена", callback_data="cancel")],
    ])

def kb_date() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="сегодня", callback_data="date:today"),
         InlineKeyboardButton(text="вчера", callback_data="date:yday")],
        [InlineKeyboardButton(text="ввести вручную (ддммгг)", callback_data="date:manual")],
        [InlineKeyboardButton(text="отмена", callback_data="cancel")],
    ])

def fmt_ddmmyy(d: dt.date) -> str:
    return d.strftime("%d%m%y")

@dp.message(F.text == "/start")
async def start(m: Message, state: FSMContext):
    if not only_admin(m.from_user.id):
        return
    await state.clear()
    await m.answer("ок. жми «заполнить» или пиши строкой через ;", reply_markup=kb_main())

@dp.callback_query(F.data == "fill")
async def fill(c: CallbackQuery, state: FSMContext):
    if not only_admin(c.from_user.id):
        return
    await state.clear()
    await state.set_state(Form.date)
    await c.message.answer("дата?", reply_markup=kb_date())
    await c.answer()

@dp.callback_query(F.data.startswith("date:"))
async def pick_date(c: CallbackQuery, state: FSMContext):
    if not only_admin(c.from_user.id):
        return
    v = c.data.split(":", 1)[1]
    today = dt.date.today()

    if v == "today":
        await state.update_data(date=fmt_ddmmyy(today))
        await c.message.answer(f"дата ок: {fmt_ddmmyy(today)}. дальше будет «наименование» (следующий кусок).")
    elif v == "yday":
        d = today - dt.timedelta(days=1)
        await state.update_data(date=fmt_ddmmyy(d))
        await c.message.answer(f"дата ок: {fmt_ddmmyy(d)}. дальше будет «наименование» (следующий кусок).")
    else:
        await c.message.answer("введи дату в формате ддммгг, пример: 050126")

    await c.answer()

@dp.message(Form.date)
async def manual_date(m: Message, state: FSMContext):
    if not only_admin(m.from_user.id):
        return
    t = "".join(ch for ch in (m.text or "").strip() if ch.isdigit())
    if len(t) != 6:
        await m.answer("не то. надо ровно 6 цифр: ддммгг (пример 050126).")
        return
    await state.update_data(date=t)
    await m.answer(f"дата ок: {t}. дальше будет «наименование» (следующий кусок).")

@dp.callback_query(F.data == "cancel")
async def cancel(c: CallbackQuery, state: FSMContext):
    if only_admin(c.from_user.id):
        await state.clear()
        await c.message.answer("отменено.", reply_markup=kb_main())
    await c.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
