import os
import asyncio
import logging
from html import escape

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
ORDER_CHANNEL_ID = os.getenv("ORDER_CHANNEL_ID", "")
SUPPORT_CHANNEL_ID = os.getenv("SUPPORT_CHANNEL_ID", "")
TELCELL_NUMBER = os.getenv("TELCELL_NUMBER", "043055510")
PORT = int(os.getenv("PORT", "10000"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN չգտնվեց։ Ավելացրու BOT_TOKEN-ը Render-ի Environment Variables-ում։")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

users = {}
support_threads = {}

BRAWL_PASS_PRICES = {
    "brawl_pass": (2500, 3400),
    "brawl_pass_plus": (3400, 4800),
}


def get_user(user_id: int):
    if user_id not in users:
        users[user_id] = {
            "game": None,
            "product": None,
            "price": None,
            "username": None,
            "payment": None,
            "order_id": None,
            "support_waiting": False,
            "brawl_pass_type": None,
            "brawl_pass_waiting": False,
            "receipt_waiting_id": False,
            "receipt_order_message_id": None,
            "receipt_accepted": False,
        }
    return users[user_id]


CATALOG = {
    "roblox": {"name": "🎮 Roblox", "items": [
        ("40 Robux", 350), ("80 Robux", 650), ("120 Robux", 950),
        ("400 Robux", 2700), ("520 Robux", 3600), ("840 Robux", 4850),
        ("1,240 Robux", 7300), ("1,700 Robux", 8800), ("1,820 Robux", 9700),
        ("4,500 Robux", 21000), ("10,000 Robux", 40000), ("22,500 Robux", 88000),
    ]},
    "standoff2": {"name": "🔫 Standoff 2", "items": [
        ("100 Gold", 1000), ("200 Gold", 2000), ("300 Gold", 2900),
        ("500 Gold", 4000), ("600 Gold", 5100), ("700 Gold", 5800),
        ("1,000 Gold", 7100), ("1,500 Gold", 10300), ("3,000 Gold", 15800),
    ]},
    "brawlstars": {"name": "⭐ Brawl Stars", "items": [
        ("30 Gems", 750), ("80 Gems", 1500), ("170 Gems", 2800),
        ("360 Gems", 5100), ("950 Gems", 12800),
        ("Brawl Pass", 2500), ("Brawl Pass+", 3400),
        ("Прокачка Brawl Pass → Brawl Pass+", 1800), ("Pro Pass", 12300),
    ]},
    "pubg": {"name": "🪂 PUBG Mobile", "items": [
        ("33 UC + 🎁", 300), ("66 UC + 🎁", 500), ("99 UC + 🎁", 700),
        ("132 UC + 🎁", 1000), ("150 UC + 🎁", 1100), ("198 UC + 🎁", 1400),
        ("210 UC + 🎁", 1600), ("325 UC + 🎁", 2000), ("355 + 5 UC + 🎁", 2100),
        ("445 UC + 🎁", 2900), ("505 UC + 🎁", 3400), ("660 UC + 🎁", 4000),
        ("720 UC + 🎁", 4300), ("985 UC + 🎁", 6000), ("1,135 UC + 🎁", 7000),
        ("1,320 UC + 🎁", 7800), ("1,860 UC + 🎁", 10000), ("2,185 UC + 🎁", 11500),
    ]},
}


def fmt_price(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def main_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Roblox", callback_data="game:roblox"), InlineKeyboardButton(text="🔫 Standoff 2", callback_data="game:standoff2")],
        [InlineKeyboardButton(text="⭐ Brawl Stars", callback_data="game:brawlstars"), InlineKeyboardButton(text="🪂 PUBG Mobile", callback_data="game:pubg")],
        [InlineKeyboardButton(text="📩 Կապվեք մեզ հետ", callback_data="contact:open")],
    ])


def game_keyboard(game: str):
    buttons = []
    for index, (name, price) in enumerate(CATALOG[game]["items"]):
        if game == "brawlstars" and name == "Brawl Pass":
            text = "🎫 Brawl Pass — սկսած 2 500 ֏"
        elif game == "brawlstars" and name == "Brawl Pass+":
            text = "⭐ Brawl Pass+ — սկսած 3 400 ֏"
        else:
            text = f"⚡ {name} — {fmt_price(price)} ֏"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"product:{game}:{index}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def product_keyboard(game: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Գնել", callback_data="buy:confirm")],
        [InlineKeyboardButton(text="⬅️ Հետ", callback_data=f"back:game:{game}")],
    ])


