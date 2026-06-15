from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.states import ProductSt, CategorySt
from bot.keyboards.menus import (
    products_kb, cancel_kb, back_cancel_kb, main_kb, inline_items_kb
)
from bot.database.connection import get_pool
from bot.utils.amount_parser import parse_amount, fmt_som

router = Router()

UNITS = ["dona", "kg", "g", "litr", "metr", "m²", "quti", "juft"]


def _no_auth(shop_id):
    return shop_id is None


@router.message(F.text == "📦 Mahsulotlar")
async def products_menu(message: Message, state: FSMContext, shop_id: int = None, role: str = None):
    if _no_auth(shop_id):
        await message.answer("❌ Avval kiring: /start")
        return
    await state.clear()
    await message.answer("📦 <b>Mahsulotlar</b>", parse_mode="HTML", reply_markup=products_kb())


@router.message(ProductSt.menu, F.text == "⬅️ Orqaga")
@router.message(F.text == "⬅️ Orqaga")
async def products_back(message: Message, state: FSMContext, role: str = None, shop_id: int = None):
    await state.clear()
    if shop_id:
        await message.answer("🏠 Asosiy menyu", reply_markup=main_kb(role or "staff"))


# ─── RO'YXAT ──────────────────────────────────────────────────────────────
@router.message(F.text == "📋 Ro'yxat")
async def products_list(message: Message, state: FSMContext, shop_id: int = None):
    if _no_auth(shop_id):
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT p.id, p.name, p.sell_price_som, p.sell_price_usd,
                      p.stock_qty, p.unit, c.name as cat
               FROM products p
               LEFT JOIN categories c ON c.id = p.category_id
               WHERE p.shop_id = $1 AND p.is_active = TRUE
               ORDER BY p.name""",
            shop_id
        )
    if not rows:
        await message.answer("📭 Mahsulot yo'q. ➕ Qo'shish tugmasini bosing.")
        return
    text = "📦 <b>Mahsulotlar ro'yxati:</b>\n\n"
    for i, r in enumerate(rows, 1):
        price = f"{fmt_som(float(r['sell_price_som']))} so'm"
        if r['sell_price_usd']:
            price += f" | {r['sell_price_usd']:.2f}$"
        stock_icon = "⚠️" if r['stock_qty'] <= 5 else "✅"
        text += (
            f"{i}. <b>{r['name']}</b>\n"
            f"   💰 {price}\n"
            f"   {stock_icon} Qoldiq: {r['stock_qty']:g} {r['unit']}\n"
            f"   📂 {r['cat'] or 'Kategoriyasiz'}\n\n"
        )
    for chunk in _split_text(text):
        await message.answer(chunk, parse_mode="HTML")


# ─── QO'SHISH ─────────────────────────────────────────────────────────────
@router.message(F.text == "➕ Qo'shish")
async def product_add_start(message: Message, state: FSMContext,
                             shop_id: int = None,
                             use_som: bool = True, use_usd: bool = True):
    if _no_auth(shop_id):
        return
    await state.update_data(use_som=use_som, use_usd=use_usd)
    await state.set_state(ProductSt.entering_name)
    await message.answer("📝 Mahsulot nomini kiriting:", reply_markup=cancel_kb())


@router.message(ProductSt.entering_name)
async def product_add_name(message: Message, state: FSMContext, shop_id: int = None):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("📦 Mahsulotlar", reply_markup=products_kb())
        return
    await state.update_data(name=message.text.strip())
    pool = await get_pool()
    async with pool.acquire() as conn:
        cats = await conn.fetch(
            "SELECT id, name FROM categories WHERE shop_id=$1 ORDER BY name", shop_id
        )
    items = [{"id": c["id"], "label": c["name"]} for c in cats]
    items.append({"id": 0, "label": "➕ Yangi kategoriya"})
    await state.update_data(cats=[(c["id"], c["name"]) for c in cats])
    await message.answer(
        "📂 Kategoriyani tanlang:",
        reply_markup=inline_items_kb(items, "cat_sel")
    )
    await state.set_state(ProductSt.entering_category)


@router.callback_query(ProductSt.entering_category, F.data.startswith("cat_sel:"))
async def product_add_cat(cb: CallbackQuery, state: FSMContext):
    cat_id = int(cb.data.split(":")[1])
    await state.update_data(cat_id=cat_id if cat_id != 0 else None)
    await cb.message.edit_reply_markup()
    if cat_id == 0:
        await cb.message.answer("📝 Yangi kategoriya nomini kiriting:", reply_markup=cancel_kb())
        await state.set_state(CategorySt.entering_name)
    else:
        await _ask_sell_price(cb.message, state)
    await cb.answer()


@router.callback_query(ProductSt.entering_category, F.data == "cat_sel_cancel")
async def product_add_cat_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_reply_markup()
    await cb.message.answer("❌ Bekor qilindi", reply_markup=products_kb())
    await cb.answer()


@router.message(CategorySt.entering_name)
async def category_add(message: Message, state: FSMContext, shop_id: int = None):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("📦 Mahsulotlar", reply_markup=products_kb())
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO categories (shop_id, name) VALUES ($1,$2) ON CONFLICT (shop_id,name) DO UPDATE SET name=EXCLUDED.name RETURNING id",
            shop_id, message.text.strip()
        )
    await state.update_data(cat_id=row["id"])
    await message.answer("✅ Kategoriya qo'shildi!")
    await _ask_sell_price(message, state)


@router.message(ProductSt.entering_sell_price_som)
async def product_sell_som(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("📦 Mahsulotlar", reply_markup=products_kb())
        return
    price, _ = parse_amount(message.text)
    if price is None:
        await message.answer("⚠️ Raqam kiriting (masalan: 15ming yoki 15000):")
        return
    await state.update_data(sell_price_som=price)
    data = await state.get_data()
    if data.get("use_usd", True):
        await message.answer("💵 Sotish narxi ($, 0=yo'q):", reply_markup=cancel_kb())
        await state.set_state(ProductSt.entering_sell_price_usd)
    else:
        await state.update_data(sell_price_usd=0)
        await _ask_buy_price(message, state)


@router.message(ProductSt.entering_sell_price_usd)
async def product_sell_usd(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("📦 Mahsulotlar", reply_markup=products_kb())
        return
    price, _ = parse_amount(message.text)
    if price is None:
        await message.answer("⚠️ Raqam kiriting:")
        return
    await state.update_data(sell_price_usd=price)
    await _ask_buy_price(message, state)


@router.message(ProductSt.entering_buy_price_som)
async def product_buy_som(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("📦 Mahsulotlar", reply_markup=products_kb())
        return
    price, _ = parse_amount(message.text)
    if price is None:
        await message.answer("⚠️ Raqam kiriting:")
        return
    await state.update_data(buy_price_som=price)
    data = await state.get_data()
    if data.get("use_usd", True):
        await message.answer("💵 Xarid narxi ($, 0=yo'q):", reply_markup=cancel_kb())
        await state.set_state(ProductSt.entering_buy_price_usd)
    else:
        await state.update_data(buy_price_usd=0)
        await _ask_stock(message, state)


@router.message(ProductSt.entering_buy_price_usd)
async def product_buy_usd(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("📦 Mahsulotlar", reply_markup=products_kb())
        return
    price, _ = parse_amount(message.text)
    if price is None:
        await message.answer("⚠️ Raqam kiriting:")
        return
    await state.update_data(buy_price_usd=price)
    await _ask_stock(message, state)


@router.message(ProductSt.entering_stock)
async def product_stock(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("📦 Mahsulotlar", reply_markup=products_kb())
        return
    qty, _ = parse_amount(message.text)
    if qty is None:
        await message.answer("⚠️ Raqam kiriting:")
        return
    await state.update_data(stock_qty=qty)
    await message.answer("⚠️ Minimal qoldiq chegarasi (masalan 5):", reply_markup=cancel_kb())
    await state.set_state(ProductSt.entering_min_stock)


@router.message(ProductSt.entering_min_stock)
async def product_min_stock(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("📦 Mahsulotlar", reply_markup=products_kb())
        return
    min_qty, _ = parse_amount(message.text)
    if min_qty is None:
        await message.answer("⚠️ Raqam kiriting:")
        return
    await state.update_data(min_stock_qty=min_qty)
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    from aiogram.utils.keyboard import ReplyKeyboardBuilder
    b = ReplyKeyboardBuilder()
    for i in range(0, len(UNITS), 2):
        row = [KeyboardButton(text=UNITS[i])]
        if i + 1 < len(UNITS):
            row.append(KeyboardButton(text=UNITS[i + 1]))
        b.row(*row)
    b.row(KeyboardButton(text="❌ Bekor qilish"))
    await message.answer("📏 O'lchov birligini tanlang:", reply_markup=b.as_markup(resize_keyboard=True))
    await state.set_state(ProductSt.entering_unit)


@router.message(ProductSt.entering_unit)
async def product_unit(message: Message, state: FSMContext, shop_id: int = None):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("📦 Mahsulotlar", reply_markup=products_kb())
        return
    unit = message.text.strip()
    data = await state.get_data()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO products
               (shop_id, category_id, name, buy_price_som, buy_price_usd,
                sell_price_som, sell_price_usd, stock_qty, min_stock_qty, unit)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""",
            shop_id, data.get("cat_id"), data["name"],
            data.get("buy_price_som", 0), data.get("buy_price_usd", 0),
            data["sell_price_som"], data.get("sell_price_usd", 0),
            data["stock_qty"], data["min_stock_qty"], unit
        )
    await state.clear()
    await message.answer(
        f"✅ <b>{data['name']}</b> qo'shildi!\n"
        f"💰 Narx: {fmt_som(data['sell_price_som'])} so'm\n"
        f"📦 Qoldiq: {data['stock_qty']:g} {unit}",
        parse_mode="HTML",
        reply_markup=products_kb()
    )


