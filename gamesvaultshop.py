import os
import asyncio
import logging
import base64
from html import escape
from io import BytesIO

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from openai import AsyncOpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID = os.getenv("CHANNEL_ID", "")
ORDER_CHANNEL_ID = os.getenv("ORDER_CHANNEL_ID", CHANNEL_ID)
SUPPORT_CHANNEL_ID = os.getenv("SUPPORT_CHANNEL_ID", "")
TELCELL_NUMBER = os.getenv("TELCELL_NUMBER", "043055510")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
PORT = int(os.getenv("PORT", "10000"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN չգտնվեց։ Ավելացրու BOT_TOKEN-ը Render-ի Environment Variables-ում։")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
ai_client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

users = {}
support_threads = {}

BRAWL_PASS_PRICES = {
    "brawl_pass": {True: 2500, False: 3400},
    "brawl_pass_plus": {True: 3400, False: 4800},
}


def get_user(user_id: int):
    if user_id not in users:
        users[user_id] = {
            "game": None, "product": None, "price": None, "username": None,
            "payment": None, "order_id": None, "support_waiting": False,
            "brawl_pass_type": None, "brawl_pass_analyzing": False,
        }
    return users[user_id]


CATALOG = {
    "roblox": {"name": "🎮 Roblox", "items": [("40 Robux", 350), ("80 Robux", 650), ("120 Robux", 950), ("400 Robux", 2700), ("520 Robux", 3600), ("840 Robux", 4850), ("1,240 Robux", 7300), ("1,700 Robux", 8800), ("1,820 Robux", 9700), ("4,500 Robux", 21000), ("10,000 Robux", 40000), ("22,500 Robux", 88000)]},
    "standoff2": {"name": "🔫 Standoff 2", "items": [("100 Gold", 1000), ("200 Gold", 2000), ("300 Gold", 2900), ("500 Gold", 4000), ("600 Gold", 5100), ("700 Gold", 5800), ("1,000 Gold", 7100), ("1,500 Gold", 10300), ("3,000 Gold", 15800)]},
    "brawlstars": {"name": "⭐ Brawl Stars", "items": [("30 Gems", 750), ("80 Gems", 1500), ("170 Gems", 2800), ("360 Gems", 5100), ("950 Gems", 12800), ("Brawl Pass", 2500), ("Brawl Pass+", 3400), ("Прокачка Brawl Pass → Brawl Pass+", 1800), ("Pro Pass", 12300)]},
    "pubg": {"name": "🪂 PUBG Mobile", "items": [("33 UC + 🎁", 300), ("66 UC + 🎁", 500), ("99 UC + 🎁", 700), ("132 UC + 🎁", 1000), ("150 UC + 🎁", 1100), ("198 UC + 🎁", 1400), ("210 UC + 🎁", 1600), ("325 UC + 🎁", 2000), ("355 + 5 UC + 🎁", 2100), ("445 UC + 🎁", 2900), ("505 UC + 🎁", 3400), ("660 UC + 🎁", 4000), ("720 UC + 🎁", 4300), ("985 UC + 🎁", 6000), ("1,135 UC + 🎁", 7000), ("1,320 UC + 🎁", 7800), ("1,860 UC + 🎁", 10000), ("2,185 UC + 🎁", 11500)]},
}


def main_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Roblox", callback_data="game:roblox"), InlineKeyboardButton(text="🔫 Standoff 2", callback_data="game:standoff2")],
        [InlineKeyboardButton(text="⭐ Brawl Stars", callback_data="game:brawlstars"), InlineKeyboardButton(text="🪂 PUBG Mobile", callback_data="game:pubg")],
        [InlineKeyboardButton(text="📩 Կապվեք մեզ հետ", callback_data="contact:open")],
    ])


def game_keyboard(game: str):
    buttons = []
    for index, (name, price) in enumerate(CATALOG[game]["items"]):
        if game == "brawlstars" and name in {"Brawl Pass", "Brawl Pass+"}:
            shown_price = "սկսած 2 500 ֏" if name == "Brawl Pass" else "սկսած 3 400 ֏"
            buttons.append([InlineKeyboardButton(text=f"🎫 {name} — {shown_price}", callback_data=f"product:{game}:{index}")])
        else:
            buttons.append([InlineKeyboardButton(text=f"⚡ {name} — {price:,} ֏".replace(",", " "), callback_data=f"product:{game}:{index}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def product_keyboard(game: str):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Գնել", callback_data="buy:confirm")], [InlineKeyboardButton(text="⬅️ Հետ", callback_data=f"back:game:{game}")]])


