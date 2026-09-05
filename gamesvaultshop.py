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

# ⭐ ԿԱՐԳԱՎՈՐՈՒՄՆԵՐ
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
ORDER_CHANNEL_ID = os.getenv("ORDER_CHANNEL_ID", "")
SUPPORT_CHANNEL_ID = os.getenv("SUPPORT_CHANNEL_ID", "")
TELCELL_NUMBER = os.getenv("TELCELL_NUMBER", "043055510")
CARD_NUMBER = os.getenv("CARD_NUMBER", "")
PORT = int(os.getenv("PORT", "8080"))
STATE_FILE = Path(os.getenv("STATE_FILE", "orders_state.json"))
LOG_FILE = Path("bot.log")
BAN_FILE = Path("banned_users.json")

# ⭐ 2FA-Ի ՆԿԱՐՆԵՐ
VERIFY_IMAGES = {
    "device": "images/2fa_device.jpg",
    "auth": "images/2fa_auth.jpg",
    "email": "images/2fa_email.jpg"
}

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN չգտնվեց")
if not ADMIN_ID:
    raise RuntimeError("ADMIN_ID չգտնվեց")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

users = {}
banned_users = set()
state_lock = asyncio.Lock()
order_stats = defaultdict(int)

# ⭐ STARTUP
@dp.startup()
async def on_startup():
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook-ը ջնջվեց")
    except Exception as e:
        logger.warning(f"Webhook-ի ջնջումը ձախողվեց: {e}")

# ⭐ ԽԱՂԵՐԻ ԷՄՈՋԻՆԵՐ
GAME_EMOJIS = {
    "roblox": "🎮",
    "standoff2": "🔫",
    "brawlstars": "⭐",
    "pubg": "🪂",
    "fcmobile": "⚽"
}

# ⭐ BRAWL PASS-Ի ԳՆԵՐ
BRAWL_PASS_PRICES = {
    "Brawl Pass": {"low": 2500, "high": 3400},
    "Brawl Pass+": {"low": 3400, "high": 4800}
}

# ⭐ ԿԱՏԱԼՈԳ
CATALOG = {
    "roblox": {"name": "Roblox", "items": [("40 Robux",350),("80 Robux",650),("120 Robux",950),("400 Robux",2700),("520 Robux",3600),("840 Robux",4850),("1,240 Robux",7300),("1,700 Robux",8800),("1,820 Robux",9700),("4,500 Robux",21000),("10,000 Robux",40000),("22,500 Robux",88000)]},
    "standoff2": {"name": "Standoff 2", "items": [("100 Gold",1000),("200 Gold",2000),("300 Gold",2900),("500 Gold",4000),("600 Gold",5100),("700 Gold",5800),("1,000 Gold",7100),("1,500 Gold",10300),("3,000 Gold",15800)]},
    "brawlstars": {"name": "Brawl Stars", "items": [("30 Gems",800),("80 Gems",1600),("170 Gems",3000),("360 Gems",5300),("950 Gems",13000),("Brawl Pass",0),("Brawl Pass+",0),("Պրոգրես Brawl Pass → Brawl Pass+",1800),("Pro Pass",12800)]},
    "pubg": {"name": "PUBG Mobile", "items": [("60 UC",500),("300 UC + 25 UC 🎁",2000),("600 UC + 60 UC 🎁",4000),("1,500 UC + 300 UC 🎁",10000),("3,000 UC + 850 UC 🎁",20000),("6,000 UC + 2,100 UC 🎁",40000)]},
    "fcmobile": {"name": "FC Mobile", "items": [("40 FC Points",300),("100 FC Points",650),("500 + 20 FC Points 🎁",3000),("1,000 + 70 FC Points 🎁",5500),("2,000 + 200 FC Points 🎁",11000),("5,000 + 750 FC Points 🎁",27000),("10,000 + 2,000 FC Points 🎁",54000)]},
}

def blank_user():
    return {
        "game": None, "product": None, "price": None, "payment": None,
        "username": None, "order_id": None, "game_id": None, "game_password": None,
        "receipt_file_id": None, "receipt_waiting": False,
        "game_id_waiting": False, "game_password_waiting": False,
        "receipt_accepted": False,
        "verification_type": None, "verification_done": False,
        "verification_code_waiting": False, "verification_attempts": 0,
        "verification_device_waiting": False,
        "order_message_id": None, "order_chat_id": None,
        "support_waiting": False, "refund_waiting": False,
        "refund_method": None, "refund_operator": None,
        "refund_details": None,
        "status": "⏳ Ընթացքի մեջ", "is_completed": False,
        "created_at": datetime.datetime.now().isoformat(), "completed_at": None,
        "brawl_pass_waiting": False, "brawl_pass_screenshot_file_id": None,
        "brawl_pass_price_selected": False, "brawl_pass_product": None,
        "brawl_pass_rejected": False,
        "verification_code": None,
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
        users = {}
    try:
        if BAN_FILE.exists():
            banned_users = set(json.loads(BAN_FILE.read_text("utf-8")))
    except:
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

# ⭐ ԿԼԱՎԻԱՏՈՒՐԱՆԵՐ
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
                text = "🎫 Brawl Pass — գինը կընտրի ադմինը"
            else:
                text = "⭐ Brawl Pass+ — գինը կընտրի ադմինը"
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
        [InlineKeyboardButton(text="💳 Քարտով", callback_data="payment:card")],
        [InlineKeyboardButton(text="💵 Telcell", callback_data="payment:telcell")],
        [InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:product")]
    ])