def payment_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Վճարել քարտով", callback_data="payment:card")],
        [InlineKeyboardButton(text="💵 Վճարել կանխիկ", callback_data="payment:cash")],
        [InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:product")],
    ])


def receipt_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧾 Ուղարկել չեկի նկարը", callback_data="payment:done")],
        [InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:payment")],
    ])


def pass_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:game:brawlstars")]])


def admin_pass_price_keyboard(user_id: int, pass_type: str):
    low, high = BRAWL_PASS_PRICES[pass_type]
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"💰 {fmt_price(low)} ֏", callback_data=f"passprice:{user_id}:{low}"),
        InlineKeyboardButton(text=f"💰 {fmt_price(high)} ֏", callback_data=f"passprice:{user_id}:{high}"),
    ]])


def admin_receipt_keyboard(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Отклонить чек", callback_data=f"receipt:reject:{user_id}"),
            InlineKeyboardButton(text="✅ Принять чек", callback_data=f"receipt:accept:{user_id}"),
        ],
        [
            InlineKeyboardButton(text="📦 Подтвердить заказ", callback_data=f"receipt:confirm:{user_id}"),
            InlineKeyboardButton(text="↩️ Назад", callback_data=f"receipt:back:{user_id}"),
        ],
    ])


def main_text():
    return (
        "💎 <b>Games Vault Shop</b> ❤️‍🔥\n\n"
        "💎 <b>Games Vault Shop-ում՝ միշտ VAULT-Ա!</b>\n\n"
        "🎮 Ընտրիր խաղը և տես հասանելի ապրանքները։\n\n"
        "⚡ Արագ պատվեր\n"
        "💳 Telcell Wallet\n"
        "🧾 Չեկի ստուգում\n"
        "📩 Աջակցություն և կապ\n\n"
        "❗ Գնումից առաջ ստուգիր ապրանքի տեսակը և գինը։"
    )


def game_text(game: str):
    return f"{CATALOG[game]['name']}\n\n📦 Ընտրիր անհրաժեշտ ապրանքը։\n\n💰 Բոլոր գները նշված են դրամով։"


def order_caption(user_id: int, user: dict, status: str):
    username = user.get("username") or "չկա"
    product = user.get("product") or "չկա"
    game = user.get("game")
    game_name = CATALOG.get(game, {}).get("name", "չկա") if game else "չկա"
    price = user.get("price")
    price_text = f"{fmt_price(price)} ֏" if isinstance(price, int) else "սահմանված չէ"
    order_id = user.get("order_id") or str(user_id)
    return (
        "🧾 <b>ՊԱՏՎԵՐ</b>\n\n"
        f"👤 Username՝ @{escape(username)}\n"
        f"🆔 ID՝ <code>{user_id}</code>\n"
        f"🎮 Խաղ՝ <b>{escape(game_name)}</b>\n"
        f"📦 Ապրանք՝ <b>{escape(product)}</b>\n"
        f"💰 Գումար՝ <b>{price_text}</b>\n"
        f"🔖 Պատվեր՝ <code>{escape(order_id)}</code>\n\n{status}"
    )


