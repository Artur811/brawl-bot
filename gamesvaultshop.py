import os
import asyncio
import json
import logging
import uuid
import datetime
from pathlib import Path
from html import escape
from collections import defaultdict

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup, InputMediaPhoto, FSInputFile
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# ⭐ ՆԱՍՏԱՏՈՒՄՆԵՐ
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
ORDER_CHANNEL_ID = os.getenv("ORDER_CHANNEL_ID", "")
SUPPORT_CHANNEL_ID = os.getenv("SUPPORT_CHANNEL_ID", "")
TELCELL_NUMBER = os.getenv("TELCELL_NUMBER", "043055510")
PORT = int(os.getenv("PORT", "10000"))
STATE_FILE = Path(os.getenv("STATE_FILE", "orders_state.json"))
LOG_FILE = Path("bot.log")
BAN_FILE = Path("banned_users.json")

# ⭐ 2FA-ի նկարների հասցեները
VERIFY_IMAGES = {
    "device": "images/2fa_device.jpg",
    "auth": "images/2fa_auth.jpg",
    "email": "images/2fa_email.jpg"
}

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN չգտնվեց։")
if not ADMIN_ID:
    raise RuntimeError("ADMIN_ID չգտնվեց։")

# ⭐ ԼՈԳԱՎՈՐՈՒՄ
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ⭐ ԲՈՏԻ ՍՏԵՂԾՈՒՄ
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

users = {}
banned_users = set()
state_lock = asyncio.Lock()
order_stats = defaultdict(int)

# ⭐ ԽԱՂԵՐԻ ԷՄՈՋԻՆԵՐ
GAME_EMOJIS = {
    "roblox": "🎮",
    "standoff2": "🔫",
    "brawlstars": "⭐",
    "pubg": "🪂",
    "fcmobile": "⚽"
}

# ⭐ BRAWL PASS-Ի ԳՆԵՐԸ
BRAWL_PASS_PRICES = {
    "Brawl Pass": {"low": 2500, "high": 3400},
    "Brawl Pass+": {"low": 3400, "high": 4800}
}

CATALOG = {
    "roblox": {"name": "Roblox", "items": [("40 Robux",350),("80 Robux",650),("120 Robux",950),("400 Robux",2700),("520 Robux",3600),("840 Robux",4850),("1,240 Robux",7300),("1,700 Robux",8800),("1,820 Robux",9700),("4,500 Robux",21000),("10,000 Robux",40000),("22,500 Robux",88000)]},
    "standoff2": {"name": "Standoff 2", "items": [("100 Gold",1000),("200 Gold",2000),("300 Gold",2900),("500 Gold",4000),("600 Gold",5100),("700 Gold",5800),("1,000 Gold",7100),("1,500 Gold",10300),("3,000 Gold",15800)]},
    "brawlstars": {"name": "Brawl Stars", "items": [("30 Gems",800),("80 Gems",1600),("170 Gems",3000),("360 Gems",5300),("950 Gems",13000),("Brawl Pass",0),("Brawl Pass+",0),("Պրոգրես Brawl Pass → Brawl Pass+",1800),("Pro Pass",12800)]},
    "pubg": {"name": "PUBG Mobile", "items": [("60 UC",500),("300 UC + 25 UC 🎁",2000),("600 UC + 60 UC 🎁",4000),("1,500 UC + 300 UC 🎁",10000),("3,000 UC + 850 UC 🎁",20000),("6,000 UC + 2,100 UC 🎁",40000)]},
    "fcmobile": {"name": "FC Mobile", "items": [("40 FC Points",300),("100 FC Points",650),("500 + 20 FC Points 🎁",3000),("1,000 + 70 FC Points 🎁",5500),("2,000 + 200 FC Points 🎁",11000),("5,000 + 750 FC Points 🎁",27000),("10,000 + 2,000 FC Points 🎁",54000)]},
}

def blank_user():
    return {
        "game": None,
        "product": None,
        "price": None,
        "payment": None,
        "username": None,
        "order_id": None,
        "game_id": None,
        "game_password": None,
        "receipt_file_id": None,
        "receipt_waiting": False,
        "game_id_waiting": False,
        "game_password_waiting": False,
        "receipt_accepted": False,
        "verification_type": None,
        "verification_done": False,
        "verification_code_waiting": False,
        "verification_attempts": 0,
        "order_message_id": None,
        "order_chat_id": None,
        "support_waiting": False,
        "refund_waiting": False,
        "refund_method": None,
        "refund_details": None,
        "status": "🆕 Նոր պատվեր",
        "is_completed": False,
        "created_at": datetime.datetime.now().isoformat(),
        "completed_at": None,
        "brawl_pass_waiting": False,
        "brawl_pass_screenshot_file_id": None,
        "brawl_pass_price_selected": False,
        "brawl_pass_product": None,
        "brawl_pass_rejected": False,
    }

def get_user(uid):
    if uid not in users: 
        users[uid] = blank_user()
    else:
        base = blank_user()
        for key in base:
            if key not in users[uid]:
                users[uid][key] = base[key]
    return users[uid]

def load_state():
    global users, banned_users
    try:
        if STATE_FILE.exists():
            raw = json.loads(STATE_FILE.read_text("utf-8"))
            users = {int(k): v for k, v in raw.items()}
            for uid in users:
                base = blank_user()
                for key in base:
                    if key not in users[uid]:
                        users[uid][key] = base[key]
    except Exception:
        logger.exception("State load failed")
        users = {}
    
    try:
        if BAN_FILE.exists():
            banned_users = set(json.loads(BAN_FILE.read_text("utf-8")))
    except Exception:
        banned_users = set()

async def save_state():
    async with state_lock:
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(users, ensure_ascii=False), encoding="utf-8")
        tmp.replace(STATE_FILE)

async def save_bans():
    BAN_FILE.write_text(json.dumps(list(banned_users)), encoding="utf-8")

def fmt(n): 
    return f"{int(n):,}".replace(",", " ")

def kb(rows): 
    return InlineKeyboardMarkup(inline_keyboard=rows)

def is_brawl_pass(product):
    return product in BRAWL_PASS_PRICES

def get_game_emoji(game):
    return GAME_EMOJIS.get(game, "🎮")

# ⭐ ԿԼԱՎԻԱՏՈՒՐԱՆԵՐ (առանց «Չեղարկել» կոճակի)
def main_kb():
    return kb([
        [InlineKeyboardButton(text="🎮 Roblox", callback_data="game:roblox"), 
         InlineKeyboardButton(text="🔫 Standoff 2", callback_data="game:standoff2")],
        [InlineKeyboardButton(text="⭐ Brawl Stars", callback_data="game:brawlstars"), 
         InlineKeyboardButton(text="🪂 PUBG Mobile", callback_data="game:pubg")],
        [InlineKeyboardButton(text="⚽ FC Mobile", callback_data="game:fcmobile")],
        [InlineKeyboardButton(text="📩 Կապվեք մեզ հետ", callback_data="contact:open")]
    ])

