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

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))
ORDER_CHANNEL_ID = os.getenv('ORDER_CHANNEL_ID', '')
SUPPORT_CHANNEL_ID = os.getenv('SUPPORT_CHANNEL_ID', '')
TELCELL_NUMBER = os.getenv('TELCELL_NUMBER', '043055510')
PORT = int(os.getenv('PORT', '10000'))
STATE_FILE = Path(os.getenv('STATE_FILE', 'orders_state.json'))

if not BOT_TOKEN:
    raise RuntimeError('BOT_TOKEN չգտնվեց։ Ավելացրու BOT_TOKEN-ը Render-ի Environment Variables-ում։')

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')

users = {}
state_lock = asyncio.Lock()

BRAWL_PASS_PRICES = {
    'brawl_pass': (2500, 3400),
    'brawl_pass_plus': (3400, 4800),
}

VERIFY_IMAGES = {
    'device': 'https://devforum-uploads.s3.dualstack.us-east-2.amazonaws.com/uploads/original/5X/a/4/c/b/a4cb7f66e45935445932f8d966013463406a251e.png',
    'authenticator': 'https://devforum-uploads.s3.dualstack.us-east-2.amazonaws.com/uploads/original/5X/8/d/a/5/8da5d76034856021ad807288f8c8e8a43c66a8b4.png',
    'email': 'https://devforum-uploads.s3.dualstack.us-east-2.amazonaws.com/uploads/original/5X/4/2/6/8/4268f5cf79d76d381d13648d545b8929d562ae08.png',
}

CATALOG = {
    'roblox': {'name': '🎮 Roblox', 'items': [
        ('40 Robux', 350), ('80 Robux', 650), ('120 Robux', 950),
        ('400 Robux', 2700), ('520 Robux', 3600), ('840 Robux', 4850),
        ('1,240 Robux', 7300), ('1,700 Robux', 8800), ('1,820 Robux', 9700),
        ('4,500 Robux', 21000), ('10,000 Robux', 40000), ('22,500 Robux', 88000),
    ]},
    'standoff2': {'name': '🔫 Standoff 2', 'items': [
        ('100 Gold', 1000), ('200 Gold', 2000), ('300 Gold', 2900),
        ('500 Gold', 4000), ('600 Gold', 5100), ('700 Gold', 5800),
        ('1,000 Gold', 7100), ('1,500 Gold', 10300), ('3,000 Gold', 15800),
    ]},
    'brawlstars': {'name': '⭐ Brawl Stars', 'items': [
        ('30 Gems', 750), ('80 Gems', 1500), ('170 Gems', 2800),
        ('360 Gems', 5100), ('950 Gems', 12800), ('Brawl Pass', 2500),
        ('Brawl Pass+', 3400), ('Прокачка Brawl Pass → Brawl Pass+', 1800),
        ('Pro Pass', 12300),
    ]},
    'pubg': {'name': '🪂 PUBG Mobile', 'items': [
        ('33 UC + 🎁', 300), ('66 UC + 🎁', 500), ('99 UC + 🎁', 700),
        ('132 UC + 🎁', 1000), ('150 UC + 🎁', 1100), ('198 UC + 🎁', 1400),
        ('210 UC + 🎁', 1600), ('325 UC + 🎁', 2000), ('355 + 5 UC + 🎁', 2100),
        ('445 UC + 🎁', 2900), ('505 UC + 🎁', 3400), ('660 UC + 🎁', 4000),
        ('720 UC + 🎁', 4300), ('985 UC + 🎁', 6000), ('1,135 UC + 🎁', 7000),
        ('1,320 UC + 🎁', 7800), ('1,860 UC + 🎁', 10000), ('2,185 UC + 🎁', 11500),
    ]},
    'fcmobile': {'name': '⚽ FC Mobile', 'items': [
        ('40 FC Points', 300), ('100 FC Points', 650),
        ('500 + 20 FC Points 🎁', 3000), ('1,000 + 70 FC Points 🎁', 5500),
        ('2,000 + 200 FC Points 🎁', 11000), ('5,000 + 750 FC Points 🎁', 27000),
        ('10,000 + 2,000 FC Points 🎁', 54000),
    ]},
}


def blank_user():
    return {
        'game': None, 'product': None, 'price': None, 'username': None,
        'payment': None, 'order_id': None, 'brawl_pass_type': None,
        'brawl_pass_waiting': False, 'receipt_waiting_id': False,
        'receipt_order_message_id': None, 'receipt_accepted': False,
        'refund_waiting': False, 'refund_method': None, 'refund_operator': None,
        'refund_details_ready': False, 'refund_details': None, 'game_id': None,
        'support_waiting': False, 'verification_type': None, 'verification_done': False,
    }


