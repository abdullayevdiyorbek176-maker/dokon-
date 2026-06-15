from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import date

from bot.states import PurchaseSt
from bot.keyboards.menus import purchases_kb, cancel_kb, back_cancel_kb, main_kb, inline_items_kb, yes_no_kb
from bot.database.connection import get_pool
from bot.utils.amount_parser import parse_amount, fmt_som

router = Router()


@router.message(F.text == "📥 Kirim")
async def purchases_menu(message: Message, state: FSMContext, shop_id: int = None, role: str = None):
    if shop_id is None:
        await message.answer("❌ Avval kiring: /start")
        return
    await state.clear()
    await message.answer("📥 <b>Kirim bo'limi</b>", parse_mode="HTML", reply_markup=purchases_kb())


# ─── YANGI KIRIM ──────────────────────────────────────────────────────────
@router.message(F.text == "➕ Yangi kirim")
async def purchase_new_start(message: Message, state: FSMContext,
                              shop_id: int = None,
                              use_som: bool = True, use_usd: bool = True):
    if shop_id is None:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        suppliers = await conn.fetch(
            "SELECT id, name, phone FROM suppliers WHERE shop_id=$1 ORDER BY name", shop_id
        )
    items = [{"id": s["id"], "label": f"{s['name']} ({s['phone'] or 'tel yo\'q'})"} for s in suppliers]
    items.append({"id": 0, "label": "➕ Yangi taminotchi"})
    items.append({"id": -1, "label": "🔄 Taminotchisiz"})
    await state.update_data(items=[], total_som=0.0, total_usd=0.0,
                            use_som=use_som, use_usd=use_usd)
    await message.answer("🏭 Taminotchini tanlang:", reply_markup=inline_items_kb(items, "pur_sup"))
    await state.set_state(PurchaseSt.selecting_supplier)


@router.callback_query(PurchaseSt.selecting_supplier, F.data.startswith("pur_sup:"))
async def purchase_supplier_selected(cb: CallbackQuery, state: FSMContext, shop_id: int = None):
    sup_id = int(cb.data.split(":")[1])
    await state.update_data(supplier_id=sup_id if sup_id > 0 else None)
    await cb.message.edit_reply_markup()
    if sup_id == 0:
        await cb.message.answer(
            "🏭 Yangi taminotchi nomi:", reply_markup=cancel_kb()
        )
        await state.set_state(None)
        await cb.answer()
        return
    await _ask_product(cb.message, state, shop_id)
    await cb.answer()


