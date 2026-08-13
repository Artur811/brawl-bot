import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.exceptions import TelegramBadRequest


# =========================================================
# НАСТРОЙКИ
# =========================================================

TOKEN = os.getenv("8994024293:AAGPKSVcsS-zUuBpEUT426db4PtSk-cWnVQ")

ADMIN_ID = int(os.getenv("ADMIN_ID", "8833455229"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003924262565"))
TELCELL_NUMBER = os.getenv("TELCELL_NUMBER", "043055510")

if not TOKEN:
    raise RuntimeError(
        "❌ BOT_TOKEN не найден. Добавь BOT_TOKEN в Environment Variables Render."
    )

logging.basicConfig(level=logging.INFO)

bot = Bot(TOKEN)
dp = Dispatcher()


# =========================================================
# ТОВАРЫ
# =========================================================

PRODUCTS = {
    "roblox": [
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

    "pubg": [
        ("60 UC", 450),
        ("325 UC + 🎁25", 1900),
        ("660 UC + 🎁60", 3800),
        ("1,800 UC + 🎁300", 9500),
        ("3,850 UC + 🎁850", 18000),
        ("8,100 UC + 🎁2,100", 36000),
    ],

    "brawl": [
        ("30 Gems", 750),
        ("80 Gems", 1500),
        ("170 Gems", 2800),
        ("360 Gems", 4900),
        ("950 Gems", 12000),
        ("Brawl Pass", 2500),
        ("Brawl Pass Plus", 3400),
    ],

    "standoff": [
        ("100 Gold", 950),
        ("200 Gold", 1900),
        ("300 Gold", 2750),
        ("500 Gold", 3800),
        ("600 Gold", 4800),
        ("700 Gold", 5400),
        ("1,000 Gold", 6600),
        ("1,500 Gold", 9500),
        ("3,000 Gold", 14500),
    ],
}


GAME_NAMES = {
    "roblox": "🎮 Roblox",
    "pubg": "🎯 PUBG Mobile",
    "brawl": "⭐ Brawl Stars",
    "standoff": "😎 Standoff 2",
}


# =========================================================
# ЗАКАЗЫ
# =========================================================

orders = {}
order_counter = 1000


# =========================================================
# ГЛАВНОЕ МЕНЮ
# =========================================================

def main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎮 Roblox",
                    callback_data="game:roblox"
                ),
                InlineKeyboardButton(
                    text="🎯 PUBG Mobile",
                    callback_data="game:pubg"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⭐ Brawl Stars",
                    callback_data="game:brawl"
                ),
                InlineKeyboardButton(
                    text="😎 Standoff 2",
                    callback_data="game:standoff"
                ),
            ],
        ]
    )


# =========================================================
# МЕНЮ ТОВАРОВ
# =========================================================

def product_menu(game):
    rows = []

    for i, (name, price) in enumerate(PRODUCTS[game]):
        rows.append([
            InlineKeyboardButton(
                text=f"🎁 {name} — {price} ֏",
                callback_data=f"product:{game}:{i}"
            )
        ])

    rows.append([
        InlineKeyboardButton(
            text="⬅️ Հետ",
            callback_data="back_main"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


# =========================================================
# МЕНЮ ОПЛАТЫ
# =========================================================

def payment_menu(game):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💵 Կանխիկ / Telcell",
                    callback_data="pay_cash"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 Քարտ",
                    callback_data="pay_card"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Հետ",
                    callback_data=f"game:{game}"
                )
            ],
        ]
    )


# =========================================================
# КНОПКИ АДМИНА
# =========================================================

def admin_buttons(user_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Ընդունել չեկը",
                    callback_data=f"admin_accept:{user_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Մերժել",
                    callback_data=f"admin_reject:{user_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🎉 Կատարված է",
                    callback_data=f"admin_done:{user_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Պատվերը չի տրամադրվել",
                    callback_data=f"admin_not_given:{user_id}"
                )
            ],
        ]
    )


# =========================================================
# КНОПКА НАЗАД ПОСЛЕ ЧЕКА
# =========================================================

def receipt_back_menu(game):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Հետ",
                    callback_data=f"game:{game}"
                )
            ]
        ]
    )


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start(message: Message):

    await message.answer(
        "🎮 <b>GAMES VAULT SHOP</b> ❤️‍🔥\n\n"
        "Բարի գալուստ։\n"
        "Ընտրեք խաղը 👇",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )


