from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile
from aiogram.fsm.context import FSMContext
from datetime import date

from bot.states import ReportSt
from bot.keyboards.menus import reports_kb, cancel_kb, back_cancel_kb
from bot.database.connection import get_pool
from bot.services.report_service import (
    get_daily_report, get_monthly_report,
    format_daily_report, format_monthly_report
)
from bot.services.excel_service import (
    generate_daily_excel, generate_monthly_excel, generate_stock_excel
)
from bot.services.pdf_service import generate_daily_pdf, generate_monthly_pdf

router = Router()

MONTHS_UZ = ["Yanvar","Fevral","Mart","Aprel","May","Iyun",
             "Iyul","Avgust","Sentabr","Oktabr","Noyabr","Dekabr"]


@router.message(F.text == "📊 Hisobotlar")
async def reports_menu(message: Message, state: FSMContext, shop_id: int = None, role: str = None):
    if shop_id is None:
        await message.answer("❌ Avval kiring: /start")
        return
    await state.clear()
    await message.answer("📊 <b>Hisobotlar</b>", parse_mode="HTML", reply_markup=reports_kb(role or "staff"))


# ─── BUGUNGI HISOBOT ──────────────────────────────────────────────────────
@router.message(F.text == "📅 Bugungi hisobot")
async def today_report(message: Message, shop_id: int = None):
    if shop_id is None:
        return
    await message.answer("⏳ Hisobot tayyorlanmoqda...")
    report = await get_daily_report(shop_id, date.today())
    await message.answer(format_daily_report(report), parse_mode="HTML")