async def _ask_product(message, state, shop_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        products = await conn.fetch(
            "SELECT id, name, unit FROM products WHERE shop_id=$1 AND is_active=TRUE ORDER BY name", shop_id
        )
    items = [{"id": p["id"], "label": f"{p['name']} ({p['unit']})"} for p in products]
    items.append({"id": -1, "label": "✅ Kirimni yakunlash"})
    data = await state.get_data()
    cart = data.get("items", [])
    cart_text = ""
    if cart:
        cart_text = "\n\n📦 Qo'shilganlar:\n"
        for it in cart:
            cart_text += f"• {it['name']}: {it['qty']:g} × {fmt_som(it['price_som'])} so'm\n"
    await message.answer(
        f"📦 Mahsulot tanlang:{cart_text}",
        reply_markup=inline_items_kb(items, "pur_prod")
    )
    await state.set_state(PurchaseSt.adding_item_product)


@router.callback_query(PurchaseSt.adding_item_product, F.data.startswith("pur_prod:"))
async def purchase_product_selected(cb: CallbackQuery, state: FSMContext, shop_id: int = None):
    prod_id = int(cb.data.split(":")[1])
    if prod_id == -1:
        await cb.message.edit_reply_markup()
        await _purchase_finalize(cb.message, state, shop_id)
        await cb.answer()
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        prod = await conn.fetchrow(
            "SELECT name, unit, buy_price_som, buy_price_usd FROM products WHERE id=$1", prod_id
        )
    await state.update_data(cur_prod_id=prod_id, cur_prod_name=prod["name"],
                             cur_prod_unit=prod["unit"],
                             cur_def_som=float(prod["buy_price_som"]),
                             cur_def_usd=float(prod["buy_price_usd"]))
    await cb.message.edit_reply_markup()
    await cb.message.answer(
        f"📦 <b>{prod['name']}</b>\n"
        f"📏 Miqdor ({prod['unit']}) kiriting:",
        parse_mode="HTML", reply_markup=cancel_kb()
    )
    await state.set_state(PurchaseSt.adding_item_qty)
    await cb.answer()


@router.message(PurchaseSt.adding_item_qty)
async def purchase_qty(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("📥 Kirim", reply_markup=purchases_kb())
        return
    qty, _ = parse_amount(message.text)
    if qty is None or qty <= 0:
        await message.answer("⚠️ Musbat raqam kiriting:")
        return
    data = await state.get_data()
    await state.update_data(cur_qty=qty)
    if data.get("use_som", True):
        def_som = data.get("cur_def_som", 0)
        await message.answer(
            f"💰 Xarid narxi (so'm) — avvalgi: {fmt_som(def_som)}\n0 yozing yoki kiriting:",
            reply_markup=cancel_kb()
        )
        await state.set_state(PurchaseSt.adding_item_price_som)
    else:
        await state.update_data(cur_price_som=0)
        def_usd = data.get("cur_def_usd", 0)
        await message.answer(
            f"💵 Xarid narxi ($) — avvalgi: {def_usd:.2f}\n0 yozing yoki kiriting:",
            reply_markup=cancel_kb()
        )
        await state.set_state(PurchaseSt.adding_item_price_usd)


@router.message(PurchaseSt.adding_item_price_som)
async def purchase_price_som(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("📥 Kirim", reply_markup=purchases_kb())
        return
    price, _ = parse_amount(message.text)
    if price is None:
        await message.answer("⚠️ Raqam kiriting:")
        return
    data = await state.get_data()
    if price == 0:
        price = data.get("cur_def_som", 0)
    await state.update_data(cur_price_som=price)
    if data.get("use_usd", True):
        def_usd = data.get("cur_def_usd", 0)
        await message.answer(
            f"💵 Xarid narxi ($) — avvalgi: {def_usd:.2f}\n0 yozing yoki kiriting:",
            reply_markup=cancel_kb()
        )
        await state.set_state(PurchaseSt.adding_item_price_usd)
    else:
        await state.update_data(cur_price_usd=0)
        await _purchase_add_to_cart(message, state)


@router.message(PurchaseSt.adding_item_price_usd)
async def purchase_price_usd(message: Message, state: FSMContext, shop_id: int = None):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("📥 Kirim", reply_markup=purchases_kb())
        return
    price_usd, _ = parse_amount(message.text)
    if price_usd is None:
        await message.answer("⚠️ Raqam kiriting:")
        return
    data = await state.get_data()
    if price_usd == 0:
        price_usd = data.get("cur_def_usd", 0)
    await state.update_data(cur_price_usd=price_usd)
    await _purchase_add_to_cart(message, state)


async def _purchase_add_to_cart(message, state):
    data = await state.get_data()
    shop_id = None
    from bot.middlewares.auth_middleware import user_sessions
    sess = user_sessions.get(message.from_user.id, {})
    shop_id = sess.get("shop_id")
    item = {
        "prod_id": data["cur_prod_id"],
        "name": data["cur_prod_name"],
        "unit": data["cur_prod_unit"],
        "qty": data["cur_qty"],
        "price_som": data.get("cur_price_som", 0),
        "price_usd": data.get("cur_price_usd", 0),
    }
    cart = data.get("items", [])
    cart.append(item)
    total_som = data.get("total_som", 0) + item["qty"] * item["price_som"]
    total_usd = data.get("total_usd", 0) + item["qty"] * item["price_usd"]
    await state.update_data(items=cart, total_som=total_som, total_usd=total_usd)
    use_som = data.get("use_som", True)
    price_txt = f"{fmt_som(item['price_som'])} so'm" if use_som else f"{item['price_usd']:.2f}$"
    await message.answer(
        f"✅ <b>{item['name']}</b>: {item['qty']:g} × {price_txt} qo'shildi",
        parse_mode="HTML"
    )
    await _ask_product(message, state, shop_id)


async def _purchase_finalize(message, state, shop_id):
    data = await state.get_data()
    cart = data.get("items", [])
    if not cart:
        await message.answer("⚠️ Hech narsa qo'shilmagan!", reply_markup=purchases_kb())
        await state.clear()
        return
    total_som = data.get("total_som", 0)
    total_usd = data.get("total_usd", 0)
    text = f"📋 <b>Kirim xulosasi:</b>\n\n"
    for it in cart:
        text += (
            f"• {it['name']}: {it['qty']:g} × {fmt_som(it['price_som'])} = "
            f"{fmt_som(it['qty']*it['price_som'])} so'm\n"
        )
    text += f"\n💰 <b>Jami: {fmt_som(total_som)} so'm"
    if total_usd:
        text += f" | {total_usd:.2f}$"
    text += "</b>\n\n💳 To'lov (so'm, 0=qarz):"
    await message.answer(text, parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(PurchaseSt.entering_paid_som)


@router.message(PurchaseSt.entering_paid_som)
async def purchase_paid(message: Message, state: FSMContext, shop_id: int = None):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("📥 Kirim", reply_markup=purchases_kb())
        return
    paid, _ = parse_amount(message.text)
    if paid is None:
        await message.answer("⚠️ Raqam kiriting:")
        return
    data = await state.get_data()
    cart = data["items"]
    total_som = data["total_som"]
    total_usd = data["total_usd"]
    sup_id = data.get("supplier_id")
    debt = max(0.0, total_som - paid)
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            pur = await conn.fetchrow(
                """INSERT INTO purchases (shop_id, supplier_id, total_som, total_usd, paid_som, created_by)
                   VALUES ($1,$2,$3,$4,$5,$6) RETURNING id""",
                shop_id, sup_id, total_som, total_usd, paid, message.from_user.id
            )
            for it in cart:
                await conn.execute(
                    """INSERT INTO purchase_items (purchase_id, product_id, qty, price_som, price_usd)
                       VALUES ($1,$2,$3,$4,$5)""",
                    pur["id"], it["prod_id"], it["qty"], it["price_som"], it["price_usd"]
                )
                await conn.execute(
                    "UPDATE products SET stock_qty=stock_qty+$1, buy_price_som=$2, buy_price_usd=$3 WHERE id=$4",
                    it["qty"], it["price_som"], it["price_usd"], it["prod_id"]
                )
            if sup_id and debt > 0:
                await conn.execute(
                    "UPDATE suppliers SET debt_som=debt_som+$1 WHERE id=$2", debt, sup_id
                )
    await state.clear()
    txt = (
        f"✅ <b>Kirim saqlandi!</b>\n\n"
        f"💰 Jami: {fmt_som(total_som)} so'm\n"
        f"💳 To'landi: {fmt_som(paid)} so'm\n"
    )
    if debt > 0:
        txt += f"💸 Qarz: {fmt_som(debt)} so'm\n"
    await message.answer(txt, parse_mode="HTML", reply_markup=purchases_kb())


# ─── KIRIM TARIXI ─────────────────────────────────────────────────────────
@router.message(F.text == "📋 Kirim tarixi")
async def purchase_history(message: Message, shop_id: int = None):
    if shop_id is None:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT p.id, p.date, p.total_som, p.paid_som, s.name as sup
               FROM purchases p LEFT JOIN suppliers s ON s.id=p.supplier_id
               WHERE p.shop_id=$1 ORDER BY p.created_at DESC LIMIT 20""",
            shop_id
        )
    if not rows:
        await message.answer("📭 Kirim tarixi yo'q.")
        return
    text = "📋 <b>So'nggi 20 kirim:</b>\n\n"
    for r in rows:
        debt = float(r["total_som"]) - float(r["paid_som"])
        text += (
            f"📅 {r['date']} | {r['sup'] or 'Taminotchisiz'}\n"
            f"   💰 {r['total_som']:,.0f} so'm"
        )
        if debt > 0:
            text += f" | 💸 Qarz: {debt:,.0f}"
        text += "\n\n"
    await message.answer(text, parse_mode="HTML")