# =========================================================
# ВЫБОР ИГРЫ
# =========================================================

@dp.callback_query(F.data.startswith("game:"))
async def select_game(callback: CallbackQuery):

    game = callback.data.split(":")[1]

    if game not in PRODUCTS:

        await callback.answer(
            "❌ Խաղը չի գտնվել։",
            show_alert=True
        )

        return

    await callback.message.edit_text(
        f"<b>{GAME_NAMES[game]}</b>\n\n"
        "🎁 Ընտրեք ապրանքը 👇",
        reply_markup=product_menu(game),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# ВЫБОР ТОВАРА
# =========================================================

@dp.callback_query(F.data.startswith("product:"))
async def select_product(callback: CallbackQuery):

    try:

        _, game, index = callback.data.split(":")

        index = int(index)

        name, price = PRODUCTS[game][index]

    except (ValueError, KeyError, IndexError):

        await callback.answer(
            "❌ Սխալ ապրանք։",
            show_alert=True
        )

        return

    orders[callback.from_user.id] = {
        "user_id": callback.from_user.id,
        "username": callback.from_user.username or "",
        "name": callback.from_user.full_name,
        "game": game,
        "product": name,
        "price": price,
        "status": "confirm",
    }

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Գնել",
                    callback_data="confirm_buy"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Հետ",
                    callback_data=f"game:{game}"
                )
            ],
        ]
    )

    await callback.message.edit_text(
        "🛒 <b>Պատվերի հաստատում</b>\n\n"
        f"🎮 Խաղ՝ <b>{GAME_NAMES[game]}</b>\n"
        f"🎁 Ապրանք՝ <b>{name}</b>\n"
        f"💰 Գին՝ <b>{price} ֏</b>\n\n"
        "Ճի՞շտ է ամեն ինչ։",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# ПОКУПКА
# =========================================================

@dp.callback_query(F.data == "confirm_buy")
async def confirm_buy(callback: CallbackQuery):

    order = orders.get(callback.from_user.id)

    if not order:

        await callback.answer(
            "❌ Պատվերը չի գտնվել։",
            show_alert=True
        )

        return

    order["status"] = "payment_method"

    await callback.message.edit_text(
        "💳 <b>Ընտրեք վճարման եղանակը</b>",
        reply_markup=payment_menu(order["game"]),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# TELCELL
# =========================================================

@dp.callback_query(F.data == "pay_cash")
async def pay_cash(callback: CallbackQuery):

    order = orders.get(callback.from_user.id)

    if not order:

        await callback.answer(
            "❌ Պատվերը չի գտնվել։",
            show_alert=True
        )

        return

    order["payment_method"] = "Telcell"
    order["status"] = "waiting_receipt"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📸 Ուղարկել չեկը",
                    callback_data="send_receipt"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Հետ",
                    callback_data=f"game:{order['game']}"
                )
            ],
        ]
    )

    await callback.message.edit_text(
        "😎❤️‍🔥 <b>Վճարման կարգը</b>\n\n"

        "1️⃣ Գնացեք մոտակա <b>Telcell</b> տերմինալ։\n\n"

        "2️⃣ Ընտրեք <b>Telcell Wallet</b>։\n\n"

        f"3️⃣ Մուտքագրեք համարը՝ "
        f"<code>{TELCELL_NUMBER}</code>\n\n"

        "4️⃣ Կատարեք վճարումը։\n\n"

        "5️⃣ 📸 Վճարումից հետո ուղարկեք չեկի լուսանկարը։\n\n"

        "6️⃣ Չեկը հաստատվելուց հետո "
        "կպահանջվի միայն խաղային ID-ն։",

        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# КАРТА — ЕЩЁ НЕДОСТУПНА
# =========================================================

@dp.callback_query(F.data == "pay_card")
async def pay_card(callback: CallbackQuery):

    order = orders.get(callback.from_user.id)

    if not order:

        await callback.answer(
            "❌ Պատվերը չի գտնվել։",
            show_alert=True
        )

        return

    order["payment_method"] = "Card"
    order["status"] = "card_unavailable"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💵 Վճարել Telcell-ով",
                    callback_data="pay_cash"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Հետ",
                    callback_data=f"game:{order['game']}"
                )
            ],
        ]
    )

    await callback.message.edit_text(
        "💳 <b>Վճարում քարտով</b>\n\n"

        "⚠️ <b>Քարտով վճարումը դեռ հասանելի չէ։</b>\n\n"

        "🔧 Մենք դեռ աշխատում ենք այս վճարման եղանակի "
        "միացման վրա։\n\n"

        "💵 Այս պահին կարող եք վճարել "
        "<b>Telcell</b>-ով։",

        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# ОТПРАВИТЬ ЧЕК
# =========================================================

@dp.callback_query(F.data == "send_receipt")
async def send_receipt(callback: CallbackQuery):

    order = orders.get(callback.from_user.id)

    if not order:

        await callback.answer(
            "❌ Պատվերը չի գտնվել։",
            show_alert=True
        )

        return

    order["status"] = "waiting_receipt"

    await callback.message.edit_text(
        "📸 <b>Ուղարկեք վճարման չեկի լուսանկարը։</b>\n\n"
        "Ուղարկեք ամբողջական և ընթեռնելի լուսանկար։\n\n"
        "⬅️ Կարող եք վերադառնալ ներքևի կոճակով։",

        reply_markup=receipt_back_menu(order["game"]),

        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# ПОЛУЧЕНИЕ ЧЕКА
# =========================================================

@dp.message(F.photo)
async def receive_receipt(message: Message):

    user_id = message.from_user.id
    order = orders.get(user_id)

    if not order:
        return

    if order.get("status") != "waiting_receipt":
        return

    order["receipt_file_id"] = message.photo[-1].file_id
    order["status"] = "waiting_game_id"

    await message.answer(
        "✅ <b>Կտրոնը ստացվեց։</b>\n\n"

        "📝 Այժմ ուղարկեք ձեր խաղային "
        "<b>ID / Login</b>-ը։\n\n"

        "⚠️ Մի ուղարկեք բանկային գաղտնաբառեր կամ քարտի տվյալներ։",

        reply_markup=receipt_back_menu(order["game"]),

        parse_mode="HTML"
    )


# =========================================================
# ТЕКСТОВЫЕ СОСТОЯНИЯ
# =========================================================

@dp.message(F.text)
async def receive_text(message: Message):

    user_id = message.from_user.id
    order = orders.get(user_id)

    if not order:
        return

    status = order.get("status")

    # =====================================================
    # GAME ID
    # =====================================================

    if status == "waiting_game_id":

        order["game_id"] = message.text.strip()
        order["status"] = "admin_review"

        await message.answer(
            "✅ <b>ID-ն ստացվեց։</b>\n\n"
            "⏳ Պատվերը ուղարկվեց ադմինիստրատորին։",
            parse_mode="HTML"
        )

        await send_order_to_admin(user_id)

    # =====================================================
    # REFUND PHONE
    # =====================================================

    elif status == "waiting_refund_phone":

        order["refund_data"] = message.text.strip()
        order["status"] = "refund_admin"

        await message.answer(
            "✅ <b>Հեռախոսահամարը ստացվեց։</b>\n\n"
            "⏳ Վերադարձը կստուգվի ադմինիստրատորի կողմից։",
            parse_mode="HTML"
        )

        await send_refund_to_admin(user_id)

    # =====================================================
    # REFUND CARD
    # =====================================================

    elif status == "waiting_refund_card":

        order["refund_data"] = message.text.strip()
        order["status"] = "refund_admin"

        await message.answer(
            "✅ <b>Տվյալները ստացվեցին։</b>\n\n"
            "⏳ Վերադարձը կստուգվի ադմինիստրատորի կողմից։",
            parse_mode="HTML"
        )

        await send_refund_to_admin(user_id)


# =========================================================
# ОТПРАВКА ЗАКАЗА АДМИНУ
# =========================================================

async def send_order_to_admin(user_id):

    global order_counter

    order = orders[user_id]

    order_counter += 1
    order["number"] = order_counter

    caption = (
        "🛒 <b>ՆՈՐ ՊԱՏՎԵՐ</b>\n\n"

        f"🆔 Պատվեր՝ <b>#{order['number']}</b>\n"
        f"👤 Հաճախորդ՝ <b>{order['name']}</b>\n"
        f"🔢 Telegram ID՝ <code>{user_id}</code>\n\n"

        f"🎮 Խաղ՝ <b>{GAME_NAMES[order['game']]}</b>\n"
        f"🎁 Ապրանք՝ <b>{order['product']}</b>\n"
        f"💰 Գին՝ <b>{order['price']} ֏</b>\n"
        f"💳 Վճարում՝ "
        f"<b>{order.get('payment_method', '-')}</b>\n"
        f"🎮 Game ID՝ "
        f"<code>{order.get('game_id', '-')}</code>\n\n"

        "📸 Կտրոնը կցված է։"
    )

    if "receipt_file_id" in order:

        await bot.send_photo(
            ADMIN_ID,
            order["receipt_file_id"],
            caption=caption,
            reply_markup=admin_buttons(user_id),
            parse_mode="HTML"
        )

    else:

        await bot.send_message(
            ADMIN_ID,
            caption,
            reply_markup=admin_buttons(user_id),
            parse_mode="HTML"
        )


# =========================================================
# АДМИН — ПРИНЯТЬ ЧЕК
# =========================================================

@dp.callback_query(F.data.startswith("admin_accept:"))
async def admin_accept(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:

        await callback.answer(
            "❌ Մուտքը արգելված է։",
            show_alert=True
        )

        return

    user_id = int(callback.data.split(":")[1])
    order = orders.get(user_id)

    if not order:

        await callback.answer(
            "❌ Պատվերը չի գտնվել։",
            show_alert=True
        )

        return

    order["status"] = "in_progress"

    await bot.send_message(
        user_id,
        "✅ <b>Կտրոնը ընդունվեց։</b>\n\n"
        "⏳ Պատվերը կատարման մեջ է։",
        parse_mode="HTML"
    )

    try:

        await callback.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="❌ Մերժել",
                            callback_data=f"admin_reject:{user_id}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🎉 Կատարված է",
                            callback_data=f"admin_done:{user_id}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="❌ Պատվերը չի տրամադրվել",
                            callback_data=f"admin_not_given:{user_id}"
                        )
                    ],
                ]
            )
        )

    except TelegramBadRequest:
        pass

    await callback.answer("✅ Չեկը ընդունվեց")


