from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

from bot.utils.amount_parser import fmt_som  # noqa: F401  — re-export for handlers


def main_kb(role: str = "staff") -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📦 Mahsulotlar"),
        KeyboardButton(text="📥 Kirim"),
    )
    builder.row(
        KeyboardButton(text="💰 Sotish"),
        KeyboardButton(text="👥 Mijozlar"),
    )
    builder.row(
        KeyboardButton(text="🏭 Taminotchilar"),
        KeyboardButton(text="💸 Xarajatlar"),
    )
    if role == "boss":
        builder.row(
            KeyboardButton(text="📊 Hisobotlar"),
            KeyboardButton(text="🏦 Kassa"),
        )
        builder.row(
            KeyboardButton(text="👨‍💼 Xodimlar"),
            KeyboardButton(text="⚙️ Sozlamalar"),
        )
        builder.row(
            KeyboardButton(text="❓ Yordam"),
        )
    else:
        builder.row(
            KeyboardButton(text="📊 Hisobotlar"),
            KeyboardButton(text="❓ Yordam"),
        )
    return builder.as_markup(resize_keyboard=True)


def products_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📋 Ro'yxat"),
        KeyboardButton(text="➕ Qo'shish"),
    )
    builder.row(
        KeyboardButton(text="✏️ Tahrirlash"),
        KeyboardButton(text="🗑️ O'chirish"),
    )
    builder.row(
        KeyboardButton(text="📂 Kategoriyalar"),
        KeyboardButton(text="⚠️ Kam qolganlar"),
    )
    builder.row(KeyboardButton(text="⬅️ Orqaga"))
    return builder.as_markup(resize_keyboard=True)


def purchases_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="➕ Yangi kirim"),
        KeyboardButton(text="📋 Kirim tarixi"),
    )
    builder.row(
        KeyboardButton(text="🏭 Taminotchilar"),
        KeyboardButton(text="⬅️ Orqaga"),
    )
    return builder.as_markup(resize_keyboard=True)


def sales_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="➕ Yangi sotuv"),
        KeyboardButton(text="📋 Sotuv tarixi"),
    )
    builder.row(KeyboardButton(text="⬅️ Orqaga"))
    return builder.as_markup(resize_keyboard=True)


def customers_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📋 Mijozlar ro'yxati"),
        KeyboardButton(text="➕ Yangi mijoz"),
    )
    builder.row(
        KeyboardButton(text="💳 Qarzlar"),
        KeyboardButton(text="💳 Qarz to'lash (mijoz)"),
    )
    builder.row(KeyboardButton(text="⬅️ Orqaga"))
    return builder.as_markup(resize_keyboard=True)


def suppliers_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📋 Taminotchilar ro'yxati"),
        KeyboardButton(text="➕ Yangi taminotchi"),
    )
    builder.row(
        KeyboardButton(text="💳 Taminotchi qarzlar"),
        KeyboardButton(text="💳 Taminotchi qarz to'lash"),
    )
    builder.row(KeyboardButton(text="⬅️ Orqaga"))
    return builder.as_markup(resize_keyboard=True)


def expenses_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="➕ Xarajat qo'shish"),
        KeyboardButton(text="📋 Xarajatlar tarixi"),
    )
    builder.row(KeyboardButton(text="⬅️ Orqaga"))
    return builder.as_markup(resize_keyboard=True)


def reports_kb(role: str = "staff") -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📅 Bugungi hisobot"),
        KeyboardButton(text="📆 Oylik hisobot"),
    )
    if role == "boss":
        builder.row(
            KeyboardButton(text="📊 Excel export"),
            KeyboardButton(text="📄 PDF export"),
        )
        builder.row(
            KeyboardButton(text="📈 Foyda tarixi"),
            KeyboardButton(text="📉 Ombor holati"),
        )
    builder.row(KeyboardButton(text="⬅️ Orqaga"))
    return builder.as_markup(resize_keyboard=True)


def staff_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="👥 Xodimlar ro'yxati"),
        KeyboardButton(text="➕ Xodim qo'shish"),
    )
    builder.row(
        KeyboardButton(text="🗑️ Xodim o'chirish"),
        KeyboardButton(text="⬅️ Orqaga"),
    )
    return builder.as_markup(resize_keyboard=True)


def settings_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="💱 Dollar kursi"),
        KeyboardButton(text="⚠️ Min. qoldiq"),
    )
    builder.row(
        KeyboardButton(text="🏪 Dokon nomi"),
        KeyboardButton(text="🔑 Parol o'zgartirish"),
    )
    builder.row(KeyboardButton(text="⬅️ Orqaga"))
    return builder.as_markup(resize_keyboard=True)


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True
    )


def back_cancel_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="⬅️ Orqaga"),
        KeyboardButton(text="❌ Bekor qilish"),
    )
    return builder.as_markup(resize_keyboard=True)


def yes_no_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="✅ Ha"),
        KeyboardButton(text="❌ Yo'q"),
    )
    return builder.as_markup(resize_keyboard=True)


def auth_choice_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🏪 Yangi dokon ochish"),
        KeyboardButton(text="🔑 Mavjud dokonga kirish"),
    )
    return builder.as_markup(resize_keyboard=True)


def skip_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="⏩ O'tkazib yuborish"),
        KeyboardButton(text="❌ Bekor qilish"),
    )
    return builder.as_markup(resize_keyboard=True)


def expense_categories_kb() -> ReplyKeyboardMarkup:
    cats = ["Ijara", "Maosh", "Transport", "Kommunal", "Reklama", "Ta'mirlash", "Boshqa"]
    builder = ReplyKeyboardBuilder()
    for i in range(0, len(cats), 2):
        row = [KeyboardButton(text=cats[i])]
        if i + 1 < len(cats):
            row.append(KeyboardButton(text=cats[i + 1]))
        builder.row(*row)
    builder.row(KeyboardButton(text="❌ Bekor qilish"))
    return builder.as_markup(resize_keyboard=True)


def inline_items_kb(items: list, prefix: str, page: int = 0, per_page: int = 8) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start = page * per_page
    end = start + per_page
    page_items = items[start:end]
    for item in page_items:
        builder.button(
            text=item["label"],
            callback_data=f"{prefix}:{item['id']}"
        )
    builder.adjust(1)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"{prefix}_page:{page-1}"))
    if end < len(items):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"{prefix}_page:{page+1}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="❌ Bekor", callback_data=f"{prefix}_cancel"))
    return builder.as_markup()


def kassa_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="💰 Kassa holati"),
        KeyboardButton(text="💵 Pul topshirish"),
    )
    builder.row(
        KeyboardButton(text="➕ Qo'lda kirim"),
        KeyboardButton(text="➖ Qo'lda chiqim"),
    )
    builder.row(
        KeyboardButton(text="📋 Harakatlar tarixi"),
        KeyboardButton(text="⬅️ Orqaga"),
    )
    return builder.as_markup(resize_keyboard=True)


def payment_method_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💵 Naqd pul", callback_data="pay_method:naxt"),
        InlineKeyboardButton(text="💳 Karta", callback_data="pay_method:karta"),
    ]])


def fmt_money(som: float, usd: float = 0) -> str:
    parts = []
    if som:
        parts.append(f"{fmt_som(som)} so'm")
    if usd:
        parts.append(f"{usd:.2f}$")
    return " | ".join(parts) if parts else "0 so'm"