# ─── O'CHIRISH ────────────────────────────────────────────────────────────
@router.message(F.text == "🗑️ O'chirish")
async def product_delete_start(message: Message, state: FSMContext, shop_id: int = None):
    if _no_auth(shop_id):
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name FROM products WHERE shop_id=$1 AND is_active=TRUE ORDER BY name", shop_id
        )
    if not rows:
        await message.answer("📭 O'chiriladigan mahsulot yo'q.")
        return
    items = [{"id": r["id"], "label": r["name"]} for r in rows]
    await message.answer("🗑️ O'chiriladigan mahsulotni tanlang:", reply_markup=inline_items_kb(items, "del_prod"))
    await state.set_state(ProductSt.selecting)


@router.callback_query(ProductSt.selecting, F.data.startswith("del_prod:"))
async def product_delete_confirm(cb: CallbackQuery, state: FSMContext, shop_id: int = None):
    prod_id = int(cb.data.split(":")[1])
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT name FROM products WHERE id=$1 AND shop_id=$2", prod_id, shop_id)
    if not row:
        await cb.answer("Topilmadi")
        return
    await state.update_data(del_id=prod_id, del_name=row["name"])
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ O'chirish", callback_data="del_prod_yes"),
        InlineKeyboardButton(text="❌ Bekor", callback_data="del_prod_no"),
    ]])
    await cb.message.edit_text(f"🗑️ <b>{row['name']}</b>ni o'chirasizmi?", parse_mode="HTML", reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data == "del_prod_yes")
