import os
import asyncio
import logging
from html import escape
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

BOT_TOKEN=os.getenv("BOT_TOKEN")
ADMIN_ID=int(os.getenv("ADMIN_ID","0"))
ORDER_CHANNEL_ID=os.getenv("ORDER_CHANNEL_ID","")
SUPPORT_CHANNEL_ID=os.getenv("SUPPORT_CHANNEL_ID","")
PORT=int(os.getenv("PORT","10000"))
TELCELL_NUMBER="055363432"
if not BOT_TOKEN: raise RuntimeError("BOT_TOKEN չգտնվեց")
bot=Bot(BOT_TOKEN); dp=Dispatcher(); users={}; support_map={}; orders={}
logging.basicConfig(level=logging.INFO,format="%(asctime)s | %(levelname)s | %(message)s")

CATALOG={
"roblox":{"name":"🎮 Roblox","items":[("40 Robux",350),("80 Robux",650),("120 Robux",950),("400 Robux",2700),("520 Robux",3600),("840 Robux",4850),("1,240 Robux",7300),("1,700 Robux",8800),("1,820 Robux",9700),("4,500 Robux",21000),("10,000 Robux",40000),("22,500 Robux",88000)]},
"standoff2":{"name":"🔫 Standoff 2","items":[("100 Gold",1000),("200 Gold",2000),("300 Gold",2900),("500 Gold",4000),("600 Gold",5100),("700 Gold",5800),("1,000 Gold",7100),("1,500 Gold",10300),("3,000 Gold",15800)]},
"brawlstars":{"name":"⭐ Brawl Stars","items":[("30 Gems",800),("80 Gems",1600),("170 Gems",3000),("360 Gems",5300),("950 Gems",13000),("🎫 Brawl Pass — аккаунт 1",2700),("🎫 Brawl Pass — аккаунт 2",3600),("🎫 Brawl Pass Plus — аккаунт 1",3600),("🎫 Brawl Pass Plus — аккаунт 2",5000),("🎫 Pro Pass",12800)]},
"pubg":{"name":"🪂 PUBG Mobile","items":[("33 UC + 🎁",300),("66 UC + 🎁",500),("99 UC + 🎁",700),("132 UC + 🎁",1000),("150 UC + 🎁",1100),("198 UC + 🎁",1400),("210 UC + 🎁",1600),("325 UC + 🎁",2000),("355 + 5 UC + 🎁",2100),("445 UC + 🎁",2900),("505 UC + 🎁",3400),("660 UC + 🎁",4000),("720 UC + 🎁",4300),("985 UC + 🎁",6000),("1,135 UC + 🎁",7000),("1,320 UC + 🎁",7800),("1,860 UC + 🎁",10000),("2,185 UC + 🎁",11500)]}}

def U(uid): return users.setdefault(uid,{"game":None,"product":None,"price":None,"state":None,"order_id":None,"support":False})
def main_kb(): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎮 Roblox",callback_data="g:roblox")],[InlineKeyboardButton(text="🔫 Standoff 2",callback_data="g:standoff2")],[InlineKeyboardButton(text="⭐ Brawl Stars",callback_data="g:brawlstars")],[InlineKeyboardButton(text="🪂 PUBG Mobile",callback_data="g:pubg")],[InlineKeyboardButton(text="📩 Կապվեք մեզ հետ",callback_data="support")]])
def game_kb(g): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"⚡ {n} — {p:,} ֏".replace(","," "),callback_data=f"p:{g}:{i}")] for i,(n,p) in enumerate(CATALOG[g]["items"])] + [[InlineKeyboardButton(text="⬅️ Հետ",callback_data="home")]])
def product_kb(g): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Գնել",callback_data="buy")],[InlineKeyboardButton(text="⬅️ Հետ",callback_data=f"bg:{g}")]])
def pay_kb(): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Վճարել եմ",callback_data="paid")],[InlineKeyboardButton(text="💳 Քարտ տրամադրել — հասանելի չէ",callback_data="card")],[InlineKeyboardButton(text="⬅️ Հետ",callback_data="bp")]])
def receipt_kb(): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Հետ",callback_data="bpay")]])
def order_kb(uid): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Ընդունել չեկը",callback_data=f"ok:{uid}")],[InlineKeyboardButton(text="❌ Մերժել չեկը",callback_data=f"no:{uid}")],[InlineKeyboardButton(text="💸 Վերադարձ կատարել",callback_data=f"ref:{uid}")]])
def refund_kb(uid): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💳 Վերադարձ քարտին",callback_data=f"rc:{uid}")],[InlineKeyboardButton(text="📱 Վերադարձ հեռախոսահամարին",callback_data=f"rp:{uid}")]])
def done_kb(uid,m): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Վերադարձը կատարված է",callback_data=f"rd:{m}:{uid}")]])

