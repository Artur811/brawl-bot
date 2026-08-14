import os
import asyncio
import logging
import re
from html import escape

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID = os.getenv("CHANNEL_ID", "")
ORDER_CHANNEL_ID = os.getenv("ORDER_CHANNEL_ID", CHANNEL_ID)
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

def get_user(user_id: int):
    if user_id not in users:
        users[user_id] = {"game": None, "product": None, "price": None, "username": None, "payment": None, "order_id": None, "support_waiting": False}
    return users[user_id]

CATALOG = {
    "roblox": {"name": "🎮 Roblox", "items": [("40 Robux", 350), ("80 Robux", 650), ("120 Robux", 950), ("400 Robux", 2700), ("520 Robux", 3600), ("840 Robux", 4850), ("1,240 Robux", 7300), ("1,700 Robux", 8800), ("1,820 Robux", 9700), ("4,500 Robux", 21000), ("10,000 Robux", 40000), ("22,500 Robux", 88000)]},
    "standoff2": {"name": "🔫 Standoff 2", "items": [("100 Gold", 1000), ("200 Gold", 2000), ("300 Gold", 2900), ("500 Gold", 4000), ("600 Gold", 5100), ("700 Gold", 5800), ("1,000 Gold", 7100), ("1,500 Gold", 10300), ("3,000 Gold", 15800)]},
    "brawlstars": {"name": "⭐ Brawl Stars", "items": [("30 Gems", 800), ("80 Gems", 1600), ("170 Gems", 3000), ("360 Gems", 5300), ("950 Gems", 13000)]},
    "pubg": {"name": "🪂 PUBG Mobile", "items": [("33 UC + 🎁", 300), ("66 UC + 🎁", 500), ("99 UC + 🎁", 700), ("132 UC + 🎁", 1000), ("150 UC + 🎁", 1100), ("198 UC + 🎁", 1400), ("210 UC + 🎁", 1600), ("325 UC + 🎁", 2000), ("355 + 5 UC + 🎁", 2100), ("445 UC + 🎁", 2900), ("505 UC + 🎁", 3400), ("660 UC + 🎁", 4000), ("720 UC + 🎁", 4300), ("985 UC + 🎁", 6000), ("1,135 UC + 🎁", 7000), ("1,320 UC + 🎁", 7800), ("1,860 UC + 🎁", 10000), ("2,185 UC + 🎁", 11500)]},
    "brawlpass": {"name": "🎫 Brawl Pass", "items": [("Brawl Pass — аккаунт 1", 2700), ("Brawl Pass — аккаунт 2", 3600), ("Brawl Pass Plus — аккаунт 1", 3600), ("Brawl Pass Plus — аккаунт 2", 5000), ("Pro Pass", 12800)]},
}

def main_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Roblox", callback_data="game:roblox"), InlineKeyboardButton(text="🔫 Standoff 2", callback_data="game:standoff2")],
        [InlineKeyboardButton(text="⭐ Brawl Stars", callback_data="game:brawlstars"), InlineKeyboardButton(text="🪂 PUBG Mobile", callback_data="game:pubg")],
        [InlineKeyboardButton(text="🎫 Brawl Pass", callback_data="game:brawlpass")],
        [InlineKeyboardButton(text="📩 Կապվեք մեզ հետ", callback_data="contact:open")],
    ])

def game_keyboard(game: str):
    buttons = [[InlineKeyboardButton(text=f"⚡ {name} — {price:,} ֏".replace(",", " "), callback_data=f"product:{game}:{index}")] for index, (name, price) in enumerate(CATALOG[game]["items"])]
    buttons.append([InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def product_keyboard(game: str):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Գնել", callback_data="buy:confirm")], [InlineKeyboardButton(text="⬅️ Հետ", callback_data=f"back:game:{game}")]])

def payment_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Վճարել եմ", callback_data="payment:done")], [InlineKeyboardButton(text="💳 Քարտ տրամադրել — հասանելի չէ", callback_data="card:unavailable")], [InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:product")]])

