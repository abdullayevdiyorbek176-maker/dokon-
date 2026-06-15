from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from bot.states import SettingsSt
from bot.keyboards.menus import settings_kb, cancel_kb, main_kb
from bot.database.connection import get_pool
from bot.middlewares.auth_middleware import user_sessions

router = Router()


def _boss_only(role: str) -> bool:
    return role != "boss"


def _currency_kb(use_som: bool, use_usd: bool) -> InlineKeyboardMarkup:
    som_icon = "✅ Yoqiq" if use_som else "❌ O'chiq"
    usd_icon = "✅ Yoqiq" if use_usd else "❌ O'chiq"
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"💴 So'm: {som_icon}", callback_data="toggle_som"),
        InlineKeyboardButton(text=f"💵 Dollar: {usd_icon}", callback_data="toggle_usd"),
    ]])


@router.message(F.text == "⚙️ Sozlamalar")
async def settings_menu(message: Message, state: FSMContext,
                        shop_id: int = None, role: str = None,
                        use_som: bool = True, use_usd: bool = True):
    if shop_id is None:
        await message.answer("❌ Avval kiring: /start")
        return
    if _boss_only(role):
        await message.answer("🚫 Faqat raxbar uchun!")
        return
    await state.clear()
    pool = await get_pool()
    async with pool.acquire() as conn:
        shop = await conn.fetchrow("SELECT name FROM shops WHERE id=$1", shop_id)
        rate_row = await conn.fetchrow(
            "SELECT rate FROM usd_rates WHERE shop_id=$1 ORDER BY set_at DESC LIMIT 1", shop_id
        )
    from bot.config import USD_RATE
    rate = float(rate_row["rate"]) if rate_row else USD_RATE
    await message.answer(
        f"⚙️ <b>Sozlamalar</b>\n\n"
        f"🏪 Dokon: <b>{shop['name']}</b>\n"
        f"💱 Dollar kursi: <b>{rate:,.0f} so'm</b>\n\n"
        "💱 <b>Valyuta sozlamalari:</b>",
        parse_mode="HTML",
        reply_markup=settings_kb(),
    )
    await message.answer(
        "Qaysi valyutalarni ishlatmoqchisiz?",
        reply_markup=_currency_kb(use_som, use_usd),
    )


@router.callback_query(F.data.in_({"toggle_som", "toggle_usd"}))
async def toggle_currency(cb: CallbackQuery,
                          shop_id: int = None, role: str = None,
                          use_som: bool = True, use_usd: bool = True):
    if _boss_only(role):
        await cb.answer("🚫 Faqat raxbar!", show_alert=True)
        return

    if cb.data == "toggle_som":
        new_val = not use_som
        if not new_val and not use_usd:
            await cb.answer("⚠️ Kamida bitta valyuta yoqiq bo'lishi kerak!", show_alert=True)
            return
        field = "use_som"
        label = "So'm"
    else:
        new_val = not use_usd
        if not new_val and not use_som:
            await cb.answer("⚠️ Kamida bitta valyuta yoqiq bo'lishi kerak!", show_alert=True)
            return
        field = "use_usd"
        label = "Dollar"

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(f"UPDATE shops SET {field}=$1 WHERE id=$2", new_val, shop_id)

    # barcha sessiyalardagi xodimlar uchun ham yangilash
    for uid, sess in user_sessions.items():
        if sess.get("shop_id") == shop_id:
            user_sessions[uid][field] = new_val

    sess = user_sessions.get(cb.from_user.id, {})
    new_use_som = sess.get("use_som", True)
    new_use_usd = sess.get("use_usd", True)

    await cb.message.edit_reply_markup(reply_markup=_currency_kb(new_use_som, new_use_usd))
    status = "✅ Yoqildi" if new_val else "❌ O'chirildi"
    await cb.answer(f"{label}: {status}", show_alert=False)


@router.message(F.text == "💱 Dollar kursi")
async def settings_usd_start(message: Message, state: FSMContext,
                              shop_id: int = None, role: str = None):
    if shop_id is None or _boss_only(role):
        return
    await state.set_state(SettingsSt.entering_usd_rate)
    await message.answer("💱 Yangi dollar kursini kiriting (so'm):", reply_markup=cancel_kb())


@router.message(SettingsSt.entering_usd_rate)
async def settings_usd_set(message: Message, state: FSMContext, shop_id: int = None):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("⚙️ Sozlamalar", reply_markup=settings_kb())
        return
    try:
        rate = float(message.text.replace(",", "").replace(" ", ""))
        if rate <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Musbat raqam kiriting:")
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO usd_rates (shop_id, rate) VALUES ($1,$2)", shop_id, rate
        )
    await state.clear()
    await message.answer(
        f"✅ Dollar kursi: <b>{rate:,.0f} so'm</b>",
        parse_mode="HTML",
        reply_markup=settings_kb()
    )


@router.message(F.text == "🏪 Dokon nomi")
async def settings_shop_name_start(message: Message, state: FSMContext,
                                   shop_id: int = None, role: str = None):
    if shop_id is None or _boss_only(role):
        return
    await state.set_state(SettingsSt.main)
    await message.answer("🏪 Yangi dokon nomini kiriting:", reply_markup=cancel_kb())


@router.message(SettingsSt.main)
async def settings_shop_name_set(message: Message, state: FSMContext,
                                 shop_id: int = None):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("⚙️ Sozlamalar", reply_markup=settings_kb())
        return
    if len(message.text.strip()) < 2:
        await message.answer("⚠️ Nom kamida 2 harf:")
        return
    new_name = message.text.strip()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE shops SET name=$1 WHERE id=$2", new_name, shop_id)
    for uid, sess in user_sessions.items():
        if sess.get("shop_id") == shop_id:
            user_sessions[uid]["shop_name"] = new_name
    await state.clear()
    await message.answer(
        f"✅ Dokon nomi: <b>{new_name}</b>",
        parse_mode="HTML",
        reply_markup=settings_kb()
    )


@router.message(F.text == "🔑 Parol o'zgartirish")
async def settings_password_info(message: Message, shop_id: int = None, role: str = None):
    if shop_id is None or _boss_only(role):
        return
    await message.answer(
        "🔑 Parolni o'zgartirish uchun @diyor_bek700 ga murojaat qiling.\n"
        "📱 Tel: +998947677000",
        reply_markup=settings_kb()
    )


@router.message(F.text == "❓ Yordam")
async def help_handler(message: Message):
    await message.answer(
        "❓ <b>Yordam</b>\n\n"
        "Bu bot dokon uchun hisob-kitob tizimi.\n\n"
        "📞 Muammo bo'lsa:\n"
        "🔗 @diyor_bek700\n"
        "📱 +998947677000",
        parse_mode="HTML"
    )