# =========================================================
# АДМИН — МЕЖЕТ
# =========================================================

@dp.callback_query(F.data.startswith("admin_reject:"))
async def admin_reject(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:

        await callback.answer(
            "❌ Մուտքը արգելված է։",
            show_alert=True
        )

        return

    user_id = int(callback.data.split(":")[1])
    order = orders.get(user_id)

    if not order:

        await callback.answer(
            "❌ Պատվերը չի գտնվել։",
            show_alert=True
        )

        return

    order["status"] = "rejected"

    # =====================================================
    # КЛИЕНТУ
    # =====================================================

    await bot.send_message(
        user_id,

        "❌ <b>Վճարման կտրոնը մերժվեց։</b>\n\n"
        "Խնդրում ենք կապվել ադմինիստրատորի հետ։",

        parse_mode="HTML"
    )

    # =====================================================
    # КАНАЛ — ЗАКАЗ ДАЖЕ ПРИ МЕЖЕТ
    # =====================================================

    await send_order_status_to_channel(
        order,
        user_id,
        "❌ Մերժված"
    )

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except TelegramBadRequest:
        pass

    await callback.answer("❌ Չեկը մերժվեց")


# =========================================================
# АДМИН — ВЫПОЛНЕНО
# =========================================================

@dp.callback_query(F.data.startswith("admin_done:"))
async def admin_done(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:

        await callback.answer(
            "❌ Մուտքը արգելված է։",
            show_alert=True
        )

        return

    user_id = int(callback.data.split(":")[1])
    order = orders.get(user_id)

    if not order:

        await callback.answer(
            "❌ Պատվերը չի գտնվել։",
            show_alert=True
        )

        return

    order["status"] = "completed"

    # =====================================================
    # КЛИЕНТУ
    # =====================================================

    await bot.send_message(
        user_id,

        "🎉 <b>Պատվերը կատարված է։</b>\n\n"

        f"🎮 {GAME_NAMES[order['game']]}\n"
        f"🎁 {order['product']}\n\n"

        "✅ Դոնաթը կատարվել է։\n"
        "❤️ Շնորհակալություն Games Vault Shop-ից օգտվելու համար։",

        parse_mode="HTML"
    )

    # =====================================================
    # КАНАЛ
    # =====================================================

    await send_order_status_to_channel(
        order,
        user_id,
        "✅ Կատարված"
    )

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except TelegramBadRequest:
        pass

    await callback.answer("🎉 Պատվերը կատարված է")


# =========================================================
# АДМИН — НЕ ВЫДАН
# =========================================================

@dp.callback_query(F.data.startswith("admin_not_given:"))
async def admin_not_given(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:

        await callback.answer(
            "❌ Մուտքը արգելված է։",
            show_alert=True
        )

        return

    user_id = int(callback.data.split(":")[1])
    order = orders.get(user_id)

    if not order:

        await callback.answer(
            "❌ Պատվերը չի գտնվել։",
            show_alert=True
        )

        return

    order["status"] = "refund_choice"

    # =====================================================
    # КАНАЛ — ЗАКАЗ НЕ ВЫДАН
    # =====================================================

    await send_order_status_to_channel(
        order,
        user_id,
        "❌ Չի տրամադրվել"
    )

    # =====================================================
    # КЛИЕНТУ
    # =====================================================

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📱 Հեռախոսահամարին",
                    callback_data=f"refund_phone:{user_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 Քարտին",
                    callback_data=f"refund_card:{user_id}"
                )
            ],
        ]
    )

    await bot.send_message(
        user_id,

        "❌ <b>Պատվերը չի տրամադրվել։</b>\n\n"

        f"💰 Գումար՝ <b>{order['price']} ֏</b>\n\n"

        "Ընտրեք վերադարձի տարբերակը 👇",

        reply_markup=keyboard,
        parse_mode="HTML"
    )

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except TelegramBadRequest:
        pass

    await callback.answer(
        "❌ Պատվերը նշվեց որպես չտրամադրված"
    )


