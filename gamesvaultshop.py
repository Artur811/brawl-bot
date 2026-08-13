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
TELCELL_NUMBER = os.getenv("TELCELL_NUMBER", "055363432")
PORT = int(os.getenv("PORT", "10000"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN չգտնվեց")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

users = {}
support_threads = {}

CATALOG = {
    "roblox": {"name": "🎮 Roblox", "items": [
        ("40 Robux",350),("80 Robux",650),("120 Robux",950),("400 Robux",2700),
        ("520 Robux",3600),("840 Robux",4850),("1,240 Robux",7300),("1,700 Robux",8800),
        ("1,820 Robux",9700),("4,500 Robux",21000),("10,000 Robux",40000),("22,500 Robux",88000)]},
    "standoff2": {"name": "🔫 Standoff 2", "items": [
        ("100 Gold",1000),("200 Gold",2000),("300 Gold",2900),("500 Gold",4000),
        ("600 Gold",5100),("700 Gold",5800),("1,000 Gold",7100),("1,500 Gold",10300),("3,000 Gold",15800)]},
    "brawlstars": {"name": "⭐ Brawl Stars", "items": [
        ("30 Gems",800),("80 Gems",1600),("170 Gems",3000),("360 Gems",5300),("950 Gems",13000),
        ("🎫 Brawl Pass — аккаунт 1",2700),("🎫 Brawl Pass — аккаунт 2",3600),
        ("🎫 Brawl Pass Plus — аккаунт 1",3600),("🎫 Brawl Pass Plus — аккаунт 2",5000),("🎫 Pro Pass",12800)]},
    "pubg": {"name": "🪂 PUBG Mobile", "items": [
        ("33 UC + 🎁",300),("66 UC + 🎁",500),("99 UC + 🎁",700),("132 UC + 🎁",1000),("150 UC + 🎁",1100),
        ("198 UC + 🎁",1400),("210 UC + 🎁",1600),("325 UC + 🎁",2000),("355 + 5 UC + 🎁",2100),
        ("445 UC + 🎁",2900),("505 UC + 🎁",3400),("660 UC + 🎁",4000),("720 UC + 🎁",4300),
        ("985 UC + 🎁",6000),("1,135 UC + 🎁",7000),("1,320 UC + 🎁",7800),("1,860 UC + 🎁",10000),("2,185 UC + 🎁",11500)]},
}

TELCELL_TEXT = 'OK-ից Բարևներ😎❤️‍🔥🥕🐣Telcell տերմինալով ընտրում եք "Telcell Wallet" տարբերակը և գրում եք հեռախոսահամարը "055363432"🏌️\nՁեզ կտրվի 2 տարբերակ ընտրելու\n"AEB և EvocaBank" ընտրում եք ցանկացածը և գումարը փոխանցում, ապա Չեկը նկարում ուղղարկում մեզ, ապա📝տրամադրում եք ID-ն և 1-2 րոպեում ստանում եք ձեր Դոնաթը✅❤️'

def user_data(uid):
    return users.setdefault(uid, {"game":None,"product":None,"price":None,"payment":None,"order_id":None,"username":None,"review":False})

def menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Roblox", callback_data="game:roblox"), InlineKeyboardButton(text="🔫 Standoff 2", callback_data="game:standoff2")],
        [InlineKeyboardButton(text="⭐ Brawl Stars", callback_data="game:brawlstars"), InlineKeyboardButton(text="🪂 PUBG Mobile", callback_data="game:pubg")],
        [InlineKeyboardButton(text="⭐ Отзыв", callback_data="review:open")],
    ])

def game_kb(game):
    rows=[]
    for i,(name,price) in enumerate(CATALOG[game]["items"]):
        rows.append([InlineKeyboardButton(text=f"⚡ {name} — {price:,} ֏".replace(","," "), callback_data=f"product:{game}:{i}")])
    rows.append([InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def product_kb(game):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Գնել",callback_data="buy")],[InlineKeyboardButton(text="⬅️ Հետ",callback_data=f"back:game:{game}")]])

def pay_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Վճարել եմ",callback_data="paid")],
        [InlineKeyboardButton(text="💳 Քարտ տրամադրել — հասանելի չէ",callback_data="card:no")],
        [InlineKeyboardButton(text="⬅️ Հետ",callback_data="back:product")]])

def receipt_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Հետ",callback_data="back:payment")]])