# ─── OYLIK HISOBOT ────────────────────────────────────────────────────────
@router.message(F.text == "📆 Oylik hisobot")
async def monthly_report_start(message: Message, state: FSMContext, shop_id: int = None, role: str = None):
    if shop_id is None:
        return
    today = date.today()
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    from aiogram.utils.keyboard import ReplyKeyboardBuilder
    b = ReplyKeyboardBuilder()
    for i in range(6):
        m = (today.month - i - 1) % 12 + 1
        y = today.year - ((today.month - i - 1) // 12)
        b.button(text=f"{MONTHS_UZ[m-1]} {y}")
    b.button(text="❌ Bekor qilish")
    b.adjust(2)
    await message.answer("📆 Oy tanlang:", reply_markup=b.as_markup(resize_keyboard=True))
    await state.set_state(ReportSt.selecting_period)


@router.message(ReportSt.selecting_period)
async def monthly_report_show(message: Message, state: FSMContext, shop_id: int = None, role: str = None):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("📊 Hisobotlar", reply_markup=reports_kb(role or "staff"))
        return
    txt = message.text.strip()
    parts = txt.split()
    if len(parts) != 2:
        await message.answer("⚠️ Oyni to'g'ri tanlang")
        return
    try:
        month = MONTHS_UZ.index(parts[0]) + 1
        year = int(parts[1])
    except (ValueError, IndexError):
        await message.answer("⚠️ Noto'g'ri format")
        return
    await state.clear()
    await message.answer("⏳ Oylik hisobot tayyorlanmoqda...")
    report = await get_monthly_report(shop_id, year, month)
    await message.answer(format_monthly_report(report), parse_mode="HTML", reply_markup=reports_kb(role or "staff"))


# ─── EXCEL EXPORT ─────────────────────────────────────────────────────────
@router.message(F.text == "📊 Excel export")
async def excel_export_menu(message: Message, state: FSMContext, shop_id: int = None, role: str = None):
    if shop_id is None or role != "boss":
        return
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    from aiogram.utils.keyboard import ReplyKeyboardBuilder
    b = ReplyKeyboardBuilder()
    b.row(
        KeyboardButton(text="📅 Bugungi Excel"),
        KeyboardButton(text="📆 Oylik Excel"),
    )
    b.row(
        KeyboardButton(text="📦 Ombor Excel"),
        KeyboardButton(text="❌ Bekor qilish"),
    )
    await message.answer("📊 Excel turi:", reply_markup=b.as_markup(resize_keyboard=True))
    await state.set_state(ReportSt.selecting_export)


@router.message(ReportSt.selecting_export, F.text == "📅 Bugungi Excel")
async def excel_daily(message: Message, state: FSMContext, shop_id: int = None, role: str = None):
    await state.clear()
    await message.answer("⏳ Excel tayyorlanmoqda...")
    try:
        data = await generate_daily_excel(shop_id, date.today())
        fname = f"hisobot_{date.today().strftime('%Y%m%d')}.xlsx"
        await message.answer_document(
            BufferedInputFile(data, filename=fname),
            caption=f"📊 Kunlik hisobot — {date.today().strftime('%d.%m.%Y')}",
            reply_markup=reports_kb(role or "boss")
        )
    except Exception as e:
        await message.answer(f"❌ Xato: {e}", reply_markup=reports_kb(role or "boss"))


@router.message(ReportSt.selecting_export, F.text == "📦 Ombor Excel")
async def excel_stock(message: Message, state: FSMContext, shop_id: int = None, role: str = None):
    await state.clear()
    await message.answer("⏳ Ombor Excel tayyorlanmoqda...")
    try:
        data = await generate_stock_excel(shop_id)
        fname = f"ombor_{date.today().strftime('%Y%m%d')}.xlsx"
        await message.answer_document(
            BufferedInputFile(data, filename=fname),
            caption="📦 Ombor holati",
            reply_markup=reports_kb(role or "boss")
        )
    except Exception as e:
        await message.answer(f"❌ Xato: {e}", reply_markup=reports_kb(role or "boss"))


@router.message(ReportSt.selecting_export, F.text == "📆 Oylik Excel")
async def excel_monthly_select(message: Message, state: FSMContext, shop_id: int = None, role: str = None):
    today = date.today()
    from aiogram.utils.keyboard import ReplyKeyboardBuilder
    from aiogram.types import KeyboardButton
    b = ReplyKeyboardBuilder()
    for i in range(4):
        m = (today.month - i - 1) % 12 + 1
        y = today.year - ((today.month - i - 1) // 12)
        b.button(text=f"excel_{m}_{y}")
    b.button(text="❌ Bekor qilish")
    b.adjust(2)
    await message.answer("📆 Oy tanlang:", reply_markup=b.as_markup(resize_keyboard=True))


@router.message(ReportSt.selecting_export, F.text.startswith("excel_"))
async def excel_monthly_gen(message: Message, state: FSMContext, shop_id: int = None, role: str = None):
    parts = message.text.split("_")
    try:
        month = int(parts[1])
        year = int(parts[2])
    except (IndexError, ValueError):
        return
    await state.clear()
    await message.answer("⏳ Oylik Excel tayyorlanmoqda...")
    try:
        data = await generate_monthly_excel(shop_id, year, month)
        fname = f"oylik_{year}_{month:02d}.xlsx"
        await message.answer_document(
            BufferedInputFile(data, filename=fname),
            caption=f"📆 Oylik hisobot — {MONTHS_UZ[month-1]} {year}",
            reply_markup=reports_kb(role or "boss")
        )
    except Exception as e:
        await message.answer(f"❌ Xato: {e}", reply_markup=reports_kb(role or "boss"))


@router.message(ReportSt.selecting_export, F.text == "❌ Bekor qilish")
async def excel_cancel(message: Message, state: FSMContext, role: str = None):
    await state.clear()
    await message.answer("📊 Hisobotlar", reply_markup=reports_kb(role or "boss"))


# ─── PDF EXPORT ───────────────────────────────────────────────────────────
@router.message(F.text == "📄 PDF export")
async def pdf_export(message: Message, shop_id: int = None, role: str = None):
    if shop_id is None or role != "boss":
        return
    await message.answer("⏳ PDF tayyorlanmoqda...")
    try:
        data = await generate_daily_pdf(shop_id, date.today())
        fname = f"hisobot_{date.today().strftime('%Y%m%d')}.pdf"
        await message.answer_document(
            BufferedInputFile(data, filename=fname),
            caption=f"📄 Kunlik hisobot — {date.today().strftime('%d.%m.%Y')}",
            reply_markup=reports_kb(role)
        )
    except Exception as e:
        await message.answer(f"❌ PDF xato: {e}", reply_markup=reports_kb(role))


# ─── FOYDA TARIXI ─────────────────────────────────────────────────────────
@router.message(F.text == "📈 Foyda tarixi")
async def profit_history(message: Message, shop_id: int = None, role: str = None):
    if shop_id is None or role != "boss":
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT date, total_sales_som, net_profit_som, sales_count
               FROM daily_reports WHERE shop_id=$1 ORDER BY date DESC LIMIT 30""",
            shop_id
        )
    if not rows:
        await message.answer("📭 Hisobot tarixi yo'q (22:00 da avtomatik to'ldiriladi)")
        return
    text = "📈 <b>So'nggi 30 kun foyda:</b>\n\n"
    for r in rows:
        text += (
            f"📅 {r['date'].strftime('%d.%m')} | "
            f"💰 {r['total_sales_som']:,.0f} so'm | "
            f"💵 Foyda: {r['net_profit_som']:,.0f} so'm\n"
        )
    await message.answer(text, parse_mode="HTML")


# ─── OMBOR HOLATI ─────────────────────────────────────────────────────────
@router.message(F.text == "📉 Ombor holati")
async def stock_status(message: Message, shop_id: int = None, role: str = None):
    if shop_id is None or role != "boss":
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT p.name, p.stock_qty, p.unit, p.sell_price_som,
                      p.stock_qty * p.buy_price_som as value
               FROM products p WHERE p.shop_id=$1 AND p.is_active=TRUE ORDER BY value DESC""",
            shop_id
        )
        total_value = await conn.fetchval(
            """SELECT COALESCE(SUM(stock_qty * buy_price_som),0)
               FROM products WHERE shop_id=$1 AND is_active=TRUE""",
            shop_id
        )
    if not rows:
        await message.answer("📭 Mahsulot yo'q.")
        return
    text = f"📦 <b>Ombor holati ({len(rows)} mahsulot):</b>\n\n"
    for r in rows:
        icon = "⚠️" if r["stock_qty"] <= 5 else "✅"
        text += f"{icon} {r['name']}: <b>{r['stock_qty']:g} {r['unit']}</b>"
        text += f" | {r['sell_price_som']:,.0f} so'm\n"
    text += f"\n💰 <b>Ombor umumiy qiymati: {float(total_value):,.0f} so'm</b>"
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