# =========================================================
# ОТПРАВКА СТАТУСА ЗАКАЗА В КАНАЛ
# =========================================================

async def send_order_status_to_channel(
    order,
    user_id,
    status_text
):

    text = (
        "📦 <b>СТАТУС ПАТВԵՐԻ</b>\n\n"

        f"🆔 Պատվեր՝ "
        f"<b>#{order.get('number', '-')}</b>\n"

        f"👤 Հաճախորդ՝ "
        f"<b>{order.get('name', '-')}</b>\n"

        f"🔢 Telegram ID՝ "
        f"<code>{user_id}</code>\n\n"

        f"🎮 Խաղ՝ "
        f"<b>{GAME_NAMES.get(order.get('game'), '-')}</b>\n"

        f"🎁 Ապրանք՝ "
        f"<b>{order.get('product', '-')}</b>\n"

        f"💰 Գումար՝ "
        f"<b>{order.get('price', '-')} ֏</b>\n"

        f"💳 Վճարում՝ "
        f"<b>{order.get('payment_method', '-')}</b>\n"

        f"🎮 Game ID՝ "
        f"<code>{order.get('game_id', '-')}</code>\n\n"

        f"📌 Կարգավիճակ՝ "
        f"<b>{status_text}</b>"
    )

    await bot.send_message(
        CHANNEL_ID,
        text,
        parse_mode="HTML"
    )