def payment_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Վճարել քարտով", callback_data="payment:card")],
        [InlineKeyboardButton(text="💵 Վճարել կանխիկ", callback_data="payment:cash")],
        [InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:product")],
    ])


def receipt_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🧾 Ուղարկել չեկի նկարը", callback_data="payment:done")], [InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:payment")]])


def pass_result_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔄 Ուղարկել նոր screenshot", callback_data="pass:retry")], [InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:game:brawlstars")]])


def main_text():
    return ("🎮 <b>Games Vault Shop</b> ❤️‍🔥\n\n" "💎 <b>Games Vault Shop-ում՝ միշտ VAULT-Ա!</b>\n\n" "Ընտրիր խաղը և տես հասանելի ապրանքները։\n\n" "⚡ Արագ պատվեր\n" "💳 Telcell Wallet\n" "🧾 Չեկի ստուգում\n" "📩 Աջակցություն և կապ\n\n" "❗ Գնումից առաջ ստուգիր ապրանքի տեսակը և գինը։")


def game_text(game: str):
    return f"{CATALOG[game]['name']}\n\nԸնտրիր անհրաժեշտ ապրանքը։\n\n💰 Գները նշված են դրամով։"


def order_caption(user_id: int, user: dict, status: str):
    username = user.get("username") or "չկա"
    return ("🧾 <b>ՊԱՏՎԵՐ</b>\n\n" f"👤 Օգտատեր՝ @{escape(username)}\n" f"🆔 ID՝ <code>{user_id}</code>\n" f"🎮 Խաղ՝ <b>{escape(CATALOG[user['game']]['name'])}</b>\n" f"📦 Ապրանք՝ <b>{escape(user['product'])}</b>\n" f"💰 Գումար՝ <b>{user['price']:,} ֏</b>\n" f"🔖 Պատվեր՝ <code>{escape(user.get('order_id') or str(user_id))}</code>\n\n" f"{status}").replace(",", " ")


def brawl_pass_prompt(pass_type: str):
    title = "🎫 Brawl Pass" if pass_type == "brawl_pass" else "⭐ Brawl Pass+"
    return (f"{title}\n\n📸 <b>Ուղարկեք ձեր Brawl Pass-ի screenshot-ը։</b>\n\n"
            "AI-ն կստուգի՝ ձեր аккаунտում կա՞ զեղչված գին։\n\n"
            "🟢 Զեղչ կա → նվազագույն գին\n"
            "🔴 Զեղչ չկա → առավելագույն գին\n\n"
            "⚠️ Ուղարկեք ամբողջական և ընթեռնելի screenshot, որտեղ երևում է Brawl Pass-ի գինը։")


async def analyze_brawl_pass_image(file_bytes: bytes, pass_type: str):
    if not ai_client:
        return None, "AI ծառայությունը դեռ միացված չէ։ Ավելացրու OPENAI_API_KEY-ը Render-ի Environment Variables-ում։"
    encoded = base64.b64encode(file_bytes).decode("utf-8")
    expected = "Brawl Pass" if pass_type == "brawl_pass" else "Brawl Pass+"
    prompt = f"""Դու Games Vault Shop-ի Brawl Stars Brawl Pass screenshot-ի ստուգիչ ես.
Սքրինշոթը պետք է վերաբերի {expected}-ին։
Որոշիր միայն՝ screenshot-ում երևո՞ւմ է հատուկ/զեղչված առաջարկ, թե՞ սովորական գին։
Եթե վստահ չես, վերադարձիր unknown.
Պատասխանիր ՄԻԱՅՆ մեկ բառով՝ discounted, regular կամ unknown.
Մի փորձիր որոշել վճարման կամ չեկի վավերությունը."""
    try:
        response = await ai_client.responses.create(
            model=OPENAI_MODEL,
            input=[{"role": "user", "content": [
                {"type": "input_text", "text": prompt},
                {"type": "input_image", "image_url": f"data:image/jpeg;base64,{encoded}"},
            ]}],
            max_output_tokens=10,
        )
        result = (response.output_text or "").strip().lower()
        if "discounted" in result:
            return True, None
        if "regular" in result:
            return False, None
        return None, "Screenshot-ը հստակ չհաջողվեց ճանաչել։ Ուղարկեք ավելի պարզ screenshot։"
    except Exception:
        logging.exception("Brawl Pass image analysis failed")
        return None, "Չհաջողվեց ստուգել screenshot-ը։ Փորձեք կրկին։"


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


