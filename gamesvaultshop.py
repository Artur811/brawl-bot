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


# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Добавь эти значения в Render Environment Variables
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID = os.getenv("CHANNEL_ID", "")

# Telcell Wallet
TELCELL_NUMBER = os.getenv("TELCELL_NUMBER", "043055510")

if not BOT_TOKEN:
    raise RuntimeError(
        "❌ BOT_TOKEN не найден. Добавь BOT_TOKEN в Environment Variables Render."
    )

if ADMIN_ID == 0:
    print("⚠️ ADMIN_ID не задан. Админские функции работать не будут.")


# =========================================================
# BOT
# =========================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
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
# MAIN MENU
# =========================================================

def main_menu_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎮 Roblox",
                    callback_data="game:roblox"
                ),
                InlineKeyboardButton(
                    text="🔫 Standoff 2",
                    callback_data="game:standoff2"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⭐ Brawl Stars",
                    callback_data="game:brawlstars"
                ),
                InlineKeyboardButton(
                    text="🪂 PUBG Mobile",
                    callback_data="game:pubg"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🎫 Brawl Pass",
                    callback_data="game:brawlpass"
                ),
            ],
        ]
    )


# =========================================================
# MAIN MENU TEXT
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


# =========================================================
# BACK BUTTON
# =========================================================

def back_button(callback_data="back:main"):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Հետ",
                    callback_data=callback_data
                )
            ]
        ]
    )


# =========================================================
# GAME MENU
# =========================================================

def game_keyboard(game: str):

    items = CATALOG[game]["items"]

    buttons = []

    for index, (name, price) in enumerate(items):

        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"⚡ {name} — {price:,} ֏".replace(",", " "),
                    callback_data=f"product:{game}:{index}"
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="⬅️ Հետ",
                callback_data="back:main"
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def cmd_start(message: Message):

    user = get_user(message.from_user.id)

    user["username"] = message.from_user.username

    await message.answer(
        main_text(),
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML"
    )


# =========================================================
# MAIN COMMAND
# =========================================================

@dp.message(Command("menu"))
async def cmd_menu(message: Message):

    await message.answer(
        main_text(),
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML"
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

    game_name = CATALOG[game]["name"]

    text = (
        f"{game_name}\n\n"
        "Ընտրիր անհրաժեշտ ապրանքը։\n\n"
        "💰 Գները նշված են դրամով։"
    )

    try:
        await callback.message.edit_text(
            text,
            reply_markup=game_keyboard(game),
            parse_mode="HTML"
        )
    except TelegramBadRequest:
        await callback.message.answer(
            text,
            reply_markup=game_keyboard(game),
            parse_mode="HTML"
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

    text = (
        "🛒 <b>Ձեր ընտրությունը</b>\n\n"
        f"🎮 Խաղ՝ <b>{escape(CATALOG[game]['name'])}</b>\n"
        f"📦 Ապրանք՝ <b>{escape(product)}</b>\n"
        f"💰 Գին՝ <b>{price:,} ֏</b>\n\n"
        "Շարունակե՞լ պատվերը։"
    ).replace(",", " ")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Գնել",
                    callback_data="buy:confirm"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Հետ",
                    callback_data=f"back:game:{game}"
                )
            ],
        ]
    )

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# BUY
# =========================================================

@dp.callback_query(F.data == "buy:confirm")
async def buy_confirm(callback: CallbackQuery):

    user = get_user(callback.from_user.id)

    if not user["product"]:
        await callback.answer(
            "❌ Սկզբում ընտրիր ապրանքը։",
            show_alert=True
        )
        return

    text = (
        "💳 <b>Վճարում</b>\n\n"
        f"📦 {escape(user['product'])}\n"
        f"💰 <b>{user['price']:,} ֏</b>\n\n"
        "Վճարումը կատարվում է միայն <b>Telcell Wallet</b>-ով։\n\n"
        f"📱 Telcell Wallet՝ <code>{TELCELL_NUMBER}</code>\n\n"
        "Վճարումից հետո սեղմիր «✅ Վճարել եմ» և ուղարկիր չեկը։"
    ).replace(",", " ")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Վճարել եմ",
                    callback_data="payment:done"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Հետ",
                    callback_data="back:product"
                )
            ],
        ]
    )

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# PAYMENT DONE
# =========================================================

@dp.callback_query(F.data == "payment:done")
async def payment_done(callback: CallbackQuery):

    user = get_user(callback.from_user.id)

    if not user["product"]:
        await callback.answer(
            "❌ Ապրանքը ընտրված չէ։",
            show_alert=True
        )
        return

    user["payment"] = "waiting_receipt"

    text = (
        "🧾 <b>Ուղարկիր վճարման չեկը</b>\n\n"
        f"📦 Ապրանք՝ <b>{escape(user['product'])}</b>\n"
        f"💰 Գին՝ <b>{user['price']:,} ֏</b>\n\n"
        "Ուղարկիր Telcell-ի վճարման չեկի նկարը այս չաթում։\n\n"
        "❗ Չեկը պետք է լինի ամբողջությամբ տեսանելի։"
    ).replace(",", " ")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Հետ",
                    callback_data="back:payment"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# RECEIPT PHOTO
# =========================================================

