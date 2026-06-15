from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from datetime import date

from bot.states import KassaSt
from bot.keyboards.menus import kassa_kb, cancel_kb, main_kb
from bot.database.connection import get_pool
from bot.utils.amount_parser import parse_amount, fmt_som

router = Router()


async def _ensure_kassa(conn, shop_id: int):
    await conn.execute(
        "INSERT INTO kassa (shop_id) VALUES ($1) ON CONFLICT (shop_id) DO NOTHING",
        shop_id
    )


async def kassa_balance(conn, shop_id: int) -> dict:
    await _ensure_kassa(conn, shop_id)
    row = await conn.fetchrow("SELECT naxt_som, karta_som FROM kassa WHERE shop_id=$1", shop_id)
    naxt = float(row["naxt_som"])
    karta = float(row["karta_som"])
    return {"naxt": naxt, "karta": karta, "total": naxt + karta}


@router.message(F.text == "🏦 Kassa")
async def kassa_menu(message: Message, state: FSMContext,
                     shop_id: int = None, role: str = None):
    if shop_id is None:
        await message.answer("❌ Avval kiring: /start")
        return
    if role != "boss":
        await message.answer("🚫 Faqat raxbar uchun!")
        return
    await state.clear()
    await message.answer("🏦 <b>Kassa</b>", parse_mode="HTML", reply_markup=kassa_kb())


