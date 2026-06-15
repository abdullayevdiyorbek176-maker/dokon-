import logging
from datetime import date
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot

from bot.config import REPORT_HOUR, REPORT_MINUTE
from bot.database.connection import get_pool
from bot.services.report_service import get_daily_report, format_daily_report

log = logging.getLogger(__name__)


async def send_daily_reports(bot: Bot):
    pool = await get_pool()
    async with pool.acquire() as conn:
        shops = await conn.fetch("SELECT id, name FROM shops WHERE is_active=TRUE")
        for shop in shops:
            try:
                report = await get_daily_report(shop["id"], date.today())
                text = format_daily_report(report)
                bosses = await conn.fetch(
                    """SELECT telegram_id FROM shop_users
                       WHERE shop_id=$1 AND role='boss' AND is_active=TRUE""",
                    shop["id"]
                )
                for boss in bosses:
                    try:
                        await bot.send_message(boss["telegram_id"], text, parse_mode="HTML")
                    except Exception as e:
                        log.warning(f"Boss {boss['telegram_id']} ga yuborib bo'lmadi: {e}")
                await conn.execute(
                    """INSERT INTO daily_reports
                       (shop_id, date, total_sales_som, total_sales_usd, cost_of_goods_som,
                        gross_profit_som, total_expenses_som, net_profit_som, sales_count)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                       ON CONFLICT (shop_id, date) DO UPDATE SET
                       total_sales_som=EXCLUDED.total_sales_som,
                       total_sales_usd=EXCLUDED.total_sales_usd,
                       cost_of_goods_som=EXCLUDED.cost_of_goods_som,
                       gross_profit_som=EXCLUDED.gross_profit_som,
                       total_expenses_som=EXCLUDED.total_expenses_som,
                       net_profit_som=EXCLUDED.net_profit_som,
                       sales_count=EXCLUDED.sales_count,
                       generated_at=NOW()""",
                    shop["id"], date.today(),
                    report["total_som"], report["total_usd"], report["cost_som"],
                    report["gross_profit"], report["expenses_som"], report["net_profit"],
                    report["sales_count"]
                )
            except Exception as e:
                log.error(f"Dokon {shop['id']} hisoboti xatosi: {e}")


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")
    scheduler.add_job(
        send_daily_reports,
        CronTrigger(hour=REPORT_HOUR, minute=REPORT_MINUTE, timezone="Asia/Tashkent"),
        args=[bot],
        id="daily_report",
        replace_existing=True,
    )
    return scheduler