def get_user(uid):
    if uid not in users:
        users[uid] = blank_user()
    else:
        users[uid] = {**blank_user(), **users[uid]}
    return users[uid]


def load_state():
    global users
    try:
        if STATE_FILE.exists():
            users = {int(k): v for k, v in json.loads(STATE_FILE.read_text('utf-8')).items()}
    except Exception:
        logging.exception('Could not load saved state')
        users = {}


async def save_state():
    async with state_lock:
        tmp = STATE_FILE.with_suffix('.tmp')
        tmp.write_text(json.dumps(users, ensure_ascii=False), 'utf-8')
        tmp.replace(STATE_FILE)


def fmt(value):
    return f'{int(value):,}'.replace(',', ' ')


def kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_kb():
    return kb([
        [InlineKeyboardButton(text='🎮 Roblox', callback_data='game:roblox'), InlineKeyboardButton(text='🔫 Standoff 2', callback_data='game:standoff2')],
        [InlineKeyboardButton(text='⭐ Brawl Stars', callback_data='game:brawlstars'), InlineKeyboardButton(text='🪂 PUBG Mobile', callback_data='game:pubg')],
        [InlineKeyboardButton(text='⚽ FC Mobile', callback_data='game:fcmobile')],
        [InlineKeyboardButton(text='📩 Կապվեք մեզ հետ', callback_data='contact:open')],
    ])


def game_kb(game):
    rows = []
    for i, (name, price) in enumerate(CATALOG[game]['items']):
        if name == 'Brawl Pass':
            text = '🎫 Brawl Pass — 2 500 / 3 400 ֏'
        elif name == 'Brawl Pass+':
            text = '⭐ Brawl Pass+ — 3 400 / 4 800 ֏'
        else:
            text = f'⚡ {name} — {fmt(price)} ֏'
        rows.append([InlineKeyboardButton(text=text, callback_data=f'product:{game}:{i}')])
    rows.append([InlineKeyboardButton(text='⬅️ Հետ', callback_data='back:main')])
    return kb(rows)


def product_kb(game):
    return kb([
        [InlineKeyboardButton(text='✅ Գնել', callback_data='buy:confirm')],
        [InlineKeyboardButton(text='⬅️ Հետ', callback_data=f'back:game:{game}')],
    ])


def payment_kb():
    return kb([
        [InlineKeyboardButton(text='💳 Վճարել քարտով', callback_data='payment:card')],
        [InlineKeyboardButton(text='💵 Վճարել կանխիկ', callback_data='payment:cash')],
        [InlineKeyboardButton(text='⬅️ Հետ', callback_data='back:product')],
    ])


def receipt_kb():
    return kb([
        [InlineKeyboardButton(text='🧾 Ուղարկել չեկի նկարը', callback_data='payment:done')],
        [InlineKeyboardButton(text='⬅️ Հետ', callback_data='back:payment')],
    ])


def admin_kb(uid):
    user = get_user(uid)
    rows = [
        [InlineKeyboardButton(text='❌ Մերժել չեկը', callback_data=f'receipt:reject:{uid}'), InlineKeyboardButton(text='✅ Հաստատել չեկը', callback_data=f'receipt:accept:{uid}')],
        [InlineKeyboardButton(text='💸 Տրամադրել հետ գումարը', callback_data=f'receipt:refund:{uid}')],
    ]
    if user['receipt_accepted']:
        rows.append([InlineKeyboardButton(text='🔐 2FA', callback_data=f'verify_menu:{uid}')])
        rows.append([InlineKeyboardButton(text='📦 Հաստատել պատվերը', callback_data=f'receipt:confirm:{uid}')])
    if user['refund_details_ready']:
        rows.append([InlineKeyboardButton(text='✅ Հետ գումարի վերադարձը ավարտված է', callback_data=f'receipt:refund_complete:{uid}')])
    return kb(rows)


def admin_verify_kb(uid):
    return kb([
        [InlineKeyboardButton(text='📧 E-mail', callback_data=f'verify:{uid}:email')],
        [InlineKeyboardButton(text='🔐 Authenticator', callback_data=f'verify:{uid}:authenticator')],
        [InlineKeyboardButton(text='⬅️ Հետ', callback_data=f'verify_back:{uid}')],
    ])


def client_verify_kb():
    return kb([
        [InlineKeyboardButton(text='✅ Մուտքը հաստատեցի', callback_data='verify_done')],
        [InlineKeyboardButton(text='⬅️ Հետ', callback_data='back:main')],
    ])