async def product_delete_yes(cb: CallbackQuery, state: FSMContext, shop_id: int = None):
    data = await state.get_data()
    prod_id = data.get("del_id")
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE products SET is_active=FALSE WHERE id=$1 AND shop_id=$2", prod_id, shop_id)
    await state.clear()
    await cb.message.edit_text(f"✅ <b>{data.get('del_name')}</b> o'chirildi", parse_mode="HTML")
    await cb.message.answer("📦 Mahsulotlar", reply_markup=products_kb())
    await cb.answer()


@router.callback_query(F.data == "del_prod_no")
async def product_delete_no(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("❌ Bekor qilindi")
    await cb.message.answer("📦 Mahsulotlar", reply_markup=products_kb())
    await cb.answer()


# ─── TAHRIRLASH ───────────────────────────────────────────────────────────
@router.message(F.text == "✏️ Tahrirlash")
async def product_edit_start(message: Message, state: FSMContext, shop_id: int = None):
    if _no_auth(shop_id):
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name FROM products WHERE shop_id=$1 AND is_active=TRUE ORDER BY name", shop_id
        )
    if not rows:
        await message.answer("📭 Mahsulot yo'q.")
        return
    items = [{"id": r["id"], "label": r["name"]} for r in rows]
    await message.answer("✏️ Tahrirlanadigan mahsulotni tanlang:", reply_markup=inline_items_kb(items, "edit_prod"))
    await state.set_state(ProductSt.selecting)


