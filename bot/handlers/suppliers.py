from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.states import SupplierSt
from bot.keyboards.menus import suppliers_kb, cancel_kb, inline_items_kb
from bot.database.connection import get_pool

router = Router()


@router.message(F.text == "🏭 Taminotchilar")
async def suppliers_menu(message: Message, state: FSMContext, shop_id: int = None, role: str = None):
    if shop_id is None:
        await message.answer("❌ Avval kiring: /start")
        return
    await state.clear()
    await message.answer("🏭 <b>Taminotchilar</b>", parse_mode="HTML", reply_markup=suppliers_kb())


@router.message(F.text == "📋 Taminotchilar ro'yxati")
async def suppliers_list(message: Message, shop_id: int = None):
    if shop_id is None:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, phone, debt_som, debt_usd FROM suppliers WHERE shop_id=$1 ORDER BY name",
            shop_id
        )
    if not rows:
        await message.answer("📭 Taminotchi yo'q. ➕ Qo'shing.")
        return
    text = f"🏭 <b>Taminotchilar ({len(rows)} ta):</b>\n\n"
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
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "💳 Taminotchi qarzlar")
async def suppliers_debts(message: Message, shop_id: int = None):
    if shop_id is None:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT name, phone, debt_som, debt_usd FROM suppliers
               WHERE shop_id=$1 AND (debt_som > 0 OR debt_usd > 0) ORDER BY debt_som DESC""",
            shop_id
        )
        total_som = await conn.fetchval(
            "SELECT COALESCE(SUM(debt_som),0) FROM suppliers WHERE shop_id=$1", shop_id
        )
        total_usd = await conn.fetchval(
            "SELECT COALESCE(SUM(debt_usd),0) FROM suppliers WHERE shop_id=$1", shop_id
        )
    if not rows:
        await message.answer("✅ Taminotchilarga qarz yo'q!")
        return
    text = "💸 <b>Taminotchi qarzlar:</b>\n\n"
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


@router.message(F.text == "➕ Yangi taminotchi")
async def supplier_add_start(message: Message, state: FSMContext, shop_id: int = None):
    if shop_id is None:
        return
    await state.set_state(SupplierSt.entering_name)
    await message.answer("🏭 Taminotchi nomini kiriting:", reply_markup=cancel_kb())


@router.message(SupplierSt.entering_name)
async def supplier_add_name(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🏭 Taminotchilar", reply_markup=suppliers_kb())
        return
    if len(message.text.strip()) < 2:
        await message.answer("⚠️ Nom kamida 2 harf:")
        return
    await state.update_data(name=message.text.strip())
    await message.answer("📞 Telefon raqami (ixtiyoriy, 0=o'tkazish):", reply_markup=cancel_kb())
    await state.set_state(SupplierSt.entering_phone)


@router.message(SupplierSt.entering_phone)
async def supplier_add_phone(message: Message, state: FSMContext, shop_id: int = None):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🏭 Taminotchilar", reply_markup=suppliers_kb())
        return
    phone = None if message.text.strip() in ("0", "-") else message.text.strip()
    data = await state.get_data()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO suppliers (shop_id, name, phone) VALUES ($1,$2,$3)",
            shop_id, data["name"], phone
        )
    await state.clear()
    await message.answer(
        f"✅ <b>{data['name']}</b> qo'shildi!", parse_mode="HTML", reply_markup=suppliers_kb()
    )


@router.message(F.text == "💳 Taminotchi qarz to'lash")
async def supplier_select_for_debt(message: Message, state: FSMContext, shop_id: int = None):
    if shop_id is None:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, name, debt_som FROM suppliers
               WHERE shop_id=$1 AND debt_som > 0 ORDER BY name""",
            shop_id
        )
    if not rows:
        await message.answer("✅ Qarzli taminotchi yo'q!")
        return
    items = [{"id": r["id"], "label": f"{r['name']} — {r['debt_som']:,.0f} so'm"} for r in rows]
    await message.answer("🏭 Taminotchini tanlang:", reply_markup=inline_items_kb(items, "pay_sup"))
    await state.set_state(SupplierSt.selected)


@router.callback_query(SupplierSt.selected, F.data.startswith("pay_sup:"))
async def supplier_debt_pay_select(cb: CallbackQuery, state: FSMContext):
    sup_id = int(cb.data.split(":")[1])
    await state.update_data(sup_id=sup_id)
    await cb.message.edit_reply_markup()
    await cb.message.answer("💰 To'lov miqdori (so'm):", reply_markup=cancel_kb())
    await state.set_state(SupplierSt.paying_debt_som)
    await cb.answer()


@router.message(SupplierSt.paying_debt_som)


@router.message(SupplierSt.paying_debt_som)
async def supplier_pay_debt_som(message: Message, state: FSMContext, shop_id: int = None):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🏭 Taminotchilar", reply_markup=suppliers_kb())
        return
    try:
        amount = float(message.text.replace(",", "").replace(" ", ""))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Musbat raqam:")
        return
    data = await state.get_data()
    sup_id = data.get("sup_id")
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE suppliers SET debt_som=GREATEST(0, debt_som-$1) WHERE id=$2 AND shop_id=$3",
            amount, sup_id, shop_id
        )
        await conn.execute(
            """INSERT INTO debt_payments (shop_id, payment_type, entity_id, amount_som)
               VALUES ($1,'supplier',$2,$3)""",
            shop_id, sup_id, amount
        )
    await state.clear()
    await message.answer(
        f"✅ {amount:,.0f} so'm to'landi!", reply_markup=suppliers_kb()
    )
