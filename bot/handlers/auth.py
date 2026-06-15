import re
import bcrypt
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.states import AuthSt
from bot.keyboards.menus import auth_choice_kb, cancel_kb, main_kb
from bot.database.connection import get_pool
from bot.middlewares.auth_middleware import user_sessions

router = Router()

HELP_TEXT = "📞 Yordam: @diyor_bek700\n📱 Tel: +998947677000"
_LOGIN_RE = re.compile(r'^[a-zA-Z0-9_]{3,30}$')


def _hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def _check_pw(pw: str, hashed: str) -> bool:
    return bcrypt.checkpw(pw.encode(), hashed.encode())


def _set_session(tg_id: int, shop_id: int, role: str, user_db_id: int,
                 shop_name: str, use_som: bool = True, use_usd: bool = True):
    user_sessions[tg_id] = {
        "shop_id": shop_id, "role": role,
        "user_db_id": user_db_id, "shop_name": shop_name,
        "use_som": use_som, "use_usd": use_usd,
    }


# ─── START ────────────────────────────────────────────────────────────────
@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext, shop_id: int = None):
    await state.clear()
    if shop_id:
        sess = user_sessions.get(message.from_user.id, {})
        role = sess.get("role", "staff")
        await message.answer(
            f"✅ Xush kelibsiz, <b>{message.from_user.first_name}</b>!\n"
            f"🏪 {sess.get('shop_name', 'Dokon')}",
            parse_mode="HTML",
            reply_markup=main_kb(role),
        )
        return
    await message.answer(
        "👋 <b>Dokon Bot</b>ga xush kelibsiz!\n\n"
        "Yangi dokon ochasizmi yoki mavjud dokonga kirasizmi?",
        parse_mode="HTML",
        reply_markup=auth_choice_kb(),
    )
    await state.set_state(AuthSt.choosing_action)


@router.message(F.text == "/help")
async def cmd_help(message: Message):
    await message.answer(f"❓ <b>Yordam</b>\n\n{HELP_TEXT}", parse_mode="HTML")


# ─── YANGI DOKON ──────────────────────────────────────────────────────────
@router.message(AuthSt.choosing_action, F.text == "🏪 Yangi dokon ochish")
async def new_shop_start(message: Message, state: FSMContext):
    await state.set_state(AuthSt.entering_shop_name)
    await message.answer("🏪 Dokon nomini kiriting:", reply_markup=cancel_kb())


