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

CATALOG = {
    "roblox": {"name": "🎮 Roblox", "items": [("40 Robux", 350), ("80 Robux", 650), ("120 Robux", 950), ("400 Robux", 2700), ("520 Robux", 3600), ("840 Robux", 4850), ("1,240 Robux", 7300), ("1,700 Robux", 8800), ("1,820 Robux", 9700), ("4,500 Robux", 21000), ("10,000 Robux", 40000), ("22,500 Robux", 88000)]},
    "standoff2": {"name": "🔫 Standoff 2", "items": [("100 Gold", 1000), ("200 Gold", 2000), ("300 Gold", 2900), ("500 Gold", 4000), ("600 Gold", 5100), ("700 Gold", 5800), ("1,000 Gold", 7100), ("1,500 Gold", 10300), ("3,000 Gold", 15800)]},
    "brawlstars": {"name": "⭐ Brawl Stars", "items": [("30 Gems", 750), ("80 Gems", 1500), ("170 Gems", 2800), ("360 Gems", 5100), ("950 Gems", 12800), ("Brawl Pass", 2500), ("Brawl Pass+", 3400), ("Прокачка Brawl Pass → Brawl Pass+", 1800), ("Pro Pass", 12300)]},
    "pubg": {"name": "🪂 PUBG Mobile", "items": [("33 UC + 🎁", 300), ("66 UC + 🎁", 500), ("99 UC + 🎁", 700), ("132 UC + 🎁", 1000), ("150 UC + 🎁", 1100), ("198 UC + 🎁", 1400), ("210 UC + 🎁", 1600), ("325 UC + 🎁", 2000), ("355 + 5 UC + 🎁", 2100), ("445 UC + 🎁", 2900), ("505 UC + 🎁", 3400), ("660 UC + 🎁", 4000), ("720 UC + 🎁", 4300), ("985 UC + 🎁", 6000), ("1,135 UC + 🎁", 7000), ("1,320 UC + 🎁", 7800), ("1,860 UC + 🎁", 10000), ("2,185 UC + 🎁", 11500)]},
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
            "refund_waiting": False,
            "refund_method": None,
            "refund_operator": None,
            "refund_details_ready": False,
            "refund_complete": False,
        }
    return users[user_id]


def reset_refund_state(user: dict):
    user["refund_waiting"] = False
    user["refund_method"] = None
    user["refund_operator"] = None
    user["refund_details_ready"] = False
    user["refund_complete"] = False


def fmt_price(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def main_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎮 Roblox", callback_data="game:roblox"), InlineKeyboardButton(text="🔫 Standoff 2", callback_data="game:standoff2")], [InlineKeyboardButton(text="⭐ Brawl Stars", callback_data="game:brawlstars"), InlineKeyboardButton(text="🪂 PUBG Mobile", callback_data="game:pubg")], [InlineKeyboardButton(text="📩 Կապվեք մեզ հետ", callback_data="contact:open")]])


def game_keyboard(game: str):
    buttons = []
    for index, (name, price) in enumerate(CATALOG[game]["items"]):
        if game == "brawlstars" and name == "Brawl Pass":
            text = "🎫 Brawl Pass — 2 500 / 3 400 ֏"
        elif game == "brawlstars" and name == "Brawl Pass+":
            text = "⭐ Brawl Pass+ — 3 400 / 4 800 ֏"
        else:
            text = f"⚡ {name} — {fmt_price(price)} ֏"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"product:{game}:{index}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def product_keyboard(game: str):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Գնել", callback_data="buy:confirm")], [InlineKeyboardButton(text="⬅️ Հետ", callback_data=f"back:game:{game}")]])


def payment_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💳 Վճարել քարտով", callback_data="payment:card")], [InlineKeyboardButton(text="💵 Վճարել կանխիկ", callback_data="payment:cash")], [InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:product")]])


def receipt_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🧾 Ուղարկել չեկի նկարը", callback_data="payment:done")], [InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:payment")]])