def refund_method_kb():
    return kb([
        [InlineKeyboardButton(text='📱 Հեռախոսահամարին', callback_data='refundclient:phone')],
        [InlineKeyboardButton(text='💳 Քարտին', callback_data='refundclient:card')],
    ])


def operators_kb():
    return kb([
        [InlineKeyboardButton(text='📞 Viva', callback_data='refundclient:operator:Viva')],
        [InlineKeyboardButton(text='📞 Team Telecom Armenia', callback_data='refundclient:operator:Team Telecom Armenia')],
        [InlineKeyboardButton(text='📞 Ucom', callback_data='refundclient:operator:Ucom')],
        [InlineKeyboardButton(text='⬅️ Հետ', callback_data='refundclient:back')],
    ])


def back_kb(callback_data):
    return kb([[InlineKeyboardButton(text='⬅️ Հետ', callback_data=callback_data)]])


def main_text():
    return ('💎 <b>Games Vault Shop</b> ❤️‍🔥\n\n'
            '💎 <b>Games Vault Shop-ում՝ միշտ VAULT-Ա!</b>\n\n'
            '🎮 Ընտրիր խաղը և տես հասանելի ապրանքները։\n\n'
            '⚡ Արագ պատվեր\n💳 Telcell Wallet\n🧾 Չեկի ստուգում\n📩 Աջակցություն և կապ։')


def order_summary(uid, user, status):
    game = CATALOG.get(user.get('game'), {}).get('name', 'չկա')
    gid = f'\n🎮 Game ID՝ <code>{escape(str(user["game_id"]))}</code>' if user.get('game_id') else ''
    return (f'🧾 <b>ՊԱՏՎԵՐ</b>\n\n'
            f'👤 Username՝ @{escape(user.get("username") or "չկա")}\n'
            f'🆔 Telegram ID՝ <code>{uid}</code>{gid}\n'
            f'🎮 Խաղ՝ <b>{escape(game)}</b>\n'
            f'📦 Ապրանք՝ <b>{escape(user.get("product") or "չկա")}</b>\n'
            f'💰 Գին՝ <b>{fmt(user.get("price") or 0)} ֏</b>\n\n'
            f'📌 <b>Կարգավիճակ՝ {status}</b>')


def final_status(uid, user, status):
    game = CATALOG.get(user.get('game'), {}).get('name', 'չկա')
    return (f'🧾 <b>ՊԱՏՎԵՐԻ ԿԱՐԳԱՎԻՃԱԿ</b>\n\n'
            f'👤 Գնորդ՝ @{escape(user.get("username") or "չկա")}\n'
            f'🎮 Խաղ՝ <b>{escape(game)}</b>\n'
            f'📦 Ապրանք՝ <b>{escape(user.get("product") or "չկա")}</b>\n'
            f'💰 Գին՝ <b>{fmt(user.get("price") or 0)} ֏</b>\n\n'
            f'📌 <b>Կարգավիճակ՝ {status}</b>')


def cash_text(user):
    return (f'💎 <b>Games Vault Shop-ից Բարևներ</b> ❤️‍🔥\n\n'
            f'💵 <b>Վճարման քայլերը՝</b>\n\n'
            f'1️⃣ Telcell տերմինալում ընտրեք <b>«Telcell Wallet»</b> և մուտքագրեք հեռախոսահամարը՝ <code>{escape(TELCELL_NUMBER)}</code> 📱\n\n'
            f'2️⃣ Կատարեք վճարումը՝ <b>{fmt(user["price"])} ֏</b> 💰\n\n'
            f'3️⃣ 🧾 Վճարումից հետո նկարեք չեկը և ուղարկեք մեզ։\n\n'
            f'4️⃣ 🆔 Այնուհետև տրամադրեք ձեր Game ID / Username-ը։\n\n'
            f'⚡ <b>1–2 րոպեում ստանում եք ձեր Դոնաթը։</b> ✅❤️‍🔥\n\n'
            f'📦 Պատվեր՝ <b>{escape(user["product"])}</b>')


async def notify(uid, text, markup=None):
    try:
        await bot.send_message(uid, text, parse_mode='HTML', reply_markup=markup)
    except Exception:
        logging.exception('notify failed')