def receipt_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:payment")]])

def refund_keyboard(user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💳 Վերադարձ քարտին", callback_data=f"refund:card:{user_id}")], [InlineKeyboardButton(text="📱 Վերադարձ հեռախոսահամարին", callback_data=f"refund:phone:{user_id}")]])

def refund_done_keyboard(user_id: int, method: str):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Վերադարձը կատարված է", callback_data=f"refund:done:{method}:{user_id}")]])

def main_text():
    return ("🎮 <b>Games Vault Shop</b> ❤️‍🔥\n\n" "💎 <b>Games Vault Shop-ում՝ միշտ VAULT-Ա!</b>\n\n" "Ընտրիր խաղը և տես հասանելի ապրանքները։\n\n" "⚡ Արագ պատվեր\n" "💳 Telcell Wallet\n" "🧾 Չեկի ստուգում\n" "📩 Աջակցություն և կապ\n\n" "❗ Գնումից առաջ ստուգիր ապրանքի տեսակը և գինը։")

def game_text(game: str):
    return f"{CATALOG[game]['name']}\n\nԸնտրիր անհրաժեշտ ապրանքը։\n\n💰 Գները նշված են դրամով։"

def order_caption(user_id: int, user: dict, status: str):
    username = user.get("username") or "չկա"
    return ("🧾 <b>ՊԱՏՎԵՐ</b>\n\n" f"👤 Օգտատեր՝ @{escape(username)}\n" f"🆔 ID՝ <code>{user_id}</code>\n" f"🎮 Խաղ՝ <b>{escape(CATALOG[user['game']]['name'])}</b>\n" f"📦 Ապրանք՝ <b>{escape(user['product'])}</b>\n" f"💰 Գումար՝ <b>{user['price']:,} ֏</b>\n" f"🔖 Պատվեր՝ <code>{escape(user.get('order_id') or str(user_id))}</code>\n\n" f"{status}").replace(",", " ")

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
    if not user.get("support_waiting") or not SUPPORT_CHANNEL_ID:
        return
    username = message.from_user.username or "չկա"
    support_text = ("📩 <b>ՆՈՐ ՀԱՂՈՐԴԱԳՐՈՒԹՅՈՒՆ</b>\n\n" f"👤 Username՝ @{escape(username)}\n" f"🆔 ID՝ <code>{message.from_user.id}</code>\n\n" f"💬 {escape(message.text)}\n\n" "↩️ Պատասխանեք այս հաղորդագրությանը՝ օգտատիրոջը ուղարկելու համար։")
    sent = await bot.send_message(chat_id=SUPPORT_CHANNEL_ID, text=support_text, parse_mode="HTML")
    support_threads[sent.message_id] = message.from_user.id
    user["support_waiting"] = False
    await message.answer("✅ Հաղորդագրությունը ստացվեց։ Մենք կպատասխանենք շուտով։", reply_markup=main_menu_keyboard())

@dp.message(F.photo)
async def photo_router(message: Message):
    user = get_user(message.from_user.id)
    if user.get("support_waiting") and SUPPORT_CHANNEL_ID:
        username = message.from_user.username or "չկա"
        caption = ("📷 <b>ՆՈՐ ՀԱՂՈՐԴԱԳՐՈՒԹՅՈՒՆ</b>\n\n" f"👤 Username՝ @{escape(username)}\n" f"🆔 ID՝ <code>{message.from_user.id}</code>\n\n" "↩️ Պատասխանեք այս հաղորդագրությանը՝ օգտատիրոջը ուղարկելու համար։")
        sent = await bot.send_photo(chat_id=SUPPORT_CHANNEL_ID, photo=message.photo[-1].file_id, caption=caption, parse_mode="HTML")
        support_threads[sent.message_id] = message.from_user.id
        user["support_waiting"] = False
        await message.answer("✅ Նկարը ստացվեց։ Մենք կպատասխանենք շուտով։", reply_markup=main_menu_keyboard())
        return
    if user.get("payment") != "waiting_receipt":
        return
    user["payment"] = "receipt_sent"
    user["username"] = message.from_user.username
    user["order_id"] = user.get("order_id") or f"{message.from_user.id}-{message.message_id}"
    target = ORDER_CHANNEL_ID or ADMIN_ID
    if not target:
        await message.answer("❌ Պատվերների ալիքը դեռ կարգավորված չէ։")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Ընդունել չեկը", callback_data=f"order:accept:{message.from_user.id}"), InlineKeyboardButton(text="❌ Մերժել չեկը", callback_data=f"order:reject:{message.from_user.id}")], [InlineKeyboardButton(text="💸 Վերադարձ կատարել", callback_data=f"order:refund:{message.from_user.id}")]])
    await bot.send_photo(chat_id=target, photo=message.photo[-1].file_id, caption=order_caption(message.from_user.id, user, "🟡 <b>Սպասում է չեկի ստուգման</b>"), reply_markup=keyboard, parse_mode="HTML")
    await message.answer("✅ Չեկը ստացվեց։\n\nՍպասիր մեր ստուգմանը։", parse_mode="HTML")

@dp.channel_post()
async def support_channel_reply(message: Message):
    if not SUPPORT_CHANNEL_ID or str(message.chat.id) != str(SUPPORT_CHANNEL_ID) or not message.reply_to_message:
        return
    source = message.reply_to_message.text or message.reply_to_message.caption or ""
    user_id = support_threads.get(message.reply_to_message.message_id)
    if not user_id:
        match = re.search(r"ID՝ <code>(\d+)</code>", source)
        if match:
            user_id = int(match.group(1))
    if not user_id:
        return
    try:
        if message.text:
            await bot.send_message(user_id, f"📩 <b>Պատասխան Games Vault Shop-ից</b>\n\n{escape(message.text)}", parse_mode="HTML")
        elif message.photo:
            await bot.send_photo(user_id, message.photo[-1].file_id, caption="📩 <b>Պատասխան Games Vault Shop-ից</b>", parse_mode="HTML")
    except Exception:
        logging.exception("Չհաջողվեց ուղարկել աջակցման պատասխանը օգտատիրոջը")

@dp.callback_query(F.data.startswith("game:"))
async def select_game(callback: CallbackQuery):
    game = callback.data.split(":", 1)[1]
    if game not in CATALOG:
        await callback.answer("❌ Սխալ խաղ։", show_alert=True)
        return
    user = get_user(callback.from_user.id)
    user.update({"game": game, "product": None, "price": None, "payment": None, "order_id": None, "support_waiting": False})
    await callback.message.edit_text(game_text(game), reply_markup=game_keyboard(game), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("product:"))
async def select_product(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 3 or parts[1] not in CATALOG:
        await callback.answer("❌ Սխալ ապրանք։", show_alert=True)
        return
    try:
        index = int(parts[2])
    except ValueError:
        await callback.answer("❌ Սխալ ապրանք։", show_alert=True)
        return
    items = CATALOG[parts[1]]["items"]
    if index < 0 or index >= len(items):
        await callback.answer("❌ Սխալ ապրանք։", show_alert=True)
        return
    game = parts[1]
    product, price = items[index]
    user = get_user(callback.from_user.id)
    user.update({"game": game, "product": product, "price": price, "payment": None, "order_id": None})
    text = ("🛒 <b>Ձեր ընտրությունը</b>\n\n" f"🎮 Խաղ՝ <b>{escape(CATALOG[game]['name'])}</b>\n" f"📦 Ապրանք՝ <b>{escape(product)}</b>\n" f"💰 Գին՝ <b>{price:,} ֏</b>\n\n" "Շարունակե՞լ պատվերը։").replace(",", " ")
    await callback.message.edit_text(text, reply_markup=product_keyboard(game), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "buy:confirm")
async def buy_confirm(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user.get("product"):
        await callback.answer("❌ Սկզբում ընտրիր ապրանքը։", show_alert=True)
        return
    text = ("💳 <b>Վճարում</b>\n\n" f"📦 {escape(user['product'])}\n" f"💰 <b>{user['price']:,} ֏</b>\n\n" "Վճարումը կատարվում է միայն <b>Telcell Wallet</b>-ով։\n\n" "💳 Քարտով վճարումը՝ <b>հասանելի չէ</b>։\n\n" f"📱 Telcell Wallet՝ <code>{escape(TELCELL_NUMBER)}</code>\n\n" "Վճարումից հետո սեղմիր «✅ Վճարել եմ» և ուղարկիր չեկը։").replace(",", " ")
    await callback.message.edit_text(text, reply_markup=payment_keyboard(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "card:unavailable")
async def card_unavailable(callback: CallbackQuery):
    await callback.answer("💳 Քարտով վճարումը հասանելի չէ։ Վճարիր Telcell Wallet-ով։", show_alert=True)

@dp.callback_query(F.data == "payment:done")
async def payment_done(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user.get("product"):
        await callback.answer("❌ Ապրանքը ընտրված չէ։", show_alert=True)
        return
    user["payment"] = "waiting_receipt"
    user["order_id"] = f"{callback.from_user.id}-{callback.message.message_id}"
    await callback.message.edit_text("🧾 <b>Ուղարկիր վճարման չեկը</b>\n\nՈւղարկիր Telcell-ի վճարման չեկի նկարը այս չաթում։\n\n❗ Չեկը պետք է ամբողջությամբ տեսանելի լինի։", reply_markup=receipt_keyboard(), parse_mode="HTML")
    await callback.answer()

async def admin_only(callback: CallbackQuery) -> bool:
    if ADMIN_ID and callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Դուք չունեք թույլտվություն։", show_alert=True)
        return False
    if not ADMIN_ID:
        await callback.answer("❌ ADMIN_ID-ը կարգավորված չէ։", show_alert=True)
        return False
    return True

@dp.callback_query(F.data.startswith("order:accept:"))
async def order_accept(callback: CallbackQuery):
    if not await admin_only(callback): return
    user_id = int(callback.data.rsplit(":", 1)[1])
    user = get_user(user_id)
    user["payment"] = "accepted"
    await bot.send_message(user_id, "✅ <b>Չեկը ընդունված է։</b>\n\nՁեր պատվերը ընդունվել է։", parse_mode="HTML")
    try:
        await callback.message.edit_caption(caption=order_caption(user_id, user, "✅ <b>Չեկը ընդունված է</b>"), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💸 Վերադարձ կատարել", callback_data=f"order:refund:{user_id}")]]))
    except TelegramBadRequest: pass
    await callback.answer("Չեկը ընդունվեց։")

@dp.callback_query(F.data.startswith("order:reject:"))
async def order_reject(callback: CallbackQuery):
    if not await admin_only(callback): return
    user_id = int(callback.data.rsplit(":", 1)[1])
    user = get_user(user_id)
    user["payment"] = "rejected"
    await bot.send_message(user_id, "❌ <b>Չեկը մերժված է։</b>\n\nՍտուգիր վճարումը և անհրաժեշտության դեպքում ուղարկիր նոր չեկ։", parse_mode="HTML")
    try:
        await callback.message.edit_caption(caption=order_caption(user_id, user, "❌ <b>Չեկը մերժված է</b>"), parse_mode="HTML", reply_markup=None)
    except TelegramBadRequest: pass
    await callback.answer("Չեկը մերժվեց։")

@dp.callback_query(F.data.startswith("order:refund:"))
async def order_refund(callback: CallbackQuery):
    if not await admin_only(callback): return
    user_id = int(callback.data.rsplit(":", 1)[1])
    await callback.message.edit_caption(caption=(callback.message.caption or "") + "\n\n💸 <b>Ընտրվեց վերադարձի եղանակը</b>", parse_mode="HTML", reply_markup=refund_keyboard(user_id))
    await callback.answer()

@dp.callback_query(F.data.startswith("refund:card:"))
async def refund_card(callback: CallbackQuery):
    if not await admin_only(callback): return
    user_id = int(callback.data.rsplit(":", 1)[1])
    user = get_user(user_id)
    user["payment"] = "refund_card_pending"
    await bot.send_message(user_id, "💳 <b>Վերադարձ քարտին</b>\n\nՎերադարձը կկատարվի ձեռքով։ Սպասիր հաստատմանը։", parse_mode="HTML")
    await callback.message.edit_caption(caption=(callback.message.caption or "") + "\n\n💳 <b>Վերադարձ՝ քարտին</b>\n🟡 Սպասում է կատարմանը", parse_mode="HTML", reply_markup=refund_done_keyboard(user_id, "card"))
    await callback.answer("Ընտրվեց վերադարձը քարտին։")

@dp.callback_query(F.data.startswith("refund:phone:"))
async def refund_phone(callback: CallbackQuery):
    if not await admin_only(callback): return
    user_id = int(callback.data.rsplit(":", 1)[1])
    user = get_user(user_id)
    user["payment"] = "refund_phone_pending"
    await bot.send_message(user_id, "📱 <b>Վերադարձ հեռախոսահամարին</b>\n\n⚠️ Եթե գումարը վերադարձվում է հեռախոսահամարին, այն կավելանա հեռախոսի <b>հաշվեկշռին / զանգերի բալանսին</b>։ Այն չի փոխանցվի որպես քարտային կամ կանխիկ գումար։", parse_mode="HTML")
    await callback.message.edit_caption(caption=(callback.message.caption or "") + "\n\n📱 <b>Վերադարձ՝ հեռախոսահամարին</b>\n🟡 Սպասում է կատարմանը", parse_mode="HTML", reply_markup=refund_done_keyboard(user_id, "phone"))
    await callback.answer("Ընտրվեց վերադարձը հեռախոսահամարին։")

@dp.callback_query(F.data.startswith("refund:done:"))
async def refund_done(callback: CallbackQuery):
    if not await admin_only(callback): return
    _, _, method, user_id_text = callback.data.split(":", 3)
    user_id = int(user_id_text)
    user = get_user(user_id)
    user["payment"] = "refunded"
    method_text = "քարտին" if method == "card" else "հեռախոսահամարին"
    await bot.send_message(user_id, f"✅ <b>Վերադարձը կատարված է</b>\n\nԳումարը վերադարձվել է {method_text}։", parse_mode="HTML")
    try:
        await callback.message.edit_caption(caption=(callback.message.caption or "") + "\n\n✅ <b>ՎԵՐԱԴԱՐՁԸ ԿԱՏԱՐՎԱԾ Է</b>", parse_mode="HTML", reply_markup=None)
    except TelegramBadRequest: pass
    await callback.answer("Վերադարձը հաստատվեց։")

@dp.callback_query(F.data == "back:main")
async def back_main(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    user["support_waiting"] = False
    await callback.message.edit_text(main_text(), reply_markup=main_menu_keyboard(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("back:game:"))
async def back_game(callback: CallbackQuery):
    game = callback.data.split(":", 2)[2]
    if game not in CATALOG:
        await callback.answer("❌ Սխալ խաղ։", show_alert=True)
        return
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
    text = ("🛒 <b>Ձեր ընտրությունը</b>\n\n" f"🎮 Խաղ՝ <b>{escape(CATALOG[game]['name'])}</b>\n" f"📦 Ապրանք՝ <b>{escape(user['product'])}</b>\n" f"💰 Գին՝ <b>{user['price']:,} ֏</b>\n\n" "Շարունակե՞լ պատվերը։").replace(",", " ")
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