def pass_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:game:brawlstars")]])


def admin_pass_price_keyboard(user_id: int, pass_type: str):
    low, high = BRAWL_PASS_PRICES[pass_type]
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"💰 {fmt_price(low)} ֏", callback_data=f"passprice:{user_id}:{low}"), InlineKeyboardButton(text=f"💰 {fmt_price(high)} ֏", callback_data=f"passprice:{user_id}:{high}")]])


def admin_receipt_keyboard(user_id: int, receipt_accepted: bool = False, refund_details_ready: bool = False):
    rows = [
        [InlineKeyboardButton(text="❌ Մերժել չեկը", callback_data=f"receipt:reject:{user_id}"), InlineKeyboardButton(text="✅ Հաստատել չեկը", callback_data=f"receipt:accept:{user_id}")],
        [InlineKeyboardButton(text="💸 Տրամադրել հետ գումարը", callback_data=f"receipt:refund:{user_id}")],
    ]
    if receipt_accepted:
        rows.append([InlineKeyboardButton(text="📦 Հաստատել պատվերը", callback_data=f"receipt:confirm:{user_id}")])
    if refund_details_ready:
        rows.append([InlineKeyboardButton(text="✅ Հետ գումարի վերադարձը ավարտված է", callback_data=f"receipt:refund_complete:{user_id}")])
    rows.append([InlineKeyboardButton(text="↩️ Հետ", callback_data=f"receipt:back:{user_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def refund_client_method_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Հեռախոսահամարին", callback_data="refundclient:phone")],
        [InlineKeyboardButton(text="💳 Քարտին", callback_data="refundclient:card")],
    ])


def refund_operators_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Viva", callback_data="refundclient:operator:Viva")],
        [InlineKeyboardButton(text="📞 Team Telecom Armenia", callback_data="refundclient:operator:Team Telecom Armenia")],
        [InlineKeyboardButton(text="📞 Ucom", callback_data="refundclient:operator:Ucom")],
        [InlineKeyboardButton(text="↩️ Հետ", callback_data="refundclient:back")],
    ])


def refund_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ Հետ", callback_data="refundclient:back")]])


def main_text():
    return ("💎 <b>Games Vault Shop</b> ❤️‍🔥\n\n" "💎 <b>Games Vault Shop-ում՝ միշտ VAULT-Ա!</b>\n\n" "🎮 Ընտրիր խաղը և տես հասանելի ապրանքները։\n\n" "⚡ Արագ պատվեր\n" "💳 Telcell Wallet\n" "🧾 Չեկի ստուգում\n" "📩 Աջակցություն և կապ\n\n" "❗ Գնումից առաջ ստուգիր ապրանքի տեսակը և գինը։")


def game_text(game: str):
    return f"{CATALOG[game]['name']}\n\n📦 Ընտրիր անհրաժեշտ ապրանքը։\n\n💰 Բոլոր գները նշված են դրամով."


def order_caption(user_id: int, user: dict, status: str):
    username = user.get("username") or "չկա"
    product = user.get("product") or "չկա"
    game = user.get("game")
    game_name = CATALOG.get(game, {}).get("name", "չկա") if game else "չկա"
    price = user.get("price")
    price_text = f"{fmt_price(price)} ֏" if isinstance(price, int) else "սահմանված չէ"
    order_id = user.get("order_id") or str(user_id)
    return ("🧾 <b>ՊԱՏՎԵՐ</b>\n\n" f"👤 Username՝ @{escape(username)}\n" f"🆔 ID՝ <code>{user_id}</code>\n" f"🎮 Խաղ՝ <b>{escape(game_name)}</b>\n" f"📦 Ապրանք՝ <b>{escape(product)}</b>\n" f"💰 Գումար՝ <b>{price_text}</b>\n" f"🔖 Պատվեր՝ <code>{escape(order_id)}</code>\n\n{status}")


