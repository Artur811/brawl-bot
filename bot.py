from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
import asyncio
import os

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
                    url="https://funpay.com/users/19690950/"
                )
            ]
        ]
    )

    await message.answer(
        "💎 Лучший магазин для игроков Brawl Stars 💎

🛒 У нас можно купить: • Аккаунты разных рангов 🏆
• Гемы 💚
• Brawl Pass 🎟️
• Донат и внутриигровые товары ⚡
• Акции магазинов 🛍️🔥

⚡ Быстрая выдача
🔒 Безопасные сделки
💬 Отзывчивая поддержка

🚀 Прокачай свой аккаунт уже сегодня!"
        reply_markup=keyboard
    )

async def health(request):
    return web.Response(text="OK")

async def main():

    app = web.Application()
    app.router.add_get("/", health)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", 10000))

    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    print("BOT STARTED")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
