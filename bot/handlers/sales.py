from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from datetime import date

from bot.states import SaleSt
from bot.keyboards.menus import sales_kb, cancel_kb, inline_items_kb
from bot.database.connection import get_pool
from bot.utils.amount_parser import parse_amount, fmt_som

router = Router()


@router.message(F.text == "💰 Sotish")
async def sales_menu(message: Message, state: FSMContext, shop_id: int = None, role: str = None):
    if shop_id is None:
        await message.answer("❌ Avval kiring: /start")
        return
    await state.clear()
    await message.answer("💰 <b>Sotish bo'limi</b>", parse_mode="HTML", reply_markup=sales_kb())


# ─── YANGI SOTUV ──────────────────────────────────────────────────────────

@router.message(F.text == "➕ Yangi sotuv")
async def sale_new_start(message: Message, state: FSMContext,
                          shop_id: int = None,
                          use_som: bool = True, use_usd: bool = True):
    if shop_id is None:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        customers = await conn.fetch(
            "SELECT id, name, phone FROM customers WHERE shop_id=$1 ORDER BY name", shop_id
        )
    _no_tel = "tel yo'q"
    items = [{"id": c["id"], "label": f"{c['name']} ({c['phone'] or _no_tel})"} for c in customers]
    items.insert(0, {"id": 0, "label": "🚶 Naqd (mijoz kiritmasdan)"})
    items.append({"id": -1, "label": "➕ Yangi mijoz"})
    await state.update_data(cart=[], total_som=0.0, total_usd=0.0, cost_som=0.0,
                            use_som=use_som, use_usd=use_usd)
    await message.answer("👥 Mijozni tanlang:", reply_markup=inline_items_kb(items, "sale_cust"))
    await state.set_state(SaleSt.selecting_customer)


@router.callback_query(SaleSt.selecting_customer, F.data.startswith("sale_cust:"))
async def sale_customer_selected(cb: CallbackQuery, state: FSMContext, shop_id: int = None):
    cust_id = int(cb.data.split(":")[1])
    await state.update_data(customer_id=cust_id if cust_id > 0 else None)
    await cb.message.edit_reply_markup()
    await _ask_sale_product(cb.message, state, shop_id)
    await cb.answer()


async def _ask_sale_product(message, state, shop_id):
    pool = await get_pool()
    async with pool.acquire() as conn:
        products = await conn.fetch(
            """SELECT id, name, sell_price_som, sell_price_usd, stock_qty, unit
               FROM products WHERE shop_id=$1 AND is_active=TRUE AND stock_qty > 0
               ORDER BY name""",
            shop_id
        )
    items = [
        {"id": p["id"],
         "label": f"{p['name']} ({p['stock_qty']:g} {p['unit']}) — {fmt_som(float(p['sell_price_som']))} so'm"}
        for p in products
    ]
    items.append({"id": -1, "label": "✅ Sotuvni yakunlash"})
    data = await state.get_data()
    cart = data.get("cart", [])
    cart_text = ""
    if cart:
        cart_text = "\n\n🛒 Savatcha:\n"
        for it in cart:
            subtotal = it["qty"] * it["price_som"] - it.get("discount_som", 0)
            cart_text += (
                f"• {it['name']}: {it['qty']:g} × {fmt_som(it['price_som'])} = "
                f"{fmt_som(subtotal)} so'm\n"
            )
    await message.answer(
        f"📦 Mahsulot tanlang:{cart_text}",
        reply_markup=inline_items_kb(items, "sale_prod")
    )
    await state.set_state(SaleSt.adding_item_product)


