import os
import asyncio
import json
import logging
from pathlib import Path
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
STATE_FILE = Path(os.getenv("STATE_FILE", "orders_state.json"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN չգտնվեց։ Ավելացրու BOT_TOKEN-ը Render-ի Environment Variables-ում։")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
users = {}
state_lock = asyncio.Lock()

BRAWL_PASS_PRICES = {"brawl_pass": (2500, 3400), "brawl_pass_plus": (3400, 4800)}
CATALOG = {
    "roblox": {"name":"🎮 Roblox", "items":[("40 Robux",350),("80 Robux",650),("120 Robux",950),("400 Robux",2700),("520 Robux",3600),("840 Robux",4850),("1,240 Robux",7300),("1,700 Robux",8800),("1,820 Robux",9700),("4,500 Robux",21000),("10,000 Robux",40000),("22,500 Robux",88000)]},
    "standoff2": {"name":"🔫 Standoff 2", "items":[("100 Gold",1000),("200 Gold",2000),("300 Gold",2900),("500 Gold",4000),("600 Gold",5100),("700 Gold",5800),("1,000 Gold",7100),("1,500 Gold",10300),("3,000 Gold",15800)]},
    "brawlstars": {"name":"⭐ Brawl Stars", "items":[("30 Gems",750),("80 Gems",1500),("170 Gems",2800),("360 Gems",5100),("950 Gems",12800),("Brawl Pass",2500),("Brawl Pass+",3400),("Прокачка Brawl Pass → Brawl Pass+",1800),("Pro Pass",12300)]},
    "pubg": {"name":"🪂 PUBG Mobile", "items":[("33 UC + 🎁",300),("66 UC + 🎁",500),("99 UC + 🎁",700),("132 UC + 🎁",1000),("150 UC + 🎁",1100),("198 UC + 🎁",1400),("210 UC + 🎁",1600),("325 UC + 🎁",2000),("355 + 5 UC + 🎁",2100),("445 UC + 🎁",2900),("505 UC + 🎁",3400),("660 UC + 🎁",4000),("720 UC + 🎁",4300),("985 UC + 🎁",6000),("1,135 UC + 🎁",7000),("1,320 UC + 🎁",7800),("1,860 UC + 🎁",10000),("2,185 UC + 🎁",11500)]}
}


def blank_user():
    return {"game":None,"product":None,"price":None,"username":None,"payment":None,"order_id":None,"brawl_pass_type":None,"brawl_pass_waiting":False,"receipt_waiting_id":False,"receipt_order_message_id":None,"receipt_accepted":False,"refund_waiting":False,"refund_method":None,"refund_operator":None,"refund_details_ready":False,"game_id":None}


def load_state():
    global users
    try:
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text("utf-8"))
            users = {int(k): v for k, v in data.items()}
            for uid in list(users):
                base = blank_user()
                base.update(users[uid])
                users[uid] = base
            logging.info("Loaded %s saved user/order states", len(users))
    except Exception:
        logging.exception("Could not load saved order state")
        users = {}


async def save_state():
    async with state_lock:
        try:
            tmp = STATE_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(users, ensure_ascii=False), "utf-8")
            tmp.replace(STATE_FILE)
        except Exception:
            logging.exception("Could not save order state")


def get_user(uid):
    if uid not in users:
        users[uid] = blank_user()
    else:
        base = blank_user()
        base.update(users[uid])
        users[uid] = base
    return users[uid]


def fmt(v): return f"{v:,}".replace(","," ")

def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎮 Roblox",callback_data="game:roblox"),InlineKeyboardButton(text="🔫 Standoff 2",callback_data="game:standoff2")],[InlineKeyboardButton(text="⭐ Brawl Stars",callback_data="game:brawlstars"),InlineKeyboardButton(text="🪂 PUBG Mobile",callback_data="game:pubg")],[InlineKeyboardButton(text="📩 Կապվեք մեզ հետ",callback_data="contact:open")]])