def brawl_pass_prompt(pass_type: str):
    title = "🎫 Brawl Pass" if pass_type == "brawl_pass" else "⭐ Brawl Pass+"
    low, high = BRAWL_PASS_PRICES[pass_type]
    return (f"{title}\n\n" "📸 <b>Ուղարկիր screenshot-ը, որտեղ հստակ երևում է քո Pass-ի գինը։</b>\n\n" "👨‍💼 Screenshot-ը կստանա ադմինը և ինքը կընտրի ճիշտ գինը։\n\n" f"💰 Հնարավոր գներ՝ <b>{fmt_price(low)} ֏</b> / <b>{fmt_price(high)} ֏</b>\n\n" "⚠️ Կարևոր է հենց քո ընտրած Pass-ի գինը։")


def cash_payment_text(user: dict):
    product = escape(user.get("product") or "Պատվեր")
    price = user.get("price") or 0
    return ("💎 <b>Games Vault Shop-ից Բարևներ</b> ❤️‍🔥\n\n" "💵 <b>Վճարման քայլերը՝</b>\n\n" "1️⃣ Telcell տերմինալում ընտրեք <b>«Telcell Wallet»</b> և մուտքագրեք հեռախոսահամարը՝ " f"<code>{escape(TELCELL_NUMBER)}</code> 📱\n\n" f"2️⃣ Կատարեք վճարումը՝ <b>{fmt_price(price)} ֏</b> 💰\n\n" "3️⃣ 🧾 Վճարումից հետո նկարեք չեկը և ուղարկեք մեզ։\n\n" "4️⃣ 🆔 Այնուհետև տրամադրեք ձեր ID-ն։\n\n" "⚡ <b>1–2 րոպեում ստանում եք ձեր Դոնաթը։</b> ✅❤️‍🔥\n\n" f"📦 Պատվեր՝ <b>{product}</b>")


async def notify_user(user_id: int, text: str, reply_markup=None):
    try:
        await bot.send_message(user_id, text, parse_mode="HTML", reply_markup=reply_markup)
    except Exception:
        logging.exception("Failed to notify user %s", user_id)


async def update_admin_receipt_message(user_id: int, status: str):
    user = get_user(user_id)
    message_id = user.get("receipt_order_message_id")
    if not message_id or not ORDER_CHANNEL_ID:
        return
    try:
        await bot.edit_message_caption(
            chat_id=ORDER_CHANNEL_ID,
            message_id=message_id,
            caption=order_caption(user_id, user, status),
            parse_mode="HTML",
            reply_markup=admin_receipt_keyboard(
                user_id,
                user.get("receipt_accepted", False),
                user.get("refund_details_ready", False),
            ),
        )
    except Exception:
        logging.exception("Failed to update admin receipt message")


@dp.message(CommandStart())
async def cmd_start(message: Message):
    user = get_user(message.from_user.id)
    user["username"] = message.from_user.username
    user["support_waiting"] = False
    await message.answer(main_text(), reply_markup=main_menu_keyboard(), parse_mode="HTML")


@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    user = get_user(message.from_user.id)
    user["support_waiting"] = False
    await message.answer(main_text(), reply_markup=main_menu_keyboard(), parse_mode="HTML")