def game_kb(game):
    rows = []
    for i, (name, price) in enumerate(CATALOG[game]["items"]):
        if name in BRAWL_PASS_PRICES:
            if name == "Brawl Pass":
                text = "🎫 Brawl Pass — ընտրել գինը ադմինի կողմից"
            else:
                text = "⭐ Brawl Pass+ — ընտրել գինը ադմինի կողմից"
        else:
            text = f"⚡ {name} — {fmt(price)} ֏"
        rows.append([InlineKeyboardButton(text=text, callback_data=f"product:{game}:{i}")])
    rows.append([InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:main")])
    return kb(rows)

def product_kb(game):
    return kb([
        [InlineKeyboardButton(text="✅ Գնել", callback_data="buy:confirm")],
        [InlineKeyboardButton(text="⬅️ Հետ", callback_data=f"back:game:{game}")]
    ])

def payment_kb():
    return kb([
        [InlineKeyboardButton(text="💵 Telcell", callback_data="payment:telcell")],
        [InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:product")]
    ])

def back_payment_kb(): 
    return kb([
        [InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:payment")]
    ])

def back_main_kb(): 
    return kb([
        [InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:main")]
    ])

def admin_bp_kb(uid, product_name):
    prices = BRAWL_PASS_PRICES[product_name]
    return kb([
        [
            InlineKeyboardButton(text=f"💰 {fmt(prices['low'])} ֏", 
                               callback_data=f"bpset:{uid}:{prices['low']}"),
            InlineKeyboardButton(text=f"💰 {fmt(prices['high'])} ֏", 
                               callback_data=f"bpset:{uid}:{prices['high']}")
        ],
        [InlineKeyboardButton(text="❌ Սխալ screenshot", 
                            callback_data=f"bpreject:{uid}")]
    ])

def admin_id_reject_kb(uid): 
    return kb([
        [InlineKeyboardButton(text="❌ Սխալ ID / Username", callback_data=f"id:reject:{uid}")]
    ])

def admin_password_reject_kb(uid):
    return kb([
        [InlineKeyboardButton(text="❌ Սխալ պասսվորդ", callback_data=f"pass:reject:{uid}")]
    ])

def admin_main_kb(uid):
    return kb([
        [InlineKeyboardButton(text="🔐 2FA հաստատում", callback_data=f"verify:menu:{uid}")],
        [InlineKeyboardButton(text="❌ Սխալ ID / Username", callback_data=f"id:reject:{uid}"),
         InlineKeyboardButton(text="❌ Սխալ պասսվորդ", callback_data=f"pass:reject:{uid}")],
        [InlineKeyboardButton(text="📸 Չեկը վատ է երևում", callback_data=f"receipt:bad:{uid}")],
        [InlineKeyboardButton(text="💸 Վերադարձ", callback_data=f"refund:{uid}")],
        [InlineKeyboardButton(text="✅ Ավարտել պատվերը", callback_data=f"order:complete:{uid}")]
    ])

def verify_catalog_kb(uid):
    return kb([
        [InlineKeyboardButton(text="📱 Այլ սարքով հաստատում", callback_data=f"verify:device:{uid}")],
        [InlineKeyboardButton(text="🔐 Authenticator", callback_data=f"verify:auth:{uid}")],
        [InlineKeyboardButton(text="📧 E-mail", callback_data=f"verify:email:{uid}")],
        [InlineKeyboardButton(text="⬅️ Հետ", callback_data=f"verify:back:{uid}")]
    ])

def admin_verify_retry_kb(uid, verify_type):
    return kb([
        [InlineKeyboardButton(text="🔄 Ուղարկել նոր կոդ", callback_data=f"verify:retry:{uid}:{verify_type}")],
        [InlineKeyboardButton(text="⬅️ Հետ", callback_data=f"verify:back:{uid}")]
    ])

def admin_refund_kb(uid): 
    return kb([
        [InlineKeyboardButton(text="💳 Քարտով վերադարձ", callback_data=f"refund:card:{uid}")],
        [InlineKeyboardButton(text="💵 Telcell վերադարձ", callback_data=f"refund:telcell:{uid}")],
        [InlineKeyboardButton(text="⬅️ Հետ", callback_data=f"admin:receipt:{uid}")]
    ])

def order_caption(uid):
    u = get_user(uid)
    
    if u.get("is_completed"):
        status = u.get("status", "✅ Ավարտված")
        return (f"📋 <b>Պատվեր #{escape(str(u.get('order_id') or '—'))}</b>\n"
                f"👤 {escape(str(u.get('username') or 'չկա'))}\n"
                f"🎮 {escape(CATALOG.get(u.get('game'), {}).get('name', '—'))}\n"
                f"📌 <b>{escape(status)}</b>")
    
    price = fmt(u.get("price") or 0) if u.get("price") else "Ադմինը դեռ չի ընտրել"
    verify_status = ""
    if u.get("verification_done"):
        if u.get("verification_type") == "device":
            verify_status = " (2FA: Այլ սարք ✅)"
        elif u.get("verification_type") == "auth":
            verify_status = " (2FA: Authenticator ✅)"
        elif u.get("verification_type") == "email":
            verify_status = " (2FA: E-mail ✅)"
        elif u.get("verification_type") == "Пропущено":
            verify_status = " (2FA: Պրոպուսկված)"
    elif u.get("verification_code_waiting"):
        verify_status = " (⏳ Սպասվում է 2FA կոդ)"
    
    return (f"🧾 <b>Պատվեր #{escape(str(u.get('order_id') or '—'))}</b>\n"
            f"👤 ID: <code>{uid}</code>\n🔹 Username: @{escape(str(u.get('username') or 'չկա'))}\n"
            f"🎮 Խաղ: {escape(CATALOG.get(u.get('game'), {}).get('name', '—'))}\n"
            f"📦 Ապրանք: <b>{escape(str(u.get('product') or '—'))}</b>\n"
            f"💰 Գին: <b>{price} ֏</b>\n💳 Վճարում: {escape(str(u.get('payment') or '—'))}\n"
            f"🎯 Game ID / Username: <code>{escape(str(u.get('game_id') or '—'))}</code>\n"
            f"🔑 Պասսվորդ: <code>{escape(str(u.get('game_password') or '—'))}</code>\n"
            f"📌 <b>Կարգավիճակ: {escape(str(u.get('status') or '—'))}{verify_status}</b>")

async def safe_answer(c, text=None):
    try: 
        await c.answer(text or "")
    except Exception: 
        pass

async def send_client(uid, text, markup=None):
    try: 
        await bot.send_message(uid, text, reply_markup=markup)
    except Exception: 
        logger.exception("Client message failed")

async def send_client_photo(uid, photo_path, caption, markup=None):
    try:
        photo = FSInputFile(photo_path)
        await bot.send_photo(uid, photo, caption=caption, reply_markup=markup)
    except Exception:
        logger.exception("Send photo failed")
        await send_client(uid, caption, markup)

async def notify_admin(text, markup=None):
    # ⭐ FUNKTSIAN ERKARAREL E, BAJC HIMA CHENQ OGTAGORCUM
    pass

async def update_admin_order(uid, markup=None):
    u = get_user(uid)
    if not u.get("order_message_id") or not u.get("order_chat_id"):
        return
    try:
        await bot.edit_message_caption(
            chat_id=u["order_chat_id"],
            message_id=u["order_message_id"],
            caption=order_caption(uid),
            reply_markup=markup
        )
    except Exception: 
        logger.exception("Could not update admin order")

async def create_or_replace_order(uid, file_id=None, markup=None):
    u = get_user(uid)
    file_id = file_id or u.get("receipt_file_id") or u.get("brawl_pass_screenshot_file_id")
    if not file_id:
        return
    
    chat_id = int(ORDER_CHANNEL_ID) if ORDER_CHANNEL_ID else ADMIN_ID
    
    try:
        if u.get("order_message_id") and u.get("order_chat_id"):
            await bot.edit_message_media(
                chat_id=u["order_chat_id"],
                message_id=u["order_message_id"],
                media=InputMediaPhoto(media=file_id, caption=order_caption(uid)),
                reply_markup=markup
            )
        else:
            sent = await bot.send_photo(
                chat_id, file_id, 
                caption=order_caption(uid), 
                reply_markup=markup
            )
            u["order_message_id"] = sent.message_id
            u["order_chat_id"] = chat_id
            
            if ORDER_CHANNEL_ID:
                try:
                    order_stats["total"] = order_stats.get("total", 0) + 1
                    order_stats["today"] = order_stats.get("today", 0) + 1
                except:
                    pass
    except Exception: 
        logger.exception("Could not create/replace admin order")
    await save_state()

def new_order(u, message):
    if not u.get("order_id"): 
        u["order_id"] = uuid.uuid4().hex[:8].upper()
    u["username"] = message.from_user.username
    u["is_completed"] = False
    u["created_at"] = datetime.datetime.now().isoformat()

async def check_banned(uid):
    if uid in banned_users:
        await bot.send_message(uid, "🚫 <b>Ձեզ արգելված է օգտվել բոտից</b>\n\nԿապվեք ադմինի հետ։")
        return True
    return False

async def clean_old_orders():
    while True:
        await asyncio.sleep(86400)
        try:
            now = datetime.datetime.now()
            deleted = 0
            for uid in list(users.keys()):
                u = users[uid]
                if u.get("is_completed") and u.get("completed_at"):
                    try:
                        completed = datetime.datetime.fromisoformat(u["completed_at"])
                        if (now - completed).days > 30:
                            base = blank_user()
                            for key in base:
                                if key not in ["username", "order_id", "game", "status", "is_completed", "completed_at"]:
                                    u[key] = base[key]
                            deleted += 1
                    except:
                        pass
            if deleted > 0:
                logger.info(f"Cleaned {deleted} old orders")
                await save_state()
        except Exception as e:
            logger.exception(f"Clean old orders error: {e}")

# ⭐ ՀԵՆԴԼԵՐՆԵՐ
@dp.message(CommandStart())
async def start(message: Message):
    uid = message.from_user.id
    if await check_banned(uid):
        return
    
    u = get_user(uid)
    u.clear()
    u.update(blank_user())
    u["username"] = message.from_user.username
    await save_state()
    await message.answer(
        "💎 <b>Games Vault Shop</b>\n\nԸնտրիր խաղը և ստացիր քո թվային ապրանքը արագ ու անվտանգ։",
        reply_markup=main_kb()
    )

@dp.message(Command("cancel"))
async def cancel_command(message: Message):
    uid = message.from_user.id
    if await check_banned(uid):
        return
    
    u = get_user(uid)
    u.clear()
    u.update(blank_user())
    u["username"] = message.from_user.username
    await save_state()
    await message.answer("❌ Պատվերը չեղարկվեց։", reply_markup=main_kb())

@dp.message(Command("stats"))
async def stats_command(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Մուտքը արգելված է")
        return
    
    active = sum(1 for u in users.values() if not u.get("is_completed"))
    completed = sum(1 for u in users.values() if u.get("is_completed"))
    refunds = sum(1 for u in users.values() if u.get("status") == "💸 Վերադարձ")
    
    today = datetime.datetime.now().date()
    today_orders = 0
    week_orders = 0
    
    for u in users.values():
        if u.get("is_completed") and u.get("completed_at"):
            try:
                date = datetime.datetime.fromisoformat(u["completed_at"]).date()
                if date == today:
                    today_orders += 1
                if (today - date).days <= 7:
                    week_orders += 1
            except:
                pass
    
    text = (
        "📊 <b>Վիճակագրություն</b>\n\n"
        f"🟢 Ակտիվ պատվերներ՝ <b>{active}</b>\n"
        f"✅ Ավարտված պատվերներ՝ <b>{completed}</b>\n"
        f"💸 Վերադարձներ՝ <b>{refunds}</b>\n"
        f"📦 Այսօրվա պատվերներ՝ <b>{today_orders}</b>\n"
        f"📅 Շաբաթվա պատվերներ՝ <b>{week_orders}</b>\n"
        f"👤 Ընդհանուր օգտատերեր՝ <b>{len(users)}</b>\n"
        f"🚫 Արգելված՝ <b>{len(banned_users)}</b>"
    )
    await message.answer(text)

@dp.message(Command("ban"))
async def ban_command(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Մուտքը արգելված է")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("📝 Օրինակ՝ <code>/ban 123456789</code>")
            return
        uid = int(parts[1])
        banned_users.add(uid)
        await save_bans()
        await message.answer(f"✅ Օգտատերը <code>{uid}</code> արգելվեց")
        await bot.send_message(uid, "🚫 <b>Ձեզ արգելվել է օգտվել բոտից</b>\n\nԿապվեք ադմինի հետ։")
    except:
        await message.answer("❌ Սխալ ID")

@dp.message(Command("unban"))
async def unban_command(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Մուտքը արգելված է")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("📝 Օրինակ՝ <code>/unban 123456789</code>")
            return
        uid = int(parts[1])
        if uid in banned_users:
            banned_users.remove(uid)
            await save_bans()
            await message.answer(f"✅ Օգտատերը <code>{uid}</code> ապարգելվեց")
        else:
            await message.answer(f"❌ Օգտատերը <code>{uid}</code> արգելված չէ")
    except:
        await message.answer("❌ Սխալ ID")

@dp.message(Command("admin"))
async def admin_cmd(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🛠 <b>Admin panel</b>\n\nԲոտը աշխատում է։\n\n📌 Հրամաններ՝\n/stats - վիճակագրություն\n/ban ID - արգելափակել\n/unban ID - ապարգելափակել")

@dp.message()
async def unknown_message(message: Message):
    uid = message.from_user.id
    if await check_banned(uid):
        return
    
    u = get_user(uid)
    if not u.get("order_id") or u.get("is_completed"):
        await message.answer(
            "💡 <b>Ինչպես օգտվել բոտից</b>\n\n"
            "1️⃣ Ընտրիր խաղ գլխավոր մենյուից\n"
            "2️⃣ Ընտրիր ապրանքը\n"
            "3️⃣ Հետևիր հրահանգներին\n\n"
            "📌 Եթե ինչ-որ բան չի աշխատում, սեղմիր «❌ Չեղարկել» և սկսիր նորից։",
            reply_markup=main_kb()
        )

@dp.callback_query(F.data == "back:main")
async def back_main(c: CallbackQuery):
    uid = c.from_user.id
    if await check_banned(uid):
        return
    await safe_answer(c)
    await c.message.edit_text(
        "💎 <b>Games Vault Shop</b>\n\nԸնտրիր խաղը։",
        reply_markup=main_kb()
    )

@dp.callback_query(F.data.startswith("game:"))
async def choose_game(c: CallbackQuery):
    uid = c.from_user.id
    if await check_banned(uid):
        return
    
    game = c.data.split(":", 1)[1]
    if game not in CATALOG:
        return
    u = get_user(uid)
    u["game"] = game
    u["product"] = None
    u["price"] = None
    await save_state()
    await safe_answer(c)
    await c.message.edit_text(
        f"{GAME_EMOJIS.get(game, '🎮')} {CATALOG[game]['name']}\n\nԸնտրիր ապրանքը։",
        reply_markup=game_kb(game)
    )

@dp.callback_query(F.data.startswith("back:game:"))
async def back_game(c: CallbackQuery):
    game = c.data.split(":", 2)[2]
    if game not in CATALOG:
        return
    await safe_answer(c)
    await c.message.edit_text(
        f"{CATALOG[game]['name']}\n\nԸնտրիր ապրանքը։",
        reply_markup=game_kb(game)
    )

@dp.callback_query(F.data.startswith("product:"))
async def choose_product(c: CallbackQuery):
    _, game, idx = c.data.split(":")
    try:
        name, price = CATALOG[game]["items"][int(idx)]
    except (KeyError, ValueError, IndexError):
        await safe_answer(c, "Սխալ ապրանք")
        return
    
    u = get_user(c.from_user.id)
    
    if name in BRAWL_PASS_PRICES:
        u.update(
            game=game,
            product=name,
            price=None,
            brawl_pass_waiting=True,
            brawl_pass_product=name,
            brawl_pass_screenshot_file_id=None,
            brawl_pass_price_selected=False,
            brawl_pass_rejected=False,
            status=f"⏳ Սպասվում է {name} screenshot",
            game_id=None,
            game_password=None,
            receipt_file_id=None,
            receipt_waiting=False,
            game_id_waiting=False,
            game_password_waiting=False,
            receipt_accepted=False,
            verification_done=False,
            verification_type=None,
            verification_code_waiting=False,
            verification_attempts=0,
            is_completed=False
        )
        new_order(u, c.message)
        await save_state()
        await safe_answer(c)
        
        await c.message.edit_text(
            f"📸 <b>{escape(name)}</b>\n\n"
            f"Ուղարկիր screenshot-ը, որտեղ հստակ երևում է, որ քո հաշվում <b>{escape(name)}</b> է։\n\n"
            f"⚠️ Screenshot-ը պետք է լինի ամբողջական և լավ տեսանելի։\n\n"
            f"Ադմինը screenshot-ը ստուգելուց հետո ինքը կընտրի ճիշտ գինը։",
            reply_markup=back_main_kb()
        )
        return
    
    u.update(
        game=game,
        product=name,
        price=price,
        brawl_pass_waiting=False,
        brawl_pass_product=None,
        brawl_pass_screenshot_file_id=None,
        brawl_pass_price_selected=False,
        brawl_pass_rejected=False,
        game_id=None,
        game_password=None,
        receipt_file_id=None,
        receipt_waiting=False,
        game_id_waiting=False,
        game_password_waiting=False,
        receipt_accepted=False,
        verification_done=False,
        verification_type=None,
        verification_code_waiting=False,
        verification_attempts=0,
        is_completed=False
    )
    await save_state()
    await safe_answer(c)
    await c.message.edit_text(
        f"📦 <b>{escape(name)}</b>\n\n💰 Գին՝ <b>{fmt(price)} ֏</b>\n\nՇարունակե՞նք գնումը։",
        reply_markup=product_kb(game)
    )

@dp.callback_query(F.data == "buy:confirm")
async def buy_confirm(c: CallbackQuery):
    u = get_user(c.from_user.id)
    
    if is_brawl_pass(u.get("product")):
        if not u.get("brawl_pass_price_selected") or not u.get("price"):
            await safe_answer(c, "⏳ Սպասիր ադմինի կողմից գնի ընտրությանը")
            return
    else:
        if not u.get("game") or not u.get("product") or not u.get("price"):
            await safe_answer(c, "Սխալ պատվեր")
            return
    
    await safe_answer(c)
    await c.message.edit_text(
        f"💳 <b>Վճարման եղանակ</b>\n\nՊատվեր՝ {escape(u['product'])}\nԳին՝ <b>{fmt(u['price'])} ֏</b>",
        reply_markup=payment_kb()
    )

@dp.callback_query(F.data == "back:product")
async def back_product(c: CallbackQuery):
    u = get_user(c.from_user.id)
    
    if is_brawl_pass(u.get("product")):
        if u.get("brawl_pass_price_selected"):
            await safe_answer(c)
            await c.message.edit_text(
                f"📦 <b>{escape(u['product'])}</b>\n\n💰 Գինը ընտրված է՝ <b>{fmt(u.get('price'))} ֏</b>\n\nՇարունակե՞նք գնումը։",
                reply_markup=product_kb(u['game'])
            )
        else:
            await safe_answer(c)
            await c.message.edit_text(
                f"📸 <b>{escape(u['product'])}</b>\n\n⏳ Սպասում ենք ադմինի կողմից գնի ընտրությանը։",
                reply_markup=back_main_kb()
            )
        return
    
    if not u.get("game") or not u.get("product"):
        return await back_main(c)
    
    await safe_answer(c)
    await c.message.edit_text(
        f"📦 <b>{escape(u['product'])}</b>\n\n💰 Գին՝ <b>{fmt(u.get('price') or 0)} ֏</b>",
        reply_markup=product_kb(u['game'])
    )

@dp.callback_query(F.data == "payment:telcell")
async def payment_telcell(c: CallbackQuery):
    uid = c.from_user.id
    if await check_banned(uid):
        return
    
    u = get_user(uid)
    u["payment"] = "Telcell"
    u["receipt_waiting"] = True
    u["status"] = "⏳ Սպասվում է վճարման screenshot"
    new_order(u, c.message)
    await save_state()
    await safe_answer(c)
    await c.message.edit_text(
        f"💵 <b>Telcell-ով վճարում</b>\n\n"
        f"<b>Հարգելի հաճախորդ,</b>\n"
        f"Ձեր պատվերը ստանալու համար խնդրում ենք կատարել վճարում <b>Telcell</b>-ի միջոցով։\n\n"
        f"📌 <b>Քայլ 1.</b> Գնացեք ձեր քաղաքի <b>մոտակա Telcell</b> տերմինալ։\n"
        f"📌 <b>Քայլ 2.</b> Ընտրեք <b>«Telcell Wallet»</b> բաժինը։\n"
        f"📌 <b>Քայլ 3.</b> Մուտքագրեք մեր համարը՝\n"
        f"📞 <code>{TELCELL_NUMBER}</code>\n\n"
        f"📌 <b>Քայլ 4.</b> Մուտքագրեք գումարը՝\n"
        f"💰 <b>{fmt(u['price'])} ֏</b>\n\n"
        f"📌 <b>Քայլ 5.</b> Հաստատեք վճարումը։\n"
        f"📌 <b>Քայլ 6.</b> Չեկի լուսանկարն ուղարկեք այս chat-ում։\n\n"
        f"⚠️ <b>Կարևոր է.</b> Չեկի լուսանկարը պետք է լինի <b>պարզ և ընթեռնելի</b>։\n\n"
        f"✅ Screenshot-ը ստանալուց հետո կհաստատենք պատվերը։\n\n"
        f"<b>Games Vault Shop</b> 🎮\n"
        f"<i>Արագ ու անվտանգ գնումներ։</i> 💎",
        reply_markup=back_payment_kb()
    )

@dp.callback_query(F.data == "back:payment")
async def back_payment(c: CallbackQuery):
    await safe_answer(c)
    await c.message.edit_text(
        "💳 <b>Ընտրիր վճարման եղանակը</b>",
        reply_markup=payment_kb()
    )

@dp.message(F.photo)
async def photo_input(message: Message):
    uid = message.from_user.id
    u = get_user(uid)
    file_id = message.photo[-1].file_id
    
    if u.get("brawl_pass_waiting") and u.get("brawl_pass_product"):
        product_name = u["brawl_pass_product"]
        u["brawl_pass_screenshot_file_id"] = file_id
        u["brawl_pass_waiting"] = False
        u["brawl_pass_rejected"] = False
        u["status"] = f"⏳ Սպասվում է ադմինի կողմից {product_name} գնի ընտրություն"
        new_order(u, message)
        
        await create_or_replace_order(uid, file_id, admin_bp_kb(uid, product_name))
        
        await message.answer(
            f"📸 Screenshot-ը ստացվեց։\n\n⏳ Սպասիր՝ ադմինը կստուգի screenshot-ը և կընտրի համապատասխան գինը {product_name}-ի համար։",
            reply_markup=back_main_kb()
        )
        return
    
    if u.get("receipt_waiting"):
        u["receipt_file_id"] = file_id
        u["receipt_accepted"] = False
        u["receipt_waiting"] = False
        u["status"] = "📋 Չեկը ստուգվում է"
        await save_state()
        
        await create_or_replace_order(uid, file_id, admin_main_kb(uid))
        await message.answer(
            "📸 Նոր չեկի screenshot-ը ստացվեց։\n\n✅ Այժմ ադմինը կստուգի այն։",
            reply_markup=main_kb()
        )
        return
    
    if not u.get("receipt_waiting") and not u.get("order_id"):
        return
    
    if not u.get("price"):
        await message.answer(
            "⏳ Գինը դեռ ընտրված չէ։ Սպասիր ադմինի որոշմանը։",
            reply_markup=back_main_kb()
        )
        return
    
    u["receipt_file_id"] = file_id
    u["receipt_accepted"] = False
    u["status"] = "⏳ Սպասվում է ID"
    u["game_id_waiting"] = True
    u["receipt_waiting"] = False
    new_order(u, message)
    
    await create_or_replace_order(uid, file_id, admin_id_reject_kb(uid))
    await message.answer(
        "📸 Վճարման screenshot-ը ստացվեց։\n\n✅ Այժմ ադմինը կստուգի այն։\n\n🎯 Հիմա ուղարկիր քո <b>Game ID / Username</b>։",
        reply_markup=back_main_kb()
    )

@dp.message(F.text)
async def text_input(message: Message):
    uid = message.from_user.id
    u = get_user(uid)
    text = message.text.strip()
    
    if u.get("verification_code_waiting"):
        if len(text) == 6 and text.isdigit():
            u["verification_code_waiting"] = False
            u["verification_done"] = True
            u["verification_attempts"] = 0
            u["status"] = "🔐 2FA կոդը հաստատված է"
            await save_state()
            await update_admin_order(uid, admin_main_kb(uid))
            await message.answer(
                "✅ <b>2FA կոդը հաստատվեց։</b>\n\n"
                "Պատվերը պատրաստ է ավարտման։\n\n"
                "⏳ Սպասիր ադմինի կողմից պատվերի ավարտմանը։",
                reply_markup=main_kb()
            )
            return
        else:
            u["verification_attempts"] = u.get("verification_attempts", 0) + 1
            await save_state()
            
            await message.answer(
                f"❌ <b>Սխալ կոդ</b> (փորձ #{u['verification_attempts']})\n\n"
                f"Մուտքագրիր <b>6-նիշանի կոդը</b> (միայն թվեր)։\n\n"
                f"📝 Օրինակ՝ <code>123456</code>",
                reply_markup=back_main_kb()
            )
            return
    
    if u.get("support_waiting"):
        if SUPPORT_CHANNEL_ID:
            await bot.send_message(
                int(SUPPORT_CHANNEL_ID),
                f"📩 <b>Support</b>\n👤 <code>{uid}</code>\n@{escape(message.from_user.username or 'չկա')}\n\n{escape(text)}"
            )
        u["support_waiting"] = False
        await save_state()
        await message.answer("✅ Հաղորդագրությունը ուղարկվեց աջակցությանը։", reply_markup=main_kb())
        return
    
    if u.get("refund_waiting"):
        u["refund_details"] = text
        u["refund_waiting"] = False
        u["status"] = "💸 Վերադարձ"
        await save_state()
        await update_admin_order(uid, admin_refund_kb(uid))
        await message.answer("✅ Տվյալները ստացվեցին։ Ադմինը կկատարի վերադարձը։", reply_markup=main_kb())
        return
    
    if u.get("game_id_waiting"):
        u["game_id"] = text
        u["game_id_waiting"] = False
        u["status"] = "⏳ Սպասվում է պասսվորդ"
        u["game_password_waiting"] = True
        await save_state()
        await update_admin_order(uid, admin_password_reject_kb(uid))
        await message.answer(
            "✅ ID / Username-ը ստացվեց։\n\n🔑 Հիմա ուղարկիր <b>պասսվորդը</b> (password)։",
            reply_markup=back_main_kb()
        )
        return
    
    if u.get("game_password_waiting"):
        u["game_password"] = text
        u["game_password_waiting"] = False
        u["status"] = "📋 Չեկը ստուգվում է"
        await save_state()
        await update_admin_order(uid, admin_main_kb(uid))
        await message.answer(
            "✅ Պասսվորդը ստացվեց։\n\n⏳ Սպասիր ադմինի կողմից չեկի հաստատմանը։",
            reply_markup=main_kb()
        )
        return
    
    await message.answer("Ընտրիր բաժինը։", reply_markup=main_kb())

@dp.callback_query(F.data == "contact:open")
async def contact_open(c: CallbackQuery):
    u = get_user(c.from_user.id)
    u["support_waiting"] = True
    await save_state()
    await safe_answer(c)
    await c.message.edit_text(
        "📩 <b>Կապ Games Vault Shop-ի հետ</b>\n\nՈւղարկիր հաղորդագրություն, և մենք կպատասխանենք։",
        reply_markup=back_main_kb()
    )

@dp.callback_query(F.data.startswith("bpset:"))
async def bp_set_price(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await safe_answer(c, "Մուտքը արգելված է")
        return
    
    _, uid_s, price_s = c.data.split(":")
    uid = int(uid_s)
    price = int(price_s)
    u = get_user(uid)
    
    if not is_brawl_pass(u.get("product")):
        await safe_answer(c, "Սա Brawl Pass պատվեր չէ")
        return
    
    bp_prices = BRAWL_PASS_PRICES[u["product"]]
    if price not in [bp_prices["low"], bp_prices["high"]]:
        await safe_answer(c, "Սխալ գին")
        return
    
    u["price"] = price
    u["brawl_pass_price_selected"] = True
    u["brawl_pass_rejected"] = False
    u["status"] = f"💰 Գինը ընտրված է՝ {fmt(price)} ֏"
    await save_state()
    
    await update_admin_order(uid, None)
    
    await send_client(
        uid,
        f"✅ <b>Screenshot-ը հաստատվեց։</b>\n\n"
        f"📦 {escape(u['product'])}\n"
        f"💰 Ձեր գինը՝ <b>{fmt(price)} ֏</b>\n\n"
        f"Սեղմիր «Շարունակել գնումը», որպեսզի ընտրես վճարման եղանակը։",
        kb([
            [InlineKeyboardButton(text="💳 Շարունակել գնումը", callback_data="buy:confirm")],
            [InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:main")]
        ])
    )
    
    await safe_answer(c, f"✅ Գինը ընտրված է՝ {fmt(price)} ֏")

@dp.callback_query(F.data.startswith("bpreject:"))
async def bp_reject(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await safe_answer(c, "Մուտքը արգելված է")
        return    
    uid = int(c.data.split(":")[1])
    u = get_user(uid)
    
    if not is_brawl_pass(u.get("product")):
        await safe_answer(c, "Սա Brawl Pass պատվեր չէ")
        return
    
    u["brawl_pass_waiting"] = True
    u["brawl_pass_price_selected"] = False
    u["brawl_pass_screenshot_file_id"] = None
    u["brawl_pass_rejected"] = True
    u["status"] = "⏳ Սպասվում է նոր Brawl Pass screenshot"
    await save_state()
    
    await send_client(
        uid,
        f"❌ <b>Screenshot-ը սխալ է կամ լավ չի երևում</b>\n\n"
        f"Ուղարկիր <b>նոր, ամբողջական և ավելի հստակ screenshot</b> {u['product']}-ի համար։\n\n"
        f"📸 Պարզապես ուղարկիր նոր screenshot-ը այս chat-ում։\n\n"
        f"⚠️ Հին պատվերը չի կրկնվի, սպասում ենք նոր screenshot-ի։",
        reply_markup=back_main_kb()
    )
    
    await update_admin_order(uid, admin_bp_kb(uid, u["product"]))
    await safe_answer(c, "❌ Screenshot-ը մերժվեց, սպասվում է նորը")

@dp.callback_query(F.data.startswith("id:reject:"))
async def admin_id_reject(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await safe_answer(c, "Մուտքը արգելված է")
        return
    
    uid = int(c.data.split(":")[2])
    u = get_user(uid)
    
    u["game_id_waiting"] = True
    u["game_id"] = None
    u["status"] = "⏳ Սպասվում է նոր ID"
    await save_state()
    await send_client(uid, "❌ <b>Սխալ ID / Username</b>\n\nՈւղարկիր ճիշտ Game ID / Username-ը։", back_main_kb())
    await update_admin_order(uid, admin_id_reject_kb(uid))
    await safe_answer(c, "Սպասվում է նոր ID")

@dp.callback_query(F.data.startswith("pass:reject:"))
async def admin_password_reject(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await safe_answer(c, "Մուտքը արգելված է")
        return
    
    uid = int(c.data.split(":")[2])
    u = get_user(uid)
    
    u["game_password_waiting"] = True
    u["game_password"] = None
    u["status"] = "⏳ Սպասվում է նոր պասսվորդ"
    await save_state()
    await send_client(uid, "❌ <b>Սխալ պասսվորդ</b>\n\nՈւղարկիր ճիշտ պասսվորդը։", back_main_kb())
    await update_admin_order(uid, admin_password_reject_kb(uid))
    await safe_answer(c, "Սպասվում է նոր պասսվորդ")

@dp.callback_query(F.data.startswith("receipt:bad:"))
async def receipt_bad(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await safe_answer(c, "Մուտքը արգելված է")
        return
    
    uid = int(c.data.split(":")[2])
    u = get_user(uid)
    
    u["receipt_waiting"] = True
    u["receipt_accepted"] = False
    u["status"] = "⏳ Սպասվում է նոր չեկ (վատ որակ)"
    await save_state()
    
    await send_client(
        uid,
        "📸 <b>Չեկի screenshot-ը վատ է երևում</b>\n\n"
        "Խնդրում ենք ուղարկել <b>նոր, ավելի հստակ screenshot</b> չեկից։\n\n"
        "✅ Համոզվեք, որ լուսանկարը՝\n"
        "• <b>պարզ</b> է և առանց լղոզման\n"
        "• <b>ամբողջական</b> (երևում է ամբողջ չեկը)\n"
        "• <b>լավ լուսավորված</b>\n\n"
        "📸 Պարզապես ուղարկիր նոր screenshot-ը այս chat-ում։",
        reply_markup=back_main_kb()
    )
    
    await update_admin_order(uid, admin_main_kb(uid))
    await safe_answer(c, "📸 Կլիենտին խնդրեցինք նոր չեկ ուղարկել")

@dp.callback_query(F.data.startswith("order:complete:"))
async def order_complete(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await safe_answer(c, "Մուտքը արգելված է")
        return
    
    uid = int(c.data.split(":")[2])
    u = get_user(uid)
    
    if not u.get("verification_done"):
        u["verification_type"] = "Пропущено"
        u["verification_done"] = True
    
    u["status"] = "✅ Դոնատը հաստատված է"
    u["is_completed"] = True
    u["completed_at"] = datetime.datetime.now().isoformat()
    
    game = u.get("game")
    username = u.get("username")
    order_id = u.get("order_id")
    
    u["product"] = None
    u["price"] = None
    u["payment"] = None
    u["game_id"] = None
    u["game_password"] = None
    u["verification_type"] = None
    u["verification_done"] = False
    u["verification_code_waiting"] = False
    u["receipt_file_id"] = None
    u["receipt_accepted"] = False
    u["game_id_waiting"] = False
    u["game_password_waiting"] = False
    u["receipt_waiting"] = False
    u["brawl_pass_waiting"] = False
    u["brawl_pass_screenshot_file_id"] = None
    u["brawl_pass_price_selected"] = False
    u["brawl_pass_product"] = None
    u["brawl_pass_rejected"] = False
    
    await save_state()
    await update_admin_order(uid, None)
    
    await send_client(uid, "🎉 <b>Պատվերը ավարտված է։</b>\n\n✅ Դուք ստացել եք ձեր ապրանքը։\n\nՇնորհակալություն Games Vault Shop-ը ընտրելու համար։\n\n💎 <b>Games Vault Shop</b> 🎮", main_kb())
    await safe_answer(c, "Պատվերը ավարտվեց")

@dp.callback_query(F.data.startswith("refund:"))
async def refund_action(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await safe_answer(c, "Մուտքը արգելված է")
        return
    
    parts = c.data.split(":")
    uid = int(parts[-1])
    u = get_user(uid)
    
    if len(parts) == 2:
        u["refund_waiting"] = True
        u["status"] = "💸 Սպասվում են վերադարձի տվյալներ"
        await save_state()
        await update_admin_order(uid, admin_refund_kb(uid))
        await send_client(uid, "💸 <b>Վերադարձ</b>\n\nՈւղարկիր այն տվյալները, որոնցով պետք է կատարվի վերադարձը։")
        await safe_answer(c)
        return
    
    method = "Քարտ" if parts[1] == "card" else "Telcell"
    u["status"] = "💸 Վերադարձ"
    u["is_completed"] = True
    u["completed_at"] = datetime.datetime.now().isoformat()
    
    game = u.get("game")
    username = u.get("username")
    order_id = u.get("order_id")
    
    u["product"] = None
    u["price"] = None
    u["payment"] = None
    u["game_id"] = None
    u["game_password"] = None
    u["receipt_file_id"] = None
    u["receipt_accepted"] = False
    u["game_id_waiting"] = False
    u["game_password_waiting"] = False
    u["receipt_waiting"] = False
    
    await save_state()
    await update_admin_order(uid, None)
    
    await send_client(uid, f"💸 Վերադարձի հայտը ընդունվեց։ Եղանակ՝ <b>{method}</b>։\n\nՇնորհակալություն Games Vault Shop-ը ընտրելու համար։", main_kb())
    await safe_answer(c, "Վերադարձը նշվեց")

@dp.callback_query(F.data.startswith("verify:menu:"))
async def verify_menu(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await safe_answer(c, "Մուտքը արգելված է")
        return
    
    uid = int(c.data.split(":")[2])
    await safe_answer(c)
    await c.message.edit_text(
        "🔐 <b>2FA հաստատում</b>\n\n"
        "Ընտրիր հաստատման եղանակը՝\n\n"
        "📱 <b>Այլ սարքով</b> - հաստատիր մեկ այլ սարքից\n"
        "🔐 <b>Authenticator</b> - մուտքագրիր կոդը Google/Microsoft Authenticator-ից\n"
        "📧 <b>E-mail</b> - մուտքագրիր կոդը E-mail-ից\n\n"
        "⚠️ Կարող ես նաև պարզապես ավարտել պատվերը առանց 2FA։",
        reply_markup=verify_catalog_kb(uid)
    )

@dp.callback_query(F.data.startswith("verify:back:"))
async def verify_back(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await safe_answer(c, "Մուտքը արգելված է")
        return
    
    uid = int(c.data.split(":")[2])
    await safe_answer(c)
    await c.message.edit_text(
        "🛠 <b>Ադմինի վահանակ</b>\n\nԸնտրիր գործողությունը՝",
        reply_markup=admin_main_kb(uid)
    )

@dp.callback_query(F.data.startswith("verify:device:"))
async def verify_device(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await safe_answer(c, "Մուտքը արգելված է")
        return
    
    uid = int(c.data.split(":")[2])
    u = get_user(uid)
    
    u["verification_type"] = "device"
    u["verification_done"] = True
    u["verification_code_waiting"] = False
    u["verification_attempts"] = 0
    u["status"] = "🔐 2FA՝ Այլ սարքով հաստատում"
    await save_state()
    
    await send_client_photo(
        uid,
        VERIFY_IMAGES["device"],
        "📱 <b>2FA — Այլ սարքով հաստատում</b>\n\n"
        "1️⃣ Բացիր Roblox հավելվածը մեկ այլ սարքից (հեռախոս/պլանշետ)\n"
        "2️⃣ Հաստատիր մուտքը Roblox հավելվածում\n"
        "3️⃣ Սեղմիր «Approve» կամ «Հաստատել»\n\n"
        "⚠️ <b>Կարևոր.</b> Հաստատիր միայն այն մուտքը, որը դու ես սկսել։\n\n"
        "✅ Հաստատումից հետո պատվերը կավարտվի։",
        back_main_kb()
    )
    
    await c.message.edit_text(
        "✅ 2FA՝ Այլ սարքով հաստատում — հրահանգը ուղարկվեց клиенту\n\n"
        "🛠 <b>Ադմինի վահանակ</b>\n\nԸնտրիր գործողությունը՝",
        reply_markup=admin_main_kb(uid)
    )
    await safe_answer(c, "✅ 2FA՝ Այլ սարք — հրահանգը ուղարկվեց")

@dp.callback_query(F.data.startswith("verify:auth:"))
async def verify_auth(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await safe_answer(c, "Մուտքը արգելված է")
        return
    
    uid = int(c.data.split(":")[2])
    u = get_user(uid)
    
    u["verification_type"] = "auth"
    u["verification_done"] = False
    u["verification_code_waiting"] = True
    u["verification_attempts"] = 0
    u["status"] = "⏳ Սպասվում է Authenticator կոդ"
    await save_state()
    
    await send_client_photo(
        uid,
        VERIFY_IMAGES["auth"],
        "🔐 <b>2FA — Authenticator</b>\n\n"
        "1️⃣ Բացիր Google Authenticator / Microsoft Authenticator\n"
        "2️⃣ Գտիր Roblox-ի 6-նիշանի կոդը\n"
        "3️⃣ <b>Մուտքագրիր կոդը</b> այս chat-ում\n\n"
        "⚠️ <b>Կարևոր.</b> Կոդը թարմացվում է ամեն 30 վայրկյանը մեկ։\n\n"
        "📝 Ուղարկիր 6-նիշանի կոդը (օրինակ՝ <code>123456</code>)",
        back_main_kb()
    )
    
    await c.message.edit_text(
        "⏳ Սպասում ենք Authenticator կոդի մուտքագրմանը...\n\n"
        "🛠 <b>Ադմինի վահանակ</b>",
        reply_markup=admin_main_kb(uid)
    )
    await safe_answer(c, "⏳ Սպասում ենք Authenticator կոդի")

@dp.callback_query(F.data.startswith("verify:email:"))
async def verify_email(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await safe_answer(c, "Մուտքը արգելված է")
        return
    
    uid = int(c.data.split(":")[2])
    u = get_user(uid)
    
    u["verification_type"] = "email"
    u["verification_done"] = False
    u["verification_code_waiting"] = True
    u["verification_attempts"] = 0
    u["status"] = "⏳ Սպասվում է E-mail կոդ"
    await save_state()
    
    await send_client_photo(
        uid,
        VERIFY_IMAGES["email"],
        "📧 <b>2FA — E-mail</b>\n\n"
        "1️⃣ Ստուգիր քո E-mail-ը (Gmail, Mail.ru, և այլն)\n"
        "2️⃣ Roblox-ը ուղարկել է 6-նիշանի հաստատման կոդ\n"
        "3️⃣ <b>Մուտքագրիր կոդը</b> այս chat-ում\n\n"
        "⚠️ <b>Կարևոր.</b> Ստուգիր նաև Spam պանակը։\n\n"
        "📝 Ուղարկիր 6-նիշանի կոդը (օրինակ՝ <code>123456</code>)",
        back_main_kb()
    )
    
    await c.message.edit_text(
        "⏳ Սպասում ենք E-mail կոդի մուտքագրմանը...\n\n"
        "🛠 <b>Ադմինի վահանակ</b>",
        reply_markup=admin_main_kb(uid)
    )
    await safe_answer(c, "⏳ Սպասում ենք E-mail կոդի")

@dp.callback_query(F.data.startswith("verify:retry:"))
async def verify_retry(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await safe_answer(c, "Մուտքը արգելված է")
        return
    
    parts = c.data.split(":")
    uid = int(parts[2])
    verify_type = parts[3]
    u = get_user(uid)
    
    u["verification_attempts"] = 0
    u["verification_code_waiting"] = True
    u["verification_done"] = False
    u["status"] = f"⏳ Սպասվում է նոր {verify_type} կոդ"
    await save_state()
    
    if verify_type == "auth":
        await send_client_photo(
            uid,
            VERIFY_IMAGES["auth"],
            "🔄 <b>Մուտքագրիր նոր 2FA կոդ — Authenticator</b>\n\n"
            "1️⃣ Բացիր Google Authenticator / Microsoft Authenticator\n"
            "2️⃣ Գտիր Roblox-ի 6-նիշանի կոդը\n"
            "3️⃣ <b>Մուտքագրիր նոր կոդը</b> այս chat-ում\n\n"
            "⚠️ <b>Կարևոր.</b> Կոդը թարմացվում է ամեն 30 վայրկյանը մեկ։\n\n"
            "📝 Ուղարկիր 6-նիշանի կոդը (օրինակ՝ <code>123456</code>)",
            back_main_kb()
        )
    elif verify_type == "email":
        await send_client_photo(
            uid,
            VERIFY_IMAGES["email"],
            "🔄 <b>Մուտքագրիր նոր 2FA կոդ — E-mail</b>\n\n"
            "1️⃣ Ստուգիր քո E-mail-ը (Gmail, Mail.ru, և այլն)\n"
            "2️⃣ Roblox-ը ուղարկել է նոր 6-նիշանի կոդ\n"
            "3️⃣ <b>Մուտքագրիր նոր կոդը</b> այս chat-ում\n\n"
            "⚠️ <b>Կարևոր.</b> Ստուգիր նաև Spam պանակը։\n\n"
            "📝 Ուղարկիր 6-նիշանի կոդը (օրինակ՝ <code>123456</code>)",
            back_main_kb()
        )
    
    await c.message.edit_text(
        "🔄 Նոր 2FA կոդը ուղարկվեց клиенту\n\n"
        "⏳ Սպասում ենք նոր կոդի մուտքագրմանը...\n\n"
        "🛠 <b>Ադմինի վահանակ</b>",
        reply_markup=admin_main_kb(uid)
    )
    await safe_answer(c, "🔄 Նոր կոդը ուղարկվեց клиенту")

# ⭐ ԱՌՈՂՋՈՒԹՅԱՆ ՍԵՐՎԵՐ
async def health_handler(request):
    return web.Response(text="OK")

async def run_web():
    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info("Health server started on port %s", PORT)
    while True:
        await asyncio.sleep(3600)

# ⭐ ԳՈՐԾԱՐԿՈՒՄ
async def main():
    load_state()
    await save_bans()
    asyncio.create_task(clean_old_orders())
    await asyncio.gather(
        dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()),
        run_web()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