def game_kb(game):
    rows=[]
    for i,(name,price) in enumerate(CATALOG[game]["items"]):
        if game=="brawlstars" and name=="Brawl Pass": t="🎫 Brawl Pass — 2 500 / 3 400 ֏"
        elif game=="brawlstars" and name=="Brawl Pass+": t="⭐ Brawl Pass+ — 3 400 / 4 800 ֏"
        else: t=f"⚡ {name} — {fmt(price)} ֏"
        rows.append([InlineKeyboardButton(text=t,callback_data=f"product:{game}:{i}")])
    rows.append([InlineKeyboardButton(text="⬅️ Հետ",callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def product_kb(game):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Գնել",callback_data="buy:confirm")],[InlineKeyboardButton(text="⬅️ Հետ",callback_data=f"back:game:{game}")]])

def payment_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💳 Վճարել քարտով",callback_data="payment:card")],[InlineKeyboardButton(text="💵 Վճարել կանխիկ",callback_data="payment:cash")],[InlineKeyboardButton(text="⬅️ Հետ",callback_data="back:product")]])

def receipt_kb(): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🧾 Ուղարկել չեկի նկարը",callback_data="payment:done")],[InlineKeyboardButton(text="⬅️ Հետ",callback_data="back:payment")]])

def admin_kb(uid,accepted=False,refund_ready=False):
    rows=[[InlineKeyboardButton(text="❌ Մերժել չեկը",callback_data=f"receipt:reject:{uid}"),InlineKeyboardButton(text="✅ Հաստատել չեկը",callback_data=f"receipt:accept:{uid}")],[InlineKeyboardButton(text="💸 Տրամադրել հետ գումարը",callback_data=f"receipt:refund:{uid}")]]
    if accepted: rows.append([InlineKeyboardButton(text="📦 Հաստատել պատվերը",callback_data=f"receipt:confirm:{uid}")])
    if refund_ready: rows.append([InlineKeyboardButton(text="✅ Հետ գումարի վերադարձը ավարտված է",callback_data=f"receipt:refund_complete:{uid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def refund_method_kb(): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📱 Հեռախոսահամարին",callback_data="refundclient:phone")],[InlineKeyboardButton(text="💳 Քարտին",callback_data="refundclient:card")]])

def operators_kb(): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📞 Viva",callback_data="refundclient:operator:Viva")],[InlineKeyboardButton(text="📞 Team Telecom Armenia",callback_data="refundclient:operator:Team Telecom Armenia")],[InlineKeyboardButton(text="📞 Ucom",callback_data="refundclient:operator:Ucom")],[InlineKeyboardButton(text="⬅️ Հետ",callback_data="refundclient:back")]])

def back_kb(cb): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Հետ",callback_data=cb)]])

def main_text(): return "💎 <b>Games Vault Shop</b> ❤️‍🔥\n\n💎 <b>Games Vault Shop-ում՝ միշտ VAULT-Ա!</b>\n\n🎮 Ընտրիր խաղը և տես հասանելի ապրանքները։\n\n⚡ Արագ պատվեր\n💳 Telcell Wallet\n🧾 Չեկի ստուգում\n📩 Աջակցություն և կապ\n\n❗ Գնումից առաջ ստուգիր ապրանքի տեսակը և գինը։"

def order_summary(uid,user,status):
    game=CATALOG.get(user.get("game"),{}).get("name","չկա")
    game_id=f"\n🎮 Game ID՝ <code>{escape(str(user.get('game_id')))}</code>" if user.get("game_id") else ""
    return f"🧾 <b>ՊԱՏՎԵՐԻ ԱՄՓՈՓՈՒՄ</b>\n\n👤 Username՝ @{escape(user.get('username') or 'չկա')}\n🆔 Telegram ID՝ <code>{uid}</code>{game_id}\n🎮 Խաղ՝ <b>{escape(game)}</b>\n📦 Ապրանք՝ <b>{escape(user.get('product') or 'չկա')}</b>\n💰 Գին՝ <b>{fmt(user.get('price') or 0)} ֏</b>\n🔖 Պատվեր՝ <code>{escape(user.get('order_id') or str(uid))}</code>\n\n📌 <b>Կարգավիճակ՝ {status}</b>"

def final_status(uid,user,status):
    game=CATALOG.get(user.get("game"),{}).get("name","չկա")
    game_id=f"\n🎮 Game ID՝ <code>{escape(str(user.get('game_id')))}</code>" if user.get("game_id") else ""
    return f"🧾 <b>ՊԱՏՎԵՐԻ ԿԱՐԳԱՎԻՃԱԿ</b>\n\n👤 Գնորդ՝ @{escape(user.get('username') or 'չկա')}\n🎮 Խաղ՝ <b>{escape(game)}</b>{game_id}\n📦 Ապրանք՝ <b>{escape(user.get('product') or 'չկա')}</b>\n💰 Գին՝ <b>{fmt(user.get('price') or 0)} ֏</b>\n\n📌 <b>Կարգավիճակ՝ {status}</b>"

def cash_text(u):
    return f"💎 <b>Games Vault Shop-ից Բարևներ</b> ❤️‍🔥\n\n💵 <b>Վճարման քայլերը՝</b>\n\n1️⃣ Telcell տերմինալում ընտրեք <b>«Telcell Wallet»</b> և մուտքագրեք հեռախոսահամարը՝ <code>{escape(TELCELL_NUMBER)}</code> 📱\n\n2️⃣ Կատարեք վճարումը՝ <b>{fmt(u['price'])} ֏</b> 💰\n\n3️⃣ 🧾 Վճարումից հետո նկարեք չեկը և ուղարկեք մեզ։\n\n4️⃣ 🆔 Այնուհետև տրամադրեք ձեր ID-ն։\n\n⚡ <b>1–2 րոպեում ստանում եք ձեր Դոնաթը։</b> ✅❤️‍🔥\n\n📦 Պատվեր՝ <b>{escape(u['product'])}</b>"

async def notify(uid,text,markup=None):
    try: await bot.send_message(uid,text,parse_mode="HTML",reply_markup=markup)
    except Exception: logging.exception("notify failed")

async def finalize(uid,status,client_text):
    u=get_user(uid)
    mid=u.get("receipt_order_message_id")
    if mid and ORDER_CHANNEL_ID:
        try: await bot.delete_message(ORDER_CHANNEL_ID,mid)
        except Exception: logging.exception("delete order message failed")
    if ORDER_CHANNEL_ID:
        try: await bot.send_message(ORDER_CHANNEL_ID,final_status(uid,u,status),parse_mode="HTML")
        except Exception: logging.exception("final status message failed")
    await notify(uid,client_text,main_kb())
    users[uid]=blank_user()
    await save_state()

@dp.message(CommandStart())
async def start(m):
    u=get_user(m.from_user.id); u["username"]=m.from_user.username
    await save_state()
    await m.answer(main_text(),reply_markup=main_kb(),parse_mode="HTML")

@dp.message(Command("menu"))
async def menu(m): await m.answer(main_text(),reply_markup=main_kb(),parse_mode="HTML")

@dp.callback_query(F.data.startswith("game:"))
async def game(c):
    g=c.data.split(":",1)[1]; u=get_user(c.from_user.id); u.update({"game":g,"product":None,"price":None,"payment":None,"brawl_pass_type":None,"brawl_pass_waiting":False,"receipt_waiting_id":False,"receipt_order_message_id":None,"receipt_accepted":False,"game_id":None})
    await save_state()
    await c.message.edit_text(f"{CATALOG[g]['name']}\n\n📦 Ընտրիր անհրաժեշտ ապրանքը։\n\n💰 Բոլոր գները նշված են դրամով։",reply_markup=game_kb(g),parse_mode="HTML"); await c.answer()

@dp.callback_query(F.data.startswith("product:"))
async def product(c):
    _,g,i=c.data.split(":"); name,price=CATALOG[g]["items"][int(i)]; u=get_user(c.from_user.id); u.update({"game":g,"product":name,"price":price,"username":c.from_user.username})
    if g=="brawlstars" and name in {"Brawl Pass","Brawl Pass+"}:
        u["brawl_pass_type"]="brawl_pass" if name=="Brawl Pass" else "brawl_pass_plus"; u["brawl_pass_waiting"]=True
        await save_state()
        await c.message.edit_text(f"📸 <b>Ուղարկիր screenshot-ը, որտեղ հստակ երևում է քո {escape(name)}-ի գինը։</b>\n\n👨‍💼 Screenshot-ը կստանա ադմինը և ինքը կընտրի ճիշտ գինը։",reply_markup=back_kb("back:game:brawlstars"),parse_mode="HTML"); await c.answer(); return
    await save_state()
    await c.message.edit_text(f"🛒 <b>Ձեր ընտրությունը</b>\n\n🎮 Խաղ՝ <b>{escape(CATALOG[g]['name'])}</b>\n📦 Ապրանք՝ <b>{escape(name)}</b>\n💰 Գին՝ <b>{fmt(price)} ֏</b>\n\nՇարունակե՞լ պատվերը։",reply_markup=product_kb(g),parse_mode="HTML"); await c.answer()

@dp.message(F.photo)
async def photo(m):
    u=get_user(m.from_user.id)
    if u.get("brawl_pass_waiting"):
        u["brawl_pass_waiting"]=False; p=u["brawl_pass_type"]; low,high=BRAWL_PASS_PRICES[p]; title="Brawl Pass" if p=="brawl_pass" else "Brawl Pass+"
        sent=await bot.send_photo(ORDER_CHANNEL_ID,m.photo[-1].file_id,caption=f"📸 <b>BRAWL PASS SCREENSHOT</b>\n\n👤 @{escape(m.from_user.username or 'չկա')}\n🆔 <code>{m.from_user.id}</code>\n📦 <b>{title}</b>\n\n💰 Ընտրիր ճիշտ գինը՝ {fmt(low)} ֏ / {fmt(high)} ֏",parse_mode="HTML",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"💰 {fmt(low)} ֏",callback_data=f"passprice:{m.from_user.id}:{low}"),InlineKeyboardButton(text=f"💰 {fmt(high)} ֏",callback_data=f"passprice:{m.from_user.id}:{high}")]]))
        u["pass_admin_message_id"]=sent.message_id; await save_state(); await m.answer("✅ Screenshot-ը ստացվեց։ Ադմինը կընտրի ճիշտ գինը։",reply_markup=main_kb()); return
    if u.get("payment")!="receipt_pending": return
    u["payment"]="receipt_sent"; u["order_id"]=f"{m.from_user.id}-{m.message_id}"; u["username"]=m.from_user.username; u["receipt_accepted"]=False; u["receipt_waiting_id"]=True; u["game_id"]=None
    sent=await bot.send_photo(ORDER_CHANNEL_ID,m.photo[-1].file_id,caption=order_summary(m.from_user.id,u,"⏳ Չեկը սպասում է ադմինի ստուգմանը։"),parse_mode="HTML",reply_markup=admin_kb(m.from_user.id))
    u["receipt_order_message_id"]=sent.message_id
    await save_state()
    await m.answer("💎 <b>Չեկը ստացվեց։</b> ❤️‍🔥\n\n🆔 Հիմա ուղարկիր քո ID-ն։",parse_mode="HTML")