@router.callback_query(SaleSt.adding_item_product, F.data.startswith("sale_prod:"))
async def sale_product_selected(cb: CallbackQuery, state: FSMContext, shop_id: int = None):
    prod_id = int(cb.data.split(":")[1])
    if prod_id == -1:
        await cb.message.edit_reply_markup()
        await _sale_enter_payment(cb.message, state, shop_id)
        await cb.answer()
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        prod = await conn.fetchrow(
            "SELECT name, unit, sell_price_som, sell_price_usd, buy_price_som, stock_qty FROM products WHERE id=$1",
            prod_id
        )
    await state.update_data(
        cur_prod_id=prod_id, cur_prod_name=prod["name"],
        cur_prod_unit=prod["unit"],
        cur_sell_som=float(prod["sell_price_som"]),
        cur_sell_usd=float(prod["sell_price_usd"]),
        cur_cost_som=float(prod["buy_price_som"]),
        cur_max_qty=float(prod["stock_qty"]),
    )
    await cb.message.edit_reply_markup()
    await cb.message.answer(
        f"📦 <b>{prod['name']}</b>\n"
        f"💰 Narx: {fmt_som(float(prod['sell_price_som']))} so'm"
        + (f" | {prod['sell_price_usd']:.2f}$" if float(prod['sell_price_usd']) else "") +
        f"\n📦 Qoldiq: {prod['stock_qty']:g} {prod['unit']}\n\n"
        f"Miqdor kiriting ({prod['unit']}):",
        parse_mode="HTML", reply_markup=cancel_kb()
    )
    await state.set_state(SaleSt.adding_item_qty)
    await cb.answer()


@router.message(SaleSt.adding_item_qty)
async def sale_qty(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("💰 Sotish", reply_markup=sales_kb())
        return
    qty, _ = parse_amount(message.text)
    if qty is None or qty <= 0:
        await message.answer("⚠️ Musbat raqam kiriting:")
        return
    data = await state.get_data()
    max_qty = data.get("cur_max_qty", 0)
    if qty > max_qty:
        await message.answer(f"⚠️ Omborda faqat {max_qty:g} {data.get('cur_prod_unit', '')} bor!")
        return
    await state.update_data(cur_qty=qty)
    await message.answer("💸 Chegirma (so'm, 0=yo'q):", reply_markup=cancel_kb())
    await state.set_state(SaleSt.entering_discount)


@router.message(SaleSt.entering_discount)
async def sale_discount(message: Message, state: FSMContext, shop_id: int = None):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("💰 Sotish", reply_markup=sales_kb())
        return
    discount, _ = parse_amount(message.text)
    if discount is None:
        discount = 0.0
    data = await state.get_data()
    item = {
        "prod_id": data["cur_prod_id"],
        "name": data["cur_prod_name"],
        "unit": data["cur_prod_unit"],
        "qty": data["cur_qty"],
        "price_som": data["cur_sell_som"],
        "price_usd": data["cur_sell_usd"],
        "cost_som": data["cur_cost_som"],
        "discount_som": discount,
    }
    cart = data.get("cart", [])
    cart.append(item)
    total_som = data.get("total_som", 0) + item["qty"] * item["price_som"] - discount
    total_usd = data.get("total_usd", 0) + item["qty"] * item["price_usd"]
    cost_som = data.get("cost_som", 0) + item["qty"] * item["cost_som"]
    await state.update_data(cart=cart, total_som=total_som, total_usd=total_usd, cost_som=cost_som)
    sub = item["qty"] * item["price_som"] - discount
    await message.answer(
        f"✅ <b>{item['name']}</b>: {item['qty']:g} × {fmt_som(item['price_som'])}"
        f"{f' - {fmt_som(discount)}' if discount else ''} = {fmt_som(sub)} so'm",
        parse_mode="HTML"
    )
    await _ask_sale_product(message, state, shop_id)


# ─── TO'LOV USULI ─────────────────────────────────────────────────────────

async def _sale_enter_payment(message, state, shop_id):
    data = await state.get_data()
    cart = data.get("cart", [])
    if not cart:
        await message.answer("⚠️ Savatcha bo'sh!", reply_markup=sales_kb())
        await state.clear()
        return
    total_som = data.get("total_som", 0)
    text = "🛒 <b>Sotuv xulosasi:</b>\n\n"
    for it in cart:
        sub = it["qty"] * it["price_som"] - it.get("discount_som", 0)
        text += (
            f"• {it['name']}: {it['qty']:g} × {fmt_som(it['price_som'])} = "
            f"{fmt_som(sub)} so'm\n"
        )
    text += f"\n💰 <b>Jami: {fmt_som(total_som)} so'm</b>\n\n💳 To'lov usulini tanlang:"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💵 Naqd pul", callback_data="pay_method:naxt"),
        InlineKeyboardButton(text="💳 Karta", callback_data="pay_method:karta"),
    ]])
    await message.answer(text, parse_mode="HTML", reply_markup=kb)
    await state.set_state(SaleSt.selecting_payment_method)


