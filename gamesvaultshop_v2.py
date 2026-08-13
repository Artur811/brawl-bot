import os
import asyncio
import logging
import re

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
ORDER_CHANNEL_ID = int(os.getenv("ORDER_CHANNEL_ID", "0"))
SUPPORT_CHANNEL_ID = int(os.getenv("SUPPORT_CHANNEL_ID", "0"))
TELCELL_NUMBER = os.getenv("TELCELL_NUMBER", "043055510")
PORT = int(os.getenv("PORT", "10000"))
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
WEBHOOK_PATH = "/telegram/webhook"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не найден. Добавь BOT_TOKEN в Render Environment Variables.")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
users = {}
orders = {}

CATALOG = {
    "roblox": {"name": "🎮 Roblox", "items": [("40 Robux",350),("80 Robux",650),("120 Robux",950),("400 Robux",2700),("520 Robux",3600),("840 Robux",4850),("1,240 Robux",7300),("1,700 Robux",8800),("1,820 Robux",9700),("4,500 Robux",21000),("10,000 Robux",40000),("22,500 Robux",88000)]},
    "standoff2": {"name": "🔫 Standoff 2", "items": [("100 Gold",1000),("200 Gold",2000),("300 Gold",2900),("500 Gold",4000),("600 Gold",5100),("700 Gold",5800),("1,000 Gold",7100),("1,500 Gold",10300),("3,000 Gold",15800)]},
    "brawlstars": {"name": "⭐ Brawl Stars", "items": [("30 Gems",800),("80 Gems",1600),("170 Gems",3000),("360 Gems",5300),("950 Gems",13000)]},
    "pubg": {"name": "🪂 PUBG Mobile", "items": [("33 UC + 🎁",300),("66 UC + 🎁",500),("99 UC + 🎁",700),("132 UC + 🎁",1000),("150 UC + 🎁",1100),("198 UC + 🎁",1400),("210 UC + 🎁",1600),("325 UC + 🎁",2000),("355 + 5 UC + 🎁",2100),("445 UC + 🎁",2900),("505 UC + 🎁",3400),("660 UC + 🎁",4000),("720 UC + 🎁",4300),("985 UC + 🎁",6000),("1,135 UC + 🎁",7000),("1,320 UC + 🎁",7800),("1,860 UC + 🎁",10000),("2,185 UC + 🎁",11500)]},
    "brawlpass": {"name": "🎫 Brawl Pass", "items": [("Brawl Pass — аккаунт 1",2700),("Brawl Pass — аккаунт 2",3600),("Brawl Pass Plus — аккаунт 1",3600),("Brawl Pass Plus — аккаунт 2",5000),("Pro Pass",12800)]},
}

def user_data(user_id):
    return users.setdefault(user_id, {"game":None,"product":None,"price":None,"state":None,"username":None,"order_id":None,"refund":None})

def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Roblox", callback_data="game:roblox"), InlineKeyboardButton(text="🔫 Standoff 2", callback_data="game:standoff2")],
        [InlineKeyboardButton(text="⭐ Brawl Stars", callback_data="game:brawlstars"), InlineKeyboardButton(text="🪂 PUBG Mobile", callback_data="game:pubg")],
        [InlineKeyboardButton(text="🎫 Brawl Pass", callback_data="game:brawlpass")],
        [InlineKeyboardButton(text="📩 Կապվեք մեզ հետ", callback_data="support")],
    ])

def game_keyboard(game):
    rows = [[InlineKeyboardButton(text=f"⚡ {name} — {price:,} ֏".replace(",", " "), callback_data=f"product:{game}:{i}")] for i,(name,price) in enumerate(CATALOG[game]["items"])]
    rows.append([InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def product_keyboard(game):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Գնել", callback_data="buy")],[InlineKeyboardButton(text="⬅️ Հետ", callback_data=f"back:game:{game}")]])

def payment_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Վճարել եմ", callback_data="paid")],[InlineKeyboardButton(text="💳 Քարտ տրամադրել — հասանելի չէ", callback_data="card_no")],[InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:product")]])

def receipt_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:payment")]])