@dp.message(F.text)
async def text(m):
    u=get_user(m.from_user.id)

    # Refund details have priority.
    if u.get("refund_waiting") and u.get("refund_method") in {"phone","card"} and u.get("refund_details_ready") is False and (u.get("refund_operator") or u.get("refund_method")=="card"):
        u["refund_details_ready"]=True; u["refund_details"]=m.text.strip(); await save_state()
        method="📱 Հեռախոսահամար" if u["refund_method"]=="phone" else "💳 Քարտ"
        op=f"\n📞 Օպերատոր՝ <b>{escape(u.get('refund_operator') or '-')}</b>" if u.get("refund_operator") else ""
        await notify(ADMIN_ID,f"💸 <b>Տվյալները վերադարձի համար</b>\n\n🆔 User ID՝ <code>{m.from_user.id}</code>\n📦 {escape(u.get('product') or '')}\n💰 {fmt(u.get('price') or 0)} ֏\n📌 Եղանակ՝ <b>{method}</b>{op}\n📝 Տվյալներ՝ <code>{escape(m.text.strip())}</code>",admin_kb(m.from_user.id,u.get("receipt_accepted",False),True)); await m.answer("✅ Տվյալները ստացվեցին։ Սպասիր վերադարձի հաստատմանը։"); return

    # FIX: after a receipt, the next text is the customer's game ID.
    # This also works when the process was restarted and the state was restored from orders_state.json.
    if u.get("receipt_waiting_id") or (u.get("payment") in {"receipt_sent","receipt_accepted"} and u.get("receipt_order_message_id")):
        game_id=m.text.strip()
        if not game_id:
            await m.answer("⚠️ ID-ն դատարկ է։ Ուղարկիր ճիշտ ID-ն։")
            return
        u["game_id"]=game_id; u["receipt_waiting_id"]=False
        await save_state()
        caption=order_summary(m.from_user.id,u,"⏳ Չեկը սպասում է ադմինի ստուգմանը։")
        try:
            await bot.edit_message_caption(chat_id=ORDER_CHANNEL_ID,message_id=u["receipt_order_message_id"],caption=caption,parse_mode="HTML",reply_markup=admin_kb(m.from_user.id,u.get("receipt_accepted",False),u.get("refund_details_ready",False)))
        except Exception:
            logging.exception("Could not update order with customer game ID")
        await m.answer("✅ <b>ID-ն ստացվեց։</b>\n\n⏳ Վճարումը ստուգվում է, և պատվերը մշակվում է։",parse_mode="HTML")
        return

    await m.answer("ℹ️ Եթե ուզում ես ուղարկել պատվերի ID-ն, նախ ուղարկիր չեկի նկարը։",reply_markup=main_kb())