@dp.message(F.photo)
async def receive_receipt(message: Message):

    user = get_user(message.from_user.id)

    if user.get("payment") != "waiting_receipt":

        await message.answer(
            "❗ Սկզբում ընտրիր ապրանքը և անցիր до оплаты через Telcell Wallet.",
            reply_markup=main_menu_keyboard()
        )

        return

    photo = message.photo[-1]

    # Generate order ID
    order_id = (
        f"{message.from_user.id}-"
        f"{message.message_id}"
    )

    user["order_id"] = order_id
    user["payment"] = "waiting_admin"

    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "չկա"
    )

    admin_text = (
        "🛎 <b>ՆՈՐ ՊԱՏՎԵՐ</b>\n\n"
        f"🆔 Order ID՝ <code>{order_id}</code>\n"
        f"👤 User ID՝ <code>{message.from_user.id}</code>\n"
        f"👤 Username՝ {escape(username)}\n\n"
        f"🎮 Խաղ՝ <b>{escape(CATALOG[user['game']]['name'])}</b>\n"
        f"📦 Ապրանք՝ <b>{escape(user['product'])}</b>\n"
        f"💰 Գին՝ <b>{user['price']:,} ֏</b>\n\n"
        "🧾 Վճարման չեկը կցված է։"
    ).replace(",", " ")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Հաստատել",
                    callback_data=f"order:approve:{order_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Մերժել",
                    callback_data=f"order:reject:{order_id}"
                ),
            ]
        ]
    )

    # Send to admin
    if ADMIN_ID:

        try:

            await bot.send_photo(
                chat_id=ADMIN_ID,
                photo=photo.file_id,
                caption=admin_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        except Exception as e:

            logging.exception(
                "Ошибка отправки чека админу: %s",
                e
            )

    # Send to channel if configured
    if CHANNEL_ID:

        try:

            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=photo.file_id,
                caption=admin_text,
                parse_mode="HTML"
            )

        except Exception as e:

            logging.exception(
                "Ошибка отправки в канал: %s",
                e
            )

    await message.answer(
        "✅ <b>Չեկը ստացվեց։</b>\n\n"
        "Պատվերը ուղարկվել է ստուգման։\n"
        "Խնդրում ենք սպասել հաստատմանը։",
        parse_mode="HTML"
    )


# =========================================================
# APPROVE ORDER
# =========================================================

@dp.callback_query(F.data.startswith("order:approve:"))
async def approve_order(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:
        await callback.answer(
            "❌ Դու ադմին չես։",
            show_alert=True
        )
        return

    order_id = callback.data.split(":", 2)[2]

    target_user_id = None

    for uid, data in users.items():

        if data.get("order_id") == order_id:
            target_user_id = uid
            break

    if target_user_id is None:

        await callback.answer(
            "❌ Պատվերը չի գտնվել։",
            show_alert=True
        )

        return

    user = users[target_user_id]

    user["payment"] = "approved"

    try:

        await bot.send_message(
            chat_id=target_user_id,
            text=(
                "✅ <b>Պատվերը հաստատվեց!</b>\n\n"
                f"📦 {escape(user['product'])}\n"
                f"💰 {user['price']:,} ֏\n\n"
                "Շնորհակալություն Games Vault Shop-ը ընտրելու համար ❤️‍🔥"
            ).replace(",", " "),
            parse_mode="HTML"
        )

    except Exception as e:

        logging.exception(
            "Не удалось отправить подтверждение пользователю: %s",
            e
        )

    try:

        await callback.message.edit_caption(
            caption=(
                "✅ <b>ՊԱՏՎԵՐԸ ՀԱՍՏԱՏՎԱԾ Է</b>\n\n"
                f"🆔 Order ID՝ <code>{order_id}</code>\n"
                f"📦 {escape(user['product'])}\n"
                f"💰 {user['price']:,} ֏"
            ).replace(",", " "),
            parse_mode="HTML"
        )

    except Exception:

        pass

    await callback.answer("✅ Պատվերը հաստատվեց։")


# =========================================================
# REJECT ORDER
# =========================================================

@dp.callback_query(F.data.startswith("order:reject:"))
async def reject_order(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:

        await callback.answer(
            "❌ Դու ադմին չես։",
            show_alert=True
        )

        return

    order_id = callback.data.split(":", 2)[2]

    target_user_id = None

    for uid, data in users.items():

        if data.get("order_id") == order_id:
            target_user_id = uid
            break

    if target_user_id is None:

        await callback.answer(
            "❌ Պատվերը չի գտնվել։",
            show_alert=True
        )

        return

    user = users[target_user_id]

    user["payment"] = "rejected"

    try:

        await bot.send_message(
            chat_id=target_user_id,
            text=(
                "❌ <b>Պատվերը մերժվեց</b>\n\n"
                f"📦 {escape(user['product'])}\n"
                f"💰 {user['price']:,} ֏\n\n"
                "Խնդրում ենք կապվել Games Vault Shop-ի հետ։"
            ).replace(",", " "),
            parse_mode="HTML"
        )

    except Exception as e:

        logging.exception(
            "Не удалось отправить отказ пользователю: %s",
            e
        )

    try:

        await callback.message.edit_caption(
            caption=(
                "❌ <b>ՊԱՏՎԵՐԸ ՄԵՐԺՎԱԾ Է</b>\n\n"
                f"🆔 Order ID՝ <code>{order_id}</code>\n"
                f"📦 {escape(user['product'])}\n"
                f"💰 {user['price']:,} ֏"
            ).replace(",", " "),
            parse_mode="HTML"
        )

    except Exception:

        pass

    await callback.answer("❌ Պատվերը մերժվեց։")


# =========================================================
# BACK TO MAIN
# =========================================================

@dp.callback_query(F.data == "back:main")
async def back_main(callback: CallbackQuery):

    await callback.message.edit_text(
        main_text(),
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# BACK TO GAME
# =========================================================

@dp.callback_query(F.data.startswith("back:game:"))
async def back_game(callback: CallbackQuery):

    game = callback.data.split(":")[2]

    if game not in CATALOG:

        await callback.message.edit_text(
            main_text(),
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML"
        )

        await callback.answer()
        return

    user = get_user(ca