def main_text(): return "🎮 <b>Games Vault Shop</b> ❤️‍🔥\n\n💎 <b>Games Vault Shop-ում՝ միշտ VAULT-Ա!</b>\n\nԸնտրիր խաղը։"
def telcell_text(): return 'OK-ից Բարևներ😎❤️‍🔥🥕🐣Telcell տերմինալով ընտրում եք "Telcell Wallet" տարբերակը և գրում եք հեռախոսահամարը "055363432"🏌️\n\nՁեզ կտրվի 2 տարբերակ ընտրելու\n"AEB և EvocaBank" ընտրում եք ցանկացածը և գումարը փոխանցում, ապա Չեկը նկարում ուղղարկում մեզ, ապա📝տրամադրում եք ID-ն և 1-2 րոպեում ստանում եք ձեր Դոնաթը✅❤️'
def product_text(u): return f"🛒 <b>Ձեր ընտրությունը</b>\n\n🎮 Խաղ՝ <b>{escape(CATALOG[u['game']]['name'])}</b>\n📦 Ապրանք՝ <b>{escape(u['product'])}</b>\n💰 Գին՝ <b>{u['price']:,} ֏</b>\n\nՇարունակե՞լ պատվերը։".replace(","," ")

@dp.message(CommandStart())
async def start(m:Message): U(m.from_user.id)["support"]=False; await m.answer(main_text(),reply_markup=main_kb(),parse_mode="HTML")
@dp.message(Command("menu"))
async def menu(m:Message): await m.answer(main_text(),reply_markup=main_kb(),parse_mode="HTML")
@dp.callback_query(F.data.startswith("g:"))
async def game(c:CallbackQuery):
 g=c.data[2:]; u=U(c.from_user.id); u.update(game=g,product=None,price=None,state=None); await c.message.edit_text(f"{CATALOG[g]['name']}\n\nԸնտրիր ապրանքը։",reply_markup=game_kb(g)); await c.answer()
@dp.callback_query(F.data.startswith("p:"))
async def product(c:CallbackQuery):
 _,g,i=c.data.split(":"); n,p=CATALOG[g]["items"][int(i)]; u=U(c.from_user.id); u.update(game=g,product=n,price=p); await c.message.edit_text(product_text(u),reply_markup=product_kb(g),parse_mode="HTML"); await c.answer()
@dp.callback_query(F.data=="buy")
async def buy(c:CallbackQuery): await c.message.edit_text(telcell_text(),reply_markup=pay_kb()); await c.answer()
@dp.callback_query(F.data=="card")
async def card(c:CallbackQuery): await c.answer("💳 Քարտով վճարումը հասանելի չէ։",show_alert=True)
@dp.callback_query(F.data=="paid")
async def paid(c:CallbackQuery): U(c.from_user.id)["state"]="receipt"; await c.message.edit_text("🧾 <b>Ուղարկիր վճարման չեկը</b>\n\nՈւղարկիր չեկի լուսանկարը այստեղ։",reply_markup=receipt_kb(),parse_mode="HTML"); await c.answer()
@dp.message(F.photo)
async def receipt(m:Message):
 u=U(m.from_user.id)
 if u.get("state")!="receipt": return
 u["state"]="waiting"; u["order_id"]=f"{m.from_user.id}-{m.message_id}"; orders[m.from_user.id]=u.copy()
 cap=f"🧾 <b>ՆՈՐ ՊԱՏՎԵՐ</b>\n\n🆔 ID՝ <code>{m.from_user.id}</code>\n📦 {escape(u['product'])}\n💰 <b>{u['price']:,} ֏</b>\n🔖 <code>{u['order_id']}</code>\n\n🟡 <b>Սպասում է չեկի ստուգման</b>".replace(","," ")
 target=ORDER_CHANNEL_ID or ADMIN_ID
 if target: await bot.send_photo(target,m.photo[-1].file_id,caption=cap,reply_markup=order_kb(m.from_user.id),parse_mode="HTML")
 await m.answer("✅ Չեկը ստացվեց։ Սպասիր ստուգմանը։",reply_markup=main_kb())
@dp.callback_query(F.data.startswith("ok:"))
async def ok(c:CallbackQuery):
 if c.from_user.id!=ADMIN_ID: await c.answer("❌ Թույլտվություն չկա։",show_alert=True); return
 uid=int(c.data[3:]); U(uid)["state"]="accepted"; await bot.send_message(uid,"✅ <b>Չեկը ընդունված է։</b> Պատվերը հաստատվեց։",parse_mode="HTML"); await c.answer("✅ Ընդունված է։")
@dp.callback_query(F.data.startswith("no:"))
async def no(c:CallbackQuery):
 if c.from_user.id!=ADMIN_ID: await c.answer("❌ Թույլտվություն չկա։",show_alert=True); return
 uid=int(c.data[3:]); U(uid)["state"]="rejected"; await bot.send_message(uid,"❌ <b>Չեկը մերժված է։</b>",parse_mode="HTML"); await c.answer("❌ Մերժված է։")
@dp.callback_query(F.data.startswith("ref:"))
async def ref(c:CallbackQuery):
 if c.from_user.id!=ADMIN_ID: await c.answer("❌ Թույլտվություն չկա։",show_alert=True); return
 uid=int(c.data[4:]); await c.message.answer("💸 <b>Ընտրեք վերադարձի եղանակը</b>",reply_markup=refund_kb(uid),parse_mode="HTML"); await c.answer()
