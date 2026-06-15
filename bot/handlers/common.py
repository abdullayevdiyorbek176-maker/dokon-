from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.keyboards.menus import main_kb, inline_items_kb

router = Router()


@router.callback_query(F.data.endswith("_cancel"))
async def generic_inline_cancel(cb: CallbackQuery, state: FSMContext, role: str = None):
    await state.clear()
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await cb.message.answer("❌ Bekor qilindi", reply_markup=main_kb(role or "staff"))
    await cb.answer()


@router.callback_query(F.data.regexp(r".+_page:\d+"))
async def generic_pagination(cb: CallbackQuery, state: FSMContext, shop_id: int = None):
    parts = cb.data.rsplit("_page:", 1)
    if len(parts) != 2:
        await cb.answer()
        return
    prefix = parts[0]
    page = int(parts[1])
    await cb.answer("Sahifa almashtirilyapti...")
