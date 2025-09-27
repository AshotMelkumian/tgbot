import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# --- переменные окружения ---
API_TOKEN = os.getenv("API_TOKEN")  # токен бота
ADMIN_ID = int(os.getenv("ADMIN_ID"))  # твой Telegram ID

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- данные ---
IPHONES = [
    "iPhone 11 Pro", "iPhone 11 Pro Max",
    "iPhone 12", "iPhone 12 mini", "iPhone 12 Pro", "iPhone 12 Pro Max",
    "iPhone 13", "iPhone 13 mini", "iPhone 13 Pro", "iPhone 13 Pro Max",
    "iPhone 14", "iPhone 14 Plus", "iPhone 14 Pro", "iPhone 14 Pro Max",
    "iPhone 15", "iPhone 15 Plus", "iPhone 15 Pro", "iPhone 15 Pro Max",
    "iPhone 16 Pro", "iPhone 16 Pro Max"
]

IPHONE_PRICES = {
    "iPhone 11 Pro": 20000,
    "iPhone 11 Pro Max": 22000,
    "iPhone 12": 23000,
    "iPhone 12 mini": 21000,
    "iPhone 12 Pro": 25000,
    "iPhone 12 Pro Max": 27000,
    "iPhone 13": 28000,
    "iPhone 13 mini": 26000,
    "iPhone 13 Pro": 30000,
    "iPhone 13 Pro Max": 32000,
    "iPhone 14": 35000,
    "iPhone 14 Plus": 37000,
    "iPhone 14 Pro": 40000,
    "iPhone 14 Pro Max": 42000,
    "iPhone 15": 45000,
    "iPhone 15 Plus": 47000,
    "iPhone 15 Pro": 50000,
    "iPhone 15 Pro Max": 52000,
    "iPhone 16 Pro": 60000,
    "iPhone 16 Pro Max": 62000,
}

QUESTIONS = [
    ("Имеется ли коробка для данного телефона?", 500, 0),
    ("Поставляется ли телефон с кабелем в комплекте?", 300, 0),
    ("Состояние батареи больше 84%?", 0, -2000),
    ("Необходимо ли заменить дисплей на телефоне?", -5000, 0),
    ("Необходимо ли заменить корпус на телефоне?", -4000, 0),
    ("Работает ли Face-ID на данном телефоне?", 0, -6000),
    ("Есть ли глубокие царапины на экране?", 0, -1500),
    ("Присутствуют ли глубокие царапины на корпусе?", 0, -1500),
]

MODELS_PER_PAGE = 5

# --- состояния ---
class SellPhone(StatesGroup):
    choosing_model = State()
    answering_questions = State()
    tradein = State()

# --- старт ---
@dp.message(F.text == "/start")
async def start_cmd(message: types.Message, state: FSMContext):
    await state.update_data(page=0)
    await send_model_page(message, state)

# --- пагинация моделей ---
async def send_model_page(message_or_callback, state: FSMContext):
    data = await state.get_data()
    page = data.get("page", 0)
    start_idx = page * MODELS_PER_PAGE
    end_idx = start_idx + MODELS_PER_PAGE
    models = IPHONES[start_idx:end_idx]

    if not models:
        await (message_or_callback.answer if isinstance(message_or_callback, types.Message)
               else message_or_callback.message.answer)("Нет моделей на этой странице.")
        return

    buttons = [[InlineKeyboardButton(text=f"📱 {model}", callback_data=f"model:{model}")] for model in models]

    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data="nav:prev"))
    if end_idx < len(IPHONES):
        nav_buttons.append(InlineKeyboardButton(text="➡️ Вперед", callback_data="nav:next"))
    if nav_buttons:
        buttons.append(nav_buttons)

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    text = "📱 Выберите модель iPhone:"
    if isinstance(message_or_callback, types.Message):
        await message_or_callback.answer(text, reply_markup=kb)
    else:
        await message_or_callback.message.edit_text(text, reply_markup=kb)

    await state.set_state(SellPhone.choosing_model)

# --- обработка выбора модели и навигации ---
@dp.callback_query(SellPhone.choosing_model)
async def handle_model_choice(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if callback.data.startswith("model:"):
        model = callback.data.split(":")[1]
        await state.update_data(model=model, price=IPHONE_PRICES[model], q_index=0)
        await callback.message.answer(f"Вы выбрали {model}. Давайте ответим на вопросы.")
        await ask_question(callback.message, state)
    elif callback.data == "nav:next":
        await state.update_data(page=data.get("page", 0) + 1)
        await send_model_page(callback, state)
    elif callback.data == "nav:prev":
        await state.update_data(page=data.get("page", 0) - 1)
        await send_model_page(callback, state)

# --- вопросы ---
async def ask_question(message: types.Message, state: FSMContext):
    data = await state.get_data()
    q_index = data["q_index"]

    if q_index >= len(QUESTIONS):
        price = data["price"]
        await message.answer(f"✅ Примерная стоимость вашего телефона: {price} руб.")
        await ask_tradein(message, state)
        return

    q_text, _, _ = QUESTIONS[q_index]
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да", callback_data="yes"),
                InlineKeyboardButton(text="Нет", callback_data="no"),
            ]
        ]
    )
    await message.answer(q_text, reply_markup=kb)
    await state.set_state(SellPhone.answering_questions)

@dp.callback_query(SellPhone.answering_questions)
async def handle_answer(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    q_index = data["q_index"]
    price = data["price"]

    q_text, yes_val, no_val = QUESTIONS[q_index]

    if callback.data == "yes":
        price += yes_val
    else:
        price += no_val

    await state.update_data(price=price, q_index=q_index + 1)
    await ask_question(callback.message, state)

# --- Trade-in ---
async def ask_tradein(message: types.Message, state: FSMContext):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да", callback_data="tradein:yes"),
                InlineKeyboardButton(text="Нет", callback_data="tradein:no"),
            ]
        ]
    )
    await message.answer("💡 Хочешь сдать телефон в Trade-in?", reply_markup=kb)
    await state.set_state(SellPhone.tradein)

@dp.callback_query(SellPhone.tradein)
async def handle_tradein(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "tradein:yes":
        user = callback.from_user
        await bot.send_message(
            ADMIN_ID,
            f"Пользователь @{user.username or user.full_name} хочет сдать телефон в Trade-in."
        )
        await callback.message.answer("Спасибо! Мы свяжемся с вами для оформления Trade-in ✅")
    else:
        await callback.message.answer("Ок, спасибо за использование бота!")
    await state.clear()

# --- запуск ---
async def main():
    print("Бот запускается...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
