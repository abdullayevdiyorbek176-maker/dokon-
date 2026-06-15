from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from datetime import date

from bot.states import ExpenseSt
from bot.keyboards.menus import expenses_kb, cancel_kb, expense_categories_kb
from bot.database.connection import get_pool
from bot.utils.amount_parser import parse_amount, fmt_som

router = Router()


@router.message(F.text == "💸 Xarajatlar")
async def expenses_menu(message: Message, state: FSMContext, shop_id: int = None):
    if shop_id is None:
        await message.answer("❌ Avval kiring: /start")
        return
    await state.clear()
    await message.answer("💸 <b>Xarajatlar</b>", parse_mode="HTML", reply_markup=expenses_kb())


@router.message(F.text == "➕ Xarajat qo'shish")
async def expense_add_start(message: Message, state: FSMContext, shop_id: int = None):
    if shop_id is None:
        return
    await state.set_state(ExpenseSt.selecting_category)
    await message.answer("📂 Xarajat turini tanlang:", reply_markup=expense_categories_kb())


CATS = ["Ijara", "Maosh", "Transport", "Kommunal", "Reklama", "Ta'mirlash", "Boshqa"]


@router.message(ExpenseSt.selecting_category)
async def expense_category(message: Message, state: FSMContext, use_usd: bool = True):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("💸 Xarajatlar", reply_markup=expenses_kb())
        return
    if message.text not in CATS:
        await message.answer("⚠️ Ro'yxatdan tanlang:")
        return
    await state.update_data(category=message.text, use_usd=use_usd)
    await message.answer(
        "💰 Miqdor (so'm)\n<i>Masalan: 50ming yoki 50000</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )
    await state.set_state(ExpenseSt.entering_amount_som)


@router.message(ExpenseSt.entering_amount_som)
async def expense_amount_som(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("💸 Xarajatlar", reply_markup=expenses_kb())
        return
    amount, _ = parse_amount(message.text)
    if amount is None or amount < 0:
        await message.answer("⚠️ Musbat raqam kiriting:")
        return
    await state.update_data(amount_som=amount)
    data = await state.get_data()
    if data.get("use_usd", True):
        await message.answer("💵 Dollar miqdori (0=yo'q):", reply_markup=cancel_kb())
        await state.set_state(ExpenseSt.entering_amount_usd)
    else:
        await state.update_data(amount_usd=0)
        await message.answer("📝 Izoh (- yozing o'tkazish uchun):", reply_markup=cancel_kb())
        await state.set_state(ExpenseSt.entering_description)


@router.message(ExpenseSt.entering_amount_usd)
async def expense_amount_usd(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("💸 Xarajatlar", reply_markup=expenses_kb())
        return
    amount_usd, _ = parse_amount(message.text)
    if amount_usd is None:
        amount_usd = 0.0
    await state.update_data(amount_usd=amount_usd)
    await message.answer("📝 Izoh (- yozing o'tkazish uchun):", reply_markup=cancel_kb())
    await state.set_state(ExpenseSt.entering_description)


@router.message(ExpenseSt.entering_description)
async def expense_description(message: Message, state: FSMContext, shop_id: int = None):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("💸 Xarajatlar", reply_markup=expenses_kb())
        return
    desc = None if message.text.strip() == "-" else message.text.strip()
    data = await state.get_data()
    amount_som = data["amount_som"]
    amount_usd = data.get("amount_usd", 0)
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """INSERT INTO expenses (shop_id, category, amount_som, amount_usd, description, created_by)
                   VALUES ($1,$2,$3,$4,$5,$6)""",
                shop_id, data["category"], amount_som, amount_usd, desc, message.from_user.id
            )
            # Kassadan chiqarish (naxt)
            await conn.execute(
                "INSERT INTO kassa (shop_id) VALUES ($1) ON CONFLICT (shop_id) DO NOTHING",
                shop_id
            )
            if amount_som > 0:
                await conn.execute(
                    "UPDATE kassa SET naxt_som=GREATEST(0, naxt_som-$1), updated_at=NOW() WHERE shop_id=$2",
                    amount_som, shop_id
                )
                await conn.execute(
                    """INSERT INTO kassa_movements
                       (shop_id, movement_type, method, amount_som, note, created_by)
                       VALUES ($1,'expense','naxt',$2,$3,$4)""",
                    shop_id, amount_som, f"{data['category']}" + (f": {desc}" if desc else ""),
                    message.from_user.id
                )
    await state.clear()
    txt = (
        f"✅ <b>Xarajat saqlandi!</b>\n"
        f"📂 {data['category']}\n"
        f"💰 {fmt_som(amount_som)} so'm"
    )
    if amount_usd:
        txt += f" | {amount_usd:.2f}$"
    if desc:
        txt += f"\n📝 {desc}"
    await message.answer(txt, parse_mode="HTML", reply_markup=expenses_kb())


@router.message(F.text == "📋 Xarajatlar tarixi")
async def expenses_history(message: Message, shop_id: int = None):
    if shop_id is None:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT category, amount_som, amount_usd, description, date
               FROM expenses WHERE shop_id=$1 ORDER BY created_at DESC LIMIT 30""",
            shop_id
        )
        total = await conn.fetchrow(
            "SELECT COALESCE(SUM(amount_som),0) as s, COALESCE(SUM(amount_usd),0) as u FROM expenses WHERE shop_id=$1",
            shop_id
        )
    if not rows:
        await message.answer("📭 Xarajat yo'q.")
        return
    text = "💸 <b>So'nggi 30 xarajat:</b>\n\n"
    for r in rows:
        text += f"📅 {r['date']} | {r['category']}\n   {fmt_som(float(r['amount_som']))} so'm"
        if r["amount_usd"]:
            text += f" | {r['amount_usd']:.2f}$"
        if r["description"]:
            text += f" — {r['description']}"
        text += "\n"
    text += f"\n📊 <b>Jami: {fmt_som(float(total['s']))} so'm"
    if total["u"]:
        text += f" | {float(total['u']):.2f}$"
    text += "</b>"
    for chunk in _split(text):
        await message.answer(chunk, parse_mode="HTML")


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
