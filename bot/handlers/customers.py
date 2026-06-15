from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.states import CustomerSt
from bot.keyboards.menus import customers_kb, cancel_kb, inline_items_kb
from bot.database.connection import get_pool

router = Router()


@router.message(F.text == "👥 Mijozlar")
async def customers_menu(message: Message, state: FSMContext, shop_id: int = None):
    if shop_id is None:
        await message.answer("❌ Avval kiring: /start")
        return
    await state.clear()
    await message.answer("👥 <b>Mijozlar</b>", parse_mode="HTML", reply_markup=customers_kb())


@router.message(F.text == "📋 Mijozlar ro'yxati")
async def customers_list(message: Message, shop_id: int = None):
    if shop_id is None:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, phone, debt_som, debt_usd FROM customers WHERE shop_id=$1 ORDER BY name",
            shop_id
        )
    if not rows:
        await message.answer("📭 Mijoz yo'q. ➕ Qo'shing.")
        return
    text = f"👥 <b>Mijozlar ({len(rows)} ta):</b>\n\n"
    for r in rows:
        debt_mark = " ⚠️" if r["debt_som"] > 0 or r["debt_usd"] > 0 else ""
        text += f"• <b>{r['name']}</b>{debt_mark}"
        if r["phone"]:
            text += f" | 📞 {r['phone']}"
        if r["debt_som"] > 0:
            text += f"\n  💸 Qarz: {r['debt_som']:,.0f} so'm"
        if r["debt_usd"] > 0:
            text += f" | {r['debt_usd']:.2f}$"
        text += "\n"
    for chunk in _split(text):
        await message.answer(chunk, parse_mode="HTML")


@router.message(F.text == "💳 Qarz to'lash (mijoz)")
async def customer_select_for_debt(message: Message, state: FSMContext, shop_id: int = None):
    if shop_id is None:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, name, debt_som FROM customers
               WHERE shop_id=$1 AND debt_som > 0 ORDER BY name""",
            shop_id
        )
    if not rows:
        await message.answer("✅ Qarzli mijoz yo'q!")
        return
    items = [{"id": r["id"], "label": f"{r['name']} — {r['debt_som']:,.0f} so'm"} for r in rows]
    await message.answer("👤 Mijozni tanlang:", reply_markup=inline_items_kb(items, "pay_cust"))
    await state.set_state(CustomerSt.selected)


@router.callback_query(CustomerSt.selected, F.data.startswith("pay_cust:"))
async def customer_debt_pay_select(cb: CallbackQuery, state: FSMContext):
    cust_id = int(cb.data.split(":")[1])
    await state.update_data(cust_id=cust_id)
    await cb.message.edit_reply_markup()
    await cb.message.answer("💰 To'lov miqdori (so'm):", reply_markup=cancel_kb())
    await state.set_state(CustomerSt.paying_debt_som)
    await cb.answer()


@router.message(F.text == "💳 Qarzlar")
async def customers_debts(message: Message, shop_id: int = None):
    if shop_id is None:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT name, phone, debt_som, debt_usd FROM customers
               WHERE shop_id=$1 AND (debt_som > 0 OR debt_usd > 0) ORDER BY debt_som DESC""",
            shop_id
        )
        total_som = await conn.fetchval(
            "SELECT COALESCE(SUM(debt_som),0) FROM customers WHERE shop_id=$1", shop_id
        )
        total_usd = await conn.fetchval(
            "SELECT COALESCE(SUM(debt_usd),0) FROM customers WHERE shop_id=$1", shop_id
        )
    if not rows:
        await message.answer("✅ Mijoz qarzlari yo'q!")
        return
    text = "💸 <b>Mijoz qarzlari:</b>\n\n"
    for r in rows:
        text += f"• <b>{r['name']}</b>"
        if r["phone"]:
            text += f" ({r['phone']})"
        text += f"\n  {r['debt_som']:,.0f} so'm"
        if r["debt_usd"] > 0:
            text += f" | {r['debt_usd']:.2f}$"
        text += "\n"
    text += f"\n📊 <b>Jami: {total_som:,.0f} so'm"
    if total_usd:
        text += f" | {total_usd:.2f}$"
    text += "</b>"
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "➕ Yangi mijoz")
async def customer_add_start(message: Message, state: FSMContext, shop_id: int = None):
    if shop_id is None:
        return
    await state.set_state(CustomerSt.entering_name)
    await message.answer("👤 Mijoz ismini kiriting:", reply_markup=cancel_kb())


@router.message(CustomerSt.entering_name)
async def customer_add_name(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("👥 Mijozlar", reply_markup=customers_kb())
        return
    if len(message.text.strip()) < 2:
        await message.answer("⚠️ Ism kamida 2 harf:")
        return
    await state.update_data(name=message.text.strip())
    await message.answer("📞 Telefon raqami (ixtiyoriy, 0=o'tkazib yuborish):", reply_markup=cancel_kb())
    await state.set_state(CustomerSt.entering_phone)


@router.message(CustomerSt.entering_phone)
async def customer_add_phone(message: Message, state: FSMContext, shop_id: int = None):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("👥 Mijozlar", reply_markup=customers_kb())
        return
    phone = None if message.text.strip() in ("0", "-") else message.text.strip()
    data = await state.get_data()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO customers (shop_id, name, phone) VALUES ($1,$2,$3)",
            shop_id, data["name"], phone
        )
    await state.clear()
    await message.answer(
        f"✅ <b>{data['name']}</b> qo'shildi!", parse_mode="HTML", reply_markup=customers_kb()
    )


@router.message(CustomerSt.selected, F.text.startswith("💳 Qarz to'lash"))
async def customer_pay_debt_start(message: Message, state: FSMContext):
    await message.answer("💰 To'lov miqdori (so'm):", reply_markup=cancel_kb())
    await state.set_state(CustomerSt.paying_debt_som)


@router.message(CustomerSt.paying_debt_som)
async def customer_pay_debt_som(message: Message, state: FSMContext, shop_id: int = None):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("👥 Mijozlar", reply_markup=customers_kb())
        return
    try:
        amount = float(message.text.replace(",", "").replace(" ", ""))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Musbat raqam:")
        return
    data = await state.get_data()
    cust_id = data.get("cust_id")
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE customers SET debt_som=GREATEST(0, debt_som-$1) WHERE id=$2 AND shop_id=$3",
            amount, cust_id, shop_id
        )
        await conn.execute(
            """INSERT INTO debt_payments (shop_id, payment_type, entity_id, amount_som)
               VALUES ($1,'customer',$2,$3)""",
            shop_id, cust_id, amount
        )
    await state.clear()
    await message.answer(
        f"✅ {amount:,.0f} so'm qarz to'landi!", reply_markup=customers_kb()
    )


# ─── MIJOZ TANLASH (sotuv paytida) ────────────────────────────────────────
async def select_or_create_customer(message, state, shop_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, phone FROM customers WHERE shop_id=$1 ORDER BY name", shop_id
        )
    items = [{"id": r["id"], "label": f"{r['name']} ({r['phone'] or '—'})"} for r in rows]
    return items


def _split(text: str, limit: int = 4000) -> list:
    chunks = []
    while len(text) > limit:
        pos = text.rfind("\n", 0, limit)
        if pos == -1:
            pos = limit
        chunks.append(text[:pos])
        text = text[pos:]
    if text:
        chunks.append(text)
    return chunks