def brawl_pass_prompt(pass_type: str):
    title = "🎫 Brawl Pass" if pass_type == "brawl_pass" else "⭐ Brawl Pass+"
    low, high = BRAWL_PASS_PRICES[pass_type]
    return (
        f"{title}\n\n"
        "📸 <b>Ուղարկիր screenshot-ը, որտեղ հստակ երևում է քո Pass-ի գինը։</b>\n\n"
        "👨‍💼 Screenshot-ը կստանա ադմինը և ինքը կընտրի ճիշտ գինը։\n\n"
        f"💰 Հնարավոր գներ՝ <b>{fmt_price(low)} ֏</b> / <b>{fmt_price(high)} ֏</b>\n\n"
        "⚠️ Կարևոր է հենց քո ընտրած Pass-ի գինը։"
    )


def cash_payment_text(user: dict):
    product = escape(user.get("product") or "Պատվեր")
    price = user.get("price") or 0
    return (
        "💎 <b>Games Vault Shop-ից Բարևներ</b> ❤️‍🔥\n\n"
        "💵 <b>Վճարման քայլերը՝</b>\n\n"
        "1️⃣ Telcell տերմինալում ընտրեք <b>«Telcell Wallet»</b> և մուտքագրեք հեռախոսահամարը՝ "
        f"<code>{escape(TELCELL_NUMBER)}</code> 📱\n\n"
        f"2️⃣ Կատարեք վճարումը՝ <b>{fmt_price(price)} ֏</b> 💰\n\n"
        "3️⃣ 🧾 Վճարումից հետո նկարեք չեկը և ուղարկեք մեզ։\n\n"
        "4️⃣ 🆔 Այնուհետև ուղարկեք ձեր ID-ն։\n\n"
        "⚡ Վճարումը ստանալուց և ստուգելուց հետո 1–2 րոպեում կստանաք ձեր Դոնաթը։ ❤️‍🔥\n\n"
        f"📦 Ապրանք՝ <b>{product}</b>"
    )


@dp.message(CommandStart())
async def cmd_start(message: Message):
    user = get_user(message.from_user.id)
    user["username"] = message.from_user.username
    user["support_waiting"] = False
    user["brawl_pass_waiting"] = False
    user["receipt_waiting_id"] = False
    await message.answer(main_text(), reply_markup=main_menu_keyboard(), parse_mode="HTML")


@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    await cmd_start(message)