# =========================================================
# ВОЗВРАТ — ТЕЛЕФОН
# =========================================================

@dp.callback_query(F.data.startswith("refund_phone:"))
async def refund_phone(callback: CallbackQuery):

    user_id = int(callback.data.split(":")[1])

    if callback.from_user.id != ADMIN_ID:

        if user_id != callback.from_user.id:

            await callback.answer(
                "❌ Մուտքը արգելված է։",
                show_alert=True
            )

            return

    order = orders.get(user_id)

    if not order:

        await callback.answer(
            "❌ Պատվերը չի գտնվել։",
            show_alert=True
        )

        return

    order["refund_method"] = "phone"
    order["status"] = "waiting_refund_phone"

    await callback.message.edit_text(
        "📱 <b>Վերադարձ հեռախոսահամարին</b>\n\n"

        "Գումարը կվերադարձվի նշված "
        "հեռախոսահամարին։\n\n"

        "📝 Ուղարկեք հեռախոսահամարը։",

        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# ВОЗВРАТ — КАРТА
# =========================================================

@dp.callback_query(F.data.startswith("refund_card:"))
async def refund_card(callback: CallbackQuery):

    user_id = int(callback.data.split(":")[1])

    if callback.from_user.id != ADMIN_ID:

        if user_id != callback.from_user.id:

            await callback.answer(
                "❌ Մուտքը արգելված է։",
                show_alert=True
            )

            return

    order = orders.get(user_id)

    if not order:

        await callback.answer(
            "❌ Պատվերը չի գտնվել։",
            show_alert=True
        )

        return

    order["refund_method"] = "card"
    order["status"] = "waiting_refund_card"

    await callback.message.edit_text(
        "💳 <b>Վերադարձ քարտին</b>\n\n"

        "Ուղարկեք միայն անհրաժեշտ տվյալը "
        "փոխանցումը ստանալու համար։\n\n"

        "⚠️ PIN, CVV/CVC կամ բանկային "
        "գաղտնաբառ մի ուղարկեք։",

        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# ВОЗВРАТ — АДМИНУ
# =========================================================

async def send_refund_to_admin(user_id):

    order = orders[user_id]

    if order["refund_method"] == "phone":
        method = "📱 Հեռախոսահամար"
    else:
        method = "💳 Քարտ"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💰 Վերադարձը կատարված է",
                    callback_data=f"refund_done:{user_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Մերժել",
                    callback_data=f"refund_reject:{user_id}"
                )
            ],
        ]
    )

    await bot.send_message(
        ADMIN_ID,

        "💰 <b>ՆՈՐ ՎԵՐԱԴԱՐՁ</b>\n\n"

        f"👤 Հաճախորդ՝ "
        f"<b>{order['name']}</b>\n"

        f"🆔 Telegram ID՝ "
        f"<code>{user_id}</code>\n"

        f"🎮 Խաղ՝ "
        f"<b>{GAME_NAMES[order['game']]}</b>\n"

        f"🎁 Ապրանք՝ "
        f"<b>{order['product']}</b>\n"

        f"💰 Գումար՝ "
        f"<b>{order['price']} ֏</b>\n"

        f"📌 Եղանակ՝ "
        f"<b>{method}</b>\n"

        f"📄 Տվյալ՝ "
        f"<code>{order['refund_data']}</code>",

        reply_markup=keyboard,
        parse_mode="HTML"
    )


