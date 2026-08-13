import os, asyncio, logging, re
from html import escape
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
ORDER_CHANNEL_ID = os.getenv("ORDER_CHANNEL_ID", os.getenv("CHANNEL_ID", ""))
SUPPORT_CHANNEL_ID = os.getenv("SUPPORT_CHANNEL_ID", "")
TELCELL_NUMBER = os.getenv("TELCELL_NUMBER", "043055510")
PORT = int(os.getenv("PORT", "10000"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN չգտնվեց")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

users = {}
support_threads = {}

CATALOG = {
    "roblox": {"name": "Roblox", "items": [
        ("40 Robux", 350), ("80 Robux", 650), ("120 Robux", 950), ("400 Robux", 2700),
        ("520 Robux", 3600), ("840 Robux", 4850), ("1,240 Robux", 7300), ("1,700 Robux", 8800),
        ("1,820 Robux", 9700), ("4,500 Robux", 21000), ("10,000 Robux", 40000), ("22,500 Robux", 88000)
    ]},
    "standoff2": {"name": "Standoff 2", "items": [
        ("100 Gold", 1000), ("200 Gold", 2000), ("300 Gold", 2900), ("500 Gold", 4000),
        ("600 Gold", 5100), ("700 Gold", 5800), ("1,000 Gold", 7100), ("1,500 Gold", 10300), ("3,000 Gold", 15800)
    ]},
    "brawlstars": {"name": "Brawl Stars", "items": [
        ("30 Gems", 750), ("80 Gems", 1500), ("170 Gems", 2800), ("360 Gems", 5100), ("950 Gems", 12800),
        ("Brawl Pass", 2650), ("Brawl Pass Plus", 3500), ("Brawl Pass → Plus", 1800), ("Pro Pass", 12000)
    ]},
    "pubg": {"name": "PUBG Mobile", "items": [
        ("60 UC", 250), ("300 UC + 25 UC", 1000), ("600 UC + 60 UC", 1900),
        ("1500 UC + 300 UC", 4500), ("3000 UC + 850 UC", 8500), ("6000 UC + 2100 UC", 16500)
    ]}
}

TELCELL_TEXT = (
    "💎 <b>Games Vault Shop-ից Բարևներ ❤️‍🔥</b>\n\n"
    "💳 Telcell տերմինալով ընտրում եք <b>\"Telcell Wallet\"</b> տարբերակը և գրում եք հեռախոսահամարը <b>\"043055510\"</b>։\n\n"
    "🏦 Ձեզ կտրվի 2 տարբերակ՝ <b>AEB</b> և <b>EvocaBank</b>։ Ընտրում եք ցանկացածը և փոխանցում գումարը։\n\n"
    "🧾 Այնուհետև չեկը նկարում ուղարկում եք մեզ։\n"
    "🆔 Հետո տրամադրում եք ձեր ID-ն։\n\n"
    "⚡ 1-2 րոպեում ստանում եք ձեր Դոնաթը։ ✅❤️‍🔥"
)

def U(uid):
    return users.setdefault(uid, {
        "game": None,
        "product": None,
        "price": None,
        "payment": None,
        "review": False,
        "order_id": None,
        "username": None,
    })

def fmt(n):
    return f"{n:,}".replace(",", " ")

def kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)

def main_kb():
    return kb([
        [InlineKeyboardButton(text="🎮 Roblox", callback_data="game:roblox"), InlineKeyboardButton(text="🎮 Standoff 2", callback_data="game:standoff2")],
        [InlineKeyboardButton(text="🎮 Brawl Stars", callback_data="game:brawlstars"), InlineKeyboardButton(text="🎮 PUBG Mobile", callback_data="game:pubg")],
        [InlineKeyboardButton(text="⭐ Կարծիք / Отзыв", callback_data="review")]
    ])

def game_kb(g):
    rows = []
    for i, (n, p) in enumerate(CATALOG[g]["items"]):
        rows.append([InlineKeyboardButton(text=f"⚡ {n} — {fmt(p)} ֏", callback_data=f"product:{g}:{i}")])
    rows.append([InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:main")])
    return kb(rows)

def product_kb(g):
    return kb([
        [InlineKeyboardButton(text="✅ Գնել", callback_data="buy")],
        [InlineKeyboardButton(text="⬅️ Հետ", callback_data=f"back:game:{g}")]
    ])

def pay_kb():
    return kb([
        [InlineKeyboardButton(text="✅ Վճարել եմ", callback_data="paid")],
        [InlineKeyboardButton(text="💳 Քարտ տրամադրել — հասանելի չէ", callback_data="card:no")],
        [InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:product")]
    ])

def receipt_kb():
    return kb([[InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:payment")]])

def order_kb(uid):
    return kb([
        [InlineKeyboardButton(text="✅ Ընդունել", callback_data=f"ok:{uid}"), InlineKeyboardButton(text="❌ Մերժել", callback_data=f"no:{uid}")],
        [InlineKeyboardButton(text="💎 Վերադարձ", callback_data=f"refund:{uid}")]
    ])

def home():
    return "💎 <b>Games Vault Shop</b> ❤️‍🔥\n\n⚡ <b>Games Vault Shop-ում՝ միշտ VAULT-Ա!</b>\n\n🎮 Ընտրիր խաղը։"

def order_caption(uid, u, status):
    return (
        f"🧾 <b>ՆՈՐ ՊԱՏՎԵՐ</b>\n\n"
        f"👤 @{escape(u.get('username') or 'չկա')}\n"
        f"🆔 <code>{uid}</code>\n"
        f"🎮 {escape(CATALOG[u['game']]['name'])}\n"
        f"📦 {escape(u['product'])}\n"
        f"💰 <b>{fmt(u['price'])} ֏</b>\n\n"
        f"{status}"
    )

@dp.message(CommandStart())
async def start(m: Message):
    u = U(m.from_user.id)
    u["username"] = m.from_user.username
    u["review"] = False
    await m.answer(home(), reply_markup=main_kb(), parse_mode="HTML")

@dp.message(Command("menu"))
async def menu(m: Message):
    await m.answer(home(), reply_markup=main_kb(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("game:"))
async def game(c: CallbackQuery):
    g = c.data.split(":", 1)[1]
    u = U(c.from_user.id)
    u.update(game=g, product=None, price=None, payment=None, review=False)
    await c.message.edit_text(f"🎮 <b>{CATALOG[g]['name']}</b>\n\nԸնտրիր ապրանքը։", reply_markup=game_kb(g), parse_mode="HTML")
    await c.answer()

@dp.callback_query(F.data.startswith("product:"))
async def product(c: CallbackQuery):
    _, g, i = c.data.split(":")
    n, p = CATALOG[g]["items"][int(i)]
    u = U(c.from_user.id)
    u.update(game=g, product=n, price=p, payment=None)
    await c.message.edit_text(
        f"🛒 <b>Ձեր ընտրությունը</b>\n\n"
        f"🎮 {escape(CATALOG[g]['name'])}\n"
        f"📦 <b>{escape(n)}</b>\n"
        f"💰 <b>{fmt(p)} ֏</b>\n\n"
        f"Շարունակե՞լ պատվերը։",
        reply_markup=product_kb(g), parse_mode="HTML"
    )
    await c.answer()

@dp.callback_query(F.data == "buy")
async def buy(c: CallbackQuery):
    await c.message.edit_text(
        "💳 <b>Վճարում</b>\n\nՎճարումը կատարվում է Telcell Wallet-ով։",
        reply_markup=pay_kb(), parse_mode="HTML"
    )
    await c.answer()

@dp.callback_query(F.data == "card:no")
async def card_no(c: CallbackQuery):
    await c.answer("💳 Քարտ տրամադրել — հասանելի չէ", show_alert=True)

@dp.callback_query(F.data == "paid")
async def paid(c: CallbackQuery):
    u = U(c.from_user.id)
    u["payment"] = "receipt"
    u["order_id"] = f"{c.from_user.id}-{c.message.message_id}"
    await c.message.edit_text(
        TELCELL_TEXT + "\n\n🧾 Ուղարկիր չեկի նկարը։",
        reply_markup=receipt_kb(), parse_mode="HTML"
    )
    await c.answer()

@dp.message(F.photo)
async def receipt(m: Message):
    u = U(m.from_user.id)
    if u.get("payment") != "receipt":
        return
    u["payment"] = "sent"
    u["username"] = m.from_user.username
    if not ORDER_CHANNEL_ID:
        return await m.answer("❌ ORDER_CHANNEL_ID-ը չի կարգավորված։")
    await bot.send_photo(
        ORDER_CHANNEL_ID,
        m.photo[-1].file_id,
        caption=order_caption(m.from_user.id, u, "🟡 Սպասում է ստուգման"),
        reply_markup=order_kb(m.from_user.id),
        parse_mode="HTML"
    )
    await m.answer("✅ Չեկը ստացվեց։ Սպասիր ստուգմանը։", reply_markup=main_kb())

@dp.callback_query(F.data == "review")
async def review(c: CallbackQuery):
    u = U(c.from_user.id)
    u["review"] = True
    await c.message.edit_text(
        "⭐ <b>Կարծիք Games Vault Shop-ի մասին</b> ❤️‍🔥\n\nԳրիր քո կարծիքը հաջորդ հաղորդագրությամբ։",
        reply_markup=kb([[InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:main")]]),
        parse_mode="HTML"
    )
    await c.answer()

@dp.message(F.text)
async def text(m: Message):
    u = U(m.from_user.id)
    if not u.get("review"):
        return
    if not SUPPORT_CHANNEL_ID:
        return await m.answer("❌ SUPPORT_CHANNEL_ID-ը չի կարգավորված։")
    sent = await bot.send_message(
        SUPPORT_CHANNEL_ID,
        f"⭐ <b>ՆՈՐ ԿԱՐԾԻՔ</b> ❤️‍🔥\n\n"
        f"👤 @{escape(m.from_user.username or 'չկա')}\n"
        f"🆔 <code>{m.from_user.id}</code>\n\n"
        f"💬 {escape(m.text)}",
        parse_mode="HTML"
    )
    support_threads[sent.message_id] = m.from_user.id
    u["review"] = False
    await m.answer("✅ Ձեր կարծիքը ստացվեց։", reply_markup=main_kb())

@dp.channel_post()
async def channel_post(m: Message):
    if not SUPPORT_CHANNEL_ID or str(m.chat.id) != str(SUPPORT_CHANNEL_ID) or not m.reply_to_message:
        return
    uid = support_threads.get(m.reply_to_message.message_id)
    if not uid:
        raw = m.reply_to_message.text or m.reply_to_message.caption or ""
        z = re.search(r"ID[^0-9]*(\d+)", raw)
        uid = int(z.group(1)) if z else None
    if not uid:
        return
    try:
        if m.text:
            await bot.send_message(uid, f"📩 <b>Պատասխան Games Vault Shop-ից</b> ❤️‍🔥\n\n{escape(m.text)}", parse_mode="HTML")
        elif m.photo:
            await bot.send_photo(uid, m.photo[-1].file_id, caption="📩 <b>Պատասխան Games Vault Shop-ից</b> ❤️‍🔥", parse_mode="HTML")
    except Exception:
        logging.exception("support reply failed")

async def admin(c):
    if ADMIN_ID and c.from_user.id != ADMIN_ID:
        await c.answer("❌ Թույլտվություն չկա։", show_alert=True)
        return False
    return True

@dp.callback_query(F.data.startswith("ok:"))
async def ok(c: CallbackQuery):
    if not await admin(c):
        return
    uid = int(c.data.split(":")[1])
    await bot.send_message(uid, "✅ <b>Չեկը ընդունված է։</b>\n\nՁեր պատվերը ընդունվել է։", parse_mode="HTML")
    await c.answer("✅ Ընդունված է")

@dp.callback_query(F.data.startswith("no:"))
async def no(c: CallbackQuery):
    if not await admin(c):
        return
    uid = int(c.data.split(":")[1])
    await bot.send_message(uid, "❌ <b>Չեկը մերժված է։</b>\n\nԿարող եք ուղարկել նոր չեկ։", parse_mode="HTML")
    await c.answer("❌ Մերժված է")

@dp.callback_query(F.data.startswith("refund:"))
async def refund(c: CallbackQuery):
    if not await admin(c):
        return
    uid = int(c.data.split(":")[1])
    await bot.send_message(uid, "💎 Վերադարձը կկատարվի ձեռքով։")
    await c.answer("💎 Վերադարձ")

@dp.callback_query(F.data == "back:main")
async def back_main(c: CallbackQuery):
    await c.message.edit_text(home(), reply_markup=main_kb(), parse_mode="HTML")
    await c.answer()

@dp.callback_query(F.data.startswith("back:game:"))
async def back_game(c: CallbackQuery):
    g = c.data.split(":", 2)[2]
    await c.message.edit_text(f"🎮 <b>{CATALOG[g]['name']}</b>\n\nԸնտրիր ապրանքը։", reply_markup=game_kb(g), parse_mode="HTML")
    await c.answer()

@dp.callback_query(F.data == "back:product")
async def back_product(c: CallbackQuery):
    u = U(c.from_user.id)
    g = u.get("game")
    if not g or not u.get("product"):
        return await back_main(c)
    await c.message.edit_text(
        f"🛒 <b>{escape(u['product'])}</b>\n💰 <b>{fmt(u['price'])} ֏</b>",
        reply_markup=product_kb(g), parse_mode="HTML"
    )
    await c.answer()

@dp.callback_query(F.data == "back:payment")
async def back_payment(c: CallbackQuery):
    await buy(c)

async def health(request):
    return web.Response(text="Games Vault Shop OK")

async def main():
    logging.info("Games Vault Shop bot starting...")
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    logging.info("HTTP health server started on 0.0.0.0:%s", PORT)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
