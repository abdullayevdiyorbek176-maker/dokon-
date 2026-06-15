import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from bot.config import BOT_TOKEN
from bot.database.connection import init_db
from bot.middlewares.auth_middleware import AuthMiddleware
from bot.services.scheduler import setup_scheduler

from bot.handlers import (
    auth,
    common,
    products,
    purchases,
    sales,
    customers,
    suppliers,
    expenses,
    reports,
    staff,
    settings,
    kassa,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN o'rnatilmagan! .env faylini tekshiring.")

    log.info("Bot ishga tushmoqda...")
    await init_db()
    log.info("Bazа tayyyor.")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.outer_middleware(AuthMiddleware())
    dp.callback_query.outer_middleware(AuthMiddleware())

    dp.include_router(auth.router)
    dp.include_router(products.router)
    dp.include_router(purchases.router)
    dp.include_router(sales.router)
    dp.include_router(customers.router)
    dp.include_router(suppliers.router)
    dp.include_router(expenses.router)
    dp.include_router(reports.router)
    dp.include_router(staff.router)
    dp.include_router(settings.router)
    dp.include_router(kassa.router)
    dp.include_router(common.router)

    scheduler = setup_scheduler(bot)
    scheduler.start()
    log.info(f"Scheduler ishga tushdi (hisobot soati: {scheduler.get_jobs()[0].trigger})")

    await bot.delete_webhook(drop_pending_updates=True)
    log.info("Polling boshlandi...")
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
