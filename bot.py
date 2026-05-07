from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
import asyncio

TOKEN = "8741988605:AAEVUuVu2TEP3269YgYjfsGNaUYYb7EOQWc"

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def start(message: types.Message):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛒 Купить",
                    web_app=WebAppInfo(
                        url="https://funpay.com/users/19690950/"
                    )
                )
            ]
        ]
    )

    text = (
        "💎 Лучший магазин для игроков Brawl Stars 💎\n\n"
        "🛒 У нас можно купить:\n"
        "• Аккаунты разных рангов 🏆\n"
        "• Гемы 💚\n"
        "• Brawl Pass 🎟️\n"
        "• Донат и внутриигровые товары ⚡\n"
        "• Акции магазинов 🛍️🔥\n\n"
        "⚡ Быстрая выдача\n"
        "🔒 Безопасные сделки\n"
        "💬 Отзывчивая поддержка\n\n"
        "🚀 Прокачай свой аккаунт уже сегодня!"
    )

    await message.answer(text, reply_markup=keyboard)

async def main():
    print("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