def back_payment_kb(): 
    return kb([[InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:payment")]])

def back_main_kb(): 
    return kb([[InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:main")]])

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
        [
            InlineKeyboardButton(
                text="❌ Սխալ ID / Username",
                callback_data=f"id:reject:{uid}"
            )
        ]
    ])

def admin_password_reject_kb(uid):
    return kb([
        [InlineKeyboardButton(text="❌ Սխալ պասսվորդ", callback_data=f"pass:reject:{uid}")]
    ])

def admin_receipt_kb(uid):
    return kb([
        [InlineKeyboardButton(text="✅ Հաստատել չեկը", callback_data=f"receipt:accept:{uid}"),
         InlineKeyboardButton(text="❌ Սխալ չեկ", callback_data=f"receipt:reject:{uid}")],
        [InlineKeyboardButton(text="📸 Չեկը վատ է երևում", callback_data=f"receipt:bad:{uid}")]
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

def admin_refund_kb(uid):
    return kb([
        [InlineKeyboardButton(text="💳 Վերադարձ քարտով", callback_data=f"refund:card:{uid}")],
        [InlineKeyboardButton(text="💵 Վերադարձ Telcell-ով", callback_data=f"refund:telcell:{uid}")],
        [InlineKeyboardButton(text="⬅️ Հետ", callback_data=f"admin:receipt:{uid}")]
    ])

def operator_kb(uid):
    return kb([
        [InlineKeyboardButton(text="📱 Beeline", callback_data=f"refund:operator:{uid}:beeline"),
         InlineKeyboardButton(text="📱 Ucom", callback_data=f"refund:operator:{uid}:ucom")],
        [InlineKeyboardButton(text="📱 MTS", callback_data=f"refund:operator:{uid}:mts"),
         InlineKeyboardButton(text="📱 Viva-MTS", callback_data=f"refund:operator:{uid}:vivamts")],
        [InlineKeyboardButton(text="📱 Team", callback_data=f"refund:operator:{uid}:team")],
        [InlineKeyboardButton(text="⬅️ Հետ", callback_data=f"admin:receipt:{uid}")]
    ])

def verify_catalog_kb(uid):
    return kb([
        [InlineKeyboardButton(text="📱 Այլ սարքով հաստատում", callback_data=f"verify:device:{uid}")],
        [InlineKeyboardButton(text="🔐 Authenticator", callback_data=f"verify:auth:{uid}")],
        [InlineKeyboardButton(text="📧 E-mail", callback_data=f"verify:email:{uid}")],
        [InlineKeyboardButton(text="⬅️ Հետ", callback_data=f"verify:back:{uid}")]
    ])

def verify_device_confirm_kb(uid):
    return kb([
        [InlineKeyboardButton(text="✅ Հաստատել եմ", callback_data=f"verify:device:confirm:{uid}")],
        [InlineKeyboardButton(text="⬅️ Հետ", callback_data=f"verify:back:{uid}")]
    ])

def admin_verify_retry_kb(uid, verify_type):
    return kb([
        [InlineKeyboardButton(text="🔄 Ուղարկել նոր կոդ", callback_data=f"verify:retry:{uid}:{verify_type}")],
        [InlineKeyboardButton(text="⬅️ Հետ", callback_data=f"verify:back:{uid}")]
    ])

# ⭐ ORDER_CAPTION
def order_caption(uid):
    u = get_user(uid)
    
    if u.get("is_completed"):
        return (f"✅ Պատվերը ավարտված է\n\n"
                f"📦 Պատվեր՝ #{escape(str(u.get('order_id') or '—'))}\n"
                f"👤 Username՝ @{escape(str(u.get('username') or 'չկա'))}\n"
                f"💎 Ապրանք՝ {escape(str(u.get('product') or '—'))}\n"
                f"💰 Գին՝ {fmt(u.get('price') or 0)} ֏\n\n"
                f"📌 Կարգավիճակ՝ ✅ Ավարտված")
    
    price = fmt(u.get("price") or 0) if u.get("price") else "Ադմինը դեռ չի ընտրել"
    game_id = u.get("game_id") or "—"
    game_password = u.get("game_password") or "—"
    status = u.get("status") or "⏳ Ընթացքի մեջ"
    
    # ⭐ 2FA կարգավիճակ
    verify_status = ""
    if u.get("verification_done"):
        verify_status = f"\n🔐 2FA՝ ✅ Հաստատված ({u.get('verification_type', '—')})"
    elif u.get("verification_code_waiting"):
        verify_status = f"\n🔐 2FA՝ ⏳ Սպասվում է կոդ ({u.get('verification_type', '—')})"
    elif u.get("verification_device_waiting"):
        verify_status = f"\n🔐 2FA՝ ⏳ Սպասվում է այլ սարքի հաստատում"
    
    if u.get("refund_method") == "Քարտ":
        refund_info = f"💳 Վերադարձ քարտով՝ {escape(str(u.get('refund_details') or '—'))}"
    elif u.get("refund_method") == "Telcell":
        refund_info = f"💵 Telcell ({escape(str(u.get('refund_operator') or '—'))})՝ {escape(str(u.get('refund_details') or '—'))}"
    else:
        refund_info = ""
    
    if refund_info:
        return (f"📦 Նոր պատվեր\n\n"
                f"🎮 Խաղ՝ {escape(CATALOG.get(u.get('game'), {}).get('name', '—'))}\n"
                f"👤 Username՝ @{escape(str(u.get('username') or 'չկա'))}\n"
                f"🆔 ID՝ {escape(str(game_id))}\n"
                f"💎 Ապրանք՝ {escape(str(u.get('product') or '—'))}\n"
                f"💰 Գին՝ {price} ֏\n"
                f"💳 Վճարման եղանակ՝ {escape(str(u.get('payment') or '—'))}\n"
                f"🔑 Պասսվորդ՝ {escape(str(game_password))}\n"
                f"{verify_status}\n\n"
                f"💸 {refund_info}\n\n"
                f"📌 Կարգավիճակ՝ ⏳ {escape(str(status))}")
    
    return (f"📦 Նոր պատվեր\n\n"
            f"🎮 Խաղ՝ {escape(CATALOG.get(u.get('game'), {}).get('name', '—'))}\n"
            f"👤 Username՝ @{escape(str(u.get('username') or 'չկա'))}\n"
            f"🆔 ID՝ {escape(str(game_id))}\n"
            f"💎 Ապրանք՝ {escape(str(u.get('product') or '—'))}\n"
            f"💰 Գին՝ {price} ֏\n"
            f"💳 Վճարման եղանակ՝ {escape(str(u.get('payment') or '—'))}\n"
            f"🔑 Պասսվորդ՝ {escape(str(game_password))}\n"
            f"{verify_status}\n\n"
            f"📌 Կարգավիճակ՝ ⏳ {escape(str(status))}")

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

async def update_admin_order(uid, markup=None):
    u = get_user(uid)
    chat_id = int(ORDER_CHANNEL_ID) if ORDER_CHANNEL_ID else ADMIN_ID
    
    if not u.get("order_message_id") or not u.get("order_chat_id"):
        try:
            sent = await bot.send_photo(
                chat_id,
                u.get("receipt_file_id") or u.get("brawl_pass_screenshot_file_id"),
                caption=order_caption(uid),
                reply_markup=markup
            )
            u["order_message_id"] = sent.message_id
            u["order_chat_id"] = chat_id
            await save_state()
            return
        except Exception as e:
            logger.error(f"Failed to send to admin: {e}")
            return
    
    try:
        await bot.edit_message_caption(
            chat_id=u["order_chat_id"],
            message_id=u["order_message_id"],
            caption=order_caption(uid),
            reply_markup=markup
        )
    except Exception as e:
        if "message is not modified" not in str(e):
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
    except Exception: 
        logger.exception("Could not create/replace admin order")
    await save_state()

def new_order(u, user):
    if not u.get("order_id"):
        u["order_id"] = uuid.uuid4().hex[:8].upper()
    
    if hasattr(user, "from_user"):
        tg_user = user.from_user
    else:
        tg_user = user
    
    u["username"] = tg_user.username
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
                logger.info(f"Ջնջվեց {deleted} հին պատվեր")
                await save_state()
        except Exception as e:
            logger.exception(f"Clean old orders error: {e}")

# ⭐ HEALTH CHECK
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
    logger.info("✅ Health server started on port %s", PORT)
    while True:
        await asyncio.sleep(3600)

# ============================================
# ⭐ ՀԻՄՆԱԿԱՆ ՀԵՆԴԼԵՐՆԵՐ
# ============================================

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
        "💎 Games Vault Shop\n\nԸնտրիր խաղը և ստացիր քո թվային ապրանքը արագ ու անվտանգ։",
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

@dp.callback_query(F.data == "back:main")
async def back_main(c: CallbackQuery):
    uid = c.from_user.id
    if await check_banned(uid):
        return
    await safe_answer(c)
    await c.message.edit_text(
        "💎 Games Vault Shop\n\nԸնտրիր խաղը։",
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
        f"{get_game_emoji(game)} {CATALOG[game]['name']}\n\nԸնտրիր ապրանքը։",
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
        new_order(u, c.from_user)
        await save_state()
        await safe_answer(c)
        
        await c.message.edit_text(
            f"📸 {escape(name)}\n\n"
            f"Ուղարկիր screenshot-ը, որտեղ հստակ երևում է, որ քո հաշվում {escape(name)} է։\n\n"
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
        f"📦 {escape(name)}\n\n💰 Գին՝ {fmt(price)} ֏\n\nՇարունակե՞նք գնումը։",
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
        f"💳 Վճարման եղանակ\n\nՊատվեր՝ {escape(u['product'])}\nԳին՝ {fmt(u['price'])} ֏",
        reply_markup=payment_kb()
    )

@dp.callback_query(F.data == "back:product")
async def back_product(c: CallbackQuery):
    u = get_user(c.from_user.id)
    
    if is_brawl_pass(u.get("product")):
        if u.get("brawl_pass_price_selected"):
            await safe_answer(c)
            await c.message.edit_text(
                f"📦 {escape(u['product'])}\n\n💰 Գինը ընտրված է՝ {fmt(u.get('price'))} ֏\n\nՇարունակե՞նք գնումը։",
                reply_markup=product_kb(u['game'])
            )
        else:
            await safe_answer(c)
            await c.message.edit_text(
                f"📸 {escape(u['product'])}\n\n⏳ Սպասում ենք ադմինի կողմից գնի ընտրությանը։",
                reply_markup=back_main_kb()
            )
        return
    
    if not u.get("game") or not u.get("product"):
        return await back_main(c)
    
    await safe_answer(c)
    await c.message.edit_text(
        f"📦 {escape(u['product'])}\n\n💰 Գին՝ {fmt(u.get('price') or 0)} ֏",
        reply_markup=product_kb(u['game'])
    )

@dp.callback_query(F.data == "payment:card")
async def payment_card(c: CallbackQuery):
    uid = c.from_user.id
    if await check_banned(uid):
        return
    
    if not CARD_NUMBER:
        await c.answer(
            "❌ Քարտով վճարումը ժամանակավորապես հասանելի չէ։\nԽնդրում ենք ընտրել Telcell։",
            show_alert=True
        )
        return
    
    u = get_user(uid)
    u["payment"] = "Քարտ"
    u["receipt_waiting"] = True
    u["status"] = "⏳ Սպասվում է վճարման screenshot"
    new_order(u, c.from_user)
    await save_state()
    await safe_answer(c)
    await c.message.edit_text(
        f"💳 Քարտով վճարում\n\nՔարտ՝ {escape(CARD_NUMBER)}\nԳումար՝ {fmt(u['price'])} ֏\n\nՎճարումից հետո ուղարկիր screenshot-ը։",
        reply_markup=back_payment_kb()
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
    new_order(u, c.from_user)
    await save_state()
    await safe_answer(c)
    await c.message.edit_text(
        f"💵 Telcell-ով վճարում\n\n"
        f"Հարգելի հաճախորդ,\n"
        f"Ձեր պատվերը ստանալու համար խնդրում ենք կատարել վճարում Telcell-ի միջոցով։\n\n"
        f"📌 Քայլ 1. Գնացեք ձեր քաղաքի մոտակա Telcell տերմինալ։\n"
        f"📌 Քայլ 2. Ընտրեք «Telcell Wallet» բաժինը։\n"
        f"📌 Քայլ 3. Մուտքագրեք մեր համարը՝\n"
        f"📞 {TELCELL_NUMBER}\n\n"
        f"📌 Քայլ 4. Մուտքագրեք գումարը՝\n"
        f"💰 {fmt(u['price'])} ֏\n\n"
        f"📌 Քայլ 5. Հաստատեք վճարումը։\n"
        f"📌 Քայլ 6. Չեկի լուսանկարն ուղարկեք այս chat-ում։\n\n"
        f"⚠️ Կարևոր է. Չեկի լուսանկարը պետք է լինի պարզ և ընթեռնելի։\n\n"
        f"✅ Screenshot-ը ստանալուց հետո կհաստատենք պատվերը։\n\n"
        f"Games Vault Shop 🎮\n"
        f"Արագ ու անվտանգ գնումներ։ 💎",
        reply_markup=back_payment_kb()
    )

@dp.callback_query(F.data == "back:payment")
async def back_payment(c: CallbackQuery):
    await safe_answer(c)
    await c.message.edit_text(
        "💳 Ընտրիր վճարման եղանակը",
        reply_markup=payment_kb()
    )

# ============================================
# ⭐ ՖՈՏՈԻ ՄՇԱԿՈՒՄ
# ============================================

@dp.message(F.photo)
async def photo_input(message: Message):
    uid = message.from_user.id
    u = get_user(uid)
    file_id = message.photo[-1].file_id
    
    logger.info(f"📸 Photo from {uid}: order_id={u.get('order_id')}, price={u.get('price')}, receipt_waiting={u.get('receipt_waiting')}, game_id={u.get('game_id')}, game_id_waiting={u.get('game_id_waiting')}")
    
    # 1. Brawl Pass screenshot
    if u.get("brawl_pass_waiting") and u.get("brawl_pass_product"):
        product_name = u["brawl_pass_product"]
        u["brawl_pass_screenshot_file_id"] = file_id
        u["brawl_pass_waiting"] = False
        u["brawl_pass_rejected"] = False
        u["status"] = f"⏳ Սպասվում է ադմինի կողմից {product_name} գնի ընտրություն"
        new_order(u, message.from_user)
        
        await create_or_replace_order(uid, file_id, admin_bp_kb(uid, product_name))
        
        await message.answer(
            f"📸 Screenshot-ը ստացվեց։\n\n⏳ Սպասիր՝ ադմինը կստուգի screenshot-ը և կընտրի համապատասխան գինը {product_name}-ի համար։",
            reply_markup=back_main_kb()
        )
        return
    
    # 2. Ստուգում ենք՝ արդյոք կա order_id
    if not u.get("order_id"):
        await message.answer("⏳ Դուք դեռ չեք սկսել գնումը։\n\nԸնտրիր ապրանքը գլխավոր մենյուից։", reply_markup=main_kb())
        return
    
    # 3. Ստուգում ենք՝ արդյոք կա price
    if not u.get("price"):
        await message.answer("⏳ Գինը դեռ ընտրված չէ։ Սպասիր ադմինի որոշմանը։", reply_markup=back_main_kb())
        return
    
    # 4. ⭐ Եթե արդեն կա ID (game_id) և սպասում ենք նոր չեկի
    if u.get("receipt_waiting") and u.get("game_id"):
        u["receipt_file_id"] = file_id
        u["receipt_accepted"] = False
        u["receipt_waiting"] = False
        u["status"] = "⏳ Չեկը ստուգվում է"
        await save_state()
        
        await create_or_replace_order(uid, file_id, admin_receipt_kb(uid))
        await message.answer(
            "📸 Նոր չեկի screenshot-ը ստացվեց։\n\n✅ Այժմ ադմինը կստուգի այն։",
            reply_markup=main_kb()
        )
        return
    
    # 5. ⭐ ԱՌԱՋԻՆ ՉԵԿ (եթե ID-ն դեռ չկա)
    if not u.get("game_id") and not u.get("game_id_waiting"):
        u["receipt_file_id"] = file_id
        u["receipt_accepted"] = False
        u["status"] = "⏳ Սպասվում է ID"
        u["game_id_waiting"] = True
        u["receipt_waiting"] = False
        new_order(u, message.from_user)
        
        await create_or_replace_order(uid, file_id, admin_id_reject_kb(uid))
        await message.answer(
            "📸 Չեկը ստացվեց: ✅\n\n"
            "✏️ ԱՅԺՄ ԳՐԻՐ քո Game ID / Username-ը\n"
            "Օրինակ՝ Player123 կամ @nick\n\n"
            "📤 Պարզապես ուղարկիր տեքստը այս chat-ում:",
            reply_markup=back_main_kb()
        )
        return
    
    # 6. Եթե որևէ այլ դեպք
    await message.answer(
        "❌ Չհաջողվեց մշակել ձեր լուսանկարը։\n\n"
        "Խնդրում ենք սկսել նոր պատվեր /cancel հրամանով։",
        reply_markup=main_kb()
    )

# ⭐ ՏԵՔՍՏԻ ՄՇԱԿՈՒՄ
@dp.message(F.text)
async def text_input(message: Message):
    uid = message.from_user.id
    u = get_user(uid)
    text = message.text.strip()

    if not text:
        await message.answer("❌ Տեքստը դատարկ է։\n\nՓորձիր կրկին։")
        return

    # ⭐ SUPPORT
    if u.get("support_waiting"):
        support_chat_id = int(SUPPORT_CHANNEL_ID) if SUPPORT_CHANNEL_ID else ADMIN_ID
        try:
            await bot.send_message(
                support_chat_id,
                f"📩 <b>Support</b>\n\n"
                f"👤 ID: <code>{uid}</code>\n"
                f"👤 Username: @{escape(message.from_user.username or 'չկա')}\n"
                f"📝 Հաղորդագրություն:\n\n"
                f"{escape(text)}"
            )
            await bot.send_message(
                ADMIN_ID,
                f"📩 <b>Support</b>\n\n"
                f"👤 ID: <code>{uid}</code>\n"
                f"👤 Username: @{escape(message.from_user.username or 'չկա')}\n"
                f"📝 Հաղորդագրություն:\n\n"
                f"{escape(text)}"
            )
        except Exception as e:
            logger.error(f"Support send failed: {e}")
        
        u["support_waiting"] = False
        await save_state()
        await message.answer(
            "✅ Հաղորդագրությունը ուղարկվեց աջակցությանը։\n\n"
            "⏳ Մենք կպատասխանենք շուտով։",
            reply_markup=main_kb()
        )
        return

    # ⭐ ՎԵՐԱԴԱՐՁ - ԸՆԴՈՒՆՈՒՄ
    if u.get("refund_waiting"):
        # ՔԱՐՏ
        if u.get("refund_method") == "Քարտ":
            u["refund_details"] = text
            u["refund_waiting"] = False
            u["status"] = f"💸 Վերադարձ քարտով՝ {text}"
            await save_state()
            await update_admin_order(uid, None)
            await message.answer(
                f"✅ Քարտի համարը ստացվեց։\n\n"
                f"💳 {text}\n\n"
                f"⏳ Ադմինը կկատարի վերադարձը։",
                reply_markup=main_kb()
            )
            return
        
        # TELCELL
        if u.get("refund_method") == "Telcell":
            u["refund_details"] = text
            u["refund_waiting"] = False
            operator = u.get("refund_operator", "—")
            u["status"] = f"💸 Վերադարձ Telcell ({operator})՝ {text}"
            await save_state()
            await update_admin_order(uid, None)
            await message.answer(
                f"✅ Հեռախոսահամարը ստացվեց։\n\n"
                f"📱 {operator}\n"
                f"📞 {text}\n\n"
                f"⏳ Ադմինը կկատարի վերադարձը։",
                reply_markup=main_kb()
            )
            return

    # ⭐ GAME ID / USERNAME
    if u.get("game_id_waiting"):
        if not text:
            await message.answer("❌ ID / Username-ը դատարկ է։\n\n✏️ Ուղարկիր ճիշտ Game ID / Username-ը։")
            return

        u["game_id"] = text
        u["game_id_waiting"] = False
        u["game_password_waiting"] = True
        u["status"] = "⏳ Սպասվում է պասսվորդ"

        await save_state()
        await update_admin_order(uid, admin_password_reject_kb(uid))

        await message.answer(
            "✅ ID / Username-ը ստացվեց։\n\n"
            "🔑 ԱՅԺՄ ԳՐԻՐ քո պասսվորդը\n"
            "📝 Օրինակ՝ MyPass123\n\n"
            "⚠️ Պասսվորդը կտեսնի միայն ադմինը։",
            reply_markup=back_main_kb()
        )
        return

    # ⭐ GAME PASSWORD
    if u.get("game_password_waiting"):
        if not text:
            await message.answer("❌ Պասսվորդը դատարկ է։\n\n✏️ Ուղարկիր ճիշտ պասսվորդը։")
            return

        u["game_password"] = text
        u["game_password_waiting"] = False
        u["status"] = "⏳ Սպասվում է չեկի հաստատում"

        await save_state()
        await update_admin_order(uid, admin_receipt_kb(uid))

        await message.answer(
            "✅ Պասսվորդը ստացվեց։\n\n"
            "⏳ Սպասիր ադմինի կողմից չեկի հաստատմանը։",
            reply_markup=main_kb()
        )
        return

    # ⭐ 2FA CODE (Authenticator կամ E-mail)
    if u.get("verification_code_waiting"):
        if len(text) == 6 and text.isdigit():
            u["verification_code_waiting"] = False
            u["verification_done"] = True
            u["verification_attempts"] = 0
            u["status"] = "🔐 2FA կոդը հաստատված է"
            await save_state()
            await update_admin_order(uid, admin_main_kb(uid))
            await message.answer(
                "✅ 2FA կոդը հաստատվեց։\n\n"
                "Պատվերը պատրաստ է ավարտման։\n\n"
                "⏳ Սպասիր ադմինի կողմից պատվերի ավարտմանը։",
                reply_markup=main_kb()
            )
            return
        else:
            u["verification_attempts"] = u.get("verification_attempts", 0) + 1
            await save_state()
            await message.answer(
                f"❌ Սխալ կոդ (փորձ #{u['verification_attempts']})\n\n"
                f"Մուտքագրիր 6-նիշանի կոդը (միայն թվեր)։\n\n"
                f"📝 Օրինակ՝ 123456",
                reply_markup=back_main_kb()
            )
            return

    await message.answer("Ընտրիր բաժինը։", reply_markup=main_kb())

@dp.callback_query(F.data == "contact:open")
async def contact_open(c: CallbackQuery):
    uid = c.from_user.id
    u = get_user(uid)
    u["support_waiting"] = True
    await save_state()
    await safe_answer(c)
    await c.message.edit_text(
        "📩 <b>Կապ Games Vault Shop-ի հետ</b>\n\n"
        "✏️ Ուղարկիր հաղորդագրություն, և մենք կպատասխանենք։\n\n"
        "⚠️ Քո պատվերը կմնա անփոփոխ։",
        reply_markup=back_main_kb()
    )

# ============================================
# ⭐ BRAWL PASS ADMIN
# ============================================

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
        f"✅ Screenshot-ը հաստատվեց։\n\n"
        f"📦 {escape(u['product'])}\n"
        f"💰 Ձեր գինը՝ {fmt(price)} ֏\n\n"
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
        f"❌ Screenshot-ը սխալ է կամ լավ չի երևում\n\n"
        f"Ուղարկիր նոր, ամբողջական և ավելի հստակ screenshot {u['product']}-ի համար։\n\n"
        f"📸 Պարզապես ուղարկիր նոր screenshot-ը այս chat-ում։\n\n"
        f"⚠️ Հին պատվերը չի կրկնվի, սպասում ենք նոր screenshot-ի։",
        back_main_kb()
    )
    
    await update_admin_order(uid, admin_bp_kb(uid, u["product"]))
    await safe_answer(c, "❌ Screenshot-ը մերժվեց, սպասվում է նորը")

# ============================================
# ⭐ ՉԵԿ
# ============================================

@dp.callback_query(F.data.startswith("receipt:accept:"))
async def receipt_accept(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await safe_answer(c, "Մուտքը արգելված է")
        return
    
    uid = int(c.data.split(":")[2])
    u = get_user(uid)
    
    if not u.get("game_id"):
        await safe_answer(c, "⚠️ Սկզբում հաստատիր ID / Username-ը")
        return
    
    if not u.get("game_password"):
        await safe_answer(c, "⚠️ Սկզբում հաստատիր պասսվորդը")
        return
    
    u["receipt_accepted"] = True
    u["status"] = "✅ Չեկը հաստատված է"
    await save_state()
    
    await update_admin_order(uid, admin_main_kb(uid))
    
    await send_client(uid, "✅ Վճարման չեկը հաստատվեց։\n\n⏳ Սպասիր ադմինի կողմից պատվերի շարունակությանը։")
    await safe_answer(c, "✅ Չեկը հաստատվեց")

@dp.callback_query(F.data.startswith("receipt:reject:"))
async def receipt_reject(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await safe_answer(c, "Մուտքը արգելված է")
        return
    
    uid = int(c.data.split(":")[2])
    u = get_user(uid)
    
    u["status"] = "❌ Չեկը մերժվել է (կեղծ)"
    u["receipt_accepted"] = False
    u["receipt_waiting"] = False
    await save_state()
    
    await send_client(
        uid,
        "❌ Ձեր չեկը ՄԵՐԺՎԵԼ Է։\n\n"
        "📸 Դուք ուղարկել եք սխալ կամ կեղծ չեկ։\n\n"
        "⚠️ Եթե կարծում եք, որ սխալ է տեղի ունեցել, կապվեք աջակցության հետ։\n\n"
        "🔄 Նոր պատվեր սկսելու համար օգտագործեք /start",
        main_kb()
    )
    
    await update_admin_order(uid, None)
    await safe_answer(c, "❌ Չեկը մերժվեց, կլիենտը տեղեկացվեց")

# ⭐ ՉԵԿԸ ՎԱՏ Է ԵՐԵՎՈՒՄ - ՉԻ ՋՆՋՈՒՄ ID-Ն ՈՒ ՊԱՍՍՎՈՐԴԸ
@dp.callback_query(F.data.startswith("receipt:bad:"))
async def receipt_bad(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await safe_answer(c, "Մուտքը արգելված է")
        return
    
    uid = int(c.data.split(":")[2])
    u = get_user(uid)
    
    u["receipt_waiting"] = True
    u["receipt_accepted"] = False
    u["status"] = "📸 Սպասվում է նոր չեկ (վատ որակ)"
    await save_state()
    
    await send_client(
        uid,
        "📸 Չեկի screenshot-ը վատ է երևում\n\n"
        "Խնդրում ենք ուղարկել նոր, ավելի հստակ screenshot չեկից։\n\n"
        "✅ Համոզվեք, որ լուսանկարը՝\n"
        "• պարզ է և առանց լղոզման\n"
        "• ամբողջական (երևում է ամբողջ չեկը)\n"
        "• լավ լուսավորված\n\n"
        "📸 Պարզապես ուղարկիր նոր screenshot-ը այս chat-ում։\n\n"
        "✅ ID / Username-ը և պասսվորդը արդեն մուտքագրված են, նորից մուտքագրել պետք չէ։",
        back_main_kb()
    )
    
    await update_admin_order(uid, admin_receipt_kb(uid))
    await safe_answer(c, "📸 Կլիենտին խնդրեցինք նոր չեկ ուղարկել")

# ============================================
# ⭐ ADMIN ID REJECT
# ============================================

@dp.callback_query(F.data.startswith("id:reject:"))
async def admin_id_reject(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await safe_answer(c, "Մուտքը արգելված է")
        return

    uid = int(c.data.split(":")[2])
    u = get_user(uid)

    u["game_id"] = None
    u["game_id_waiting"] = True
    u["game_password_waiting"] = False
    u["game_password"] = None
    u["status"] = "⏳ Սպասվում է նոր ID / Username"

    await save_state()

    await send_client(
        uid,
        "❌ Սխալ ID / Username\n\n"
        "✏️ Ուղարկիր ճիշտ Game ID / Username-ը։\n\n"
        "Օրինակ՝ Player123 կամ @Player123",
        back_main_kb()
    )

    await update_admin_order(uid, admin_id_reject_kb(uid))
    await safe_answer(c, "⏳ Սպասվում է նոր ID / Username")

# ⭐ ADMIN PASSWORD REJECT
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
    
    await send_client(
        uid,
        "❌ Սխալ պասսվորդ\n\n"
        "✏️ ՈՒՂԱՐԿԻՐ ՃԻՇՏ ՊԱՍՍՎՈՐԴԸ\n"
        "📝 Օրինակ՝ MyPass123",
        back_main_kb()
    )
    
    await update_admin_order(uid, admin_password_reject_kb(uid))
    await safe_answer(c, "Սպասվում է նոր պասսվորդ")

@dp.callback_query(F.data.startswith("admin:receipt:"))
async def admin_receipt_back(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await safe_answer(c, "Մուտքը արգելված է")
        return
    
    uid = int(c.data.split(":")[2])
    await update_admin_order(uid, admin_receipt_kb(uid))
    await safe_answer(c)

# ============================================
# ⭐ ՎԵՐԱԴԱՐՁ (REFUND)
# ============================================

@dp.callback_query(F.data.startswith("refund:"))
async def refund_action(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await safe_answer(c, "Մուտքը արգելված է")
        return
    
    parts = c.data.split(":")
    
    # ⭐ Եթե սա OPERATOR է (refund:operator:{uid}:{operator})
    if len(parts) >= 4 and parts[1] == "operator":
        uid = int(parts[2])
        operator = parts[3]
        u = get_user(uid)
        u["refund_operator"] = operator
        u["refund_waiting"] = True
        u["status"] = f"💸 Սպասվում է հեռախոսահամար ({operator})"
        await save_state()
        await update_admin_order(uid, None)
        await send_client(
            uid,
            f"📱 <b>Օպերատոր՝ {operator}</b>\n\n"
            f"✏️ ՈՒՂԱՐԿԻՐ հեռախոսահամարը\n"
            f"📝 Օրինակ՝ 077 123456\n\n"
            f"⚠️ Համոզվիր, որ համարը ճիշտ է։",
            back_main_kb()
        )
        await safe_answer(c, f"⏳ Սպասվում է հեռախոսահամար ({operator})")
        return
    
    # ⭐ Մնացած դեպքերում uid-ն վերջինն է
    uid = int(parts[-1])
    u = get_user(uid)
    
    # ⭐ ԱԴՄԻՆԸ ԸՆՏՐԵԼ Է ՎԵՐԱԴԱՐՁ
    if len(parts) == 2:
        u["refund_waiting"] = True
        u["refund_method"] = None
        u["refund_operator"] = None
        u["refund_details"] = None
        u["status"] = "💸 Սպասվում է վերադարձի եղանակի ընտրություն"
        await save_state()
        await update_admin_order(uid, admin_refund_kb(uid))
        await send_client(
            uid,
            "💸 <b>Վերադարձ</b>\n\n"
            "Ընտրիր վերադարձի եղանակը՝\n\n"
            "💳 <b>Քարտով</b> - ուղարկիր քարտի համարը\n"
            "💵 <b>Telcell-ով</b> - ընտրիր օպերատորը և ուղարկիր հեռախոսահամարը",
            admin_refund_kb(uid)
        )
        await safe_answer(c)
        return
    
    # ⭐ ԿԼԻԵՆՏԸ ԸՆՏՐԵԼ Է ՔԱՐՏՈՎ
    if parts[1] == "card":
        u["refund_method"] = "Քարտ"
        u["refund_operator"] = None
        u["refund_waiting"] = True
        u["status"] = "💸 Սպասվում է քարտի համար"
        await save_state()
        await update_admin_order(uid, None)
        await send_client(
            uid,
            "💳 <b>Քարտով վերադարձ</b>\n\n"
            "✏️ ՈՒՂԱՐԿԻՐ քարտի համարը\n"
            "📝 Օրինակ՝ 1234 5678 9012 3456\n\n"
            "⚠️ Համոզվիր, որ համարը ճիշտ է։",
            back_main_kb()
        )
        await safe_answer(c, "⏳ Սպասվում է քարտի համար")
        return
    
    # ⭐ ԿԼԻԵՆՏԸ ԸՆՏՐԵԼ Է TELCELL
    if parts[1] == "telcell":
        u["refund_method"] = "Telcell"
        u["refund_operator"] = None
        u["refund_waiting"] = True
        u["status"] = "💸 Սպասվում է օպերատորի ընտրություն"
        await save_state()
        await update_admin_order(uid, None)
        await send_client(
            uid,
            "💵 <b>Telcell-ով վերադարձ</b>\n\n"
            "📱 Ընտրիր օպերատորը՝\n\n"
            "• Beeline\n"
            "• Ucom\n"
            "• MTS\n"
            "• Viva-MTS\n"
            "• Team\n\n"
            "⚠️ Ընտրիր ճիշտ օպերատոր, որպեսզի գումարը ճիշտ հասնի։",
            operator_kb(uid)
        )
        await safe_answer(c, "⏳ Սպասվում է օպերատորի ընտրություն")
        return

# ============================================
# ⭐ ԱՎԱՐՏԵԼ ՊԱՏՎԵՐԸ
# ============================================

@dp.callback_query(F.data.startswith("order:complete:"))
async def order_complete(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await safe_answer(c, "Մուտքը արգելված է")
        return
    
    uid = int(c.data.split(":")[2])
    u = get_user(uid)
    
    if not u.get("verification_done"):
        u["verification_type"] = "Բաց թողնված"
        u["verification_done"] = True
    
    order_id = u.get("order_id")
    username = u.get("username")
    product = u.get("product")
    price = u.get("price")
    
    u["status"] = "✅ Ավարտված"
    u["is_completed"] = True
    u["completed_at"] = datetime.datetime.now().isoformat()
    
    u["game_id"] = None
    u["game_password"] = None
    u["payment"] = None
    u["receipt_file_id"] = None
    u["receipt_accepted"] = False
    u["game_id_waiting"] = False
    u["game_password_waiting"] = False
    u["receipt_waiting"] = False
    u["verification_type"] = None
    u["verification_done"] = False
    u["verification_code_waiting"] = False
    u["verification_device_waiting"] = False
    u["brawl_pass_waiting"] = False
    u["brawl_pass_screenshot_file_id"] = None
    u["brawl_pass_price_selected"] = False
    u["brawl_pass_product"] = None
    u["brawl_pass_rejected"] = False
    
    await save_state()
    await update_admin_order(uid, None)
    
    await send_client(
        uid,
        f"🎉 Պատվերը ավարտված է\n\n"
        f"📦 Պատվեր՝ #{escape(str(order_id or '—'))}\n"
        f"👤 Username՝ @{escape(str(username or 'չկա'))}\n"
        f"💎 Ապրանք՝ {escape(str(product or '—'))}\n"
        f"💰 Գին՝ {fmt(price or 0)} ֏\n\n"
        f"📌 Կարգավիճակ՝ ✅ Ավարտված\n\n"
        f"Շնորհակալություն Games Vault Shop-ը ընտրելու համար։\n\n"
        f"💎 <b>Games Vault Shop</b> 🎮",
        main_kb()
    )
    await safe_answer(c, "✅ Պատվերը ավարտվեց")

# ============================================
# ⭐ 2FA - ԱՄԲՈՂՋԱԿԱՆ ԲԼՈԿ
# ============================================

@dp.callback_query(F.data.startswith("verify:menu:"))
async def verify_menu(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await safe_answer(c, "Մուտքը արգելված է")
        return
    
    uid = int(c.data.split(":")[2])
    u = get_user(uid)
    
    if not u.get("order_id") or u.get("is_completed"):
        await safe_answer(c, "⚠️ Ակտիվ պատվեր չկա")
        return
    
    await safe_answer(c)
    await update_admin_order(uid, admin_main_kb(uid))
    
    try:
        await c.message.edit_text(
            "🔐 <b>2FA հաստատում</b>\n\n"
            "Ընտրիր հաստատման եղանակը՝\n\n"
            "📱 <b>Այլ սարքով</b> - հաստատիր Roblox-ը մեկ այլ սարքից\n"
            "🔐 <b>Authenticator</b> - մուտքագրիր կոդը Google/Microsoft Authenticator-ից\n"
            "📧 <b>E-mail</b> - մուտքագրիր կոդը E-mail-ից\n\n"
            "⚠️ Կարող ես նաև պարզապես ավարտել պատվերը առանց 2FA։",
            reply_markup=verify_catalog_kb(uid)
        )
    except Exception:
        try:
            await c.message.delete()
        except:
            pass
        await c.message.answer(
            "🔐 <b>2FA հաստատում</b>\n\n"
            "Ընտրիր հաստատման եղանակը՝\n\n"
            "📱 <b>Այլ սարքով</b> - հաստատիր Roblox-ը մեկ այլ սարքից\n"
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
    try:
        await c.message.edit_text(
            "🛠 Ադմինի վահանակ\n\nԸնտրիր գործողությունը՝",
            reply_markup=admin_main_kb(uid)
        )
    except Exception:
        try:
            await c.message.delete()
        except:
            pass
        await c.message.answer(
            "🛠 Ադմինի վահանակ\n\nԸնտրիր գործողությունը՝",
            reply_markup=admin_main_kb(uid)
        )

@dp.callback_query(F.data.startswith("verify:device:"))
async def verify_device(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await safe_answer(c, "Մուտքը արգելված է")
        return
    
    parts = c.data.split(":")
    
    if len(parts) >= 4 and parts[2] == "confirm":
        uid = int(parts[3])
        u = get_user(uid)
        
        if not u.get("order_id") or u.get("is_completed"):
            await safe_answer(c, "⚠️ Ակտիվ պատվեր չկա")
            return
        
        u["verification_type"] = "device"
        u["verification_done"] = True
        u["verification_device_waiting"] = False
        u["verification_code_waiting"] = False
        u["status"] = "🔐 2FA՝ Այլ սարքով հաստատված"
        await save_state()
        
        await update_admin_order(uid, admin_main_kb(uid))
        
        await send_client(
            uid,
            "✅ 2FA հաստատումը հաջողվեց։\n\n"
            "📱 Դուք հաստատել եք մուտքը այլ սարքից։\n\n"
            "⏳ Սպասիր ադմինի կողմից պատվերի ավարտմանը։",
            main_kb()
        )
        
        await safe_answer(c, "✅ 2FA հաստատվեց (այլ սարք)")
        
        try:
            await c.message.edit_text(
                "🛠 Ադմինի վահանակ\n\n✅ 2FA հաստատվեց",
                reply_markup=admin_main_kb(uid)
            )
        except Exception:
            try:
                await c.message.delete()
            except:
                pass
            await c.message.answer(
                "🛠 Ադմինի վահանակ\n\n✅ 2FA հաստատվեց",
                reply_markup=admin_main_kb(uid)
            )
        return
    
    if len(parts) == 3:
        uid = int(parts[2])
        u = get_user(uid)
        
        if not u.get("order_id") or u.get("is_completed"):
            await safe_answer(c, "⚠️ Ակտիվ պատվեր չկա")
            return
        
        u["verification_type"] = "device"
        u["verification_done"] = False
        u["verification_device_waiting"] = True
        u["verification_code_waiting"] = False
        u["verification_attempts"] = 0
        u["status"] = "⏳ Սպասվում է այլ սարքով հաստատում"
        await save_state()
        
        await update_admin_order(uid, admin_main_kb(uid))
        
        await send_client_photo(
            uid,
            VERIFY_IMAGES["device"],
            "📱 2FA — Այլ սարքով հաստատում\n\n"
            "1️⃣ Բացիր Roblox հավելվածը մեկ այլ սարքից (հեռախոս/պլանշետ)\n"
            "2️⃣ Հաստատիր մուտքը Roblox հավելվածում\n"
            "3️⃣ Սեղմիր «Approve» կամ «Հաստատել»\n\n"
            "⚠️ Կարևոր. Հաստատիր միայն այն մուտքը, որը դու ես սկսել։\n\n"
            "✅ Հաստատումից հետո սեղմիր «✅ Հաստատել եմ» կոճակը։",
            verify_device_confirm_kb(uid)
        )
        
        try:
            await c.message.edit_text(
                "⏳ Սպասում ենք այլ սարքով հաստատման...\n\n"
                "📱 Կլիենտին ուղարկվել է հրահանգ։\n\n"
                "🛠 Ադմինի վահանակ",
                reply_markup=admin_main_kb(uid)
            )
        except Exception:
            try:
                await c.message.delete()
            except:
                pass
            await c.message.answer(
                "⏳ Սպասում ենք այլ սարքով հաստատման...\n\n"
                "📱 Կլիենտին ուղարկվել է հրահանգ։\n\n"
                "🛠 Ադմինի վահանակ",
                reply_markup=admin_main_kb(uid)
            )
        await safe_answer(c, "⏳ Սպասում ենք այլ սարքով հաստատման")

@dp.callback_query(F.data.startswith("verify:auth:"))
async def verify_auth(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await safe_answer(c, "Մուտքը արգելված է")
        return
    
    uid = int(c.data.split(":")[2])
    u = get_user(uid)
    
    if not u.get("order_id") or u.get("is_completed"):
        await safe_answer(c, "⚠️ Ակտիվ պատվեր չկա")
        return
    
    u["verification_type"] = "auth"
    u["verification_done"] = False
    u["verification_code_waiting"] = True
    u["verification_attempts"] = 0
    u["status"] = "⏳ Սպասվում է Authenticator կոդ"
    await save_state()
    
    await update_admin_order(uid, admin_verify_retry_kb(uid, "auth"))
    
    await send_client_photo(
        uid,
        VERIFY_IMAGES["auth"],
        "🔐 2FA — Authenticator\n\n"
        "1️⃣ Բացիր Google Authenticator / Microsoft Authenticator\n"
        "2️⃣ Գտիր Roblox-ի 6-նիշանի կոդը\n"
        "3️⃣ Մուտքագրիր կոդը այս chat-ում\n\n"
        "⚠️ Կարևոր. Կոդը թարմացվում է ամեն 30 վայրկյանը մեկ։\n\n"
        "📝 Ուղարկիր 6-նիշանի կոդը (օրինակ՝ 123456)",
        back_main_kb()
    )
    
    try:
        await c.message.edit_text(
            "⏳ Սպասում ենք Authenticator կոդի մուտքագրմանը...\n\n"
            "🛠 Ադմինի վահանակ",
            reply_markup=admin_verify_retry_kb(uid, "auth")
        )
    except Exception:
        try:
            await c.message.delete()
        except:
            pass
        await c.message.answer(
            "⏳ Սպասում ենք Authenticator կոդի մուտքագրմանը...\n\n"
            "🛠 Ադմինի վահանակ",
            reply_markup=admin_verify_retry_kb(uid, "auth")
        )
    await safe_answer(c, "⏳ Սպասում ենք Authenticator կոդի")

@dp.callback_query(F.data.startswith("verify:email:"))
async def verify_email(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await safe_answer(c, "Մուտքը արգելված է")
        return
    
    uid = int(c.data.split(":")[2])
    u = get_user(uid)
    
    if not u.get("order_id") or u.get("is_completed"):
        await safe_answer(c, "⚠️ Ակտիվ պատվեր չկա")
        return
    
    u["verification_type"] = "email"
    u["verification_done"] = False
    u["verification_code_waiting"] = True
    u["verification_attempts"] = 0
    u["status"] = "⏳ Սպասվում է E-mail կոդ"
    await save_state()
    
    await update_admin_order(uid, admin_verify_retry_kb(uid, "email"))
    
    await send_client_photo(
        uid,
        VERIFY_IMAGES["email"],
        "📧 2FA — E-mail\n\n"
        "1️⃣ Ստուգիր քո E-mail-ը (Gmail, Mail.ru, և այլն)\n"
        "2️⃣ Roblox-ը ուղարկել է 6-նիշանի հաստատման կոդ\n"
        "3️⃣ Մուտքագրիր կոդը այս chat-ում\n\n"
        "⚠️ Կարևոր. Ստուգիր նաև Spam պանակը։\n\n"
        "📝 Ուղարկիր 6-նիշանի կոդը (օրինակ՝ 123456)",
        back_main_kb()
    )
    
    try:
        await c.message.edit_text(
            "⏳ Սպասում ենք E-mail կոդի մուտքագրմանը...\n\n"
            "🛠 Ադմինի վահանակ",
            reply_markup=admin_verify_retry_kb(uid, "email")
        )
    except Exception:
        try:
            await c.message.delete()
        except:
            pass
        await c.message.answer(
            "⏳ Սպասում ենք E-mail կոդի մուտքագրմանը...\n\n"
            "🛠 Ադմինի վահանակ",
            reply_markup=admin_verify_retry_kb(uid, "email")
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
    
    if not u.get("order_id") or u.get("is_completed"):
        await safe_answer(c, "⚠️ Ակտիվ պատվեր չկա")
        return
    
    u["verification_code_waiting"] = True
    u["verification_done"] = False
    u["verification_attempts"] = 0
    u["status"] = f"⏳ Սպասվում է նոր {verify_type} կոդ"
    await save_state()
    
    await update_admin_order(uid, admin_verify_retry_kb(uid, verify_type))
    
    if verify_type == "auth":
        await send_client_photo(
            uid,
            VERIFY_IMAGES["auth"],
            "🔄 2FA — Authenticator (նոր կոդ)\n\n"
            "1️⃣ Բացիր Google Authenticator / Microsoft Authenticator\n"
            "2️⃣ Գտիր Roblox-ի 6-նիշանի կոդը\n"
            "3️⃣ Մուտքագրիր կոդը այս chat-ում\n\n"
            "⚠️ Կարևոր. Կոդը թարմացվում է ամեն 30 վայրկյանը մեկ։\n\n"
            "📝 Ուղարկիր 6-նիշանի կոդը (օրինակ՝ 123456)",
            back_main_kb()
        )
    elif verify_type == "email":
        await send_client_photo(
            uid,
            VERIFY_IMAGES["email"],
            "🔄 2FA — E-mail (նոր կոդ)\n\n"
            "1️⃣ Ստուգիր քո E-mail-ը (Gmail, Mail.ru, և այլն)\n"
            "2️⃣ Roblox-ը ուղարկել է 6-նիշանի հաստատման կոդ\n"
            "3️⃣ Մուտքագրիր կոդը այս chat-ում\n\n"
            "⚠️ Կարևոր. Ստուգիր նաև Spam պանակը։\n\n"
            "📝 Ուղարկիր 6-նիշանի կոդը (օրինակ՝ 123456)",
            back_main_kb()
        )
    else:
        await send_client(
            uid,
            f"🔄 2FA — {verify_type}\n\n"
            "Խնդրում ենք մուտքագրել 6-նիշանի հաստատման կոդը։",
            back_main_kb()
        )
    
    try:
        await c.message.edit_text(
            f"⏳ Սպասում ենք նոր {verify_type} կոդի մուտքագրմանը...\n\n"
            "🛠 Ադմինի վահանակ",
            reply_markup=admin_main_kb(uid)
        )
    except Exception:
        try:
            await c.message.delete()
        except:
            pass
        await c.message.answer(
            f"⏳ Սպասում ենք նոր {verify_type} կոդի մուտքագրմանը...\n\n"
            "🛠 Ադմինի վահանակ",
            reply_markup=admin_main_kb(uid)
        )
    
    await safe_answer(c, f"✅ Նոր {verify_type} կոդի հարցումը ուղարկվեց կլիենտին")

# ============================================
# ⭐ ԳՈՐԾԱՐԿՈՒՄ
# ============================================

async def main():
    load_state()
    asyncio.create_task(clean_old_orders())
    asyncio.create_task(run_web())
    
    logger.info("🚀 Բոտը գործարկվեց")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