@dp.callback_query(F.data=="buy:confirm")
async def buy(c):
    u=get_user(c.from_user.id); await c.message.edit_text(f"💳 <b>Ընտրիր վճարման եղանակը</b>\n\n📦 {escape(u['product'])}\n💰 Գումար՝ <b>{fmt(u['price'])} ֏</b>\n\nԸնտրիր՝ քարտով, թե կանխիկ։",reply_markup=payment_kb(),parse_mode="HTML"); await c.answer()

@dp.callback_query(F.data=="payment:card")
async def card(c): await c.answer("💳 Քարտով վճարումը դեռ հասանելի չէ։",show_alert=True)

@dp.callback_query(F.data=="payment:cash")
async def cash(c):
    u=get_user(c.from_user.id); u["payment"]="cash"; await save_state(); await c.message.edit_text(cash_text(u),reply_markup=receipt_kb(),parse_mode="HTML"); await c.answer()

@dp.callback_query(F.data=="payment:done")
async def done(c):
    u=get_user(c.from_user.id); u["payment"]="receipt_pending"; await save_state(); await c.message.edit_text("🧾 <b>Ուղարկիր չեկի նկարը</b>\n\n📸 Ուղարկիր վճարման չեկի լուսանկարը։",reply_markup=back_kb("back:payment"),parse_mode="HTML"); await c.answer()