def admin_order_kb(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ընդունել չեկը",callback_data=f"order:ok:{uid}"),InlineKeyboardButton(text="❌ Մերժել",callback_data=f"order:no:{uid}")],
        [InlineKeyboardButton(text="💸 Վերադարձ",callback_data=f"order:refund:{uid}")]])

def review_text():
    return "⭐ <b>Отзыв / Կապ Games Vault Shop-ի հետ</b>\n\nԳրիր կարծիքդ հաջորդ հաղորդագրությամբ։ Մենք կստանանք այն և կպատասխանենք։"

def home_text():
    return "🎮 <b>Games Vault Shop</b> ❤️‍🔥\n\n💎 <b>Games Vault Shop-ում՝ միշտ VAULT-Ա!</b>\n\nԸնտրիր խաղը։"

@dp.message(CommandStart())
async def start(m: Message):
    u=user_data(m.from_user.id); u["username"]=m.from_user.username; u["review"]=False
    await m.answer(home_text(),reply_markup=menu_kb(),parse_mode="HTML")

@dp.message(Command("menu"))
async def menu(m: Message):
    await m.answer(home_text(),reply_markup=menu_kb(),parse_mode="HTML")

@dp.callback_query(F.data.startswith("game:"))
async def game(c: CallbackQuery):
    g=c.data.split(":",1)[1]; u=user_data(c.from_user.id); u.update(game=g,product=None,price=None,payment=None,review=False)
    await c.message.edit_text(f"{CATALOG[g]['name']}\n\nԸնտրիր ապրանքը։",reply_markup=game_kb(g)); await c.answer()

@dp.callback_query(F.data.startswith("product:"))
async def product(c: CallbackQuery):
    _,g,i=c.data.split(":"); name,price=CATALOG[g]["items"][int(i)]; u=user_data(c.from_user.id); u.update(game=g,product=name,price=price,payment=None)
    text=f"🛒 <b>Ձեր ընտրությունը</b>\n\n🎮 {escape(CATALOG[g]['name'])}\n📦 <b>{escape(name)}</b>\n💰 <b>{price:,} ֏</b>\n\nՇարունակե՞լ պատվերը։".replace(","," ")
    await c.message.edit_text(text,reply_markup=product_kb(g),parse_mode="HTML"); await c.answer()

@dp.callback_query(F.data=="buy")
async def buy(c: CallbackQuery):
    u=user_data(c.from_user.id)
    await c.message.edit_text("💳 <b>Վճարում</b>\n\nՎճարումը կատարվում է Telcell Wallet-ով։",reply_markup=pay_kb(),parse_mode="HTML"); await c.answer()

@dp.callback_query(F.data=="card:no")
async def card_no(c: CallbackQuery): await c.answer("💳 Քարտ տրամադրել — հասանելի չէ",show_alert=True)

@dp.callback_query(F.data=="paid")
async def paid(c: CallbackQuery):
    u=user_data(c.from_user.id); u["payment"]="receipt"; u["order_id"]=f"{c.from_user.id}-{c.message.message_id}"
    await c.message.edit_text(TELCELL_TEXT+"\n\n🧾 Վճարումից հետո ուղարկիր չեկի նկարը։",reply_markup=receipt_kb()); await c.answer()

@dp.message(F.photo)
async def photo(m: Message):
    u=user_data(m.from_user.id)
    if u.get("payment")!="receipt": return
    u["payment"]="sent"; u["username"]=m.from_user.username
    target=ORDER_CHANNEL_ID or ADMIN_ID
    if not target: return
    caption=(f"🧾 <b>ՆՈՐ ՊԱՏՎԵՐ</b>\n\n👤 @{escape(u.get('username') or 'չկա')}\n🆔 <code>{m.from_user.id}</code>\n📦 {escape(u['product'])}\n💰 <b>{u['price']:,} ֏</b>\n\n🟡 Սպասում է ստուգման").replace(","," ")
    await bot.send_photo(target,m.photo[-1].file_id,caption=caption,reply_markup=admin_order_kb(m.from_user.id),parse_mode="HTML")
    await m.answer("✅ Չեկը ստացվեց։ Սպասիր ստուգմանը։",reply_markup=menu_kb())