async def finalize(uid, status, client_text):
    user = get_user(uid)
    message_id = user.get('receipt_order_message_id')
    if message_id and ORDER_CHANNEL_ID:
        try:
            await bot.delete_message(ORDER_CHANNEL_ID, message_id)
        except Exception:
            logging.exception('delete order message failed')
        try:
            await bot.send_message(ORDER_CHANNEL_ID, final_status(uid, user, status), parse_mode='HTML')
        except Exception:
            logging.exception('final status failed')
    await notify(uid, client_text, main_kb())
    users[uid] = blank_user()
    await save_state()


def verification_text(kind):
    if kind == 'email':
        return ('📧 <b>2FA — E-mail</b>\n\n'
                'Բացիր քո հաստատված E-mail-ը և մուտքագրիր Roblox-ի ուղարկած կոդը միայն Roblox-ի պաշտոնական մուտքի էջում։\n\n'
                '⚠️ Կոդը <b>ոչ մի դեպքում մի ուղարկիր</b> Games Vault Shop-ին կամ ադմինին։')
    if kind == 'authenticator':
        return ('🔐 <b>2FA — Authenticator</b>\n\n'
                'Բացիր քո Authenticator հավելվածը և օգտագործիր այնտեղ երևացող կոդը միայն Roblox-ի պաշտոնական մուտքի էջում։\n\n'
                '⚠️ Authenticator-ի կոդը <b>ոչ մի դեպքում մի ուղարկիր</b> Games Vault Shop-ին կամ ադմինին։')
    return ('📱 <b>2FA — Այլ սարքով հաստատում</b>\n\n'
            'Բացիր Roblox-ը այն հեռախոսում կամ պլանշետում, որտեղ քո հաշիվը արդեն մուտք գործած է։ Հաստատիր միայն այն մուտքը, որը դու ես սկսել։\n\n'
            '⚠️ Եթե մուտքը քոնը չէ՝ մերժիր այն։ Կոդ կամ գաղտնաբառ մեզ մի ուղարկիր։')


async def send_verification(uid, kind):
    user = get_user(uid)
    user['verification_type'] = kind
    user['verification_done'] = False
    await save_state()
    text = verification_text(kind)
    try:
        await bot.send_photo(uid, VERIFY_IMAGES[kind], caption=text, parse_mode='HTML', reply_markup=client_verify_kb())
    except Exception:
        logging.exception('verification image failed')
        await notify(uid, text, client_verify_kb())


@dp.message(CommandStart())
async def start(message: Message):
    user = get_user(message.from_user.id)
    user['username'] = message.from_user.username
    user['support_waiting'] = False
    await save_state()
    await message.answer(main_text(), reply_markup=main_kb(), parse_mode='HTML')


@dp.message(Command('menu'))
async def menu(message: Message):
    await message.answer(main_text(), reply_markup=main_kb(), parse_mode='HTML')


@dp.callback_query(F.data.startswith('game:'))
async def choose_game(callback: CallbackQuery):
    game = callback.data.split(':', 1)[1]
    if game not in CATALOG:
        await callback.answer('❌ Սխալ խաղ։', show_alert=True)
        return
    user = get_user(callback.from_user.id)
    user.update(blank_user())
    user['game'] = game
    user['username'] = callback.from_user.username
    await save_state()
    await callback.message.edit_text(f'{CATALOG[game]["name"]}\n\n📦 Ընտրիր անհրաժեշտ ապրանքը։', reply_markup=game_kb(game), parse_mode='HTML')
    await callback.answer()


@dp.callback_query(F.data.startswith('product:'))
async def choose_product(callback: CallbackQuery):
    _, game, index = callback.data.split(':')
    try:
        name, price = CATALOG[game]['items'][int(index)]
    except (KeyError, ValueError, IndexError):
        await callback.answer('❌ Սխալ ապրանք։', show_alert=True)
        return
    user = get_user(callback.from_user.id)
    user.update({'game': game, 'product': name, 'price': price, 'username': callback.from_user.username})
    if game == 'brawlstars' and name in {'Brawl Pass', 'Brawl Pass+'}:
        user['brawl_pass_type'] = 'brawl_pass' if name == 'Brawl Pass' else 'brawl_pass_plus'
        user['brawl_pass_waiting'] = True
        await save_state()
        await callback.message.edit_text(
            f'📸 <b>Ուղարկիր screenshot-ը, որտեղ հստակ երևում է քո {escape(name)}-ի գինը։</b>\n\n'
            '👨‍💼 Screenshot-ը կստանա ադմինը և կընտրի ճիշտ գինը։',
            reply_markup=back_kb('back:game:brawlstars'), parse_mode='HTML')
        await callback.answer()
        return
    await save_state()
    await callback.message.edit_text(
        f'🛒 <b>Ձեր ընտրությունը</b>\n\n🎮 Խաղ՝ <b>{escape(CATALOG[game]["name"])}</b>\n'
        f'📦 Ապրանք՝ <b>{escape(name)}</b>\n💰 Գին՝ <b>{fmt(price)} ֏</b>\n\nՇարունակե՞լ պատվերը։',
        reply_markup=product_kb(game), parse_mode='HTML')
    await callback.answer()


