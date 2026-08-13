import os
import asyncio
import logging
from html import escape

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.exceptions import TelegramBadRequest
from aiohttp import web


# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID = os.getenv("CHANNEL_ID", "")
# Отдельный канал именно для заказов/чеков.
# Если ORDER_CHANNEL_ID задан, заказы отправляются туда.
ORDER_CHANNEL_ID = os.getenv("ORDER_CHANNEL_ID", CHANNEL_ID)
TELCELL_NUMBER = os.getenv("TELCELL_NUMBER", "043055510")
PORT = int(os.getenv("PORT", "10000"))

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не найден. Добавь BOT_TOKEN в Environment Variables Render."
    )

if ADMIN_ID == 0:
    print("WARNING: ADMIN_ID не задан. Админские функции работать не будут.")


# =========================================================
# BOT
# =========================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


# =========================================================
# TEMPORARY USER DATA
# =========================================================

users = {}


def get_user(user_id: int):
    if user_id not in users:
        users[user_id] = {
            "game": None,
            "product": None,
            "price": None,
            "username": None,
            "player_id": None,
            "payment": None,
            "order_id": None,
        }
    return users[user_id]


# =========================================================
# CATALOG
# =========================================================

CATALOG = {
    "roblox": {
        "name": "🎮 Roblox",
        "items": [
            ("40 Robux", 350),
            ("80 Robux", 650),
            ("120 Robux", 950),
            ("400 Robux", 2700),
            ("520 Robux", 3600),
            ("840 Robux", 4850),
            ("1,240 Robux", 7300),
            ("1,700 Robux", 8800),
            ("1,820 Robux", 9700),
            ("4,500 Robux", 21000),
            ("10,000 Robux", 40000),
            ("22,500 Robux", 88000),
        ],
    },
    "standoff2": {
        "name": "🔫 Standoff 2",
        "items": [
            ("100 Gold", 1000),
            ("200 Gold", 2000),
            ("300 Gold", 2900),
            ("500 Gold", 4000),
            ("600 Gold", 5100),
            ("700 Gold", 5800),
            ("1,000 Gold", 7100),
            ("1,500 Gold", 10300),
            ("3,000 Gold", 15800),
        ],
    },
    "brawlstars": {
        "name": "⭐ Brawl Stars",
        "items": [
            ("30 Gems", 800),
            ("80 Gems", 1600),
            ("170 Gems", 3000),
            ("360 Gems", 5300),
            ("950 Gems", 13000),
        ],
    },
    "pubg": {
        "name": "🪂 PUBG Mobile",
        "items": [
            ("33 UC + 🎁", 300),
            ("66 UC + 🎁", 500),
            ("99 UC + 🎁", 700),
            ("132 UC + 🎁", 1000),
            ("150 UC + 🎁", 1100),
            ("198 UC + 🎁", 1400),
            ("210 UC + 🎁", 1600),
            ("325 UC + 🎁", 2000),
            ("355 + 5 UC + 🎁", 2100),
            ("445 UC + 🎁", 2900),
            ("505 UC + 🎁", 3400),
            ("660 UC + 🎁", 4000),
            ("720 UC + 🎁", 4300),
            ("985 UC + 🎁", 6000),
            ("1,135 UC + 🎁", 7000),
            ("1,320 UC + 🎁", 7800),
            ("1,860 UC + 🎁", 10000),
            ("2,185 UC + 🎁", 11500),
        ],
    },
    "brawlpass": {
        "name": "🎫 Brawl Pass",
        "items": [
            ("Brawl Pass — аккаунт 1", 2700),
            ("Brawl Pass — аккаунт 2", 3600),
            ("Brawl Pass Plus — аккаунт 1", 3600),
            ("Brawl Pass Plus — аккаунт 2", 5000),
            ("Pro Pass", 12800),
        ],
    },
}


# =========================================================
# KEYBOARDS
# =========================================================