@router.callback_query(SaleSt.selecting_payment_method, F.data.startswith("pay_method:"))
async def sale_payment_method(cb: CallbackQuery, state: FSMContext):
    method = cb.data.split(":")[1]
    await state.update_data(payment_method=method)
    data = await state.get_data()
    total_som = data.get("total_som", 0)
    method_txt = "💵 Naqd" if method == "naxt" else "💳 Karta"
    await cb.message.edit_reply_markup()
    await cb.message.answer(
        f"{method_txt} tanlandi.\n\n"
        f"💰 Jami: {fmt_som(total_som)} so'm\n"
        f"💳 To'lov miqdori (so'm) — yoki 0 (qarzga):",
        reply_markup=cancel_kb()
    )
    await state.set_state(SaleSt.entering_paid_som)
    await cb.answer()


@router.message(SaleSt.entering_paid_som)
async def sale_paid_som(message: Message, state: FSMContext, shop_id: int = None):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("💰 Sotish", reply_markup=sales_kb())
        return
    paid_som, _ = parse_amount(message.text)
    if paid_som is None:
        await message.answer("⚠️ Raqam kiriting:")
        return
    await state.update_data(paid_som=paid_som)
    data = await state.get_data()
    if data.get("use_usd", True):
        await message.answer("💵 Dollar miqdori (0=yo'q):", reply_markup=cancel_kb())
        await state.set_state(SaleSt.entering_paid_usd)
    else:
        await state.update_data(paid_usd=0)
        await _save_sale(message, state, shop_id)


@router.message(SaleSt.entering_paid_usd)
async def sale_paid_usd(message: Message, state: FSMContext, shop_id: int = None):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("💰 Sotish", reply_markup=sales_kb())
        return
    paid_usd, _ = parse_amount(message.text)
    if paid_usd is None:
        await message.answer("⚠️ Raqam kiriting:")
        return
    await state.update_data(paid_usd=paid_usd)
    await _save_sale(message, state, shop_id)