@dp.callback_query(F.data.startswith("game:"))
async def choose_game(callback: CallbackQuery):
    game = callback.data.split(":", 1)[1]
    if game not in CATALOG:
        await callback.answer("❌ Սխալ խաղ։", show_alert=True)
        return
    user = get_user(callback.from_user.id)
    user.update({"game": game, "product": None, "price": None, "payment": None, "order_id": None, "brawl_pass_type": None, "brawl_pass_analyzing": False})
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
    if game == "brawlstars" and item[0] in {"Brawl Pass", "Brawl Pass+"}:
        user["brawl_pass_type"] = "brawl_pass" if item[0] == "Brawl Pass" else "brawl_pass_plus"
        user["brawl_pass_analyzing"] = True
        await callback.message.edit_text(brawl_pass_prompt(user["brawl_pass_type"]), reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:game:brawlstars")]]), parse_mode="HTML")
        await callback.answer()
        return
    text = ("🛒 <b>Ձեր ընտրությունը</b>\n\n" f"🎮 Խաղ՝ <b>{escape(CATALOG[game]['name'])}</b>\n" f"📦 Ապրանք՝ <b>{escape(item[0])}</b>\n" f"💰 Գին՝ <b>{item[1]:,} ֏</b>\n\n" "Շարունակե՞լ պատվերը։").replace(",", " ")
    await callback.message.edit_text(text, reply_markup=product_keyboard(game), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "pass:retry")
async def pass_retry(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    pass_type = user.get("brawl_pass_type")
    if not pass_type:
        await callback.answer("❌ Brawl Pass-ը չի ընտրվել։", show_alert=True)
        return
    user["brawl_pass_analyzing"] = True
    await callback.message.edit_text(brawl_pass_prompt(pass_type), reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Հետ", callback_data="back:game:brawlstars")]]), parse_mode="HTML")
    await callback.answer()


@dp.message(F.photo)
async def photo_router(message: Message):
    user = get_user(message.from_user.id)
    if user.get("brawl_pass_analyzing") and user.get("brawl_pass_type"):
        if not OPENAI_API_KEY:
            user["brawl_pass_analyzing"] = False
            await message.answer("⚠️ AI ճանաչումը դեռ միացված չէ։ Ավելացրու <code>OPENAI_API_KEY</code> Render-ի Environment Variables-ում։", parse_mode="HTML", reply_markup=main_menu_keyboard())
            return
        status_message = await message.answer("🔎 <b>Ստուգում եմ screenshot-ը...</b> ⏳", parse_mode="HTML")
        try:
            file = await bot.get_file(message.photo[-1].file_id)
            buffer = BytesIO()
            await bot.download_file(file.file_path, buffer)
            result, error = await analyze_brawl_pass_image(buffer.getvalue(), user["brawl_pass_type"])
        except Exception:
            logging.exception("Failed to download Brawl Pass screenshot")
            result, error = None, "Չհաջողվեց ստանալ screenshot-ը։ Փորձեք կրկին։"
        user["brawl_pass_analyzing"] = False
        if result is None:
            await status_message.edit_text(f"⚠️ {escape(error or 'Screenshot-ը չճանաչվեց։')}", reply_markup=pass_result_keyboard(), parse_mode="HTML")
            return
        pass_type = user["brawl_pass_type"]
        price = BRAWL_PASS_PRICES[pass_type][result]
        product_name = "Brawl Pass" if pass_type == "brawl_pass" else "Brawl Pass+"
        user["product"] = product_name
        user["price"] = price
        label = "🟢 Զեղչը հասանելի է" if result else "🔴 Զեղչ չկա"
        await status_message.edit_text(("✅ <b>Screenshot-ը ճանաչվեց</b>\n\n" f"📦 {product_name}\n" f"{label}\n" f"💰 Գին՝ <b>{price:,} ֏</b>\n\n" "Շարունակե՞լ պատվերը?").replace(",", " "), reply_markup=product_keyboard("brawlstars"), parse_mode="HTML")
        return
    if user.get("support_waiting") and SUPPORT_CHANNEL_ID:
        username = message.from_user.username or "չկա"
        caption = ("📷 <b>ՆՈՐ ՀԱՂՈՐԴԱԳՐՈՒԹՅՈՒՆ</b>\n\n" f"👤 Username՝ @{escape(username)}\n" f"🆔 ID՝ <code>{message.from_user.id}</code>\n\n" "↩️ Պատասխանեք այս հաղորդագրությանը՝ օգտատիրոջը ուղարկելու համար։")
        sent = await bot.send_photo(chat_id=SUPPORT_CHANNEL_ID, photo=message.photo[-1].file_id, caption=caption, parse_mode="HTML")
        support_threads[sent.message_id] = message.from_user.id
        user["support_waiting"] = False
        await message.answer("✅ Նկարը ստացվեց։ Մենք կպատասխանենք շուտով։", reply_markup=main_menu_keyboard())
        return
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


@dp.callback_query(F.data == "buy:confirm")
async def buy_confirm(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user.get("game") or not user.get("product"):
        await callback.answer("❌ Նախ ընտրիր ապրանքը։", show_alert=True)
        return
    text = ("💳 <b>Ընտրիր վճարման եղանակը</b>\n\n" f"📦 Ապրանք՝ <b>{escape(user['product'])}</b>\n" f"💰 Գումար՝ <b>{user['price']:,} ֏</b>\n\n" "Ընտրիր՝ ինչպես ես ցանկանում վճարել։").replace(",", " ")
    await callback.message.edit_text(text, reply_markup=payment_keyboard(), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "payment:card")
async def payment_card(callback: CallbackQuery):
    await callback.answer("💳 Քարտով վճարումը դեռ հասանելի չէ։", show_alert=True)


@dp.callback_query(F.data == "payment:cash")
async def payment_cash(callback: CallbackQuery):
    text = ("💎 <b>Games Vault Shop-ից Բարևներ</b> ❤️‍🔥\n\n"
            "💵 <b>Վճարման քայլերը՝</b>\n\n"
            "1️⃣ Telcell տերմինալում ընտրեք <b>«Telcell Wallet»</b> և մուտքագրեք հեռախոսահամարը՝ <code>043055510</code> 📱\n\n"
            "2️⃣ Կատարեք վճարումը անհրաժեշտ գումարի չափով։ 💰\n\n"
            "3️⃣ 🧾 Վճարումից հետո <b>նկարեք չեկը</b> և ուղարկեք մեզ։\n\n"
            "4️⃣ 🆔 Այնուհետև ուղարկեք ձեր <b>ID-ն</b>։\n\n"
            "⚡ Վճարումը ստանալուց և ստուգելուց հետո <b>1–2 րոպեում</b> կստանաք ձեր Դոնաթը։ ❤️‍🔥\n\n"
            "🧾 <b>Ուղարկիր չեկի նկարը</b>")
    await callback.message.edit_text(text, reply_markup=receipt_keyboard(), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "payment:done")
async def payment_done(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user.get("product"):
        await callback.answer("❌ Պատվերը չի գտնվել։", show_alert=True)
        return
    user["payment"] = "receipt_pending"
    await callback.message.edit_text("🧾 <b>Ուղարկիր չեկի նկարը</b>\n\nՈւղարկիր վճարման չեկի լուսանկարը այս հաղորդագրությունից հետո։", reply_markup=receipt_keyboard(), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "card:unavailable")
async def card_unavailable(callback: CallbackQuery):
    await callback.answer("💳 Քարտով վճարումը դեռ հասանելի չէ։", show_alert=True)


@dp.callback_query(F.data == "back:main")
async def back_main(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    user["support_waiting"] = False
    user["brawl_pass_analyzing"] = False
    await callback.message.edit_text(main_text(), reply_markup=main_menu_keyboard(), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data.startswith("back:game:"))
async def back_game(callback: CallbackQuery):
    game = callback.data.split(":", 2)[2]
    if game not in CATALOG:
        await callback.answer("❌ Սխալ խաղ։", show_alert=True)
        return
    user = get_user(callback.from_user.id)
    user["brawl_pass_analyzing"] = False
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
