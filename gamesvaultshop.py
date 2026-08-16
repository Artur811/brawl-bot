from pathlib import Path
import re

SRC = Path(__file__).with_name('legacy_gamesvaultshop.py')
s = SRC.read_text(encoding='utf-8')

# Safe compatibility patch: keep the original bot and change only the requested flows.
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
photo_new = r'''    if user.get('brawl_pass_waiting'):
        if not ORDER_CHANNEL_ID:
            await message.answer('⚠️ Պատվերների ալիքը կարգավորված չէ։')
            return
        pass_type = user['brawl_pass_type']
        low, high = BRAWL_PASS_PRICES[pass_type]
        title = 'Brawl Pass' if pass_type == 'brawl_pass' else 'Brawl Pass+'
        caption = (
            f'📸 <b>BRAWL PASS SCREENSHOT</b>\n\n'
            f'👤 @{escape(message.from_user.username or "չկա")}\n'
            f'🆔 <code>{message.from_user.id}</code>\n'
            f'📦 <b>{title}</b>\n\n'
            f'💰 Ընտրիր ճիշտ գինը՝ {fmt(low)} ֏ / {fmt(high)} ֏'
        )
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
            ORDER_CHANNEL_ID,
            message.photo[-1].file_id,
            caption=caption,
            parse_mode='HTML',
            reply_markup=markup,
        )
        user['brawl_pass_waiting'] = False
        user['pass_admin_message_id'] = sent.message_id
        await save_state()
        await message.answer('✅ Screenshot-ը ստացվեց։ Ադմինը կընտրի ճիշտ գինը։', reply_markup=main_kb())
        return
'''
s, n = photo_pat.subn(lambda m: photo_new, s, count=1)
assert n == 1, 'Brawl Pass photo block not found'

marker = "\n\n@dp.message(F.photo)\nasync def photo_router(message: Message):"
pass_bad = r'''

@dp.callback_query(F.data.startswith('pass_bad:'))
async def pass_bad(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer('⛔ Միայն ադմինին։', show_alert=True)
        return
    uid = int(callback.data.split(':')[1])
    user = get_user(uid)
    if not user.get('pass_admin_message_id'):
        await callback.answer('⚠️ Այս screenshot-ի պատվերը այլևս ակտիվ չէ։', show_alert=True)
        return
    user['brawl_pass_waiting'] = True
    await save_state()
    await notify(uid, '❌ <b>Սխալ կամ վատ տեսանելի screenshot</b>։\n\n📸 Ուղարկիր նոր, ավելի հստակ screenshot։')
    await callback.answer('📸 Հաճախորդին ուղարկվեց նոր screenshot ուղարկելու խնդրանք։')
'''
assert marker in s
s = s.replace(marker, pass_bad + marker, 1)

verify_pat = re.compile(r"async def send_verification\(uid, kind\):.*?(?=\n\n@dp\.message\(CommandStart\(\)\))", re.S)
verify_new = r'''async def send_verification(uid, kind):
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
s, n = verify_pat.subn(lambda m: verify_new, s, count=1)
assert n == 1, 'send_verification block not found'

text_marker = "async def text_router(message: Message):\n    user = get_user(message.from_user.id)"
text_inject = r'''async def text_router(message: Message):
    user = get_user(message.from_user.id)
    if user.get('verification_type') in {'email', 'authenticator'} and not user.get('verification_done'):
        raw = message.text.strip()
        if ORDER_CHANNEL_ID:
            safe_text = escape(raw)
            channel_text = order_summary(message.from_user.id, user, '🟢 Հաճախորդը գրել է հաստատման հաղորդագրություն')
            channel_text += f'\n\n💬 <b>Հաղորդագրություն՝</b> {safe_text}'
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