@dp.callback_query(F.data=="review:open")
async def review_open(c: CallbackQuery):
    u=user_data(c.from_user.id); u["review"]=True
    await c.message.edit_text(review_text(),reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Հետ",callback_data="back:main")]]),parse_mode="HTML"); await c.answer()

@dp.message(F.text)
async def text_message(m: Message):
    u=user_data(m.from_user.id)
    if not u.get("review"): return
    if not SUPPORT_CHANNEL_ID:
        await m.answer("❌ SUPPORT_CHANNEL_ID-ը չի կարգավորված։")
        return
    sent=await bot.send_message(SUPPORT_CHANNEL_ID,f"⭐ <b>ՆՈՐ ԿԱՐԾԻՔ</b>\n\n👤 @{escape(m.from_user.username or 'չկա')}\n🆔 <code>{m.from_user.id}</code>\n\n💬 {escape(m.text)}",parse_mode="HTML")
    support_threads[sent.message_id]=m.from_user.id; u["review"]=False
    await m.answer("✅ Ձեր կարծիքը ստացվեց։",reply_markup=menu_kb())

@dp.channel_post()
async def channel_reply(m: Message):
    if not SUPPORT_CHANNEL_ID or str(m.chat.id)!=str(SUPPORT_CHANNEL_ID) or not m.reply_to_message: return
    uid=support_threads.get(m.reply_to_message.message_id)
    if not uid:
        raw=m.reply_to_message.text or m.reply_to_message.caption or ""; x=re.search(r"ID(?:՝|:)[^0-9]*(\d+)",raw); uid=int(x.group(1)) if x else None
    if not uid: return
    try:
        if m.text: await bot.send_message(uid,f"📩 <b>Պատասխան Games Vault Shop-ից</b>\n\n{escape(m.text)}",parse_mode="HTML")
        elif m.photo: await bot.send_photo(uid,m.photo[-1].file_id,caption="📩 <b>Պատասխան Games Vault Shop-ից</b>",parse_mode="HTML")
    except Exception: logging.exception("support reply failed")

async def admin(c):
    if ADMIN_ID and c.from_user.id!=ADMIN_ID: await c.answer("❌ Թույլտվություն չկա։",show_alert=True); return False
    return True

@dp.callback_query(F.data.startswith("order:ok:"))
async def order_ok(c):
    if not await admin(c): return
    uid=int(c.data.rsplit(":",1)[1]); await bot.send_message(uid,"✅ <b>Չեկը ընդունված է։</b>",parse_mode="HTML"); await c.answer("✅ Ընդունված է")

@dp.callback_query(F.data.startswith("order:no:"))
async def order_no(c):
    if not await admin(c): return
    uid=int(c.data.rsplit(":",1)[1]); await bot.send_message(uid,"❌ <b>Չեկը մերժված է։</b>",parse_mode="HTML"); await c.answer("❌ Մերժված է")

@dp.callback_query(F.data.startswith("order:refund:"))
async def order_refund(c):
    if not await admin(c): return
    uid=int(c.data.rsplit(":",1)[1]); await bot.send_message(uid,"💸 Վերադարձը կկատարվի ձեռքով։"); await c.answer("💸 Վերադարձ")

@dp.callback_query(F.data=="back:main")
async def back_main(c): await c.message.edit_text(home_text(),reply_markup=menu_kb(),parse_mode="HTML"); await c.answer()

@dp.callback_query(F.data.startswith("back:game:"))
async def back_game(c):
    g=c.data.split(":",2)[2]; await c.message.edit_text(f"{CATALOG[g]['name']}\n\nԸնտրիր ապրանքը։",reply_markup=game_kb(g)); await c.answer()

@dp.callback_query(F.data=="back:product")
async def back_product(c):
    u=user_data(c.from_user.id); g=u.get("game")
    if not g: return await back_main(c)
    text=f"🛒 <b>{escape(u['product'])}</b>\n💰 <b>{u['price']:,} ֏</b>".replace(","," ")
    await c.message.edit_text(text,reply_markup=product_kb(g),parse_mode="HTML"); await c.answer()

@dp.callback_query(F.data=="back:payment")
async def back_payment(c): await buy(c)

async def health(request): return web.Response(text="Games Vault Shop OK")

async def main():
    logging.info("Games Vault Shop bot starting...")
    app=web.Application(); app.router.add_get("/",health); app.router.add_get("/health",health)
    runner=web.AppRunner(app); await runner.setup(); site=web.TCPSite(runner,"0.0.0.0",PORT); await site.start()
    logging.info("HTTP health server started on 0.0.0.0:%s",PORT)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__=="__main__": asyncio.run(main())