@dp.callback_query(F.data == "contact:open")
async def contact_open(callback: CallbackQuery):
    if not SUPPORT_CHANNEL_ID:
        await callback.answer("📩 Աջակցության ալիքը դեռ կարգավորված չէ։", show_alert=True)
        return
    user = get_user(callback.from_user.id)
    user["support_waiting"] = True
    await callback.message.edit_text(
        "📩 <b>Կապ Games Vault Shop-ի հետ</b>\n\nԳրիր քո հարցը, խնդիրը կամ կարծիքը հաջորդ հաղորդագրությամբ։\nՄենք կստանանք այն և կպատասխանենք։",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:main")]]),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.message(F.text)
async def text_router(message: Message):
    user = get_user(message.from_user.id)
    user["username"] = message.from_user.username

    if user.get("receipt_waiting_id"):
        client_id = message.text.strip()
        if not client_id:
            await message.answer("🆔 Ուղարկիր քո ID-ն։")
            return
        if not ORDER_CHANNEL_ID:
            await message.answer("❌ Պատվերների ալիքը կարգավորված չէ։")
            return

        user["receipt_waiting_id"] = False
        user["payment"] = "receipt_received"
        order_id = user.get("order_id") or f"{message.from_user.id}-{message.message_id}"
        user["order_id"] = order_id

        await bot.send_message(
            chat_id=ORDER_CHANNEL_ID,
            text=(
                "🆔 <b>ՀԱՃԱԽՈՐԴԻ ID</b>\n\n"
                f"👤 Username՝ @{escape(message.from_user.username or 'չկա')}\n"
                f"🆔 ID՝ <code>{escape(client_id)}</code>\n"
                f"🔖 Պատվեր՝ <code>{escape(order_id)}</code>"
            ),
            parse_mode="HTML",
        )

        receipt_message_id = user.get("receipt_order_message_id")
        if receipt_message_id:
            try:
                await bot.edit_message_reply_markup(
                    chat_id=ORDER_CHANNEL_ID,
                    message_id=receipt_message_id,
                    reply_markup=admin_receipt_keyboard(message.from_user.id),
                )
            except Exception:
                logging.exception("Could not add admin receipt buttons")

        await message.answer(
            "✅ <b>Ամբողջ տվյալները ստացվեցին։</b>\n\n⚡ Վճարումը ստուգվում է։",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        return

    if not user.get("support_waiting") or not SUPPORT_CHANNEL_ID:
        return

    username = message.from_user.username or "չկա"
    sent = await bot.send_message(
        chat_id=SUPPORT_CHANNEL_ID,
        text=(
            "📩 <b>ՆՈՐ ՀԱՂՈՐԴԱԳՐՈՒԹՅՈՒՆ</b>\n\n"
            f"👤 Username՝ @{escape(username)}\n"
            f"🆔 ID՝ <code>{message.from_user.id}</code>\n\n"
            f"💬 {escape(message.text)}"
        ),
        parse_mode="HTML",
    )
    support_threads[sent.message_id] = message.from_user.id
    user["support_waiting"] = False
    await message.answer("✅ Հաղորդագրությունը ստացվեց։ Մենք կպատասխանենք շուտով։", reply_markup=main_menu_keyboard())


@dp.callback_query(F.data.startswith("game:"))
async def choose_game(callback: CallbackQuery):
    game = callback.data.split(":", 1)[1]
    if game not in CATALOG:
        await callback.answer("❌ Սխալ խաղ։", show_alert=True)
        return
    user = get_user(callback.from_user.id)
    user.update({
        "game": game, "product": None, "price": None, "payment": None,
        "order_id": None, "brawl_pass_type": None, "brawl_pass_waiting": False,
        "receipt_waiting_id": False, "receipt_order_message_id": None,
        "receipt_accepted": False,
    })
    await callback.message.edit_text(game_text(game), reply_markup=game_keyboard(game), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data.startswith("product:"))
async def choose_product(callback: CallbackQuery):
    _, game, index = callback.data.split(":")
    if game not in CATALOG:
        await callback.answer("❌ Սխալ խաղ։", show_alert=True)
        return
    try:
        item = CATALOG[game]["items"][int(index)]
    except (ValueError, IndexError):
        await callback.answer("❌ Սխալ ապրանք։", show_alert=True)
        return

    user = get_user(callback.from_user.id)
    user.update({
        "game": game, "product": item[0], "price": item[1],
        "username": callback.from_user.username, "payment": None,
        "order_id": None, "receipt_order_message_id": None,
        "receipt_accepted": False,
    })

    if game == "brawlstars" and item[0] in {"Brawl Pass", "Brawl Pass+"}:
        user["brawl_pass_type"] = "brawl_pass" if item[0] == "Brawl Pass" else "brawl_pass_plus"
        user["brawl_pass_waiting"] = True
        user["price"] = None
        await callback.message.edit_text(brawl_pass_prompt(user["brawl_pass_type"]), reply_markup=pass_back_keyboard(), parse_mode="HTML")
        await callback.answer()
        return

    text = (
        "🛒 <b>Ձեր ընտրությունը</b>\n\n"
        f"🎮 Խաղ՝ <b>{escape(CATALOG[game]['name'])}</b>\n"
        f"📦 Ապրանք՝ <b>{escape(item[0])}</b>\n"
        f"💰 Գին՝ <b>{fmt_price(item[1])} ֏</b>\n\nՇարունակե՞լ պատվերը։"
    )
    await callback.message.edit_text(text, reply_markup=product_keyboard(game), parse_mode="HTML")
    await callback.answer()


@dp.message(F.photo)
async def photo_router(message: Message):
    user = get_user(message.from_user.id)

    if user.get("brawl_pass_waiting") and user.get("brawl_pass_type"):
        if not ORDER_CHANNEL_ID:
            await message.answer("❌ Պատվերների ալիքը կարգավորված չէ։")
            return
        user["brawl_pass_waiting"] = False
        user["order_id"] = f"{message.from_user.id}-{message.message_id}"
        low, high = BRAWL_PASS_PRICES[user["brawl_pass_type"]]
        pass_name = "Brawl Pass" if user["brawl_pass_type"] == "brawl_pass" else "Brawl Pass+"
        caption = (
            "🎫 <b>BRAWL PASS — ԸՆՏՐԻՐ ԳԻՆԸ</b>\n\n"
            f"👤 Username՝ @{escape(message.from_user.username or 'չկա')}\n"
            f"🆔 ID՝ <code>{message.from_user.id}</code>\n"
            f"📦 Pass՝ <b>{escape(pass_name)}</b>\n"
            f"💰 Հնարավոր գներ՝ <b>{fmt_price(low)} ֏ / {fmt_price(high)} ֏</b>\n"
            f"🔖 Պատվեր՝ <code>{escape(user['order_id'])}</code>\n\n"
            "📸 Ստուգիր screenshot-ը և ընտրիր ճիշտ գինը։"
        )
        await bot.send_photo(
            chat_id=ORDER_CHANNEL_ID,
            photo=message.photo[-1].file_id,
            caption=caption,
            parse_mode="HTML",
            reply_markup=admin_pass_price_keyboard(message.from_user.id, user["brawl_pass_type"]),
        )
        await message.answer("✅ <b>Screenshot-ը ստացվեց։</b>\n\n👨‍💼 Ադմինը կստուգի գինը և կընտրի ճիշտ տարբերակը։", parse_mode="HTML")
        return

    if user.get("support_waiting") and SUPPORT_CHANNEL_ID:
        sent = await bot.send_photo(
            chat_id=SUPPORT_CHANNEL_ID,
            photo=message.photo[-1].file_id,
            caption=(
                "📷 <b>ՆՈՐ ՀԱՂՈՐԴԱԳՐՈՒԹՅՈՒՆ</b>\n\n"
                f"👤 Username՝ @{escape(message.from_user.username or 'չկա')}\n"
                f"🆔 ID՝ <code>{message.from_user.id}</code>"
            ),
            parse_mode="HTML",
        )
        support_threads[sent.message_id] = message.from_user.id
        user["support_waiting"] = False
        await message.answer("✅ Նկարը ստացվեց։ Մենք կպատասխանենք շուտով։", reply_markup=main_menu_keyboard())
        return

    if user.get("payment") != "receipt_pending":
        return
    if not ORDER_CHANNEL_ID:
        await message.answer("❌ Պատվերների ալիքը կարգավորված չէ։")
        return

    user["payment"] = "awaiting_id"
    user["receipt_waiting_id"] = True
    user["order_id"] = user.get("order_id") or f"{message.from_user.id}-{message.message_id}"
    caption = order_caption(message.from_user.id, user, "⏳ Չեկը ստացվեց։ Սպասում ենք հաճախորդի ID-ին։")
    sent = await bot.send_photo(chat_id=ORDER_CHANNEL_ID, photo=message.photo[-1].file_id, caption=caption, parse_mode="HTML")
    user["receipt_order_message_id"] = sent.message_id
    await message.answer("✅ <b>Չեկը ստացվեց։</b>\n\n🆔 Այժմ ուղարկիր քո ID-ն։", parse_mode="HTML")


@dp.callback_query(F.data.startswith("passprice:"))
async def admin_choose_pass_price(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Այս կոճակը միայն ադմինի համար է։", show_alert=True)
        return
    try:
        _, user_id_raw, price_raw = callback.data.split(":")
        user_id, price = int(user_id_raw), int(price_raw)
    except (ValueError, IndexError):
        await callback.answer("❌ Սխալ տվյալներ։", show_alert=True)
        return
    user = get_user(user_id)
    pass_type = user.get("brawl_pass_type")
    if not pass_type:
        await callback.answer("❌ Պատվերը չի գտնվել։", show_alert=True)
        return
    low, high = BRAWL_PASS_PRICES[pass_type]
    if price not in {low, high}:
        await callback.answer("❌ Այս գինը չի համապատասխանում Pass-ին։", show_alert=True)
        return
    user["price"] = price
    pass_name = "Brawl Pass" if pass_type == "brawl_pass" else "Brawl Pass+"
    await callback.message.edit_caption(
        caption=(f"🎫 <b>BRAWL PASS — ԳԻՆԸ ՀԱՍՏԱՏՎԱԾ Է</b>\n\n📦 Pass՝ <b>{pass_name}</b>\n💰 Ընտրված գին՝ <b>{fmt_price(price)} ֏</b>\n🆔 ID՝ <code>{user_id}</code>\n\n✅ Ադմինը ընտրեց գինը։"),
        reply_markup=None,
        parse_mode="HTML",
    )
    await bot.send_message(chat_id=user_id, text=f"✅ <b>Գինը հաստատվեց</b>\n\n📦 {pass_name}\n💰 Գին՝ <b>{fmt_price(price)} ֏</b>\n\nՇարունակե՞լ պատվերը։", reply_markup=product_keyboard("brawlstars"), parse_mode="HTML")
    await callback.answer(f"Գինը՝ {fmt_price(price)} ֏")


@dp.callback_query(F.data == "buy:confirm")
async def buy_confirm(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user.get("game") or not user.get("product"):
        await callback.answer("❌ Նախ ընտրիր ապրանքը։", show_alert=True)
        return
    if user.get("brawl_pass_type") and not user.get("price"):
        await callback.answer("⏳ Սպասիր, որ ադմինը հաստատի Brawl Pass-ի գինը։", show_alert=True)
        return
    await callback.message.edit_text(
        "💳 <b>Ընտրիր վճարման եղանակը</b>\n\n"
        f"📦 Ապրանք՝ <b>{escape(user['product'])}</b>\n"
        f"💰 Գումար՝ <b>{fmt_price(user['price'])} ֏</b>\n\nԸնտրիր՝ ինչպես ես ցանկանում վճարել։",
        reply_markup=payment_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.callback_query(F.data == "payment:card")
async def payment_card(callback: CallbackQuery):
    await callback.answer("💳 Քարտով վճարումը դեռ հասանելի չէ։", show_alert=True)


@dp.callback_query(F.data == "payment:cash")
async def payment_cash(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user.get("product") or not user.get("price"):
        await callback.answer("❌ Պատվերը չի գտնվել։", show_alert=True)
        return
    await callback.message.edit_text(cash_payment_text(user), reply_markup=receipt_keyboard(), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "payment:done")
async def payment_done(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user.get("product") or not user.get("price"):
        await callback.answer("❌ Նախ հաստատեք ապրանքի գինը։", show_alert=True)
        return
    user["payment"] = "receipt_pending"
    user["receipt_waiting_id"] = False
    await callback.message.edit_text(
        "🧾 <b>Ուղարկիր չեկի նկարը</b>\n\nՈւղարկիր վճարման չեկի լուսանկարը այս հաղորդագրությունից հետո։",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:payment")]]),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("receipt:"))
async def admin_receipt_actions(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Այս կոճակը միայն ադմինի համար է։", show_alert=True)
        return
    try:
        _, action, user_id_raw = callback.data.split(":")
        user_id = int(user_id_raw)
    except (ValueError, IndexError):
        await callback.answer("❌ Սխալ տվյալներ։", show_alert=True)
        return

    user = get_user(user_id)
    product = escape(user.get("product") or "Պատվեր")
    price = user.get("price") or 0

    if action == "reject":
        user["payment"] = "receipt_rejected"
        user["receipt_accepted"] = False
        await bot.send_message(chat_id=user_id, text="❌ <b>Չեկը մերժվեց։</b>\n\nԽնդրում ենք ուղարկել ճիշտ վճարման չեկ։", parse_mode="HTML")
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("Չեկը մերժվեց։")
        return

    if action == "accept":
        user["receipt_accepted"] = True
        user["payment"] = "receipt_accepted"
        await bot.send_message(chat_id=user_id, text="✅ <b>Չեկը ընդունվեց։</b>\n\n⏳ Սպասեք պատվերի վերջնական հաստատմանը։", parse_mode="HTML")
        await callback.answer("✅ Չեկը ընդունված է։")
        return

    if action == "confirm":
        if not user.get("receipt_accepted"):
            await callback.answer("⚠️ Сначала нажми «Принять чек». ", show_alert=True)
            return
        user["payment"] = "completed"
        await bot.send_message(
            chat_id=user_id,
            text=(
                "🎉 <b>Պատվերը հաստատվեց։</b>\n\n"
                f"📦 Ապրանք՝ <b>{product}</b>\n"
                f"💰 Գումար՝ <b>{fmt_price(price)} ֏</b>\n\n"
                "⚡ Ձեր Դոնաթը կստանաք 1–2 րոպեում։ ❤️‍🔥"
            ),
            parse_mode="HTML",
        )
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("📦 Պատվերը հաստատվեց։")
        return

    if action == "back":
        await callback.answer("↩️ Վերադարձ։")
        return

    await callback.answer("❌ Անհայտ գործողություն։", show_alert=True)


@dp.callback_query(F.data == "back:main")
async def back_main(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    user["support_waiting"] = False
    user["brawl_pass_waiting"] = False
    user["receipt_waiting_id"] = False
    await callback.message.edit_text(main_text(), reply_markup=main_menu_keyboard(), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data.startswith("back:game:"))
async def back_game(callback: CallbackQuery):
    game = callback.data.split(":", 2)[2]
    if game not in CATALOG:
        await callback.answer("❌ Սխալ խաղ։", show_alert=True)
        return
    user = get_user(callback.from_user.id)
    user["brawl_pass_waiting"] = False
    user["receipt_waiting_id"] = False
    await callback.message.edit_text(game_text(game), reply_markup=game_keyboard(game), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "back:product")
async def back_product(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    game = user.get("game")
    if not game or not user.get("product"):
        await callback.message.edit_text(main_text(), reply_markup=main_menu_keyboard(), parse_mode="HTML")
        await callback.answer()
        return
    if user.get("brawl_pass_type") and not user.get("price"):
        await callback.message.edit_text(brawl_pass_prompt(user["brawl_pass_type"]), reply_markup=pass_back_keyboard(), parse_mode="HTML")
        await callback.answer()
        return
    text = (
        "🛒 <b>Ձեր ընտրությունը</b>\n\n"
        f"🎮 Խաղ՝ <b>{escape(CATALOG[game]['name'])}</b>\n"
        f"📦 Ապրանք՝ <b>{escape(user['product'])}</b>\n"
        f"💰 Գին՝ <b>{fmt_price(user['price'])} ֏</b>\n\nՇարունակե՞լ պատվերը։"
    )
    await callback.message.edit_text(text, reply_markup=product_keyboard(game), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "back:payment")
async def back_payment(callback: CallbackQuery):
    await buy_confirm(callback)


async def health(request):
    return web.Response(text="Games Vault Shop is running!")


async def main():
    logging.info("Games Vault Shop bot starting...")
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info("HTTP health server started on 0.0.0.0:%s", PORT)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