@dp.callback_query(F.data.startswith("passprice:"))
async def passprice(c):
    if c.from_user.id!=ADMIN_ID: await c.answer("⛔ Միայն ադմինին։",show_alert=True); return
    _,uid,p=c.data.split(":"); uid=int(uid); u=get_user(uid); u["price"]=int(p); u["product"]="Brawl Pass" if u["brawl_pass_type"]=="brawl_pass" else "Brawl Pass+"; u["brawl_pass_type"]=None
    try: await c.message.edit_caption((c.message.caption or "")+f"\n\n✅ <b>Ընտրված գին՝ {fmt(int(p))} ֏</b>",parse_mode="HTML",reply_markup=None)
    except Exception: pass
    await save_state(); await notify(uid,f"✅ <b>Ձեր Pass-ի գինը հաստատվեց։</b>\n\n📦 {escape(u['product'])}\n💰 {fmt(u['price'])} ֏\n\nՇարունակե՞լ պատվերը։",product_kb("brawlstars")); await c.answer("✅ Գինը ընտրված է։")

async def admin_only(c):
    if c.from_user.id!=ADMIN_ID: await c.answer("⛔ Այս կոճակը հասանելի է միայն ադմինին։",show_alert=True); return False
    return True

@dp.callback_query(F.data.startswith("receipt:"))
async def receipt(c):
    if not await admin_only(c): return
    _,action,uidtxt=c.data.split(":"); uid=int(uidtxt); u=get_user(uid)
    if action=="reject":
        await finalize(uid,"❌ Չեկը մերժված է — Դոնաթը չի հաջողվել.","❌ <b>Դոնաթը չի հաջողվել.</b>\n\nՎճարման չեկը մերժվել է։ Եթե կարծում ես, որ սխալ է, կապվիր աջակցությանը։"); await c.answer("❌ Չեկը մերժվեց։"); return
    if action=="accept":
        u["receipt_accepted"]=True; u["payment"]="receipt_accepted"; u["receipt_order_message_id"]=c.message.message_id; await save_state()
        await c.message.edit_caption(caption=order_summary(uid,u,"✅ Չեկը հաստատված է։ Սպասում է Դոնաթի ավարտին."),parse_mode="HTML",reply_markup=admin_kb(uid,True,u.get("refund_details_ready",False))); await notify(uid,"✅ <b>Չեկը հաստատվեց։</b>\n\n⏳ Պատվերը պատրաստվում է։"); await c.answer("✅ Չեկը հաստատվեց։"); return
    if action=="confirm":
        if not u.get("receipt_accepted"): await c.answer("⚠️ Նախ հաստատիր չեկը։",show_alert=True); return
        await finalize(uid,"📦 Պատվերը հաստատված է — Դոնաթը հաջողությամբ ավարտված է.","🎉 <b>Դոնաթը հաջողությամբ ավարտված է։</b> ❤️‍🔥\n\nՇնորհակալություն Games Vault Shop-ը ընտրելու համար։ 💎"); await c.answer("📦 Պատվերը ավարտվեց։"); return
    if action=="refund":
        u["refund_waiting"]=True; u["refund_method"]=None; u["refund_operator"]=None; u["refund_details_ready"]=False; await save_state()
        await notify(uid,"⚠️ <b>Դոնաթը չի հաջողվել։</b>\n\n💸 Ընտրիր, թե որտեղ պետք է կատարվի վերադարձը։",refund_method_kb()); await c.answer("💸 Հաճախորդին ուղարկվեց վերադարձի ընտրությունը։"); return
    if action=="refund_complete":
        if not u.get("refund_details_ready"): await c.answer("⚠️ Հաճախորդը դեռ չի տրամադրել տվյալները։",show_alert=True); return
        await finalize(uid,"💸 Հետ գումարի վերադարձը ավարտված է — Դոնաթը չի հաջողվել.","💸 <b>Հետ գումարի վերադարձը ավարտված է։</b>\n\n❌ Դոնաթը չի հաջողվել։ Գումարը վերադարձվել է։"); await c.answer("✅ Վերադարձը ավարտվեց։"); return
    if action=="back": await c.answer("↩️"); return

