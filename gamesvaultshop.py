import os
import asyncio
import json
import logging
import uuid
from pathlib import Path
from html import escape

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
ORDER_CHANNEL_ID = os.getenv("ORDER_CHANNEL_ID", "")
SUPPORT_CHANNEL_ID = os.getenv("SUPPORT_CHANNEL_ID", "")
TELCELL_NUMBER = os.getenv("TELCELL_NUMBER", "043055510")
CARD_NUMBER = os.getenv("CARD_NUMBER", "")
PORT = int(os.getenv("PORT", "10000"))
STATE_FILE = Path(os.getenv("STATE_FILE", "orders_state.json"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN չգտնվեց։ Ավելացրու BOT_TOKEN-ը Render-ի Environment Variables-ում։")
if not ADMIN_ID:
    raise RuntimeError("ADMIN_ID չգտնվեց։")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
bot = Bot(BOT_TOKEN)
dp = Dispatcher()
users = {}
state_lock = asyncio.Lock()

BRAWL_PASS_PRICES = {"Brawl Pass": (2500, 3400), "Brawl Pass+": (3400, 4800)}

CATALOG = {
    "roblox": {"name": "🎮 Roblox", "items": [("40 Robux",350),("80 Robux",650),("120 Robux",950),("400 Robux",2700),("520 Robux",3600),("840 Robux",4850),("1,240 Robux",7300),("1,700 Robux",8800),("1,820 Robux",9700),("4,500 Robux",21000),("10,000 Robux",40000),("22,500 Robux",88000)]},
    "standoff2": {"name": "🔫 Standoff 2", "items": [("100 Gold",1000),("200 Gold",2000),("300 Gold",2900),("500 Gold",4000),("600 Gold",5100),("700 Gold",5800),("1,000 Gold",7100),("1,500 Gold",10300),("3,000 Gold",15800)]},
    "brawlstars": {"name": "⭐ Brawl Stars", "items": [("30 Gems",800),("80 Gems",1600),("170 Gems",3000),("360 Gems",5300),("950 Gems",13000),("Brawl Pass",0),("Brawl Pass+",0),("Պրոգրես Brawl Pass → Brawl Pass+",1800),("Pro Pass",12800)]},
    "pubg": {"name": "🪂 PUBG Mobile", "items": [("60 UC",500),("300 UC + 25 UC 🎁",2000),("600 UC + 60 UC 🎁",4000),("1,500 UC + 300 UC 🎁",10000),("3,000 UC + 850 UC 🎁",20000),("6,000 UC + 2,100 UC 🎁",40000)]},
    "fcmobile": {"name": "⚽ FC Mobile", "items": [("40 FC Points",300),("100 FC Points",650),("500 + 20 FC Points 🎁",3000),("1,000 + 70 FC Points 🎁",5500),("2,000 + 200 FC Points 🎁",11000),("5,000 + 750 FC Points 🎁",27000),("10,000 + 2,000 FC Points 🎁",54000)]},
}

def blank_user():
    return {
        "game":None,"product":None,"price":None,"payment":None,"username":None,"order_id":None,
        "game_id":None,"receipt_file_id":None,"receipt_waiting":False,"game_id_waiting":False,"game_id_checked":False,
        "receipt_accepted":False,"verification_type":None,"verification_done":False,"order_message_id":None,"order_chat_id":None,
        "support_waiting":False,"refund_waiting":False,"refund_method":None,"refund_details":None,"status":"Նոր պատվեր",
        "brawl_pass_waiting":False,"brawl_pass_screenshot_file_id":None,"brawl_pass_price_selected":False,
    }

def get_user(uid):
    if uid not in users: users[uid] = blank_user()
    else: users[uid] = {**blank_user(), **users[uid]}
    return users[uid]

def load_state():
    global users
    try:
        if STATE_FILE.exists():
            raw=json.loads(STATE_FILE.read_text("utf-8"))
            users={int(k):v for k,v in raw.items()}
    except Exception:
        logging.exception("State load failed"); users={}

async def save_state():
    async with state_lock:
        tmp=STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(users,ensure_ascii=False),encoding="utf-8")
        tmp.replace(STATE_FILE)

def fmt(n): return f"{int(n):,}".replace(","," ")
def kb(rows): return InlineKeyboardMarkup(inline_keyboard=rows)
def is_pass(u): return u.get("product") in BRAWL_PASS_PRICES


def main_kb():
    return kb([[InlineKeyboardButton(text="🎮 Roblox",callback_data="game:roblox"),InlineKeyboardButton(text="🔫 Standoff 2",callback_data="game:standoff2")],[InlineKeyboardButton(text="⭐ Brawl Stars",callback_data="game:brawlstars"),InlineKeyboardButton(text="🪂 PUBG Mobile",callback_data="game:pubg")],[InlineKeyboardButton(text="⚽ FC Mobile",callback_data="game:fcmobile")],[InlineKeyboardButton(text="📩 Կապվեք մեզ հետ",callback_data="contact:open")]])

def game_kb(game):
    rows=[]
    for i,(name,price) in enumerate(CATALOG[game]["items"]):
        if name=="Brawl Pass": text="🎫 Brawl Pass — 2 500 / 3 400 ֏"
        elif name=="Brawl Pass+": text="⭐ Brawl Pass+ — 3 400 / 4 800 ֏"
        else: text=f"⚡ {name} — {fmt(price)} ֏"
        rows.append([InlineKeyboardButton(text=text,callback_data=f"product:{game}:{i}")])
    rows.append([InlineKeyboardButton(text="⬅️ Հետ",callback_data="back:main")])
    return kb(rows)

def product_kb(game):
    return kb([[InlineKeyboardButton(text="✅ Գնել",callback_data="buy:confirm")],[InlineKeyboardButton(text="⬅️ Հետ",callback_data=f"back:game:{game}")]])

def payment_kb():
    return kb([[InlineKeyboardButton(text="💳 Քարտով",callback_data="payment:card")],[InlineKeyboardButton(text="💵 Telcell",callback_data="payment:telcell")],[InlineKeyboardButton(text="⬅️ Հետ",callback_data="back:product")]])
def back_payment_kb(): return kb([[InlineKeyboardButton(text="⬅️ Հետ",callback_data="back:payment")]])
def back_main_kb(): return kb([[InlineKeyboardButton(text="⬅️ Հետ",callback_data="back:main")]])

def admin_pass_kb(uid):
    product=get_user(uid).get("product")
    low,high=BRAWL_PASS_PRICES[product]
    return kb([[InlineKeyboardButton(text=f"💰 {fmt(low)} ֏",callback_data=f"passadmin:price:{uid}:{low}"),InlineKeyboardButton(text=f"💰 {fmt(high)} ֏",callback_data=f"passadmin:price:{uid}:{high}")],[InlineKeyboardButton(text="❌ Սխալ կամ վատ տեսանելի screenshot",callback_data=f"passadmin:reject:{uid}")]])

def admin_id_kb(uid): return kb([[InlineKeyboardButton(text="❌ Սխալ ID / Username",callback_data=f"id:reject:{uid}"),InlineKeyboardButton(text="✅ ID / Username ճիշտ է",callback_data=f"id:accept:{uid}")]])
def admin_receipt_kb(uid): return kb([[InlineKeyboardButton(text="❌ Սխալ կամ վատ տեսանելի screenshot",callback_data=f"receipt:reject:{uid}")],[InlineKeyboardButton(text="✅ Հաստատել չեկը",callback_data=f"receipt:accept:{uid}")],[InlineKeyboardButton(text="📦 Հաստատել պատվերը",callback_data=f"order:confirm:{uid}")],[InlineKeyboardButton(text="💸 Վերադարձ",callback_data=f"refund:{uid}")]])
def admin_verify_kb(uid): return kb([[InlineKeyboardButton(text="📱 Այլ սարքով հաստատում",callback_data=f"verify:device:{uid}")],[InlineKeyboardButton(text="🔐 Authenticator",callback_data=f"verify:auth:{uid}")],[InlineKeyboardButton(text="📧 E-mail",callback_data=f"verify:email:{uid}")],[InlineKeyboardButton(text="⬅️ Հետ",callback_data=f"admin:receipt:{uid}")]])
def admin_complete_kb(uid): return kb([[InlineKeyboardButton(text="✅ Ավարտել պատվերը",callback_data=f"order:complete:{uid}")],[InlineKeyboardButton(text="💸 Վերադարձ",callback_data=f"refund:{uid}")]])
def admin_refund_kb(uid): return kb([[InlineKeyboardButton(text="💳 Քարտով վերադարձ",callback_data=f"refund:card:{uid}")],[InlineKeyboardButton(text="💵 Telcell վերադարձ",callback_data=f"refund:telcell:{uid}")],[InlineKeyboardButton(text="⬅️ Հետ",callback_data=f"admin:receipt:{uid}")]])

def order_caption(uid):
    u=get_user(uid)
    price=fmt(u.get("price") or 0) if u.get("price") else "Ադմինը դեռ չի ընտրել"
    return (f"🧾 <b>Պատվեր #{escape(str(u.get('order_id') or '—'))}</b>\n"
            f"👤 ID: <code>{uid}</code>\n🔹 Username: @{escape(u.get('username') or 'չկա')}\n"
            f"🎮 Խաղ: {escape(CATALOG.get(u.get('game'),{}).get('name','—'))}\n"
            f"📦 Ապրանք: <b>{escape(str(u.get('product') or '—'))}</b>\n"
            f"💰 Գին: <b>{price} ֏</b>\n💳 Վճարում: {escape(str(u.get('payment') or '—'))}\n"
            f"🎯 Game ID / Username: <code>{escape(str(u.get('game_id') or '—'))}</code>\n"
            f"📌 <b>Կարգավիճակ: {escape(str(u.get('status') or '—'))}</b>")

async def safe_answer(c,text=None):
    try: await c.answer(text or "")
    except Exception: pass

async def send_client(uid,text,markup=None):
    try: await bot.send_message(uid,text,parse_mode="HTML",reply_markup=markup)
    except Exception: logging.exception("Client message failed")

async def update_admin_order(uid,markup=None):
    u=get_user(uid)
    if not u.get("order_message_id") or not u.get("order_chat_id"): return
    try:
        await bot.edit_message_caption(chat_id=u["order_chat_id"],message_id=u["order_message_id"],caption=order_caption(uid),parse_mode="HTML",reply_markup=markup)
    except Exception: logging.exception("Could not update admin order")

async def create_or_replace_order(uid, file_id=None, markup=None):
    u=get_user(uid); file_id=file_id or u.get("receipt_file_id") or u.get("brawl_pass_screenshot_file_id")
    if not file_id: return
    chat_id=int(ORDER_CHANNEL_ID) if ORDER_CHANNEL_ID else ADMIN_ID
    try:
        if u.get("order_message_id") and u.get("order_chat_id"):
            await bot.edit_message_media(chat_id=u["order_chat_id"],message_id=u["order_message_id"],media=InputMediaPhoto(media=file_id,caption=order_caption(uid),parse_mode="HTML"),reply_markup=markup)
        else:
            sent=await bot.send_photo(chat_id,file_id,caption=order_caption(uid),parse_mode="HTML",reply_markup=markup)
            u["order_message_id"],u["order_chat_id"]=sent.message_id,chat_id
    except Exception: logging.exception("Could not create/replace admin order")
    await save_state()

def new_order(u,message):
    if not u.get("order_id"): u["order_id"]=uuid.uuid4().hex[:8].upper()
    u["username"]=message.from_user.username

@dp.message(CommandStart())
async def start(message:Message):
    u=get_user(message.from_user.id); u.clear(); u.update(blank_user()); u["username"]=message.from_user.username
    await save_state(); await message.answer("💎 <b>Games Vault Shop</b>\n\nԸնտրիր խաղը և ստացիր քո թվային ապրանքը արագ ու անվտանգ։",parse_mode="HTML",reply_markup=main_kb())

@dp.message(Command("cancel"))
async def cancel(message:Message):
    u=get_user(message.from_user.id); u.clear(); u.update(blank_user()); u["username"]=message.from_user.username
    await save_state(); await message.answer("❌ Պատվերը չեղարկվեց։",reply_markup=main_kb())

@dp.callback_query(F.data=="back:main")
async def back_main(c:CallbackQuery):
    await safe_answer(c); await c.message.edit_text("💎 <b>Games Vault Shop</b>\n\nԸնտրիր խաղը։",parse_mode="HTML",reply_markup=main_kb())

@dp.callback_query(F.data.startswith("game:"))
async def choose_game(c:CallbackQuery):
    game=c.data.split(":",1)[1]
    if game not in CATALOG: return
    u=get_user(c.from_user.id); u["game"]=game; u["product"]=None; u["price"]=None
    await save_state(); await safe_answer(c); await c.message.edit_text(f"{CATALOG[game]['name']}\n\nԸնտրիր ապրանքը։",parse_mode="HTML",reply_markup=game_kb(game))

@dp.callback_query(F.data.startswith("back:game:"))
async def back_game(c:CallbackQuery):
    game=c.data.split(":",2)[2]
    if game not in CATALOG:return
    await safe_answer(c); await c.message.edit_text(f"{CATALOG[game]['name']}\n\nԸնտրիր ապրանքը։",parse_mode="HTML",reply_markup=game_kb(game))

@dp.callback_query(F.data.startswith("product:"))
async def choose_product(c:CallbackQuery):
    _,game,idx=c.data.split(":")
    try:name,price=CATALOG[game]["items"][int(idx)]
    except (KeyError,ValueError,IndexError): await safe_answer(c,"Սխալ ապրանք"); return
    u=get_user(c.from_user.id)
    u.update(game=game,product=name,price=None if name in BRAWL_PASS_PRICES else price,game_id=None,game_id_checked=False,receipt_file_id=None,receipt_waiting=False,game_id_waiting=False,receipt_accepted=False,brawl_pass_waiting=False,brawl_pass_screenshot_file_id=None,brawl_pass_price_selected=False)
    if name in BRAWL_PASS_PRICES:
        u["brawl_pass_waiting"]=True; u["status"]="Սպասվում է Brawl Pass screenshot"; new_order(u,c.message); await save_state(); await safe_answer(c)
        await c.message.edit_text(f"📸 <b>{escape(name)}</b>\n\nՈւղարկիր screenshot-ը, որտեղ հստակ երևում է՝ քո հաշվում <b>{escape(name)}</b> է։\n\n⚠️ Screenshot-ը պետք է լինի ամբողջական և լավ տեսանելի։\n\nԱդմինը screenshot-ը ստուգելուց հետո ինքը կընտրի ճիշտ գինը։",parse_mode="HTML",reply_markup=back_main_kb()); return
    await save_state(); await safe_answer(c); await c.message.edit_text(f"📦 <b>{escape(name)}</b>\n\n💰 Գին՝ <b>{fmt(price)} ֏</b>\n\nՇարունակե՞նք գնումը։",parse_mode="HTML",reply_markup=product_kb(game))

@dp.callback_query(F.data=="buy:confirm")
async def buy_confirm(c:CallbackQuery):
    u=get_user(c.from_user.id)
    if not u.get("game") or not u.get("product") or not u.get("price"): await safe_answer(c,"Սկզբում սպասիր ադմինի կողմից գնի ընտրությանը"); return
    await safe_answer(c); await c.message.edit_text(f"💳 <b>Վճարման եղանակ</b>\n\nՊատվեր՝ {escape(u['product'])}\nԳին՝ <b>{fmt(u['price'])} ֏</b>",parse_mode="HTML",reply_markup=payment_kb())

@dp.callback_query(F.data=="back:product")
async def back_product(c:CallbackQuery):
    u=get_user(c.from_user.id)
    if is_pass(u):
        await safe_answer(c); await c.message.edit_text(f"📦 <b>{escape(u['product'])}</b>\n\n💰 Ադմինը ընտրում է գինը ըստ screenshot-ի։",parse_mode="HTML",reply_markup=back_main_kb()); return
    if not u.get("game") or not u.get("product"): return await back_main(c)
    await safe_answer(c); await c.message.edit_text(f"📦 <b>{escape(u['product'])}</b>\n\n💰 Գին՝ <b>{fmt(u.get('price') or 0)} ֏</b>",parse_mode="HTML",reply_markup=product_kb(u['game']))

@dp.callback_query(F.data=="payment:card")
async def payment_card(c:CallbackQuery):
    u=get_user(c.from_user.id)
    if not CARD_NUMBER:
        await safe_answer(c); await c.message.edit_text("💳 <b>Քարտով վճարում — հասանելի չէ</b>\n\nԱյս պահին ընտրիր Telcell։",parse_mode="HTML",reply_markup=payment_kb()); return
    u["payment"]="Քարտ"; u["receipt_waiting"]=True; u["status"]="Սպասվում է վճարման screenshot"; new_order(u,c.message); await save_state(); await safe_answer(c)
    await c.message.edit_text(f"💳 <b>Քարտով վճարում</b>\n\nՔարտ՝ <code>{escape(CARD_NUMBER)}</code>\nԳումար՝ <b>{fmt(u['price'])} ֏</b>\n\nՎճարումից հետո ուղարկիր screenshot-ը։",parse_mode="HTML",reply_markup=back_payment_kb())

@dp.callback_query(F.data=="payment:telcell")
async def payment_telcell(c:CallbackQuery):
    u=get_user(c.from_user.id); u["payment"]="Telcell"; u["receipt_waiting"]=True; u["status"]="Սպասվում է վճարման screenshot"; new_order(u,c.message); await save_state(); await safe_answer(c)
    await c.message.edit_text(f"💵 <b>Telcell</b>\n\nԲացիր Telcell → ընտրիր «Telcell Wallet» → գրիր հեռախոսահամարը՝ <code>{TELCELL_NUMBER}</code>\n\nԳումար՝ <b>{fmt(u['price'])} ֏</b>\n\nՎճարումից հետո ուղարկիր screenshot-ը։",parse_mode="HTML",reply_markup=back_payment_kb())

@dp.callback_query(F.data=="back:payment")
async def back_payment(c:CallbackQuery): await safe_answer(c); await c.message.edit_text("💳 <b>Ընտրիր վճարման եղանակը</b>",parse_mode="HTML",reply_markup=payment_kb())

@dp.message(F.photo)
async def photo_input(message:Message):
    uid=message.from_user.id; u=get_user(uid); file_id=message.photo[-1].file_id
    if u.get("brawl_pass_waiting"):
        u["brawl_pass_screenshot_file_id"]=file_id; u["brawl_pass_waiting"]=False; u["status"]="Սպասվում է ադմինի կողմից Brawl Pass գնի ընտրություն"; new_order(u,message)
        await create_or_replace_order(uid,file_id,admin_pass_kb(uid)); await message.answer("📸 Screenshot-ը ստացվեց։\n\n⏳ Սպասիր՝ ադմինը կստուգի screenshot-ը և կընտրի համապատասխան գինը։",parse_mode="HTML",reply_markup=back_main_kb()); return
    if not u.get("receipt_waiting") and not u.get("order_id"): return
    if not u.get("price"):
        await message.answer("⏳ Գինը դեռ ընտրված չէ։ Սպասիր ադմինի որոշմանը։",reply_markup=back_main_kb()); return
    u["receipt_file_id"]=file_id; u["receipt_accepted"]=False; u["status"]="Սպասվում է Game ID / Username"; u["game_id_waiting"]=True; u["receipt_waiting"]=False; new_order(u,message)
    await create_or_replace_order(uid,file_id,admin_id_kb(uid)); await message.answer("📸 Վճարման screenshot-ը ստացվեց։\n\n🎯 Հիմա ուղարկիր քո <b>Game ID / Username</b>։",parse_mode="HTML",reply_markup=back_main_kb())

@dp.message(F.text)
async def text_input(message:Message):
    uid=message.from_user.id; u=get_user(uid); text=message.text.strip()
    if u.get("support_waiting"):
        if SUPPORT_CHANNEL_ID: await bot.send_message(int(SUPPORT_CHANNEL_ID),f"📩 <b>Support</b>\n👤 <code>{uid}</code>\n@{escape(message.from_user.username or 'չկա')}\n\n{escape(text)}",parse_mode="HTML")
        u["support_waiting"]=False; await save_state(); await message.answer("✅ Հաղորդագրությունը ուղարկվեց աջակցությանը։",reply_markup=main_kb()); return
    if u.get("refund_waiting"):
        u["refund_details"]=text; u["refund_waiting"]=False; u["status"]="Սպասվում է վերադարձի մշակում"; await save_state(); await update_admin_order(uid,admin_refund_kb(uid)); await message.answer("✅ Տվյալները ստացվեցին։ Ադմինը կկատարի վերադարձը։",reply_markup=main_kb()); return
    if u.get("game_id_waiting"):
        u["game_id"]=text; u["game_id_waiting"]=False; u["status"]="Սպասվում է ID-ի ստուգում"; await save_state(); await update_admin_order(uid,admin_id_kb(uid)); await message.answer("✅ ID / Username-ը ստացվեց։ Սպասիր ստուգմանը։",reply_markup=main_kb()); return
    await message.answer("Ընտրիր բաժինը։",reply_markup=main_kb())

@dp.callback_query(F.data=="contact:open")
async def contact_open(c:CallbackQuery):
    u=get_user(c.from_user.id); u["support_waiting"]=True; await save_state(); await safe_answer(c); await c.message.edit_text("📩 <b>Կապ Games Vault Shop-ի հետ</b>\n\nՈւղարկիր հաղորդագրություն, և մենք կպատասխանենք։",parse_mode="HTML",reply_markup=back_main_kb())

@dp.callback_query(F.data.startswith("passadmin:"))
async def pass_admin_action(c:CallbackQuery):
    if c.from_user.id!=ADMIN_ID: await safe_answer(c,"Մուտքը արգելված է"); return
    _,action,uid_s,*rest=c.data.split(":"); uid=int(uid_s); u=get_user(uid)
    if not is_pass(u): await safe_answer(c,"Սա Brawl Pass պատվեր չէ"); return
    if action=="reject":
        u["brawl_pass_waiting"]=True; u["brawl_pass_price_selected"]=False; u["status"]="Սպասվում է նոր Brawl Pass screenshot"; await save_state()
        await send_client(uid,"❌ <b>Screenshot-ը սխալ է կամ լավ չի երևում</b>\n\nՈւղարկիր նոր, ամբողջական և ավելի հստակ screenshot Brawl Pass-ի / Brawl Pass+-ի։\n\nՀին պատվերը չի կրկնվի։")
        await update_admin_order(uid,admin_pass_kb(uid)); await safe_answer(c,"Սպասվում է նոր screenshot"); return
    price=int(rest[0]); low,high=BRAWL_PASS_PRICES[u["product"]]
    if price not in (low,high): await safe_answer(c,"Սխալ գին"); return
    u["price"]=price; u["brawl_pass_price_selected"]=True; u["status"]=f"Գինը ընտրված է՝ {fmt(price)} ֏ — սպասվում է վճարում"; await save_state()
    await update_admin_order(uid,None)
    await send_client(uid,f"✅ <b>Screenshot-ը հաստատվեց։</b>\n\n📦 {escape(u['product'])}\n💰 Ձեր գինը՝ <b>{fmt(price)} ֏</b>\n\nՍեղմիր «Շարունակել գնումը», որպեսզի ընտրես վճարման եղանակը։",kb([[InlineKeyboardButton(text="💳 Շարունակել գնումը",callback_data="buy:confirm")],[InlineKeyboardButton(text="⬅️ Հետ",callback_data="back:main")]]))
    await safe_answer(c,f"Գինը՝ {fmt(price)} ֏")

@dp.callback_query(F.data.startswith("id:"))
async def admin_id_action(c:CallbackQuery):
    if c.from_user.id!=ADMIN_ID: await safe_answer(c,"Մուտքը արգելված է"); return
    _,action,uid_s=c.data.split(":"); uid=int(uid_s); u=get_user(uid)
    if action=="reject":
        u["game_id_waiting"]=True; u["game_id_checked"]=False; u["status"]="Սպասվում է նոր ID / Username"; await save_state(); await send_client(uid,"❌ <b>Սխալ ID / Username</b>\n\nՈւղարկիր ճիշտ Game ID / Username-ը։",back_main_kb()); await update_admin_order(uid,admin_id_kb(uid)); await safe_answer(c,"Սպասվում է նոր ID")
    else:
        u["game_id_checked"]=True; u["status"]="ID / Username-ը հաստատված է — ստուգիր չեկը"; await save_state(); await update_admin_order(uid,admin_receipt_kb(uid)); await send_client(uid,"✅ ID / Username-ը հաստատվեց։\n\nԱյժմ ստուգվում է վճարումը։"); await safe_answer(c,"ID հաստատվեց")

@dp.callback_query(F.data.startswith("receipt:reject:"))
async def receipt_reject(c:CallbackQuery):
    if c.from_user.id!=ADMIN_ID: await safe_answer(c,"Մուտքը արգելված է"); return
    uid=int(c.data.split(":")[2]); u=get_user(uid); u["receipt_waiting"]=True; u["receipt_accepted"]=False; u["status"]="Սպասվում է նոր վճարման screenshot"; await save_state(); await send_client(uid,"❌ <b>Վճարման screenshot-ը սխալ է կամ վատ տեսանելի</b>\n\nՈւղարկիր նոր screenshot։ Հին պատվերը չի կրկնվի։"); await update_admin_order(uid,admin_receipt_kb(uid)); await safe_answer(c,"Սպասվում է նոր screenshot")

@dp.callback_query(F.data.startswith("receipt:accept:"))
async def receipt_accept(c:CallbackQuery):
    if c.from_user.id!=ADMIN_ID: await safe_answer(c,"Մուտքը արգելված է"); return
    uid=int(c.data.split(":")[2]); u=get_user(uid)
    if not u.get("game_id_checked"): await safe_answer(c,"Սկզբում հաստատիր ID / Username-ը"); return
    u["receipt_accepted"]=True; u["status"]="Չեկը հաստատված է — սպասվում է պատվերի հաստատում"; await save_state(); await update_admin_order(uid,admin_receipt_kb(uid)); await send_client(uid,"✅ Վճարման screenshot-ը հաստատվեց։"); await safe_answer(c,"Չեկը հաստատվեց")

@dp.callback_query(F.data.startswith("order:confirm:"))
async def order_confirm(c:CallbackQuery):
    if c.from_user.id!=ADMIN_ID: await safe_answer(c,"Մուտքը արգելված է"); return
    uid=int(c.data.split(":")[2]); u=get_user(uid)
    if not u.get("receipt_accepted") or not u.get("game_id_checked"): await safe_answer(c,"Սկզբում հաստատիր ID-ն և չեկը"); return
    await safe_answer(c); await c.message.edit_reply_markup(reply_markup=admin_verify_kb(uid))

@dp.callback_query(F.data.startswith("admin:receipt:"))
async def admin_receipt_back(c:CallbackQuery):
    if c.from_user.id!=ADMIN_ID: await safe_answer(c,"Մուտքը արգելված է"); return
    uid=int(c.data.split(":")[2]); await update_admin_order(uid,admin_receipt_kb(uid)); await safe_answer(c)

@dp.callback_query(F.data.startswith("verify:"))
async def verification(c:CallbackQuery):
    if c.from_user.id!=ADMIN_ID: await safe_answer(c,"Մուտքը արգելված է"); return
    _,kind,uid_s=c.data.split(":"); uid=int(uid_s); u=get_user(uid); labels={"device":"Այլ սարքով հաստատում","auth":"Authenticator","email":"E-mail"}; u["verification_type"]=kind; u["verification_done"]=False; u["status"]=f"Սպասվում է 2FA՝ {labels[kind]}"; await save_state()
    texts={"device":"📱 <b>2FA — այլ սարքով հաստատում</b>\n\nՀաստատիր միայն այն մուտքը, որը դու ես սկսել արդեն մուտք գործած սարքում։","auth":"🔐 <b>2FA — Authenticator</b>\n\nՕգտագործիր Authenticator-ի կոդը միայն Roblox-ի պաշտոնական էջում։ Կոդը մեզ չի ուղարկվում։","email":"📧 <b>2FA — E-mail</b>\n\nՕգտագործիր E-mail կոդը միայն Roblox-ի պաշտոնական էջում։ Կոդը մեզ չի ուղարկվում։"}
    await send_client(uid,texts[kind]); await update_admin_order(uid,admin_complete_kb(uid)); await safe_answer(c,"2FA-ի եղանակը ընտրվեց")

@dp.callback_query(F.data.startswith("order:complete:"))
async def order_complete(c:CallbackQuery):
    if c.from_user.id!=ADMIN_ID: await safe_answer(c,"Մուտքը արգելված է"); return
    uid=int(c.data.split(":")[2]); u=get_user(uid); u["verification_done"]=True; u["status"]="Պատվերը ավարտված է"; await save_state(); await update_admin_order(uid,None); await send_client(uid,"🎉 <b>Պատվերը ավարտված է։</b>\n\nՇնորհակալություն Games Vault Shop-ը ընտրելու համար։",main_kb()); await safe_answer(c,"Պատվերը ավարտվեց")

@dp.callback_query(F.data.startswith("refund:"))
async def refund_action(c:CallbackQuery):
    if c.from_user.id!=ADMIN_ID: await safe_answer(c,"Մուտքը արգելված է"); return
    parts=c.data.split(":"); uid=int(parts[-1]); u=get_user(uid)
    if len(parts)==2:
        u["refund_waiting"]=True; u["status"]="Սպասվում են վերադարձի տվյալները"; await save_state(); await update_admin_order(uid,admin_refund_kb(uid)); await send_client(uid,"💸 <b>Վերադարձ</b>\n\nՈւղարկիր այն տվյալները, որոնցով պետք է կատարվի վերադարձը։"); await safe_answer(c); return
    method="Քարտ" if parts[1]=="card" else "Telcell"; u["refund_method"]=method; u["status"]=f"Վերադարձ՝ {method}"; await save_state(); await update_admin_order(uid,None); await send_client(uid,f"💸 Վերադարձի հայտը ընդունվեց։ Եղանակ՝ <b>{method}</b>։"); await safe_answer(c,"Վերադարձը նշվեց")

@dp.message(Command("admin"))
async def admin_cmd(message:Message):
    if message.from_user.id==ADMIN_ID: await message.answer("🛠 <b>Admin panel</b>\n\nԲոտը աշխատում է։",parse_mode="HTML")

async def health_handler(request): return web.Response(text="OK")
async def run_web():
    app=web.Application(); app.router.add_get("/",health_handler); app.router.add_get("/health",health_handler)
    runner=web.AppRunner(app); await runner.setup(); site=web.TCPSite(runner,"0.0.0.0",PORT); await site.start(); logging.info("Health server started on port %s",PORT)
    while True: await asyncio.sleep(3600)

async def main():
    load_state(); await asyncio.gather(dp.start_polling(bot,allowed_updates=dp.resolve_used_update_types()),run_web())

if __name__=="__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: pass
