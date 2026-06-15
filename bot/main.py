import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from bot.config import BOT_TOKEN
from bot.database.connection import init_db
from bot.middlewares.auth_middleware import AuthMiddleware
from bot.services.scheduler import setup_scheduler

from bot.handlers import (
    auth, common, products, purchases, sales,
    customers, suppliers, expenses, reports,
    staff, settings, kassa,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
WEBHOOK_PATH = "/telegram"
PORT = int(os.getenv("PORT", 8000))


def _build_dp(bot: Bot) -> Dispatcher:
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
    return dp


# ─── POLLING (lokal ishlab chiqish) ───────────────────────────────────────

async def run_polling():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN o'rnatilmagan!")
    log.info("Polling rejimi...")
    await init_db()
    log.info("DB tayyyor.")
    bot = Bot(token=BOT_TOKEN,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = _build_dp(bot)
    scheduler = setup_scheduler(bot)
    scheduler.start()
    log.info(f"Scheduler ishga tushdi.")
    await bot.delete_webhook(drop_pending_updates=True)
    log.info("Polling boshlandi...")
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        scheduler.shutdown()
        await bot.session.close()


# ─── WEBHOOK (Render / cloud) ─────────────────────────────────────────────

def run_webhook():
    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN o'rnatilmagan!")
    log.info(f"Webhook rejimi: {WEBHOOK_URL}")

    bot = Bot(token=BOT_TOKEN,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = _build_dp(bot)
    scheduler = setup_scheduler(bot)

    async def on_startup(_app):
        await init_db()
        log.info("DB tayyyor.")
        scheduler.start()
        log.info("Scheduler ishga tushdi.")
        await bot.set_webhook(f"{WEBHOOK_URL}{WEBHOOK_PATH}",
                              drop_pending_updates=True)
        log.info("Webhook o'rnatildi.")

    async def on_shutdown(_app):
        scheduler.shutdown()
        await bot.delete_webhook()
        await bot.session.close()

    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    # UptimeRobot va Render health-check uchun
    async def health(_request):
        return web.Response(text="OK")
    app.router.add_get("/", health)

    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    log.info(f"Server port={PORT}")
    web.run_app(app, host="0.0.0.0", port=PORT)


# ─── MAIN ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if WEBHOOK_URL:
        run_webhook()
    else:
        asyncio.run(run_polling())