# Override receipt actions before loading the legacy handlers. This keeps the original
# order data visible and guarantees a final status message even if deleting the old
# channel message is not permitted by Telegram.
receipt_marker = "\nexec(compile(s, str(SRC), 'exec'), globals(), globals())"
receipt_patch = r'''

async def _safe_finish_order(uid, status, client_text):
    user = get_user(uid)
    # Make sure the order contains the customer's Telegram username and the
    # game ID / username before producing the final status.
    user['username'] = user.get('username') or '-'
    message_id = user.get('receipt_order_message_id')
    final_text = final_status(uid, user, status)
    if message_id and ORDER_CHANNEL_ID:
        sent_status = False
        try:
            await bot.send_message(ORDER_CHANNEL_ID, final_text, parse_mode='HTML')
            sent_status = True
        except Exception:
            logging.exception('Could not send final order status')
        try:
            await bot.delete_message(ORDER_CHANNEL_ID, message_id)
        except Exception:
            logging.exception('Could not delete original order message')
            if not sent_status:
                try:
                    await bot.edit_message_caption(
                        chat_id=ORDER_CHANNEL_ID,
                        message_id=message_id,
                        caption=final_text,
                        parse_mode='HTML',
                        reply_markup=None,
                    )
                except Exception:
                    logging.exception('Could not convert order message to final status')
    await notify(uid, client_text, main_kb())
    users[uid] = blank_user()
    await save_state()


@dp.callback_query(F.data.startswith('receipt:'))
async def receipt_action_fixed(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer('⛔ Միայն ադմինին։', show_alert=True)
        return
    _, action, uid_text = callback.data.split(':')
    uid = int(uid_text)
    user = get_user(uid)
    if action == 'reject':
        await _safe_finish_order(
            uid,
            '❌ Չեկը մերժված է — Դոնաթը չի հաջողվել.',
            '❌ <b>Դոնաթը չի հաջողվել.</b>\n\nՎճարման չեկը մերժվել է.',
        )
        await callback.answer('❌ Չեկը մերժվեց.')
        return
    if action == 'accept':
        user['receipt_accepted'] = True
        user['payment'] = 'receipt_accepted'
        await save_state()
        await callback.message.edit_caption(
            order_summary(uid, user, '✅ Չեկը հաստատված է։ Ընտրիր հաջորդ գործողությունը.'),
            parse_mode='HTML',
            reply_markup=admin_kb(uid),
        )
        await notify(uid, '✅ <b>Չեկը հաստատվեց։</b>\n\n⏳ Պատվերը պատրաստվում է.')
        await callback.answer('✅ Չեկը հաստատվեց.')
        return
    if action == 'confirm':
        if not user.get('receipt_accepted'):
            await callback.answer('⚠️ Նախ հաստատիր չեկը.', show_alert=True)
            return
        if user.get('verification_type') and not user.get('verification_done'):
            await callback.answer('⚠️ Սպասիր, մինչև հաճախորդը հաստատի մուտքը 2FA-ով.', show_alert=True)
            return
        await _safe_finish_order(
            uid,
            '📦 Պատվերը հաստատված է — Դոնաթը հաջողությամբ ավարտված է.',
            '🎉 <b>Դոնաթը հաջողությամբ ավարտված է.</b> ❤️‍🔥\n\nՇնորհակալություն Games Vault Shop-ը ընտրելու համար. 💎',
        )
        await callback.answer('📦 Պատվերը ավարտվեց.')
        return
    if action == 'refund':
        user['refund_waiting'] = True
        user['refund_method'] = None
        user['refund_operator'] = None
        user['refund_details_ready'] = False
        await save_state()
        await notify(uid, '⚠️ <b>Դոնաթը չի հաջողվել.</b>\n\n💸 Ընտրիր, թե որտեղ պետք է կատարվի վերադարձը.', refund_method_kb())
        await callback.answer('💸 Հաճախորդին ուղարկվեց վերադարձի ընտրությունը.')
        return
    if action == 'refund_complete':
        if not user.get('refund_details_ready'):
            await callback.answer('⚠️ Տվյալները դեռ չեն ստացվել.', show_alert=True)
            return
        await _safe_finish_order(
            uid,
            '💸 Հետ գումարի վերադարձը ավարտված է — Դոնաթը չի հաջողվել.',
            '💸 <b>Հետ գումարի վերադարձը ավարտված է.</b>\n\n❌ Դոնաթը չի հաջողվել։ Գումարը վերադարձվել է.',
        )
        await callback.answer('✅ Վերադարձը ավարտվեց.')
        return
'''
assert receipt_marker in s
s = s.replace(receipt_marker, receipt_patch + receipt_marker, 1)

exec(compile(s, str(SRC), 'exec'), globals(), globals())
'''}