# =========================================================
# ВОЗВРАТ — ВЫПОЛНЕН
# =========================================================

@dp.callback_query(F.data.startswith("refund_done:"))
async def refund_done(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:

        await callback.answer(
            "❌ Մուտքը արգելված է։",
            show_alert=True
        )

        return

    user_id = int(callback.data.split(":")[1])
    order = orders.get(user_id)

    if not order:

        await callback.answer(
            "❌ Պատվերը չի գտնվել։",
            show_alert=True
        )

        return

    order["status"] = "refunded"

    await bot.send_message(
        user_id,

        "✅ <b>Վերադարձը կատարված է։</b>\n\n"

        f"💰 Գումար՝ "
        f"<b>{order['price']} ֏</b>\n\n"

        "❤️ Շնորհակալություն Games Vault Shop-ից օգտվելու համար։",

        parse_mode="HTML"
    )

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except TelegramBadRequest:
        pass

    await callback.answer(
        "💰 Վերադարձը հաստատվեց"
    )


# =========================================================
# ВОЗВРАТ — ОТКЛОНЁН
# =========================================================

@dp.callback_query(F.data.startswith("refund_reject:"))
async def refund_reject(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:

        await callback.answer(
            "❌ Մուտքը արգելված է։",
            show_alert=True
        )

        return

    user_id = int(callback.data.split(":")[1])
    order = orders.get(user_id)

    if not order:

        await callback.answer(
            "❌ Պատվերը չի գտնվել։",
            show_alert=True
        )

        return

    order["status"] = "refund_rejected"

    await bot.send_message(
        user_id,

        "❌ <b>Վերադարձի հայտը մերժվել է։</b>\n\n"

        "Խնդրում ենք կապվել ադմինիստրատորի հետ։",

        parse_mode="HTML"
    )

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except TelegramBadRequest:
        pass

    await callback.answer(
        "❌ Վերադարձը մերժվեց"
    )


# =========================================================
# НАЗАД — ГЛАВНОЕ МЕНЮ
# =========================================================

@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):

    await callback.message.edit_text(
        "🎮 <b>GAMES VAULT SHOP</b> ❤️‍🔥\n\n"
        "Ընտրեք խաղը 👇",

        reply_markup=main_menu(),
        parse_mode="HTML"
    )

    await callback.answer()


# =========================================================
# ЗАПУСК
# =========================================================

async def main():

    print("🎮 Games Vault Shop բոտը միացված է!")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