@dp.message(F.photo)
async def photo_router(message: Message):
    user = get_user(message.from_user.id)
    if user.get('brawl_pass_waiting'):
        if not ORDER_CHANNEL_ID:
            await message.answer('⚠️ Պատվերների ալիքը կարգավորված չէ։')
            return
        pass_type = user['brawl_pass_type']
        low, high = BRAWL_PASS_PRICES[pass_type]
        title = 'Brawl Pass' if pass_type == 'brawl_pass' else 'Brawl Pass+'
        sent = await bot.send_photo(
            ORDER_CHANNEL_ID, message.photo[-1].file_id,
            caption=(f'📸 <b>BRAWL PASS SCREENSHOT</b>\n\n👤 @{escape(message.from_user.username or "չկա")}\n'
                     f'🆔 <code>{message.from_user.id}</code>\n📦 <b>{title}</b>\n\n'
                     f'💰 Ընտրիր ճիշտ գինը՝ {fmt(low)} ֏ / {fmt(high)} ֏'),
            parse_mode='HTML',
            reply_markup=kb([[InlineKeyboardButton(text=f'💰 {fmt(low)} ֏', callback_data=f'passprice:{message.from_user.id}:{low}'),
                              InlineKeyboardButton(text=f'💰 {fmt(high)} ֏', callback_data=f'passprice:{message.from_user.id}:{high}')]]))
        user['brawl_pass_waiting'] = False
        user['pass_admin_message_id'] = sent.message_id
        await save_state()
        await message.answer('✅ Screenshot-ը ստացվեց։ Ադմինը կընտրի ճիշտ գինը։', reply_markup=main_kb())
        return
    if user.get('payment') != 'receipt_pending':
        return
    if not ORDER_CHANNEL_ID:
        await message.answer('⚠️ Պատվերների ալիքը կարգավորված չէ։')
        return
    user['payment'] = 'receipt_sent'
    user['order_id'] = f'{message.from_user.id}-{message.message_id}'
    user['username'] = message.from_user.username
    user['receipt_waiting_id'] = True
    sent = await bot.send_photo(
        ORDER_CHANNEL_ID, message.photo[-1].file_id,
        caption=order_summary(message.from_user.id, user, '⏳ Չեկը սպասում է ադմինի ստուգմանը։'),
        parse_mode='HTML', reply_markup=admin_kb(message.from_user.id))
    user['receipt_order_message_id'] = sent.message_id
    await save_state()
    await message.answer('💎 <b>Չեկը ստացվեց։</b> ❤️‍🔥\n\n🆔 Հիմա ուղարկիր քո Game ID / Username-ը։\n\n⚠️ Գաղտնաբառ, E-mail-ի կոդ կամ Authenticator-ի կոդ մի ուղարկիր։', parse_mode='HTML')


@dp.message(F.text)
async def text_router(message: Message):
    user = get_user(message.from_user.id)
    if user.get('support_waiting'):
        if not SUPPORT_CHANNEL_ID:
            user['support_waiting'] = False
            await save_state()
            await message.answer('⚠️ Աջակցության ալիքը դեռ կարգավորված չէ։', reply_markup=main_kb())
            return
        await bot.send_message(SUPPORT_CHANNEL_ID,
            f'📩 <b>Նոր հաղորդագրություն</b>\n\n👤 @{escape(message.from_user.username or "չկա")}\n'
            f'🆔 <code>{message.from_user.id}</code>\n\n💬 {escape(message.text)}', parse_mode='HTML')
        user['support_waiting'] = False
        await save_state()
        await message.answer('✅ Հաղորդագրությունը ուղարկվեց։', reply_markup=main_kb())
        return
    if (user.get('refund_waiting') and user.get('refund_method') in {'phone', 'card'}
            and not user.get('refund_details_ready')
            and (user.get('refund_operator') or user.get('refund_method') == 'card')):
        user['refund_details_ready'] = True
        user['refund_details'] = message.text.strip()
        method = '📱 Հեռախոսահամար' if user['refund_method'] == 'phone' else '💳 Քարտ'
        operator = f'\n📞 Օպերատոր՝ <b>{escape(user.get("refund_operator") or "-")}</b>' if user.get('refund_operator') else ''
        await save_state()
        await notify(ADMIN_ID,
            f'💸 <b>Տվյալները վերադարձի համար</b>\n\n🆔 <code>{message.from_user.id}</code>\n'
            f'📦 {escape(user.get("product") or "")}\n💰 {fmt(user.get("price") or 0)} ֏\n'
            f'📌 Եղանակ՝ <b>{method}</b>{operator}\n📝 Տվյալներ՝ <code>{escape(message.text.strip())}</code>',
            admin_kb(message.from_user.id))
        await message.answer('✅ Տվյալները ստացվեցին։ Սպասիր վերադարձի հաստատմանը։')
        return
    if user.get('receipt_waiting_id'):
        game_id = message.text.strip()
        if not game_id:
            await message.answer('⚠️ Ուղարկիր ճիշտ Game ID / Username։')
            return
        user['game_id'] = game_id
        user['receipt_waiting_id'] = False
        await save_state()
        try:
            await bot.edit_message_caption(
                chat_id=ORDER_CHANNEL_ID, message_id=user['receipt_order_message_id'],
                caption=order_summary(message.from_user.id, user, '⏳ Չեկը սպասում է ադմինի ստուգմանը։'),
                parse_mode='HTML', reply_markup=admin_kb(message.from_user.id))
        except Exception:
            logging.exception('Could not update order with Game ID')
        await message.answer('✅ Game ID / Username-ը ստացվեց։')