def main_menu_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎮 Roblox", callback_data="game:roblox"),
                InlineKeyboardButton(text="🔫 Standoff 2", callback_data="game:standoff2"),
            ],
            [
                InlineKeyboardButton(text="⭐ Brawl Stars", callback_data="game:brawlstars"),
                InlineKeyboardButton(text="🪂 PUBG Mobile", callback_data="game:pubg"),
            ],
            [
                InlineKeyboardButton(text="🎫 Brawl Pass", callback_data="game:brawlpass"),
            ],
            [
                InlineKeyboardButton(text="📩 Կապվեք մեզ հետ", callback_data="contact:open"),
            ],
        ]
    )


def game_keyboard(game: str):
    items = CATALOG[game]["items"]
    buttons = []

    for index, (name, price) in enumerate(items):
        buttons.append([
            InlineKeyboardButton(
                text=f"⚡ {name} — {price:,} ֏".replace(",", " "),
                callback_data=f"product:{game}:{index}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:main")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def product_keyboard(game: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Գնել", callback_data="buy:confirm")],
            [InlineKeyboardButton(text="⬅️ Հետ", callback_data=f"back:game:{game}")],
        ]
    )


def payment_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Վճարել եմ", callback_data="payment:done")],
            [InlineKeyboardButton(text="💳 Քարտ տրամադրել — հասանելի չէ", callback_data="card:unavailable")],
            [InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:product")],
        ]
    )


def receipt_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:payment")]
        ]
    )


# =========================================================
# TEXT
# =========================================================


def main_text():
    return (
        "🎮 <b>Games Vault Shop</b> ❤️‍🔥\n\n"
        "💎 <b>Games Vault Shop-ում՝ միշտ VAULT-Ա!</b>\n\n"
        "Ընտրիր խաղը և տես հասանելի ապրանքները։\n\n"
        "⚡ Արագ պատվեր\n"
        "💳 Telcell Wallet\n"
        "🧾 Չեկի հաստատում\n\n"
        "❗ Գնումից առաջ ստուգիր ապրանքի տեսակը և գինը։"
    )


def game_text(game: str):
    return (
        f"{CATALOG[game]['name']}\n\n"
        "Ընտրիր անհրաժեշտ ապրանքը։\n\n"
        "💰 Գները նշված են դրամով։"
    )


# =========================================================
# START / MENU
# =========================================================


