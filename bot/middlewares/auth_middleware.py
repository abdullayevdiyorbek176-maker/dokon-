from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

user_sessions: Dict[int, Dict] = {}


async def _restore_session(user_id: int) -> Dict:
    """DBdan sessiyani tiklaydi. Topilmasa bo'sh dict qaytaradi."""
    try:
        from bot.database.connection import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT su.id, su.role, su.shop_id,
                          s.name AS shop_name, s.use_som, s.use_usd
                   FROM shop_users su
                   JOIN shops s ON s.id = su.shop_id
                   WHERE su.telegram_id = $1
                     AND su.is_active = TRUE
                     AND s.is_active = TRUE
                   ORDER BY su.joined_at DESC
                   LIMIT 1""",
                user_id
            )
        if row:
            return {
                "shop_id":   row["shop_id"],
                "role":      row["role"],
                "user_db_id": row["id"],
                "shop_name": row["shop_name"],
                "use_som":   bool(row["use_som"]) if row["use_som"] is not None else True,
                "use_usd":   bool(row["use_usd"]) if row["use_usd"] is not None else True,
            }
    except Exception:
        pass
    return {}


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = None
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id

        if user_id:
            session = user_sessions.get(user_id, {})

            # Sessiya bo'sh bo'lsa — DBdan tiklashga urini
            if not session.get("shop_id"):
                session = await _restore_session(user_id)
                if session.get("shop_id"):
                    user_sessions[user_id] = session

            data["shop_id"]    = session.get("shop_id")
            data["role"]       = session.get("role")
            data["user_db_id"] = session.get("user_db_id")
            data["shop_name"]  = session.get("shop_name")
            data["use_som"]    = session.get("use_som", True)
            data["use_usd"]    = session.get("use_usd", True)
        else:
            data["shop_id"]    = None
            data["role"]       = None
            data["user_db_id"] = None
            data["shop_name"]  = None
            data["use_som"]    = True
            data["use_usd"]    = True

        return await handler(event, data)