def refund_keyboard(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💳 Վերադարձ քարտին", callback_data=f"r_card:{user_id}")],[InlineKeyboardButton(text="📱 Վերադարձ հեռախոսահամարին", callback_data=f"r_phone:{user_id}")]])

def admin_order_keyboard(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Ընդունել չեկը", callback_data=f"approve:{user_id}")],[InlineKeyboardButton(text="❌ Մերժել չեկը", callback_data=f"reject:{user_id}")],[InlineKeyboardButton(text="💸 Վերադարձ", callback_data=f"refund:{user_id}")]])

def admin_refund_keyboard(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Վերադարձը կատարված է", callback_data=f"refund_done:{user_id}")]])

def main_text():
    return "🎮 <b>Games Vault Shop</b> ❤️‍🔥\n\n💎 <b>Games Vault Shop-ում՝ միշտ VAULT-Ա!</b>\n\nԸնտրիր խաղը և տես հասանելի ապրանքները։\n\n⚡ Արագ պատվեր\n💳 Telcell Wallet\n🧾 Չեկի հաստատում\n📩 Աջակցություն"

@dp.message(CommandStart())
async def start(message: Message):
    u=user_data(message.from_user.id); u["username"]=message.from_user.username; u["state"]=None
    await message.answer(main_text(), reply_markup=main_keyboard(), parse_mode="HTML")

@dp.message(Command("menu"))
async def menu(message: Message):
    await message.answer(main_text(), reply_markup=main_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("game:"))
async def game_select(callback: CallbackQuery):
    game=callback.data.split(":",1)[1]
    u=user_data(callback.from_user.id); u.update({"game":game,"product":None,"price":None,"state":None,"refund":None})
    await callback.message.edit_text(f"{CATALOG[game]['name']}\n\nԸնտրիր անհրաժեշտ ապրանքը։\n\n💰 Գները նշված են դրամով։", reply_markup=game_keyboard(game))
    await callback.answer()

@dp.callback_query(F.data.startswith("product:"))
async def product_select(callback: CallbackQuery):
    _,game,index=callback.data.split(":")
    index=int(index); product,price=CATALOG[game]["items"][index]
    u=user_data(callback.from_user.id); u.update({"game":game,"product":product,"price":price,"state":None})
    text=f"🛒 <b>Ձեր ընտրությունը</b>\n\n🎮 Խաղ՝ <b>{CATALOG[game]['name']}</b>\n📦 Ապրանք՝ <b>{product}</b>\n💰 Գին՝ <b>{price:,} ֏</b>\n\nՇարունակե՞լ պատվերը։".replace(",", " ")
    await callback.message.edit_text(text, reply_markup=product_keyboard(game), parse_mode="HTML"); await callback.answer()

@dp.callback_query(F.data=="buy")
async def buy(callback: CallbackQuery):
    u=user_data(callback.from_user.id)
    text=f"💳 <b>Վճարում</b>\n\n📦 {u['product']}\n💰 <b>{u['price']:,} ֏</b>\n\nՎճարումը կատարվում է միայն <b>Telcell Wallet</b>-ով։\n\n💳 Քարտով վճարումը՝ <b>հասանելի չէ</b>։\n📱 Telcell Wallet՝ <code>{TELCELL_NUMBER}</code>\n\nՎճարումից հետո սեղմիր «✅ Վճարել եմ»։".replace(",", " ")
    await callback.message.edit_text(text, reply_markup=payment_keyboard(), parse_mode="HTML"); await callback.answer()

@dp.callback_query(F.data=="card_no")
async def card_no(callback: CallbackQuery):
    await callback.answer("💳 Քարտ տրամադրել՝ հասանելի չէ։", show_alert=True)

@dp.callback_query(F.data=="paid")
async def paid(callback: CallbackQuery):
    u=user_data(callback.from_user.id); u["state"]="receipt"
    await callback.message.edit_text("🧾 <b>Ուղարկիր չեկը</b>\n\nՈւղարկիր այստեղ Telcell-ի վճարման չեկի լուսանկարը։", reply_markup=receipt_keyboard(), parse_mode="HTML"); await callback.answer()

@dp.message(F.photo)
async def receipt(message: Message):
    u=user_data(message.from_user.id)
    if u.get("state")!="receipt":
        return
    u["state"]="waiting_admin"; u["username"]=message.from_user.username
    order_id=f"{message.from_user.id}-{message.message_id}"; u["order_id"]=order_id; orders[order_id]=dict(u)
    caption=(f"🧾 <b>ՆՈՐ ՊԱՏՎԵՐ</b>\n\n🆔 Պատվերի ID՝ <code>{order_id}</code>\n👤 Օգտատեր ID՝ <code>{message.from_user.id}</code>\n👤 Username՝ @{message.from_user.username or 'չկա'}\n🎮 Խաղ՝ <b>{CATALOG[u['game']]['name']}</b>\n📦 Ապրանք՝ <b>{u['product']}</b>\n💰 Գումար՝ <b>{u['price']:,} ֏</b>\n🟡 <b>Սպասում է չեկի ստուգման</b>").replace(",", " ")
    if ORDER_CHANNEL_ID:
        await bot.send_photo(ORDER_CHANNEL_ID, message.photo[-1].file_id, caption=caption, reply_markup=admin_order_keyboard(message.from_user.id), parse_mode="HTML")
    elif ADMIN_ID:
        await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption, reply_markup=admin_order_keyboard(message.from_user.id), parse_mode="HTML")
    await message.answer("✅ Չեկը ստացվել է։ Պատվերը ուղարկվել է ստուգման։", parse_mode="HTML")

@dp.callback_query(F.data.startswith("approve:"))
async def approve(callback: CallbackQuery):
    if callback.from_user.id!=ADMIN_ID: await callback.answer("❌ Չունես իրավունք։", show_alert=True); return
    uid=int(callback.data.split(":")[1]); u=user_data(uid); u["state"]="approved"
    await bot.send_message(uid, f"✅ <b>Չեկը ընդունված է։</b>\n\n📦 {u['product']}\n💰 {u['price']:,} ֏\n\nՊատվերը հաստատված է։", parse_mode="HTML")
    try: await callback.message.edit_caption(caption="✅ <b>ՉԵԿԸ ԸՆԴՈՒՆՎԱԾ Է</b>\n\n"+callback.message.caption.replace("🟡 <b>Սպասում է չեկի ստուգման</b>", "✅ <b>Չեկը ընդունված է</b>"), reply_markup=None, parse_mode="HTML")
    except Exception: pass
    await callback.answer("✅ Չեկը ընդունվեց։")

@dp.callback_query(F.data.startswith("reject:"))
async def reject(callback: CallbackQuery):
    if callback.from_user.id!=ADMIN_ID: await callback.answer("❌ Չունես իրավունք։", show_alert=True); return
    uid=int(callback.data.split(":")[1]); u=user_data(uid); u["state"]="rejected"
    await bot.send_message(uid, f"❌ <b>Չեկը մերժվեց։</b>\n\n📦 {u['product']}\n💰 {u['price']:,} ֏\n\nԿապվիր մեզ հետ, եթե կարծում ես, որ սխալ է տեղի ունեցել։", parse_mode="HTML")
    try: await callback.message.edit_caption(caption="❌ <b>ՉԵԿԸ ՄԵՐԺՎԱԾ Է</b>\n\n"+callback.message.caption.replace("🟡 <b>Սպասում է չեկի ստուգման</b>", "❌ <b>Չեկը մերժված է</b>"), reply_markup=None, parse_mode="HTML")
    except Exception: pass
    await callback.answer("❌ Չեկը մերժվեց։")

@dp.callback_query(F.data.startswith("refund:"))
async def refund(callback: CallbackQuery):
    if callback.from_user.id!=ADMIN_ID: await callback.answer("❌ Չունես իրավունք։", show_alert=True); return
    uid=int(callback.data.split(":")[1]); u=user_data(uid); u["state"]="refund_choice"; u["refund"]={}
    await bot.send_message(uid, "💸 <b>Վերադարձ</b>\n\nԸնտրիր, թե որտեղ վերադարձնել գումարը։", reply_markup=refund_keyboard(uid), parse_mode="HTML")
    await callback.message.edit_caption(caption=(callback.message.caption or "")+"\n\n💸 <b>Սպասում է վերադարձի եղանակի ընտրությանը</b>", reply_markup=None, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("r_card:"))
async def refund_card(callback: CallbackQuery):
    uid=int(callback.data.split(":")[1]); u=user_data(uid); u["state"]="refund_card"
    await callback.message.edit_text("💳 <b>Վերադարձ քարտին</b>\n\nՈւղարկիր քարտի համարը, որի վրա պետք է կատարվի վերադարձը։", parse_mode="HTML"); await callback.answer()

@dp.callback_query(F.data.startswith("r_phone:"))
async def refund_phone(callback: CallbackQuery):
    uid=int(callback.data.split(":")[1]); u=user_data(uid); u["state"]="refund_phone"
    await callback.message.edit_text("📱 <b>Վերադարձ հեռախոսահամարին</b>\n\n⚠️ Ուշադրություն՝ վերադարձված գումարը կհամալրի հեռախոսի հաշվեկշիռը և կարող է օգտագործվել զանգերի/կապի համար։\n\nՈւղարկիր հեռախոսահամարը։", parse_mode="HTML"); await callback.answer()

@dp.message(F.text)
async def text_handler(message: Message):
    u=user_data(message.from_user.id)
    state=u.get("state")
    if state=="refund_card":
        u["refund"]={"type":"card","value":message.text}; u["state"]="refund_pending"
        await notify_refund(message.from_user.id, "💳 Քարտ", message.text); await message.answer("✅ Տվյալները ստացվեցին։ Վերադարձը կատարվում է ձեռքով։")
    elif state=="refund_phone":
        u["refund"]={"type":"phone","value":message.text}; u["state"]="refund_pending"
        await notify_refund(message.from_user.id, "📱 Հեռախոսահամար", message.text); await message.answer("✅ Տվյալները ստացվեցին։ Վերադարձը կատարվում է ձեռքով։")
    elif state=="support":
        if SUPPORT_CHANNEL_ID:
            text=f"📩 <b>Նոր հաղորդագրություն</b>\n\n👤 ID՝ <code>{message.from_user.id}</code>\n👤 Username՝ @{message.from_user.username or 'չկա'}\n📝 {message.text}"
            await bot.send_message(SUPPORT_CHANNEL_ID, text, parse_mode="HTML")
            await message.answer("✅ Հաղորդագրությունը ուղարկվեց։ Մենք կպատասխանենք այստեղ։")
        else:
            await message.answer("⚠️ Կապի ալիքը դեռ կարգավորված չէ։")

async def notify_refund(uid, method, value):
    u=user_data(uid)
    text=f"💸 <b>ՆՈՐ ՎԵՐԱԴԱՐՁ</b>\n\n👤 ID՝ <code>{uid}</code>\n📦 {u['product']}\n💰 {u['price']:,} ֏\n{method}՝ <code>{value}</code>\n\n🟡 Սպասում է վերադարձի հաստատմանը".replace(",", " ")
    if ORDER_CHANNEL_ID: await bot.send_message(ORDER_CHANNEL_ID, text, reply_markup=admin_refund_keyboard(uid), parse_mode="HTML")

@dp.callback_query(F.data=="support")
async def support(callback: CallbackQuery):
    u=user_data(callback.from_user.id); u["state"]="support"
    await callback.message.edit_text("📩 <b>Կապվեք մեզ հետ</b>\n\nԳրիր քո հարցը կամ կարծիքը։ Հաղորդագրությունը կուղարկվի մեր աջակցությանը։", parse_mode="HTML"); await callback.answer()

@dp.channel_post()
async def support_reply(message: Message):
    if not SUPPORT_CHANNEL_ID or message.chat.id!=SUPPORT_CHANNEL_ID or not message.reply_to_message:
        return
    raw=message.reply_to_message.text or message.reply_to_message.caption or ""
    m=re.search(r"ID՝ <code>(\d+)</code>", raw)
    if not m: return
    uid=int(m.group(1))
    await bot.send_message(uid, f"📩 <b>Պատասխան աջակցությունից</b>\n\n{message.text or message.caption or ''}", parse_mode="HTML")

@dp.callback_query(F.data.startswith("refund_done:"))
async def refund_done(callback: CallbackQuery):
    if callback.from_user.id!=ADMIN_ID: await callback.answer("❌ Չունես իրավունք։", show_alert=True); return
    uid=int(callback.data.split(":")[1]); u=user_data(uid); u["state"]="refunded"
    await bot.send_message(uid, "✅ <b>Վերադարձը կատարված է։</b>\n\nԵթե վերադարձը կատարվել է հեռախոսահամարին, գումարը ավելացել է հեռախոսի հաշվեկշռին։", parse_mode="HTML")
    await callback.message.edit_reply_markup(reply_markup=None); await callback.answer("✅ Վերադարձը նշվեց որպես կատարված։")

@dp.callback_query(F.data=="back:main")
async def back_main(callback: CallbackQuery):
    await callback.message.edit_text(main_text(), reply_markup=main_keyboard(), parse_mode="HTML"); await callback.answer()

@dp.callback_query(F.data.startswith("back:game:"))
async def back_game(callback: CallbackQuery):
    game=callback.data.split(":",2)[2]; await callback.message.edit_text(f"{CATALOG[game]['name']}\n\nԸնտրիր անհրաժեշտ ապրանքը։", reply_markup=game_keyboard(game)); await callback.answer()

@dp.callback_query(F.data=="back:product")
async def back_product(callback: CallbackQuery):
    u=user_data(callback.from_user.id); game=u.get("game")
    text=f"🛒 <b>Ձեր ընտրությունը</b>\n\n🎮 {CATALOG[game]['name']}\n📦 {u['product']}\n💰 <b>{u['price']:,} ֏</b>\n\nՇարունակե՞լ պատվերը։".replace(","," ")
    await callback.message.edit_text(text, reply_markup=product_keyboard(game), parse_mode="HTML"); await callback.answer()

@dp.callback_query(F.data=="back:payment")
async def back_payment(callback: CallbackQuery):
    u=user_data(callback.from_user.id); text=f"💳 <b>Վճարում</b>\n\n📦 {u['product']}\n💰 <b>{u['price']:,} ֏</b>\n\nՎճարումը կատարվում է միայն <b>Telcell Wallet</b>-ով։\n📱 <code>{TELCELL_NUMBER}</code>".replace(",", " ")
    await callback.message.edit_text(text, reply_markup=payment_keyboard(), parse_mode="HTML"); await callback.answer()

async def health(request):
    return web.Response(text="Games Vault Shop is running")

async def webhook(request):
    if WEBHOOK_SECRET and request.headers.get("X-Telegram-Bot-Api-Secret-Token")!=WEBHOOK_SECRET:
        return web.Response(status=403,text="Forbidden")
    try:
        update=Update.model_validate(await request.json())
        await dp.feed_update(bot, update)
        return web.Response(text="OK")
    except Exception:
        logging.exception("Webhook update error")
        return web.Response(status=500,text="Internal Server Error")

async def main():
    public_url=WEBHOOK_URL or (f"{RENDER_EXTERNAL_URL}{WEBHOOK_PATH}" if RENDER_EXTERNAL_URL else "")
    if not public_url: raise RuntimeError("Нужен WEBHOOK_URL или RENDER_EXTERNAL_URL")
    app=web.Application(); app.router.add_get("/",health); app.router.add_get("/health",health); app.router.add_post(WEBHOOK_PATH,webhook)
    kwargs={"url":public_url,"drop_pending_updates":True}
    if WEBHOOK_SECRET: kwargs["secret_token"]=WEBHOOK_SECRET
    await bot.set_webhook(**kwargs)
    runner=web.AppRunner(app); await runner.setup(); await web.TCPSite(runner,"0.0.0.0",PORT).start()
    logging.info("Games Vault Shop webhook started")
    try:
        while True: await asyncio.sleep(3600)
    finally:
        await runner.cleanup(); await bot.session.close()

if __name__=="__main__": asyncio.run(main())