@router.callback_query(ProductSt.selecting, F.data.startswith("edit_prod:"))
async def product_edit_select(cb: CallbackQuery, state: FSMContext, shop_id: int = None):
    prod_id = int(cb.data.split(":")[1])
    pool = await get_pool()
    async with pool.acquire() as conn:
        r = await conn.fetchrow("SELECT * FROM products WHERE id=$1 AND shop_id=$2", prod_id, shop_id)
    if not r:
        await cb.answer("Topilmadi")
        return
    await state.update_data(edit_id=prod_id)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Nomi", callback_data="ef:name"),
         InlineKeyboardButton(text="Sotish (so'm)", callback_data="ef:sell_som")],
        [InlineKeyboardButton(text="Sotish ($)", callback_data="ef:sell_usd"),
         InlineKeyboardButton(text="Xarid (so'm)", callback_data="ef:buy_som")],
        [InlineKeyboardButton(text="Xarid ($)", callback_data="ef:buy_usd"),
         InlineKeyboardButton(text="Min.qoldiq", callback_data="ef:min_stock")],
        [InlineKeyboardButton(text="❌ Bekor", callback_data="ef:cancel")],
    ])
    await cb.message.edit_text(
        f"✏️ <b>{r['name']}</b>\n"
        f"💰 Sotuv: {r['sell_price_som']:,.0f} so'm | {r['sell_price_usd']:.2f}$\n"
        f"📦 Qoldiq: {r['stock_qty']:g} {r['unit']}\n\n"
        "Qaysi maydonni o'zgartirasiz?",
        parse_mode="HTML", reply_markup=kb
    )
    await state.set_state(ProductSt.editing_field)
    await cb.answer()


EDIT_FIELDS = {
    "name": "Yangi nom:", "sell_som": "Yangi sotish narxi (so'm):",
    "sell_usd": "Yangi sotish narxi ($):", "buy_som": "Yangi xarid narxi (so'm):",
    "buy_usd": "Yangi xarid narxi ($):", "min_stock": "Yangi minimal qoldiq:",
}


@router.callback_query(ProductSt.editing_field, F.data.startswith("ef:"))
async def product_edit_field(cb: CallbackQuery, state: FSMContext):
    field = cb.data.split(":")[1]
    if field == "cancel":
        await state.clear()
        await cb.message.edit_text("❌ Bekor qilindi")
        await cb.message.answer("📦 Mahsulotlar", reply_markup=products_kb())
        await cb.answer()
        return
    await state.update_data(edit_field=field)
    await cb.message.edit_reply_markup()
    await cb.message.answer(EDIT_FIELDS.get(field, "Yangi qiymat:"), reply_markup=cancel_kb())
    await state.set_state(ProductSt.editing_value)
    await cb.answer()


