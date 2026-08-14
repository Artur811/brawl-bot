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
    "brawlstars": {"name": "⭐ Brawl Stars", "items": [("30 Gems", 750), ("80 Gems", 1500), ("170 Gems", 2800), ("360 Gems", 5100), ("950 Gems", 12800), ("Brawl Pass — 2,500 / 3,400 ֏", 2500), ("Brawl Pass+ — 3,400 / 4,800 ֏", 3400), ("Прокачка Brawl Pass → Brawl Pass+", 1800), ("Pro Pass", 12300)]},
    "pubg": {"name": "🪂 PUBG Mobile", "items": [("33 UC + 🎁", 300), ("66 UC + 🎁", 500), ("99 UC + 🎁", 700), ("132 UC + 🎁", 1000), ("150 UC + 🎁", 1100), ("198 UC + 🎁", 1400), ("210 UC + 🎁", 1600), ("325 UC + 🎁", 2000), ("355 + 5 UC + 🎁", 2100), ("445 UC + 🎁", 2900), ("505 UC + 🎁", 3400), ("660 UC + 🎁", 4000), ("720 UC + 🎁", 4300), ("985 UC + 🎁", 6000), ("1,135 UC + 🎁", 7000), ("1,320 UC + 🎁", 7800), ("1,860 UC + 🎁", 10000), ("2,185 UC + 🎁", 11500)]},
}

def main_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Roblox", callback_data="game:roblox"), InlineKeyboardButton(text="🔫 Standoff 2", callback_data="game:standoff2")],
        [InlineKeyboardButton(text="⭐ Brawl Stars", callback_data="game:brawlstars"), InlineKeyboardButton(text="🪂 PUBG Mobile", callback_data="game:pubg")],
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

@dp.callback_query(F.data.startswith("game:"))
async def choose_game(callback: CallbackQuery):
    game = callback.data.split(":", 1)[1]
    if game not in CATALOG:
        await callback.answer("❌ Սխալ խաղ։", show_alert=True)
        return
    user = get_user(callback.from_user.id)
    user.update({"game": game, "product": None, "price": None, "payment": None, "order_id": None})
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
    user.update({"game": game, "product": item[0], "price": item[1], "username": callback.from_user.username})
    text = ("🛒 <b>Ձեր ընտրությունը</b>\n\n" f"🎮 Խաղ՝ <b>{escape(CATALOG[game]['name'])}</b>\n" f"📦 Ապրանք՝ <b>{escape(item[0])}</b>\n" f"💰 Գին՝ <b>{item[1]:,} ֏</b>\n\n" "Շարունակե՞լ պատվերը։").replace(",", " ")
    await callback.message.edit_text(text, reply_markup=product_keyboard(game), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "buy:confirm")
async def buy_confirm(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user.get("game") or not user.get("product"):
        await callback.answer("❌ Նախ ընտրիր ապրանքը։", show_alert=True)
        return
    text = ("💳 <b>Վճարում</b>\n\n" f"📦 {escape(user['product'])}\n" f"💰 Գումար՝ <b>{user['price']:,} ֏</b>\n\n" f"Telcell Wallet\n📱 Համար՝ <code>{escape(TELCELL_NUMBER)}</code>\n\n" "Telcell տերմինալով ընտրեք «Telcell Wallet» տարբերակը և գրեք հեռախոսահամարը։\n\n" "❗ Վճարումից հետո ուղարկեք չեկը։").replace(",", " ")
    await callback.message.edit_text(text, reply_markup=payment_keyboard(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "card:unavailable")
async def card_unavailable(callback: CallbackQuery):
    await callback.answer("💳 Քարտով վճարումը հասանելի չէ։", show_alert=True)

@dp.callback_query(F.data == "payment:done")
async def payment_done(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user.get("product"):
        await callback.answer("❌ Պատվերը չի գտնվել։", show_alert=True)
        return
    user["payment"] = "receipt_pending"
    await callback.message.edit_text("🧾 <b>Ուղարկիր վճարման չեկը</b>\n\nՈւղարկիր չեկի լուսանկարը այս հաղորդագրությունից հետո։", reply_markup=receipt_keyboard(), parse_mode="HTML")
    await callback.answer()

@dp.message(F.photo)
async def receipt_router(message: Message):
    user = get_user(message.from_user.id)
    if user.get("payment") != "receipt_pending":
        return
    if not ORDER_CHANNEL_ID:
        await message.answer("❌ Պատվերների ալիքը կարգավորված չէ։")
        return
    user["payment"] = "receipt_sent"
    user["order_id"] = f"{message.from_user.id}-{message.message_id}"
    caption = order_caption(message.from_user.id, user, "⏳ Վճարման չեկը ստուգման մեջ է։")
    await bot.send_photo(chat_id=ORDER_CHANNEL_ID, photo=message.photo[-1].file_id, caption=caption, parse_mode="HTML")
    await message.answer("✅ Չեկը ստացվեց և ուղարկվեց ստուգման։", reply_markup=main_menu_keyboard())

@dp.callback_query(F.data == "back:main")
async def back_main(callback: CallbackQuery):
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
