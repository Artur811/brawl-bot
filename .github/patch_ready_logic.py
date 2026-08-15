from pathlib import Path

p = Path('gamesvaultshop.py')
s = p.read_text(encoding='utf-8')

old = """    if user['receipt_accepted']:\n        rows.append([InlineKeyboardButton(text='🔐 2FA', callback_data=f'verify_menu:{uid}')])\n        rows.append([InlineKeyboardButton(text='📦 Հաստատել պատվերը', callback_data=f'receipt:confirm:{uid}')])\n"""
new = """    if user['receipt_accepted']:\n        rows.append([InlineKeyboardButton(text='🔐 2FA', callback_data=f'verify_menu:{uid}')])\n        if user.get('verification_done'):\n            rows.append([InlineKeyboardButton(text='🟢 Պատրաստ է', callback_data=f'receipt:ready:{uid}')])\n            rows.append([InlineKeyboardButton(text='❌ Դոնաթը չի հաջողվել', callback_data=f'receipt:failed:{uid}')])\n        rows.append([InlineKeyboardButton(text='📦 Հաստատել պատվերը', callback_data=f'receipt:confirm:{uid}')])\n"""
if old not in s:
    raise SystemExit('admin_kb block not found')
s = s.replace(old, new, 1)

old = """def client_verify_kb():\n    return kb([\n        [InlineKeyboardButton(text='✅ Մուտքը հաստատեցի', callback_data='verify_done')],\n        [InlineKeyboardButton(text='⬅️ Հետ', callback_data='back:main')],\n    ])\n"""
new = """def client_verify_kb():\n    return None\n"""
if old not in s:
    raise SystemExit('client_verify_kb block not found')
s = s.replace(old, new, 1)

s = s.replace("reply_markup=client_verify_kb())", "reply_markup=None)", 1)
s = s.replace("await notify(uid, text, client_verify_kb())", "await notify(uid, text)", 1)

marker = """    if user.get('support_waiting'):\n"""
insert = """    text_normalized = ' '.join(message.text.strip().lower().split())\n    if user.get('verification_type') and not user.get('verification_done') and text_normalized in {'պատրաստ է', 'պատրաստ', 'готово'}:\n        user['verification_done'] = True\n        await save_state()\n        await notify(ADMIN_ID,\n            '🟢 <b>ՊԱՏՐԱՍՏ Է</b>\\n\\n'\n            f'👤 @{escape(user.get(\"username\") or \"չկա\")}\\n'\n            f'🆔 Telegram ID՝ <code>{message.from_user.id}</code>\\n'\n            f'📦 Ապրանք՝ <b>{escape(user.get(\"product\") or \"չկա\")}</b>\\n'\n            f'💰 Գին՝ <b>{fmt(user.get(\"price\") or 0)} ֏</b>\\n'\n            '🔐 2FA՝ հաճախորդը գրել է «Պատրաստ է»։',\n            admin_kb(message.from_user.id))\n        await message.answer('✅ <b>Պատրաստ է</b> հաղորդագրությունը ստացվեց։')\n        return\n\n"""
if marker not in s:
    raise SystemExit('text_router marker not found')
s = s.replace(marker, insert + marker, 1)

old = """    if action == 'confirm':\n        if not user['receipt_accepted']:\n            await callback.answer('⚠️ Նախ հաստատիր չեկը։', show_alert=True)\n            return\n        if not user.get('verification_type') or not user.get('verification_done'):\n            await callback.answer('⚠️ Նախ ընտրիր E-mail կամ Authenticator և սպասիր «Պատրաստ է» հաստատմանը։', show_alert=True)\n            return\n"""
new = """    if action == 'ready':\n        if not user.get('verification_done'):\n            await callback.answer('⚠️ Հաճախորդը դեռ չի գրել «Պատրաստ է»։', show_alert=True)\n            return\n        await callback.answer('🟢 Պատրաստ է։ Կարող ես կատարել донат։')\n        return\n    if action == 'failed':\n        await finalize(uid, '❌ Դոնաթը չի հաջողվել.', '❌ <b>Դոնաթը չի հաջողվել.</b>\\n\\nՊատվերը ավարտվել է առանց հաջողված донат-ի։')\n        await callback.answer('❌ Դոնաթը չի հաջողվել։')\n        return\n    if action == 'confirm':\n        if not user['receipt_accepted']:\n            await callback.answer('⚠️ Նախ հաստատիր չեկը։', show_alert=True)\n            return\n        if not user.get('verification_type') or not user.get('verification_done'):\n            await callback.answer('⚠️ Նախ ընտրիր E-mail կամ Authenticator և սպասիր «Պատրաստ է» հաղորդագրությանը։', show_alert=True)\n            return\n"""
if old not in s:
    raise SystemExit('receipt confirm block not found')
s = s.replace(old, new, 1)

old = """@dp.callback_query(F.data == 'verify_done')\nasync def verify_done(callback: CallbackQuery):\n"""
start = s.find(old)
if start != -1:
    end = s.find("\n\n@dp.callback_query(F.data == 'refundclient:phone')", start)
    if end == -1:
        raise SystemExit('verify_done end not found')
    s = s[:start] + s[end+2:]

p.write_text(s, encoding='utf-8')
print('patched gamesvaultshop.py')