@dp.callback_query(F.data.startswith("rc:"))
async def rc(c:CallbackQuery):
 if c.from_user.id!=ADMIN_ID: await c.answer("❌ Թույլտվություն չկա։",show_alert=True); return
 uid=int(c.data[3:]); U(uid)["state"]="refund_card"; await c.message.edit_text("💳 <b>Վերադարձ քարտին</b>\n\nԳումարը փոխանցեք քարտին, ապա սեղմեք кнопку ниже։",reply_markup=done_kb(uid,"card"),parse_mode="HTML"); await bot.send_message(uid,"💳 Վերադարձը կատարվում է քարտին։",parse_mode="HTML"); await c.answer()
@dp.callback_query(F.data.startswith("rp:"))
async def rp(c:CallbackQuery):
 if c.from_user.id!=ADMIN_ID: await c.answer("❌ Թույլտվություն չկա։",show_alert=True); return
 uid=int(c.data[3:]); U(uid)["state"]="refund_phone"; await c.message.edit_text("📱 <b>Վերադարձ հեռախոսահամարին</b>\n\n⚠️ Գումարը կավելացվի հեռախոսի հաշվեկշռին՝ զանգերի/խոսակցությունների բալանսին։",reply_markup=done_kb(uid,"phone"),parse_mode="HTML"); await bot.send_message(uid,"📱 ⚠️ Վերադարձը կավելացվի հեռախոսի հաշվեկշռին՝ զանգերի/խոսակցությունների բալանսին։",parse_mode="HTML"); await c.answer()
@dp.callback_query(F.data.startswith("rd:"))
async def rd(c:CallbackQuery):
 if c.from_user.id!=ADMIN_ID: await c.answer("❌ Թույլտվություն չկա։",show_alert=True); return
 _,method,uidt=c.data.split(":"); uid=int(uidt); U(uid)["state"]="refunded"; text="քարտին" if method=="card" else "հեռախոսահամարին"; await bot.send_message(uid,f"✅ <b>Վերադարձը կատարված է։</b> Գումարը վերադարձվել է {text}։",parse_mode="HTML"); await c.message.edit_text(f"✅ <b>Վերադարձը կատարված է — {text}</b>",parse_mode="HTML"); await c.answer()
@dp.callback_query(F.data=="support")
async def support(c:CallbackQuery):
 U(c.from_user.id)["support"]=True; await c.message.edit_text("📩 <b>Կապվեք մեզ հետ</b>\n\nԳրեք ձեր հարցը կամ կարծիքը հաջորդ հաղորդագրությամբ։",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Հետ",callback_data="home")]]),parse_mode="HTML"); await c.answer()
@dp.message(F.text)
async def support_msg(m:Message):
 u=U(m.from_user.id)
 if not u.get("support") or not SUPPORT_CHANNEL_ID: return
 sent=await bot.send_message(SUPPORT_CHANNEL_ID,f"📩 <b>ՆՈՐ ՀԱՐՑ / ԿԱՐԾԻՔ</b>\n\n👤 @{escape(m.from_user.username or 'չկա')}\n🆔 <code>{m.from_user.id}</code>\n\n💬 {escape(m.text)}\n\n↩️ Պատասխանեք Reply-ով այս հաղորդագրությանը։",parse_mode="HTML"); support_map[sent.message_id]=m.from_user.id; u["support"]=False; await m.answer("✅ Հաղորդագրությունը ստացվեց։",reply_markup=main_kb())
@dp.channel_post(F.text)
async def support_reply(m:Message):
 r=m.reply_to_message
 if not r: return
 uid=support_map.get(r.message_id)
 if uid: await bot.send_message(uid,f"📩 <b>Պատասխան Games Vault Shop-ից</b>\n\n{escape(m.text)}",parse_mode="HTML")
@dp.callback_query(F.data=="home")
async def home(c:CallbackQuery): await c.message.edit_text(main_text(),reply_markup=main_kb(),parse_mode="HTML"); await c.answer()
@dp.callback_query(F.data.startswith("bg:"))
async def bg(c:CallbackQuery):
 g=c.data[3:]; await c.message.edit_text(f"{CATALOG[g]['name']}\n\nԸնտրիր ապրանքը։",reply_markup=game_kb(g)); await c.answer()
@dp.callback_query(F.data=="bp")
async def bp(c:CallbackQuery): await c.message.edit_text(product_text(U(c.from_user.id)),reply_markup=product_kb(U(c.from_user.id)["game"]),parse_mode="HTML"); await c.answer()
@dp.callback_query(F.data=="bpay")
async def bpay(c:CallbackQuery): await c.message.edit_text(telcell_text(),reply_markup=pay_kb()); await c.answer()

async def health(req): return web.Response(text="Games Vault Shop is running")
async def main():
 app=web.Application(); app.router.add_get("/",health); app.router.add_head("/",health); runner=web.AppRunner(app); await runner.setup(); await web.TCPSite(runner,"0.0.0.0",PORT).start(); logging.info("Games Vault Shop started"); await dp.start_polling(bot)
if __name__=="__main__": asyncio.run(main())