@dp.callback_query(F.data == 'buy:confirm')
async def buy_confirm(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    await callback.message.edit_text(
        f'💳 <b>Ընտրիր վճարման եղանակը</b>\n\n📦 {escape(user["product"])}\n💰 Գումար՝ <b>{fmt(user["price"])} ֏</b>',
        reply_markup=payment_kb(), parse_mode='HTML')
    await callback.answer()


@dp.callback_query(F.data == 'payment:card')
async def payment_card(callback: CallbackQuery):
    await callback.answer('💳 Քարտով վճարումը դեռ հասանելի չէ։', show_alert=True)


@dp.callback_query(F.data == 'payment:cash')
async def payment_cash(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    user['payment'] = 'cash'
    await save_state()
    await callback.message.edit_text(cash_text(user), reply_markup=receipt_kb(), parse_mode='HTML')
    await callback.answer()


@dp.callback_query(F.data == 'payment:done')
async def payment_done(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    user['payment'] = 'receipt_pending'
    await save_state()
    await callback.message.edit_text('🧾 <b>Ուղարկիր չեկի նկարը</b>\n\n📸 Ուղարկիր վճարման չեկի լուսանկարը։', reply_markup=back_kb('back:payment'), parse_mode='HTML')
    await callback.answer()


@dp.callback_query(F.data.startswith('passprice:'))
async def passprice(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer('⛔ Միայն ադմինին։', show_alert=True)
        return
    _, uid_text, price_text = callback.data.split(':')
    uid, price = int(uid_text), int(price_text)
    user = get_user(uid)
    user['price'] = price
    user['product'] = 'Brawl Pass' if user['brawl_pass_type'] == 'brawl_pass' else 'Brawl Pass+'
    user['brawl_pass_type'] = None
    await save_state()
    try:
        await callback.message.edit_caption((callback.message.caption or '') + f'\n\n✅ <b>Ընտրված գին՝ {fmt(price)} ֏</b>', parse_mode='HTML', reply_markup=None)
    except Exception:
        logging.exception('Could not update pass message')
    await notify(uid, f'✅ <b>Ձեր Pass-ի գինը հաստատվեց։</b>\n\n📦 {escape(user["product"])}\n💰 {fmt(price)} ֏', product_kb('brawlstars'))
    await callback.answer('✅ Գինը ընտրված է։')


async def admin_only(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer('⛔ Միայն ադմինին։', show_alert=True)
        return False
    return True


@dp.callback_query(F.data.startswith('receipt:'))
async def receipt_action(callback: CallbackQuery):
    if not await admin_only(callback):
        return
    _, action, uid_text = callback.data.split(':')
    uid = int(uid_text)
    user = get_user(uid)
    if action == 'reject':
        await finalize(uid, '❌ Չեկը մերժված է — Դոնաթը չի հաջողվել.', '❌ <b>Դոնաթը չի հաջողվել.</b>\n\nՎճարման չեկը մերժվել է։')
        await callback.answer('❌ Չեկը մերժվեց։')
        return
    if action == 'accept':
        user['receipt_accepted'] = True
        user['payment'] = 'receipt_accepted'
        await save_state()
        await callback.message.edit_caption(order_summary(uid, user, '✅ Չեկը հաստատված է։ Ընտրիր հաջորդ գործողությունը.'), parse_mode='HTML', reply_markup=admin_kb(uid))
        await notify(uid, '✅ <b>Չեկը հաստատվեց։</b>\n\n⏳ Պատվերը պատրաստվում է։')
        await callback.answer('✅ Չեկը հաստատվեց։')
        return
    if action == 'confirm':
        if not user['receipt_accepted']:
            await callback.answer('⚠️ Նախ հաստատիր չեկը։', show_alert=True)
            return
        if not user.get('verification_type') or not user.get('verification_done'):
            await callback.answer('⚠️ Նախ ընտրիր E-mail կամ Authenticator և սպասիր «Պատրաստ է» հաստատմանը։', show_alert=True)
            return
        await finalize(uid, '📦 Պատվերը հաստատված է — Դոնաթը հաջողությամբ ավարտված է.', '🎉 <b>Դոնաթը հաջողությամբ ավարտված է։</b> ❤️‍🔥\n\nՇնորհակալություն Games Vault Shop-ը ընտրելու համար։ 💎')
        await callback.answer('📦 Պատվերը ավարտվեց։')
        return
    if action == 'refund':
        user['refund_waiting'] = True
        user['refund_method'] = None
        user['refund_operator'] = None
        user['refund_details_ready'] = False
        await save_state()
        await notify(uid, '⚠️ <b>Դոնաթը չի հաջողվել։</b>\n\n💸 Ընտրիր, թե որտեղ պետք է կատարվի վերադարձը։', refund_method_kb())
        await callback.answer('💸 Հաճախորդին ուղարկվեց վերադարձի ընտրությունը։')
        return
    if action == 'refund_complete':
        if not user.get('refund_details_ready'):
            await callback.answer('⚠️ Տվյալները դեռ չեն ստացվել։', show_alert=True)
            return
        await finalize(uid, '💸 Հետ գումարի վերադարձը ավարտված է — Դոնաթը չի հաջողվել.', '💸 <b>Հետ գումարի վերադարձը ավարտված է։</b>\n\n❌ Դոնաթը չի հաջողվել։ Գումարը վերադարձվել է։')
        await callback.answer('✅ Վերադարձը ավարտվեց։')


@dp.callback_query(F.data.startswith('verify_menu:'))
async def verify_menu(callback: CallbackQuery):
    if not await admin_only(callback):
        return
    uid = int(callback.data.split(':')[1])
    user = get_user(uid)
    if not user['receipt_accepted']:
        await callback.answer('⚠️ Նախ հաստատիր չեկը։', show_alert=True)
        return
    await callback.message.edit_caption(order_summary(uid, user, '🔐 Ընտրիր 2FA տարբերակը հաճախորդի համար.'), parse_mode='HTML', reply_markup=admin_verify_kb(uid))
    await callback.answer()


@dp.callback_query(F.data.startswith('verify_back:'))
async def verify_back(callback: CallbackQuery):
    if not await admin_only(callback):
        return
    uid = int(callback.data.split(':')[1])
    user = get_user(uid)
    await callback.message.edit_caption(order_summary(uid, user, '✅ Չեկը հաստատված է.'), parse_mode='HTML', reply_markup=admin_kb(uid))
    await callback.answer()


@dp.callback_query(F.data.startswith('verify:'))
async def verify(callback: CallbackQuery):
    if not await admin_only(callback):
        return
    _, uid_text, kind = callback.data.split(':')
    uid = int(uid_text)
    if kind not in VERIFY_IMAGES:
        await callback.answer('❌ Սխալ 2FA տարբերակ։', show_alert=True)
        return
    user = get_user(uid)
    if not user['receipt_accepted']:
        await callback.answer('⚠️ Նախ հաստատիր չեկը։', show_alert=True)
        return
    user['verification_type'] = kind
    user['verification_done'] = False
    await save_state()
    await callback.message.edit_caption(order_summary(uid, user, f'🔐 Ընտրված է՝ {kind}'), parse_mode='HTML', reply_markup=admin_kb(uid))
    await send_verification(uid, kind)
    await callback.answer('✅ Ուղեցույցը ուղարկվեց հաճախորդին։')


@dp.callback_query(F.data == 'verify_done')
async def verify_done(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user.get('verification_type'):
        await callback.answer('⚠️ 2FA տարբերակը դեռ ընտրված չէ։', show_alert=True)
        return
    user['verification_done'] = True
    await save_state()
    await notify(ADMIN_ID, '🟢 <b>ՊԱՏՐԱՍՏ Է</b>\n\n'
                     f'👤 @{escape(user.get("username") or "չկա")}\n'
                     f'🆔 Telegram ID՝ <code>{callback.from_user.id}</code>\n'
                     f'📦 Ապրանք՝ <b>{escape(user.get("product") or "չկա")}</b>\n'
                     f'💰 Գին՝ <b>{fmt(user.get("price") or 0)} ֏</b>\n'
                     '🔐 2FA՝ հաստատված է։', admin_kb(callback.from_user.id))
    try:
        await callback.message.edit_reply_markup(reply_markup=back_kb('back:main'))
    except Exception:
        logging.exception('Could not update client 2FA message')
    await callback.answer('✅ Հաստատումը ստացվեց։')


@dp.callback_query(F.data == 'refundclient:phone')
async def refund_phone(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    user['refund_method'] = 'phone'
    await save_state()
    await callback.message.edit_text('📱 <b>Ընտրիր քո բջջային օպերատորը</b>։', reply_markup=operators_kb(), parse_mode='HTML')
    await callback.answer()


@dp.callback_query(F.data == 'refundclient:card')
async def refund_card(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    user['refund_method'] = 'card'
    user['refund_operator'] = None
    await save_state()
    await callback.message.edit_text('💳 <b>Ուղարկիր քարտի համարը</b>։\n\n⚠️ Մի ուղարկիր CVV/CVC, PIN կամ այլ գաղտնի կոդ։', reply_markup=back_kb('refundclient:back'), parse_mode='HTML')
    await callback.answer()


@dp.callback_query(F.data.startswith('refundclient:operator:'))
async def refund_operator(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    operator = callback.data.split(':', 2)[2]
    user['refund_operator'] = operator
    await save_state()
    await callback.message.edit_text(
        f'📱 <b>{escape(operator)}</b>\n\nՈւղարկիր հեռախոսահամարը, որին պետք է կատարվի վերադարձը։\n\n'
        '⚠️ <b>Զգուշացում․</b> եթե վերադարձը կատարվում է հեռախոսահամարին, գումարը կարող է նստել բջջային հաշվին և օգտագործվել զանգերի/կապի համար.',
        reply_markup=back_kb('refundclient:back'), parse_mode='HTML')
    await callback.answer()


@dp.callback_query(F.data == 'refundclient:back')
async def refund_back(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    user['refund_method'] = None
    user['refund_operator'] = None
    user['refund_details_ready'] = False
    await save_state()
    await callback.message.edit_text('💸 <b>Ընտրիր վերադարձի եղանակը</b>։', reply_markup=refund_method_kb(), parse_mode='HTML')
    await callback.answer()


@dp.callback_query(F.data == 'contact:open')
async def contact(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    user['support_waiting'] = True
    await save_state()
    await callback.message.edit_text('📩 <b>Կապվեք մեզ հետ</b>\n\n💬 Գրիր քո հաղորդագրությունը։', reply_markup=back_kb('back:main'), parse_mode='HTML')
    await callback.answer()


@dp.callback_query(F.data == 'back:main')
async def back_main(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    user['support_waiting'] = False
    await save_state()
    await callback.message.edit_text(main_text(), reply_markup=main_kb(), parse_mode='HTML')
    await callback.answer()


@dp.callback_query(F.data.startswith('back:game:'))
async def back_game(callback: CallbackQuery):
    game = callback.data.split(':', 2)[2]
    if game not in CATALOG:
        await callback.answer('❌ Սխալ խաղ։', show_alert=True)
        return
    user = get_user(callback.from_user.id)
    user['brawl_pass_waiting'] = False
    await save_state()
    await callback.message.edit_text(f'{CATALOG[game]["name"]}\n\n📦 Ընտրիր անհրաժեշտ ապրանքը։', reply_markup=game_kb(game), parse_mode='HTML')
    await callback.answer()


@dp.callback_query(F.data == 'back:product')
async def back_product(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    await callback.message.edit_text(
        f'🛒 <b>Ձեր ընտրությունը</b>\n\n📦 {escape(user.get("product") or "")}\n💰 {fmt(user.get("price") or 0)} ֏',
        reply_markup=product_kb(user['game']), parse_mode='HTML')
    await callback.answer()


@dp.callback_query(F.data == 'back:payment')
async def back_payment(callback: CallbackQuery):
    await buy_confirm(callback)


async def health(request):
    return web.Response(text='Games Vault Shop is running!')


async def main():
    load_state()
    app = web.Application()
    app.router.add_get('/', health)
    app.router.add_get('/health', health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
