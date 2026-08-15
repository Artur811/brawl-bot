from pathlib import Path
import re

SRC = Path(__file__).with_name('legacy_gamesvaultshop.py')
s = SRC.read_text(encoding='utf-8')

# Brawl Pass screenshot replacement flow.
s = s.replace(
    'from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup',
    'from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto',
    1,
)
s = s.replace(
    "'brawl_pass_waiting': False, 'receipt_waiting_id': False,",
    "'brawl_pass_waiting': False, 'pass_admin_message_id': None, 'receipt_waiting_id': False,",
    1,
)
photo_pat = re.compile(r"    if user\.get\('brawl_pass_waiting'\):.*?(?=    if user\.get\('payment'\) != 'receipt_pending':)", re.S)
photo_new = '''    if user.get('brawl_pass_waiting'):
        if not ORDER_CHANNEL_ID:
            await message.answer('⚠️ Պատվերների ալիքը կարգավորված չէ։')
            return
        pass_type = user['brawl_pass_type']
        low, high = BRAWL_PASS_PRICES[pass_type]
        title = 'Brawl Pass' if pass_type == 'brawl_pass' else 'Brawl Pass+'
        caption = (f'📸 <b>BRAWL PASS SCREENSHOT</b>\\n\\n👤 @{escape(message.from_user.username or "չկա")}\\n'
                   f'🆔 <code>{message.from_user.id}</code>\\n📦 <b>{title}</b>\\n\\n'
                   f'💰 Ընտրիր ճիշտ գինը՝ {fmt(low)} ֏ / {fmt(high)} ֏')
        markup = kb([
            [InlineKeyboardButton(text=f'💰 {fmt(low)} ֏', callback_data=f'passprice:{message.from_user.id}:{low}'),
             InlineKeyboardButton(text=f'💰 {fmt(high)} ֏', callback_data=f'passprice:{message.from_user.id}:{high}')],
            [InlineKeyboardButton(text='❌ Սխալ կամ վատ տեսանելի screenshot', callback_data=f'pass_bad:{message.from_user.id}')],
        ])
        old_message_id = user.get('pass_admin_message_id')
        if old_message_id:
            try:
                await bot.edit_message_media(
                    chat_id=ORDER_CHANNEL_ID,
                    message_id=old_message_id,
                    media=InputMediaPhoto(media=message.photo[-1].file_id, caption=caption, parse_mode='HTML'),
                    reply_markup=markup,
                )
                user['brawl_pass_waiting'] = False
                await save_state()
                await message.answer('✅ Նոր screenshot-ը ստացվեց և փոխարինեց նախորդը։', reply_markup=main_kb())
                return
            except Exception:
                logging.exception('Could not replace Brawl Pass screenshot; sending a new one')
        sent = await bot.send_photo(
            ORDER_CHANNEL_ID, message.photo[-1].file_id,
            caption=caption,
            parse_mode='HTML',
            reply_markup=markup)
        user['brawl_pass_waiting'] = False
        user['pass_admin_message_id'] = sent.message_id
        await save_state()
        await message.answer('✅ Screenshot-ը ստացվեց։ Ադմինը կընտրի ճիշտ գինը։', reply_markup=main_kb())
        return
'''
s, n = photo_pat.subn(photo_new, s, count=1)
assert n == 1, 'Brawl Pass photo block not found'

# Admin can reject the screenshot without creating another order.
marker = "\n\n@dp.message(F.photo)\nasync def photo_router(message: Message):"
pass_bad = '''\n\n@dp.callback_query(F.data.startswith('pass_bad:'))
async def pass_bad(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer('⛔ Միայն ադմինին։', show_alert=True)
        return
    uid = int(callback.data.split(':')[1])
    user = get_user(uid)
    if not user.get('brawl_pass_type') and not user.get('pass_admin_message_id'):
        await callback.answer('⚠️ Այս screenshot-ի պատվերը այլևս ակտիվ չէ։', show_alert=True)
        return
    user['brawl_pass_waiting'] = True
    await save_state()
    await notify(uid, '❌ <b>Սխալ կամ վատ տեսանելի screenshot</b>։\\n\\n📸 Ուղարկիր նոր, ավելի հստակ screenshot։')
    await callback.answer('📸 Հաճախորդին ուղարկվեց նոր screenshot ուղարկելու խնդրանքը։')
'''
assert marker in s
s = s.replace(marker, pass_bad + marker, 1)

# E-mail / Authenticator: no client buttons. The client types a normal confirmation;
# only non-sensitive confirmation text is routed to the order channel.
verify_pat = re.compile(r"async def send_verification\(uid, kind\):.*?(?=\n\n@dp\.message\(CommandStart\(\)\))", re.S)
verify_new = '''async def send_verification(uid, kind):
    user = get_user(uid)
    user['verification_type'] = kind
    user['verification_done'] = False
    await save_state()
    text = verification_text(kind)
    markup = client_verify_kb() if kind == 'device' else None
    try:
        await bot.send_photo(uid, VERIFY_IMAGES[kind], caption=text, parse_mode='HTML', reply_markup=markup)
    except Exception:
        logging.exception('verification image failed')
        await notify(uid, text, markup)
'''
s, n = verify_pat.subn(verify_new, s, count=1)
assert n == 1, 'send_verification block not found'

text_marker = "async def text_router(message: Message):\n    user = get_user(message.from_user.id)\n"
text_inject = '''async def text_router(message: Message):
    user = get_user(message.from_user.id)
    if user.get('verification_type') in {'email', 'authenticator'} and not user.get('verification_done'):
        raw = message.text.strip()
        sensitive = bool(re.search(r'(?i)(\\b(?:password|passwd|passcode|cvv|cvc)\\b|\\b(?:парол|код|գաղտնաբառ|կոդ)\\b|\\b\\d{6,8}\\b)', raw))
        if ORDER_CHANNEL_ID:
            if sensitive:
                channel_text = order_summary(message.from_user.id, user, '⚠️ Клиент подтвердил 2FA, но чувствительный текст не переслан.')
            else:
                channel_text = order_summary(message.from_user.id, user, '🟢 Клиент подтвердил 2FA') + f"\\n\\n💬 <b>Сообщение клиента:</b> {escape(raw)}"
            try:
                await bot.send_message(ORDER_CHANNEL_ID, channel_text, parse_mode='HTML')
            except Exception:
                logging.exception('Could not send 2FA confirmation to order channel')
        user['verification_done'] = True
        await save_state()
        return
'''
assert text_marker in s
s = s.replace(text_marker, text_inject, 1)

exec(compile(s, str(SRC), 'exec'), globals(), globals())