@dp.callback_query(F.data=="refundclient:phone")
async def rphone(c):
    u=get_user(c.from_user.id); u["refund_method"]="phone"; await save_state(); await c.message.edit_text("📱 <b>Ընտրիր քո բջջային օպերատորը</b>։",reply_markup=operators_kb(),parse_mode="HTML"); await c.answer()

@dp.callback_query(F.data=="refundclient:card")
async def rcard(c):
    u=get_user(c.from_user.id); u["refund_method"]="card"; u["refund_operator"]=None; await save_state(); await c.message.edit_text("💳 <b>Ուղարկիր քարտի համարը</b>։\n\n⚠️ Մի ուղարկիր CVV/CVC, PIN կամ այլ գաղտնի կոդ։",reply_markup=back_kb("refundclient:back"),parse_mode="HTML"); await c.answer()

@dp.callback_query(F.data.startswith("refundclient:operator:"))
async def roperator(c):
    u=get_user(c.from_user.id); op=c.data.split(":",2)[2]; u["refund_operator"]=op; await save_state()
    await c.message.edit_text(f"📱 <b>{escape(op)}</b>\n\nՈւղարկիր հեռախոսահամարը, որին պետք է կատարվի վերադարձը։\n\n⚠️ <b>Զգուշացում․</b> եթե վերադարձը կատարվում է հեռախոսահամարին, տվյալ գումարը կարող է օգտագործվել զանգերի/կապի համար և կարող է ավելանալ քո խոսակցության հաշվին։",reply_markup=back_kb("refundclient:back"),parse_mode="HTML"); await c.answer()