@router.message(ProductSt.editing_value)
async def product_edit_value(message: Message, state: FSMContext, shop_id: int = None):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("📦 Mahsulotlar", reply_markup=products_kb())
        return
    data = await state.get_data()
    field = data["edit_field"]
    prod_id = data["edit_id"]
    db_col = {
        "name": "name", "sell_som": "sell_price_som", "sell_usd": "sell_price_usd",
        "buy_som": "buy_price_som", "buy_usd": "buy_price_usd", "min_stock": "min_stock_qty",
    }.get(field)
    if not db_col:
        await state.clear()
        return
    if field == "name":
        value = message.text.strip()
    else:
        value, _ = parse_amount(message.text)
        if value is None:
            await message.answer("⚠️ Raqam kiriting (masalan: 15ming yoki 15000):")
            return
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            f"UPDATE products SET {db_col}=$1 WHERE id=$2 AND shop_id=$3",
            value, prod_id, shop_id
        )
    await state.clear()
    await message.answer("✅ O'zgartirildi!", reply_markup=products_kb())


# ─── KAM QOLGANLAR ────────────────────────────────────────────────────────
@router.message(F.text == "⚠️ Kam qolganlar")
async def low_stock(message: Message, shop_id: int = None):
    if _no_auth(shop_id):
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT name, stock_qty, min_stock_qty, unit FROM products
               WHERE shop_id=$1 AND is_active=TRUE AND stock_qty <= min_stock_qty
               ORDER BY stock_qty""",
            shop_id
        )
    if not rows:
        await message.answer("✅ Barcha mahsulotlar yetarli!")
        return
    text = "⚠️ <b>Kam qolgan mahsulotlar:</b>\n\n"
    for r in rows:
        text += f"• <b>{r['name']}</b>: {r['stock_qty']:g} {r['unit']} (min: {r['min_stock_qty']:g})\n"
    await message.answer(text, parse_mode="HTML")


# ─── KATEGORIYALAR ────────────────────────────────────────────────────────
@router.message(F.text == "📂 Kategoriyalar")
async def categories_list(message: Message, shop_id: int = None):
    if _no_auth(shop_id):
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT c.name, COUNT(p.id) as cnt
               FROM categories c LEFT JOIN products p ON p.category_id=c.id AND p.is_active=TRUE
               WHERE c.shop_id=$1 GROUP BY c.id, c.name ORDER BY c.name""",
            shop_id
        )
    text = "📂 <b>Kategoriyalar:</b>\n\n"
    for r in rows:
        text += f"• {r['name']} ({r['cnt']} mahsulot)\n"
    await message.answer(text or "📭 Kategoriya yo'q", parse_mode="HTML")


async def _ask_sell_price(message, state):
    data = await state.get_data()
    if data.get("use_som", True):
        await message.answer("💰 Sotish narxi (so'm):", reply_markup=cancel_kb())
        await state.set_state(ProductSt.entering_sell_price_som)
    else:
        await message.answer("💵 Sotish narxi ($):", reply_markup=cancel_kb())
        await state.set_state(ProductSt.entering_sell_price_usd)


async def _ask_buy_price(message, state):
    data = await state.get_data()
    if data.get("use_som", True):
        await message.answer("📦 Xarid narxi (so'm, 0=yozmaslik):", reply_markup=cancel_kb())
        await state.set_state(ProductSt.entering_buy_price_som)
    else:
        await message.answer("📦 Xarid narxi ($, 0=yozmaslik):", reply_markup=cancel_kb())
        await state.set_state(ProductSt.entering_buy_price_usd)


async def _ask_stock(message, state):
    await message.answer("📦 Boshlang'ich qoldiq (0 yozsangiz bo'ladi):", reply_markup=cancel_kb())
    await state.set_state(ProductSt.entering_stock)


def _split_text(text: str, limit: int = 4000) -> list:
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