@router.message(F.text == "💰 Kassa holati")
async def kassa_status(message: Message, shop_id: int = None, role: str = None):
    if shop_id is None or role != "boss":
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        bal = await kassa_balance(conn, shop_id)
        today = date.today()
        inc = await conn.fetchrow(
            """SELECT
               COALESCE(SUM(CASE WHEN method='naxt' THEN amount_som ELSE 0 END), 0) as naxt_in,
               COALESCE(SUM(CASE WHEN method='karta' THEN amount_som ELSE 0 END), 0) as karta_in,
               COALESCE(SUM(amount_som), 0) as total_in
               FROM kassa_movements
               WHERE shop_id=$1 AND date=$2 AND movement_type='sale_income'""",
            shop_id, today
        )
        out = await conn.fetchrow(
            """SELECT COALESCE(SUM(amount_som), 0) as total
               FROM kassa_movements
               WHERE shop_id=$1 AND date=$2
               AND movement_type IN ('expense','handover','manual_out')""",
            shop_id, today
        )

    naxt_in = float(inc["naxt_in"])
    karta_in = float(inc["karta_in"])
    total_in = float(inc["total_in"])
    total_out = float(out["total"])
    sof = total_in - total_out

    text = (
        f"🏦 <b>Kassa holati</b>\n\n"
        f"💵 Naqd pul:  <b>{fmt_som(bal['naxt'])} so'm</b>\n"
        f"💳 Karta:     <b>{fmt_som(bal['karta'])} so'm</b>\n"
        f"──────────────────────\n"
        f"💰 Jami:      <b>{fmt_som(bal['total'])} so'm</b>\n\n"
        f"📅 <b>Bugun:</b>\n"
        f"  ✅ Kirim:  {fmt_som(total_in)} so'm"
    )
    if naxt_in or karta_in:
        text += f"\n       (naqd: {fmt_som(naxt_in)}, karta: {fmt_som(karta_in)})"
    text += (
        f"\n  ❌ Chiqim: {fmt_som(total_out)} so'm"
        f"\n  📈 Sof:   <b>{fmt_som(sof)} so'm</b>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=kassa_kb())


# ─── PUL TOPSHIRISH ────────────────────────────────────────────────────────

@router.message(F.text == "💵 Pul topshirish")
async def kassa_handover_start(message: Message, state: FSMContext,
                                shop_id: int = None, role: str = None):
    if shop_id is None or role != "boss":
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        bal = await kassa_balance(conn, shop_id)
    await state.set_state(KassaSt.entering_handover_amount)
    await message.answer(
        f"💵 Kassadagi naqd: <b>{fmt_som(bal['naxt'])} so'm</b>\n\n"
        f"Necha so'm topshiriladi?\n"
        f"<i>Masalan: 50ming yoki 50000</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )


@router.message(KassaSt.entering_handover_amount)
async def kassa_handover_amount(message: Message, state: FSMContext,
                                 shop_id: int = None):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🏦 Kassa", reply_markup=kassa_kb())
        return
    amount, _ = parse_amount(message.text)
    if amount is None or amount <= 0:
        await message.answer("⚠️ To'g'ri summa kiriting (masalan: 50ming yoki 50000):")
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        bal = await kassa_balance(conn, shop_id)
    if amount > bal["naxt"]:
        await message.answer(
            f"⚠️ Kassada faqat {fmt_som(bal['naxt'])} so'm naqd bor!\n"
            f"Kichikroq summa kiriting:"
        )
        return
    await state.update_data(handover_amount=amount)
    await message.answer("👤 Kimga topshirildi (ism yoki izoh):", reply_markup=cancel_kb())
    await state.set_state(KassaSt.entering_handover_recipient)


@router.message(KassaSt.entering_handover_recipient)
async def kassa_handover_recipient(message: Message, state: FSMContext,
                                    shop_id: int = None):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🏦 Kassa", reply_markup=kassa_kb())
        return
    recipient = message.text.strip()
    data = await state.get_data()
    amount = data["handover_amount"]
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "UPDATE kassa SET naxt_som=naxt_som-$1, updated_at=NOW() WHERE shop_id=$2",
                amount, shop_id
            )
            await conn.execute(
                """INSERT INTO kassa_movements
                   (shop_id, movement_type, method, amount_som, recipient, created_by)
                   VALUES ($1,'handover','naxt',$2,$3,$4)""",
                shop_id, amount, recipient, message.from_user.id
            )
    await state.clear()
    await message.answer(
        f"✅ <b>Topshirildi!</b>\n\n"
        f"💵 Miqdor: <b>{fmt_som(amount)} so'm</b>\n"
        f"👤 Kimga:  <b>{recipient}</b>",
        parse_mode="HTML",
        reply_markup=kassa_kb()
    )


# ─── QO'LDA KIRIM / CHIQIM ─────────────────────────────────────────────────

@router.message(F.text == "➕ Qo'lda kirim")
async def kassa_manual_in_start(message: Message, state: FSMContext,
                                 shop_id: int = None, role: str = None):
    if shop_id is None or role != "boss":
        return
    await state.update_data(manual_type="in")
    await state.set_state(KassaSt.entering_manual_amount)
    await message.answer(
        "💰 Kassaga qo'shiladigan summa:\n<i>Masalan: 100ming yoki 100000</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )


@router.message(F.text == "➖ Qo'lda chiqim")
async def kassa_manual_out_start(message: Message, state: FSMContext,
                                  shop_id: int = None, role: str = None):
    if shop_id is None or role != "boss":
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        bal = await kassa_balance(conn, shop_id)
    await state.update_data(manual_type="out")
    await state.set_state(KassaSt.entering_manual_amount)
    await message.answer(
        f"💸 Kassadan chiqariladigan summa\n"
        f"(kassada: {fmt_som(bal['naxt'])} so'm naqd):",
        reply_markup=cancel_kb()
    )


@router.message(KassaSt.entering_manual_amount)
async def kassa_manual_amount(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🏦 Kassa", reply_markup=kassa_kb())
        return
    amount, _ = parse_amount(message.text)
    if amount is None or amount <= 0:
        await message.answer("⚠️ To'g'ri summa kiriting:")
        return
    await state.update_data(manual_amount=amount)
    await message.answer("📝 Izoh (- yozing o'tkazish uchun):", reply_markup=cancel_kb())
    await state.set_state(KassaSt.entering_manual_note)


@router.message(KassaSt.entering_manual_note)
async def kassa_manual_note(message: Message, state: FSMContext, shop_id: int = None):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("🏦 Kassa", reply_markup=kassa_kb())
        return
    note = None if message.text.strip() == "-" else message.text.strip()
    data = await state.get_data()
    amount = data["manual_amount"]
    manual_type = data.get("manual_type", "in")
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _ensure_kassa(conn, shop_id)
        if manual_type == "out":
            bal_row = await conn.fetchrow("SELECT naxt_som FROM kassa WHERE shop_id=$1", shop_id)
            if float(bal_row["naxt_som"]) < amount:
                await state.clear()
                await message.answer(
                    f"⚠️ Kassada faqat {fmt_som(float(bal_row['naxt_som']))} so'm naqd bor!",
                    reply_markup=kassa_kb()
                )
                return
        async with conn.transaction():
            if manual_type == "in":
                await conn.execute(
                    "UPDATE kassa SET naxt_som=naxt_som+$1, updated_at=NOW() WHERE shop_id=$2",
                    amount, shop_id
                )
                mv_type = "manual_in"
            else:
                await conn.execute(
                    "UPDATE kassa SET naxt_som=naxt_som-$1, updated_at=NOW() WHERE shop_id=$2",
                    amount, shop_id
                )
                mv_type = "manual_out"
            await conn.execute(
                """INSERT INTO kassa_movements
                   (shop_id, movement_type, method, amount_som, note, created_by)
                   VALUES ($1,$2,'naxt',$3,$4,$5)""",
                shop_id, mv_type, amount, note, message.from_user.id
            )
    await state.clear()
    sign = "+" if manual_type == "in" else "-"
    icon = "✅" if manual_type == "in" else "💸"
    await message.answer(
        f"{icon} <b>Kassa yangilandi!</b>\n\n"
        f"💰 {sign}{fmt_som(amount)} so'm",
        parse_mode="HTML",
        reply_markup=kassa_kb()
    )


# ─── HARAKATLAR TARIXI ─────────────────────────────────────────────────────

@router.message(F.text == "📋 Harakatlar tarixi")
async def kassa_history(message: Message, shop_id: int = None, role: str = None):
    if shop_id is None or role != "boss":
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT movement_type, method, amount_som, note, recipient, date
               FROM kassa_movements WHERE shop_id=$1
               ORDER BY created_at DESC LIMIT 30""",
            shop_id
        )
    if not rows:
        await message.answer("📭 Harakatlar tarixi yo'q.", reply_markup=kassa_kb())
        return
    _icons = {
        "sale_income": "💰 Sotuv",
        "expense": "💸 Xarajat",
        "handover": "🤝 Topshirish",
        "manual_in": "➕ Kirim",
        "manual_out": "➖ Chiqim",
    }
    text = "📋 <b>So'nggi 30 harakat:</b>\n\n"
    for r in rows:
        label = _icons.get(r["movement_type"], r["movement_type"])
        method = "naqd" if r["method"] == "naxt" else "karta"
        text += f"{label} ({method}) — {r['date']}\n"
        text += f"   {fmt_som(float(r['amount_som']))} so'm"
        if r["recipient"]:
            text += f" → {r['recipient']}"
        if r["note"]:
            text += f" | {r['note']}"
        text += "\n\n"
    for chunk in _split(text):
        await message.answer(chunk, parse_mode="HTML", reply_markup=kassa_kb())


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