@dp.callback_query(F.data == "contact:open")
async def contact_open(callback: CallbackQuery):
    if not SUPPORT_CHANNEL_ID:
        await callback.answer("📩 Աջակցության ալիքը դեռ կարգավորված չէ։", show_alert=True)
        return
    user = get_user(callback.from_user.id)
    user["support_waiting"] = True
    await callback.message.edit_text("📩 <b>Կապ Games Vault Shop-ի հետ</b>\n\nԳրիր քո հարցը, խնդիրը կամ կարծիքը հաջորդ հաղորդագրությամբ։\nՄենք կստանանք այն և կպատասխանենք։", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:main")]]), parse_mode="HTML")
    await callback.answer()


@dp.message(F.text)
async def text_router(message: Message):
    user = get_user(message.from_user.id)

    if user.get("refund_waiting") and user.get("refund_method") == "phone" and user.get("refund_operator"):
        phone = message.text.strip()
        if not phone:
            await message.answer("⚠️ Մուտքագրիր ճիշտ հեռախոսահամարը։")
            return
        user["refund_details_ready"] = True
        user["refund_waiting"] = False
        user["refund_phone"] = phone
        await notify_user(message.from_user.id, "✅ <b>Հեռախոսահամարը ստացվեց։</b>\n\n💸 Գումարի վերադարձի տվյալները ուղարկվեցին ադմինին։\n⏳ Սպասիր վերադարձի ավարտին։", reply_markup=main_menu_keyboard())
        await bot.send_message(
            ORDER_CHANNEL_ID,
            "💸 <b>ՎԵՐԱԴԱՐՁԻ ՏՎՅԱԼՆԵՐ</b>\n\n"
            f"👤 Username՝ @{escape(user.get('username') or 'չկա')}\n"
            f"🆔 ID՝ <code>{message.from_user.id}</code>\n"
            f"📦 Ապրանք՝ <b>{escape(user.get('product') or 'չկա')}</b>\n"
            f"💰 Գումար՝ <b>{fmt_price(user.get('price') or 0)} ֏</b>\n"
            "💔 Դոնաթը չի հաջողվել։\n"
            f"📱 Եղանակ՝ <b>Հեռախոսահամարին</b>\n"
            f"📞 Օպերատոր՝ <b>{escape(user['refund_operator'])}</b>\n"
            f"☎️ Հեռախոս՝ <code>{escape(phone)}</code>",
            parse_mode="HTML",
        )
        await update_admin_receipt_message(message.from_user.id, "⏳ <b>Սպասում է հետ գումարի վերադարձին։</b>\n📱 Հեռախոսահամարը և օպերատորը ստացվել են։")
        return

    if user.get("refund_waiting") and user.get("refund_method") == "card":
        card_data = message.text.strip()
        if not card_data:
            await message.answer("⚠️ Մուտքագրիր քարտի տվյալները։")
            return
        user["refund_details_ready"] = True
        user["refund_waiting"] = False
        user["refund_card"] = card_data
        await notify_user(message.from_user.id, "✅ <b>Քարտի տվյալները ստացվեցին։</b>\n\n💸 Գումարի վերադարձի տվյալները ուղարկվեցին ադմինին։\n⏳ Սպասիր վերադարձի ավարտին։", reply_markup=main_menu_keyboard())
        await bot.send_message(
            ORDER_CHANNEL_ID,
            "💸 <b>ՎԵՐԱԴԱՐՁԻ ՏՎՅԱԼՆԵՐ</b>\n\n"
            f"👤 Username՝ @{escape(user.get('username') or 'չկա')}\n"
            f"🆔 ID՝ <code>{message.from_user.id}</code>\n"
            f"📦 Ապրանք՝ <b>{escape(user.get('product') or 'չկա')}</b>\n"
            f"💰 Գումար՝ <b>{fmt_price(user.get('price') or 0)} ֏</b>\n"
            "💔 Դոնաթը չի հաջողվել։\n"
            "💳 Եղանակ՝ <b>Քարտին</b>\n"
            f"💳 Քարտի տվյալներ՝ <code>{escape(card_data)}</code>",
            parse_mode="HTML",
        )
        await update_admin_receipt_message(message.from_user.id, "⏳ <b>Սպասում է հետ գումարի վերադարձին։</b>\n💳 Քարտի տվյալները ստացվել են։")
        return

    if user.get("receipt_waiting_id"):
        if not user.get("receipt_order_message_id"):
            user["receipt_waiting_id"] = False
            return
        user["receipt_waiting_id"] = False
        try:
            await bot.send_message(ORDER_CHANNEL_ID, "🆔 <b>ID ստացվեց</b>\n\n" f"👤 User ID՝ <code>{message.from_user.id}</code>\n" f"🎮 Խաղ՝ <b>{escape(CATALOG.get(user.get('game'), {}).get('name', 'չկա'))}</b>\n" f"📦 Ապրանք՝ <b>{escape(user.get('product') or 'չկա')}</b>\n" f"🆔 Մուտքագրված ID՝ <code>{escape(message.text.strip())}</code>", parse_mode="HTML")
            await message.answer("✅ <b>ID-ն ստացվեց։</b>\n\n⏳ Ձեր վճարումը ստուգվում է, և պատվերը մշակվում է։", parse_mode="HTML", reply_markup=main_menu_keyboard())
        except Exception:
            logging.exception("Failed to send user ID to order channel")
            await message.answer("⚠️ Չհաջողվեց ուղարկել ID-ն։ Փորձեք կրկին։")
        return

    if not user.get("support_waiting") or not SUPPORT_CHANNEL_ID:
        return
    username = message.from_user.username or "չկա"
    support_text = ("📩 <b>ՆՈՐ ՀԱՂՈՐԴԱԳՐՈՒԹՅՈՒՆ</b>\n\n" f"👤 Username՝ @{escape(username)}\n" f"🆔 ID՝ <code>{message.from_user.id}</code>\n\n" f"💬 {escape(message.text)}")
    try:
        await bot.send_message(chat_id=SUPPORT_CHANNEL_ID, text=support_text, parse_mode="HTML")
        user["support_waiting"] = False
        await message.answer("✅ Հաղորդագրությունը ստացվեց։ Մենք կպատասխանենք շուտով։", reply_markup=main_menu_keyboard())
    except Exception:
        logging.exception("Failed to send support message")
        await message.answer("⚠️ Չհաջողվեց ուղարկել հաղորդագրությունը։")


@dp.callback_query(F.data.startswith("game:"))
async def choose_game(callback: CallbackQuery):
    game = callback.data.split(":", 1)[1]
    if game not in CATALOG:
        await callback.answer("❌ Սխալ խաղ։", show_alert=True)
        return
    user = get_user(callback.from_user.id)
    user.update({"game": game, "product": None, "price": None, "payment": None, "order_id": None, "brawl_pass_type": None, "brawl_pass_waiting": False, "receipt_waiting_id": False, "receipt_order_message_id": None, "receipt_accepted": False})
    reset_refund_state(user)
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
    user.update({"game": game, "product": item[0], "price": item[1], "username": callback.from_user.username, "payment": None, "receipt_accepted": False})
    reset_refund_state(user)
    if game == "brawlstars" and item[0] in {"Brawl Pass", "Brawl Pass+"}:
        user["brawl_pass_type"] = "brawl_pass" if item[0] == "Brawl Pass" else "brawl_pass_plus"
        user["brawl_pass_waiting"] = True
        await callback.message.edit_text(brawl_pass_prompt(user["brawl_pass_type"]), reply_markup=pass_back_keyboard(), parse_mode="HTML")
        await callback.answer()
        return
    text = ("🛒 <b>Ձեր ընտրությունը</b>\n\n" f"🎮 Խաղ՝ <b>{escape(CATALOG[game]['name'])}</b>\n" f"📦 Ապրանք՝ <b>{escape(item[0])}</b>\n" f"💰 Գին՝ <b>{fmt_price(item[1])} ֏</b>\n\n" "Շարունակե՞լ պատվերը։")
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
        user["username"] = message.from_user.username
        pass_type = user["brawl_pass_type"]
        low, high = BRAWL_PASS_PRICES[pass_type]
        title = "🎫 Brawl Pass" if pass_type == "brawl_pass" else "⭐ Brawl Pass+"
        caption = ("📸 <b>BRAWL PASS SCREENSHOT</b>\n\n" f"👤 Username՝ @{escape(message.from_user.username or 'չկա')}\n" f"🆔 ID՝ <code>{message.from_user.id}</code>\n" f"📦 Pass՝ <b>{title}</b>\n\n" f"💰 Ընտրիր ճիշտ գինը՝ <b>{fmt_price(low)} ֏</b> կամ <b>{fmt_price(high)} ֏</b>")
        sent = await bot.send_photo(chat_id=ORDER_CHANNEL_ID, photo=message.photo[-1].file_id, caption=caption, parse_mode="HTML", reply_markup=admin_pass_price_keyboard(message.from_user.id, pass_type))
        user["pass_admin_message_id"] = sent.message_id
        await message.answer("✅ <b>Screenshot-ը ստացվեց։</b>\n\n👨‍💼 Ադմինը կստուգի քո Pass-ի գինը և կընտրի ճիշտ տարբերակը։", parse_mode="HTML", reply_markup=main_menu_keyboard())
        return
    if user.get("payment") != "receipt_pending":
        return
    if not ORDER_CHANNEL_ID:
        await message.answer("❌ Պատվերների ալիքը կարգավորված չէ։")
        return
    user["payment"] = "receipt_sent"
    user["order_id"] = f"{message.from_user.id}-{message.message_id}"
    user["username"] = message.from_user.username
    user["receipt_accepted"] = False
    caption = order_caption(message.from_user.id, user, "⏳ <b>Չեկը սպասում է ադմինի ստուգմանը։</b>")
    sent = await bot.send_photo(chat_id=ORDER_CHANNEL_ID, photo=message.photo[-1].file_id, caption=caption, parse_mode="HTML", reply_markup=admin_receipt_keyboard(message.from_user.id, False))
    user["receipt_order_message_id"] = sent.message_id
    user["receipt_waiting_id"] = True
    await message.answer("💎 <b>Չեկը ստացվեց։</b> ❤️‍🔥\n\n🆔 Հիմա ուղարկիր քո ID-ն։", parse_mode="HTML")


@dp.callback_query(F.data == "buy:confirm")
async def buy_confirm(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user.get("game") or not user.get("product"):
        await callback.answer("❌ Նախ ընտրիր ապրանքը։", show_alert=True)
        return
    text = ("💳 <b>Ընտրիր վճարման եղանակը</b>\n\n" f"📦 {escape(user['product'])}\n" f"💰 Գումար՝ <b>{fmt_price(user['price'])} ֏</b>\n\n" "Ընտրիր՝ քարտով, թե կանխիկ։")
    await callback.message.edit_text(text, reply_markup=payment_keyboard(), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "payment:card")
async def payment_card(callback: CallbackQuery):
    await callback.answer("💳 Քարտով վճարումը դեռ հասանելի չէ։", show_alert=True)


@dp.callback_query(F.data == "payment:cash")
async def payment_cash(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user.get("product"):
        await callback.answer("❌ Պատվերը չի գտնվել։", show_alert=True)
        return
    user["payment"] = "cash"
    await callback.message.edit_text(cash_payment_text(user), reply_markup=receipt_keyboard(), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "payment:done")
async def payment_done(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user.get("product"):
        await callback.answer("❌ Պատվերը չի գտնվել։", show_alert=True)
        return
    user["payment"] = "receipt_pending"
    await callback.message.edit_text("🧾 <b>Ուղարկիր չեկի նկարը</b>\n\n📸 Ուղարկիր վճարման չեկի լուսանկարը այս հաղորդագրությունից հետո։", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:payment")]]), parse_mode="HTML")
    await callback.answer()


async def admin_only(callback: CallbackQuery) -> bool:
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Այս կոճակը հասանելի է միայն ադմինին։", show_alert=True)
        return False
    return True


@dp.callback_query(F.data.startswith("passprice:"))
async def admin_pass_price(callback: CallbackQuery):
    if not await admin_only(callback):
        return
    _, user_id_text, price_text = callback.data.split(":")
    user_id = int(user_id_text)
    price = int(price_text)
    user = get_user(user_id)
    user["price"] = price
    user["product"] = "Brawl Pass" if user.get("brawl_pass_type") == "brawl_pass" else "Brawl Pass+"
    user["brawl_pass_type"] = None
    try:
        await callback.message.edit_caption(caption=(callback.message.caption or "") + f"\n\n✅ <b>Ընտրված գին՝ {fmt_price(price)} ֏</b>", parse_mode="HTML", reply_markup=None)
    except Exception:
        logging.exception("Failed to update Brawl Pass admin message")
    await notify_user(user_id, "✅ <b>Ձեր Pass-ի գինը հաստատվեց։</b>\n\n" f"📦 {escape(user['product'])}\n" f"💰 Գին՝ <b>{fmt_price(price)} ֏</b>\n\nՇարունակե՞լ պատվերը։")
    try:
        await bot.send_message(user_id, "🛒 <b>Ձեր ընտրությունը</b>\n\n" f"📦 {escape(user['product'])}\n" f"💰 Գին՝ <b>{fmt_price(price)} ֏</b>\n\n" "Շարունակե՞լ պատվերը։", reply_markup=product_keyboard("brawlstars"), parse_mode="HTML")
    except Exception:
        logging.exception("Failed to send Brawl Pass purchase message")
    await callback.answer("✅ Գինը ընտրված է։")


async def admin_receipt_action(callback: CallbackQuery, action: str, user_id: int):
    if not await admin_only(callback):
        return
    user = get_user(user_id)

    if action == "reject":
        user["payment"] = "receipt_rejected"
        user["receipt_accepted"] = False
        reset_refund_state(user)
        status = "❌ <b>Չեկը մերժված է։</b>"
        await notify_user(user_id, "❌ <b>Ձեր վճարման չեկը մերժվել է։</b>\n\nԽնդրում ենք կապվել Games Vault Shop-ի աջակցության հետ։")
        await callback.answer("❌ Չեկը մերժվեց։")

    elif action == "accept":
        user["receipt_accepted"] = True
        user["payment"] = "receipt_accepted"
        reset_refund_state(user)
        status = "✅ <b>Չեկը հաստատված է։ Այժմ կարող եք հաստատել պատվերը և ավարտել Դոնաթը։</b>"
        await notify_user(user_id, "✅ <b>Չեկը հաստատվեց։</b>\n\n⏳ Ձեր պատվերը պատրաստվում է։")
        await callback.answer("✅ Չեկը հաստատվեց։")

    elif action == "refund":
        user["refund_waiting"] = True
        user["refund_method"] = None
        user["refund_operator"] = None
        user["refund_details_ready"] = False
        user["refund_complete"] = False
        user["payment"] = "refund_requested"
        status = "💔 <b>Դոնաթը չի հաջողվել։</b>\n⏳ Սպասում է հաճախորդի վերադարձի եղանակին։"
        await notify_user(
            user_id,
            "💔 <b>Դոնաթը չի հաջողվել։</b>\n\n"
            "💸 Ընտրիր գումարի վերադարձի եղանակը՝",
            reply_markup=refund_client_method_keyboard(),
        )
        await callback.answer("💸 Հաճախորդին ուղարկվեց վերադարձի եղանակի ընտրությունը։")

    elif action == "confirm":
        if not user.get("receipt_accepted"):
            await callback.answer("⛔ Նախ անհրաժեշտ է հաստատել չեկը։", show_alert=True)
            return
        user["payment"] = "completed"
        reset_refund_state(user)
        status = "📦 <b>Պատվերը հաստատված է — Դոնաթը ավարտված է։</b>"
        await notify_user(user_id, "🎉 <b>Ձեր պատվերը հաստատված է։</b> ❤️‍🔥\n\n⚡ <b>Դոնաթը հաջողությամբ ավարտված է։</b>\n\nՇնորհակալություն Games Vault Shop-ը ընտրելու համար։ 💎")
        await callback.answer("📦 Պատվերը հաստատվեց։ Դոնաթը ավարտված է։")

    elif action == "refund_complete":
        if not user.get("refund_details_ready"):
            await callback.answer("⛔ Նախ սպասեք հաճախորդի վերադարձի տվյալներին։", show_alert=True)
            return
        user["refund_complete"] = True
        user["refund_waiting"] = False
        user["payment"] = "refunded_completed"
        status = "✅ <b>Հետ գումարի վերադարձը ավարտված է։</b>"
        await notify_user(user_id, "✅ <b>Հետ գումարի վերադարձը ավարտված է։</b>\n\n💸 Գումարը վերադարձվել է ընտրված եղանակով։\n\n💎 Games Vault Shop ❤️‍🔥")
        await callback.answer("✅ Հետ գումարի վերադարձը ավարտված է։")

    elif action == "back":
        status = "✅ <b>Չեկը հաստատված է։</b>" if user.get("receipt_accepted") else "⏳ <b>Չեկը սպասում է ադմինի ստուգմանը։</b>"
        await update_admin_receipt_message(user_id, status)
        await callback.answer("↩️ Վերադարձ։")
        return

    else:
        await callback.answer("❌ Անհայտ գործողություն։", show_alert=True)
        return

    await update_admin_receipt_message(user_id, status)


@dp.callback_query(F.data.startswith("refundclient:"))
async def refund_client_callback(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user.get("refund_waiting"):
        await callback.answer("❌ Վերադարձի գործընթացը չի սկսվել։", show_alert=True)
        return

    parts = callback.data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "back":
        user["refund_method"] = None
        user["refund_operator"] = None
        await callback.message.edit_text(
            "💔 <b>Դոնաթը չի հաջողվել։</b>\n\n💸 Ընտրիր գումարի վերադարձի եղանակը՝",
            reply_markup=refund_client_method_keyboard(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    if action == "phone":
        user["refund_method"] = "phone"
        await callback.message.edit_text(
            "📱 <b>Վերադարձ հեռախոսահամարին</b>\n\n"
            "⚠️ Գումարը կավելանա բջջային հաշվեկշռին և կարող է օգտագործվել զանգերի համար։\n\n"
            "Ընտրիր քո օպերատորը՝",
            reply_markup=refund_operators_keyboard(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    if action == "card":
        user["refund_method"] = "card"
        await callback.message.edit_text(
            "💳 <b>Վերադարձ քարտին</b>\n\n"
            "Գրիր քարտի տվյալները հաջորդ հաղորդագրությամբ։",
            reply_markup=refund_back_keyboard(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    if action == "operator" and len(parts) >= 3:
        operator = ":".join(parts[2:])
        user["refund_method"] = "phone"
        user["refund_operator"] = operator
        user["refund_waiting"] = True
        await callback.message.edit_text(
            f"📞 <b>{escape(operator)}</b>\n\n"
            "☎️ Գրիր քո հեռախոսահամարը հաջորդ հաղորդագրությամբ։",
            reply_markup=refund_back_keyboard(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    await callback.answer("❌ Անհայտ գործողություն։", show_alert=True)


@dp.callback_query(F.data.startswith("receipt:"))
async def receipt_admin_callback(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("❌ Սխալ գործողություն։", show_alert=True)
        return
    _, action, user_id_text = parts
    try:
        user_id = int(user_id_text)
    except ValueError:
        await callback.answer("❌ Սխալ օգտատիրոջ ID։", show_alert=True)
        return
    await admin_receipt_action(callback, action, user_id)


@dp.callback_query(F.data == "back:main")
async def back_main(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    user["support_waiting"] = False
    user["brawl_pass_waiting"] = False
    user["refund_waiting"] = False
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
    user["refund_waiting"] = False
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
    text = ("🛒 <b>Ձեր ընտրությունը</b>\n\n" f"🎮 Խաղ՝ <b>{escape(CATALOG[game]['name'])}</b>\n" f"📦 Ապրանք՝ <b>{escape(user['product'])}</b>\n" f"💰 Գին՝ <b>{fmt_price(user['price'])} ֏</b>\n\nՇարունակե՞լ պատվերը։")
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