@dp.message(CommandStart())
async def cmd_start(message: Message):
    user = get_user(message.from_user.id)
    user["username"] = message.from_user.username

    await message.answer(
        main_text(),
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    await message.answer(
        main_text(),
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


# =========================================================
# GAME SELECT
# =========================================================


@dp.callback_query(F.data.startswith("game:"))
async def select_game(callback: CallbackQuery):
    game = callback.data.split(":", 1)[1]

    if game not in CATALOG:
        await callback.answer("❌ Սխալ խաղ։", show_alert=True)
        return

    user = get_user(callback.from_user.id)
    user["game"] = game
    user["product"] = None
    user["price"] = None
    user["payment"] = None
    user["order_id"] = None

    try:
        await callback.message.edit_text(
            game_text(game),
            reply_markup=game_keyboard(game),
            parse_mode="HTML",
        )
    except TelegramBadRequest:
        await callback.message.answer(
            game_text(game),
            reply_markup=game_keyboard(game),
            parse_mode="HTML",
        )

    await callback.answer()


# =========================================================
# PRODUCT SELECT
# =========================================================


@dp.callback_query(F.data.startswith("product:"))
async def select_product(callback: CallbackQuery):
    parts = callback.data.split(":")

    if len(parts) != 3:
        await callback.answer("❌ Սխալ ապրանք։", show_alert=True)
        return

    game = parts[1]

    try:
        index = int(parts[2])
    except ValueError:
        await callback.answer("❌ Սխալ ապրանք։", show_alert=True)
        return

    if game not in CATALOG:
        await callback.answer("❌ Սխալ խաղ։", show_alert=True)
        return

    items = CATALOG[game]["items"]
    if index < 0 or index >= len(items):
        await callback.answer("❌ Սխալ ապրանք։", show_alert=True)
        return

    product, price = items[index]
    user = get_user(callback.from_user.id)
    user["game"] = game
    user["product"] = product
    user["price"] = price
    user["payment"] = None
    user["order_id"] = None

    text = (
        "🛒 <b>Ձեր ընտրությունը</b>\n\n"
        f"🎮 Խաղ՝ <b>{escape(CATALOG[game]['name'])}</b>\n"
        f"📦 Ապրանք՝ <b>{escape(product)}</b>\n"
        f"💰 Գին՝ <b>{price:,} ֏</b>\n\n"
        "Շարունակե՞լ պատվերը։"
    ).replace(",", " ")

    await callback.message.edit_text(
        text,
        reply_markup=product_keyboard(game),
        parse_mode="HTML",
    )
    await callback.answer()


# =========================================================
# BUY / PAYMENT
# =========================================================


@dp.callback_query(F.data == "buy:confirm")
async def buy_confirm(callback: CallbackQuery):
    user = get_user(callback.from_user.id)

    if not user["product"]:
        await callback.answer("❌ Սկզբում ընտրիր ապրանքը։", show_alert=True)
        return

    text = (
        "💳 <b>Վճարում</b>\n\n"
        f"📦 {escape(user['product'])}\n"
        f"💰 <b>{user['price']:,} ֏</b>\n\n"
        "Վճարումը կատարվում է միայն <b>Telcell Wallet</b>-ով։\n\n"
        "💳 Քարտով վճարումը՝ <b>հասանելի չէ</b>։\n\n"
        f"📱 Telcell Wallet՝ <code>{escape(TELCELL_NUMBER)}</code>\n\n"
        "Վճարումից հետո սեղմիր «✅ Վճարել եմ» և ուղարկիր չեկը։"
    ).replace(",", " ")

    await callback.message.edit_text(
        text,
        reply_markup=payment_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.callback_query(F.data == "card:unavailable")
async def card_unavailable(callback: CallbackQuery):
    await callback.answer(
        "💳 Քարտ տրամադրել՝ հասանելի չէ։",
        show_alert=True,
    )


@dp.callback_query(F.data == "payment:done")
async def payment_done(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    user["payment"] = "waiting_receipt"

    await callback.message.edit_text(
        "🧾 <b>Ուղարկիր չեկը</b>\n\n"
        "Ուղարկիր այստեղ վճարման չեկի լուսանկարը։\n\n"
        "⬅️ Եթե ուզում ես վերադառնալ, սեղմիր «Հետ»։",
        reply_markup=receipt_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.message(F.photo)
async def receive_receipt(message: Message):
    user = get_user(message.from_user.id)

    if user.get("payment") != "waiting_receipt":
        return

    user["payment"] = "receipt_sent"
    user["username"] = message.from_user.username

    caption = (
        "🧾 <b>Նոր չեկ</b>\n\n"
        f"👤 Օգտատեր՝ @{escape(message.from_user.username or 'չկա')}\n"
        f"🆔 ID՝ <code>{message.from_user.id}</code>\n"
        f"🎮 Խաղ՝ {escape(CATALOG[user['game']]['name'])}\n"
        f"📦 Ապրանք՝ {escape(user['product'])}\n"
        f"💰 Գումար՝ <b>{user['price']:,} ֏</b>\n"
    ).replace(",", " ")

    target = ORDER_CHANNEL_ID or ADMIN_ID
    await bot.send_photo(
        chat_id=target,
        photo=message.photo[-1].file_id,
        caption=caption,
        parse_mode="HTML",
    )

    await message.answer(
        "✅ Չեկը ստացվել է։\n\n"
        "Սպասիր մեր պատասխանին։",
        parse_mode="HTML",
    )


@dp.callback_query(F.data.startswith("back:"))
async def back_handler(callback: CallbackQuery):
    await callback.answer()