@dp.callback_query(F.data=="refundclient:back")
async def rback(c):
    u=get_user(c.from_user.id); u["refund_method"]=None; u["refund_operator"]=None; u["refund_details_ready"]=False; await save_state(); await c.message.edit_text("💸 <b>Ընտրիր վերադարձի եղանակը</b>։",reply_markup=refund_method_kb(),parse_mode="HTML"); await c.answer()

@dp.callback_query(F.data=="contact:open")
async def contact(c): await c.answer("📩 Կապվեք մեզ հետ՝ գրեք հաղորդագրություն։",show_alert=True)

@dp.callback_query(F.data=="back:main")
async def bmain(c): await c.message.edit_text(main_text(),reply_markup=main_kb(),parse_mode="HTML"); await c.answer()

@dp.callback_query(F.data.startswith("back:game:"))
async def bgame(c):
    g=c.data.split(":",2)[2]; u=get_user(c.from_user.id); u["brawl_pass_waiting"]=False; await save_state(); await c.message.edit_text(f"{CATALOG[g]['name']}\n\n📦 Ընտրիր անհրաժեշտ ապրանքը։",reply_markup=game_kb(g),parse_mode="HTML"); await c.answer()

@dp.callback_query(F.data=="back:product")
async def bprod(c):
    u=get_user(c.from_user.id); await c.message.edit_text(f"🛒 <b>Ձեր ընտրությունը</b>\n\n📦 {escape(u.get('product') or '')}\n💰 {fmt(u.get('price') or 0)} ֏",reply_markup=product_kb(u['game']),parse_mode="HTML"); await c.answer()

@dp.callback_query(F.data=="back:payment")
async def bpay(c): await buy(c)

async def health(request): return web.Response(text="Games Vault Shop is running!")

async def main():
    load_state()
    app=web.Application(); app.router.add_get("/",health); app.router.add_get("/health",health); runner=web.AppRunner(app); await runner.setup(); await web.TCPSite(runner,"0.0.0.0",PORT).start(); await bot.delete_webhook(drop_pending_updates=True); await dp.start_polling(bot)

if __name__=="__main__": asyncio.run(main())