async def _save_sale(message, state, shop_id):
    from bot.config import USD_RATE
    data = await state.get_data()
    paid_som = data.get("paid_som", 0)
    paid_usd = data.get("paid_usd", 0)
    payment_method = data.get("payment_method", "naxt")

    pool = await get_pool()
    async with pool.acquire() as conn:
        rate_row = await conn.fetchrow(
            "SELECT rate FROM usd_rates WHERE shop_id=$1 ORDER BY set_at DESC LIMIT 1", shop_id
        )
    rate = float(rate_row["rate"]) if rate_row else USD_RATE

    paid_usd_in_som = paid_usd * rate
    total_som = data.get("total_som", 0)
    total_paid_som = paid_som + paid_usd_in_som
    change_som = max(0.0, total_paid_som - total_som)
    debt_som = max(0.0, total_som - total_paid_som)
    cart = data.get("cart", [])
    cost_som = data.get("cost_som", 0)
    cust_id = data.get("customer_id")

    async with pool.acquire() as conn:
        async with conn.transaction():
            sale = await conn.fetchrow(
                """INSERT INTO sales
                   (shop_id, customer_id, total_som, paid_som, paid_usd,
                    discount_som, change_som, payment_method, created_by)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING id""",
                shop_id, cust_id, total_som, paid_som, paid_usd,
                0, change_som, payment_method, message.from_user.id
            )
            for it in cart:
                await conn.execute(
                    """INSERT INTO sale_items
                       (sale_id, product_id, qty, sell_price_som, sell_price_usd,
                        discount_som, cost_price_som)
                       VALUES ($1,$2,$3,$4,$5,$6,$7)""",
                    sale["id"], it["prod_id"], it["qty"],
                    it["price_som"], it["price_usd"],
                    it.get("discount_som", 0), it["cost_som"]
                )
                await conn.execute(
                    "UPDATE products SET stock_qty=stock_qty-$1 WHERE id=$2",
                    it["qty"], it["prod_id"]
                )
            if cust_id and debt_som > 0:
                await conn.execute(
                    "UPDATE customers SET debt_som=debt_som+$1 WHERE id=$2", debt_som, cust_id
                )
            # Kassani yangilash
            # net_naxt = naqd tomonidan qolgan (qaytim chegirilgan) + dollar (har doim naqd)
            # change_som har doim naqd pulda qaytariladi
            net_naxt = (paid_som if payment_method == "naxt" else 0) + paid_usd_in_som - change_som
            net_karta = paid_som if payment_method == "karta" else 0

            await conn.execute(
                "INSERT INTO kassa (shop_id) VALUES ($1) ON CONFLICT (shop_id) DO NOTHING",
                shop_id
            )
            if net_naxt > 0:
                await conn.execute(
                    "UPDATE kassa SET naxt_som=naxt_som+$1, updated_at=NOW() WHERE shop_id=$2",
                    net_naxt, shop_id
                )
            elif net_naxt < 0:
                # Karta bilan to'landi, qaytim naqd kassadan berildi
                await conn.execute(
                    "UPDATE kassa SET naxt_som=GREATEST(0, naxt_som+$1), updated_at=NOW() WHERE shop_id=$2",
                    net_naxt, shop_id
                )
            if net_karta > 0:
                await conn.execute(
                    "UPDATE kassa SET karta_som=karta_som+$1, updated_at=NOW() WHERE shop_id=$2",
                    net_karta, shop_id
                )
            # Kassa harakati: qaytimdan keyin real tushgan miqdor
            total_income = max(0.0, net_naxt) + net_karta
            if total_income > 0:
                await conn.execute(
                    """INSERT INTO kassa_movements
                       (shop_id, movement_type, method, amount_som, note, created_by)
                       VALUES ($1,'sale_income',$2,$3,$4,$5)""",
                    shop_id, payment_method, total_income,
                    f"Sotuv #{sale['id']}", message.from_user.id
                )

    await state.clear()
    profit = total_som - cost_som
    method_txt = "💵 Naqd" if payment_method == "naxt" else "💳 Karta"
    txt = (
        f"✅ <b>Sotuv saqlandi!</b>\n\n"
        f"💰 Jami: {fmt_som(total_som)} so'm\n"
        f"{method_txt}: {fmt_som(paid_som)} so'm"
    )
    if paid_usd:
        txt += f" + {paid_usd:.2f}$"
    if change_som > 0:
        txt += f"\n💵 Qaytim: {fmt_som(change_som)} so'm"
    if debt_som > 0:
        txt += f"\n💸 Qarz: {fmt_som(debt_som)} so'm"
    txt += f"\n📈 Foyda: {fmt_som(profit)} so'm"
    await message.answer(txt, parse_mode="HTML", reply_markup=sales_kb())


# ─── SOTUV TARIXI ─────────────────────────────────────────────────────────

@router.message(F.text == "📋 Sotuv tarixi")
async def sale_history(message: Message, shop_id: int = None):
    if shop_id is None:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT s.id, s.date, s.total_som, s.paid_som, s.payment_method,
                      c.name as cust,
                      (SELECT COUNT(*) FROM sale_items si WHERE si.sale_id=s.id) as items_cnt
               FROM sales s LEFT JOIN customers c ON c.id=s.customer_id
               WHERE s.shop_id=$1 ORDER BY s.created_at DESC LIMIT 20""",
            shop_id
        )
    if not rows:
        await message.answer("📭 Sotuv tarixi yo'q.")
        return
    text = "📋 <b>So'nggi 20 sotuv:</b>\n\n"
    for r in rows:
        debt = float(r["total_som"]) - float(r["paid_som"])
        method = "💵" if r["payment_method"] == "naxt" else "💳"
        text += (
            f"📅 {r['date']} | {r['cust'] or 'Naqd'} {method}\n"
            f"   💰 {fmt_som(float(r['total_som']))} so'm ({r['items_cnt']} mahsulot)"
        )
        if debt > 0:
            text += f" | 💸 Qarz: {fmt_som(debt)}"
        text += "\n\n"
    await message.answer(text, parse_mode="HTML")