@router.message(AuthSt.entering_shop_name)
async def new_shop_name(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await _to_choice(message, state)
        return
    if len(message.text.strip()) < 2:
        await message.answer("⚠️ Kamida 2 harf kiriting:")
        return
    await state.update_data(shop_name=message.text.strip())
    await message.answer(
        "👤 <b>Login o'rnating</b>\n\n"
        "Login: faqat lotin harflari, raqamlar, _ (pastki chiziq)\n"
        "3–30 belgi. Masalan: <code>diyor_dokon</code>\n\n"
        "<i>Bu login boshqalar uchun ham kerak bo'ladi.</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )
    await state.set_state(AuthSt.setting_login)


@router.message(AuthSt.setting_login)
async def new_shop_set_login(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await _to_choice(message, state)
        return
    login = message.text.strip().lower()
    if not _LOGIN_RE.match(login):
        await message.answer(
            "⚠️ Login noto'g'ri!\n"
            "Faqat: <code>a-z A-Z 0-9 _</code>, 3–30 belgi.",
            parse_mode="HTML",
        )
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT COUNT(*) FROM shops WHERE login=$1", login
        )
    if exists:
        await message.answer(
            f"❌ <b>{login}</b> login band! Boshqa login tanlang:",
            parse_mode="HTML",
        )
        return
    await state.update_data(shop_login=login)
    await message.answer(
        f"✅ Login: <code>{login}</code>\n\n"
        "🔑 <b>Parol o'rnating</b>\n"
        "Kamida 4 belgi. Masalan: <code>Diyor700@</code>",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )
    await state.set_state(AuthSt.setting_password)


@router.message(AuthSt.setting_password)
async def new_shop_set_password(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await _to_choice(message, state)
        return
    if len(message.text.strip()) < 4:
        await message.answer("⚠️ Parol kamida 4 belgi:")
        return
    data = await state.get_data()
    pw = message.text.strip()
    pool = await get_pool()
    async with pool.acquire() as conn:
        shop = await conn.fetchrow(
            "INSERT INTO shops (name, login, password_hash) VALUES ($1,$2,$3) RETURNING id, name",
            data["shop_name"], data["shop_login"], _hash_pw(pw)
        )
        user_row = await conn.fetchrow(
            """INSERT INTO shop_users (shop_id, telegram_id, username, full_name, role)
               VALUES ($1,$2,$3,$4,'boss') RETURNING id""",
            shop["id"], message.from_user.id,
            message.from_user.username or "",
            message.from_user.full_name or "",
        )
        await conn.execute(
            "INSERT INTO categories (shop_id, name) VALUES ($1,$2),($1,$3),($1,$4)",
            shop["id"], "Oziq-ovqat", "Kiyim-kechak", "Boshqa"
        )
    _set_session(message.from_user.id, shop["id"], "boss", user_row["id"],
                 data["shop_name"], use_som=True, use_usd=True)
    await state.clear()
    await message.answer(
        f"🎉 <b>{data['shop_name']}</b> yaratildi!\n\n"
        f"👤 Login: <code>{data['shop_login']}</code>\n"
        f"🔑 Parol: <code>{pw}</code>\n\n"
        "<i>Xodimlarga ushbu login va parolni bering.</i>",
        parse_mode="HTML",
        reply_markup=main_kb("boss"),
    )


# ─── MAVJUD DOKONGA KIRISH ────────────────────────────────────────────────
@router.message(AuthSt.choosing_action, F.text == "🔑 Mavjud dokonga kirish")
async def existing_shop_start(message: Message, state: FSMContext):
    await state.set_state(AuthSt.entering_login)
    await message.answer("👤 Login kiriting:", reply_markup=cancel_kb())


@router.message(AuthSt.entering_login)
async def existing_shop_login(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await _to_choice(message, state)
        return
    login = message.text.strip().lower()
    pool = await get_pool()
    async with pool.acquire() as conn:
        shop = await conn.fetchrow(
            "SELECT id, name, password_hash FROM shops WHERE login=$1 AND is_active=TRUE",
            login
        )
    if not shop:
        await message.answer(
            "❌ Bu login topilmadi.\n"
            "To'g'ri login kiriting yoki:\n" + HELP_TEXT,
            reply_markup=cancel_kb(),
        )
        return
    await state.update_data(shop_id=shop["id"], shop_name=shop["name"],
                            pw_hash=shop["password_hash"])
    await message.answer("🔑 Parol kiriting:", reply_markup=cancel_kb())
    await state.set_state(AuthSt.entering_password)


@router.message(AuthSt.entering_password)
async def existing_shop_password(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await _to_choice(message, state)
        return
    data = await state.get_data()
    pw = message.text.strip()
    if not _check_pw(pw, data["pw_hash"]):
        await message.answer(
            "❌ Parol noto'g'ri! Qayta kiriting:",
            reply_markup=cancel_kb(),
        )
        return
    shop_id = data["shop_id"]
    shop_name = data["shop_name"]
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id, role, is_active FROM shop_users WHERE shop_id=$1 AND telegram_id=$2",
            shop_id, message.from_user.id
        )
        if existing:
            if not existing["is_active"]:
                await message.answer(
                    "❌ Sizning hisobingiz o'chirilgan. Raxbar bilan bog'laning.",
                    reply_markup=cancel_kb(),
                )
                return
            role = existing["role"]
            user_db_id = existing["id"]
        else:
            boss_exists = await conn.fetchval(
                "SELECT COUNT(*) FROM shop_users WHERE shop_id=$1 AND role='boss' AND is_active=TRUE",
                shop_id
            )
            role = "staff" if boss_exists else "boss"
            row = await conn.fetchrow(
                """INSERT INTO shop_users (shop_id, telegram_id, username, full_name, role)
                   VALUES ($1,$2,$3,$4,$5) RETURNING id""",
                shop_id, message.from_user.id,
                message.from_user.username or "",
                message.from_user.full_name or "",
                role,
            )
            user_db_id = row["id"]
        sr = await conn.fetchrow(
            "SELECT use_som, use_usd FROM shops WHERE id=$1", shop_id
        )
        use_som = bool(sr["use_som"]) if sr and sr["use_som"] is not None else True
        use_usd = bool(sr["use_usd"]) if sr and sr["use_usd"] is not None else True
    _set_session(message.from_user.id, shop_id, role, user_db_id, shop_name,
                 use_som=use_som, use_usd=use_usd)
    await state.clear()
    role_txt = "👑 Raxbar" if role == "boss" else "👤 Xodim"
    await message.answer(
        f"✅ <b>Kirish muvaffaqiyatli!</b>\n"
        f"🏪 Dokon: <b>{shop_name}</b>\n"
        f"Siz: <b>{role_txt}</b>",
        parse_mode="HTML",
        reply_markup=main_kb(role),
    )


async def _to_choice(message: Message, state: FSMContext):
    await state.set_state(AuthSt.choosing_action)
    await message.answer("Tanlang:", reply_markup=auth_choice_kb())
