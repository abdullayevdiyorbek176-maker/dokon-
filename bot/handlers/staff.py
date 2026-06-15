from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.states import StaffSt
from bot.keyboards.menus import staff_kb, cancel_kb, inline_items_kb, main_kb
from bot.database.connection import get_pool
from bot.middlewares.auth_middleware import user_sessions

router = Router()


def _boss_only(role: str) -> bool:
    return role != "boss"


@router.message(F.text == "👨‍💼 Xodimlar")
async def staff_menu(message: Message, state: FSMContext, shop_id: int = None, role: str = None):
    if shop_id is None:
        await message.answer("❌ Avval kiring: /start")
        return
    if _boss_only(role):
        await message.answer("🚫 Faqat raxbar uchun!")
        return
    await state.clear()
    await message.answer("👨‍💼 <b>Xodimlar</b>", parse_mode="HTML", reply_markup=staff_kb())


@router.message(F.text == "👥 Xodimlar ro'yxati")
async def staff_list(message: Message, shop_id: int = None, role: str = None):
    if shop_id is None or _boss_only(role):
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT telegram_id, username, full_name, role, joined_at
               FROM shop_users WHERE shop_id=$1 AND is_active=TRUE ORDER BY joined_at""",
            shop_id
        )
    if not rows:
        await message.answer("📭 Xodim yo'q.")
        return
    text = f"👥 <b>Xodimlar ({len(rows)} ta):</b>\n\n"
    for r in rows:
        icon = "👑" if r["role"] == "boss" else "👤"
        name = r["full_name"] or r["username"] or f"ID:{r['telegram_id']}"
        text += (
            f"{icon} <b>{name}</b>\n"
            f"   🆔 {r['telegram_id']}"
        )
        if r["username"]:
            text += f" | @{r['username']}"
        text += f"\n   Qo'shilgan: {r['joined_at'].strftime('%d.%m.%Y')}\n\n"
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "➕ Xodim qo'shish")
async def staff_add_start(message: Message, state: FSMContext, shop_id: int = None, role: str = None):
    if shop_id is None or _boss_only(role):
        return
    await state.set_state(StaffSt.entering_telegram_id)
    await message.answer(
        "👤 Xodimning Telegram ID'sini kiriting:\n\n"
        "<i>Xodim @userinfobot ga /start yozsa, ID'sini oladi</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )


@router.message(StaffSt.entering_telegram_id)
async def staff_add_id(message: Message, state: FSMContext, shop_id: int = None, role: str = None):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("👨‍💼 Xodimlar", reply_markup=staff_kb())
        return
    try:
        tg_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Faqat raqam kiriting (Telegram ID):")
        return
    if tg_id == message.from_user.id:
        await message.answer("⚠️ O'zingizni xodim sifatida qo'sha olmaysiz!")
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id, is_active FROM shop_users WHERE shop_id=$1 AND telegram_id=$2",
            shop_id, tg_id
        )
        if existing:
            if existing["is_active"]:
                await message.answer("⚠️ Bu xodim allaqachon qo'shilgan!")
                await state.clear()
                await message.answer("👨‍💼 Xodimlar", reply_markup=staff_kb())
                return
            else:
                await conn.execute(
                    "UPDATE shop_users SET is_active=TRUE WHERE id=$1", existing["id"]
                )
        else:
            await conn.execute(
                """INSERT INTO shop_users (shop_id, telegram_id, role)
                   VALUES ($1,$2,'staff')""",
                shop_id, tg_id
            )
    await state.clear()
    await message.answer(
        f"✅ Xodim (ID: <code>{tg_id}</code>) qo'shildi!\n"
        f"Endi u dokon parolini kiritib kira oladi.",
        parse_mode="HTML",
        reply_markup=staff_kb()
    )


@router.message(F.text == "🗑️ Xodim o'chirish")
async def staff_delete_start(message: Message, state: FSMContext, shop_id: int = None, role: str = None):
    if shop_id is None or _boss_only(role):
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, telegram_id, username, full_name FROM shop_users
               WHERE shop_id=$1 AND role='staff' AND is_active=TRUE ORDER BY joined_at""",
            shop_id
        )
    if not rows:
        await message.answer("📭 O'chiriladigan xodim yo'q.")
        return
    items = [
        {"id": r["id"], "label": r["full_name"] or r["username"] or f"ID:{r['telegram_id']}"}
        for r in rows
    ]
    await message.answer("🗑️ O'chiriladigan xodimni tanlang:", reply_markup=inline_items_kb(items, "del_staff"))
    await state.set_state(StaffSt.confirming_delete)


@router.callback_query(StaffSt.confirming_delete, F.data.startswith("del_staff:"))
async def staff_delete_confirm(cb: CallbackQuery, state: FSMContext, shop_id: int = None):
    staff_db_id = int(cb.data.split(":")[1])
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT telegram_id, full_name, username FROM shop_users WHERE id=$1 AND shop_id=$2",
            staff_db_id, shop_id
        )
        if not row:
            await cb.answer("Topilmadi")
            return
        await conn.execute("UPDATE shop_users SET is_active=FALSE WHERE id=$1", staff_db_id)
        tg_id = row["telegram_id"]
        if tg_id in user_sessions:
            del user_sessions[tg_id]
    await state.clear()
    name = row["full_name"] or row["username"] or f"ID:{tg_id}"
    await cb.message.edit_text(f"✅ <b>{name}</b> xodimdan chiqarildi", parse_mode="HTML")
    await cb.message.answer("👨‍💼 Xodimlar", reply_markup=staff_kb())
    await cb.answer()


@router.callback_query(StaffSt.confirming_delete, F.data == "del_staff_cancel")
async def staff_delete_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("❌ Bekor qilindi")
    await cb.message.answer("👨‍💼 Xodimlar", reply_markup=staff_kb())
    await cb.answer()
