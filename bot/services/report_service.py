from datetime import date, timedelta
from bot.database.connection import get_pool


async def get_daily_report(shop_id: int, report_date: date = None) -> dict:
    if report_date is None:
        report_date = date.today()
    pool = await get_pool()
    async with pool.acquire() as conn:
        sales = await conn.fetchrow(
            """SELECT
               COUNT(*) as cnt,
               COALESCE(SUM(total_som),0) as total_som,
               COALESCE(SUM(total_usd),0) as total_usd,
               COALESCE(SUM(paid_som),0) as paid_som,
               COALESCE(SUM(paid_usd),0) as paid_usd
               FROM sales WHERE shop_id=$1 AND date=$2""",
            shop_id, report_date
        )
        cost = await conn.fetchval(
            """SELECT COALESCE(SUM(si.qty * si.cost_price_som),0)
               FROM sale_items si
               JOIN sales s ON s.id=si.sale_id
               WHERE s.shop_id=$1 AND s.date=$2""",
            shop_id, report_date
        )
        expenses = await conn.fetchrow(
            """SELECT COALESCE(SUM(amount_som),0) as som, COALESCE(SUM(amount_usd),0) as usd
               FROM expenses WHERE shop_id=$1 AND date=$2""",
            shop_id, report_date
        )
        purchases = await conn.fetchrow(
            """SELECT COALESCE(SUM(total_som),0) as som FROM purchases WHERE shop_id=$1 AND date=$2""",
            shop_id, report_date
        )
        low_stock = await conn.fetch(
            """SELECT name, stock_qty, min_stock_qty, unit FROM products
               WHERE shop_id=$1 AND is_active=TRUE AND stock_qty <= min_stock_qty
               ORDER BY stock_qty LIMIT 10""",
            shop_id
        )
        top_products = await conn.fetch(
            """SELECT p.name, SUM(si.qty) as qty, SUM(si.qty*si.sell_price_som) as revenue
               FROM sale_items si
               JOIN sales s ON s.id=si.sale_id
               JOIN products p ON p.id=si.product_id
               WHERE s.shop_id=$1 AND s.date=$2
               GROUP BY p.name ORDER BY revenue DESC LIMIT 5""",
            shop_id, report_date
        )
        new_debts = await conn.fetchval(
            """SELECT COALESCE(SUM(total_som-paid_som),0) FROM sales
               WHERE shop_id=$1 AND date=$2 AND total_som > paid_som""",
            shop_id, report_date
        )

    total_som = float(sales["total_som"])
    cost_som = float(cost)
    expenses_som = float(expenses["som"])
    gross_profit = total_som - cost_som
    net_profit = gross_profit - expenses_som

    return {
        "date": report_date,
        "sales_count": sales["cnt"],
        "total_som": total_som,
        "total_usd": float(sales["total_usd"]),
        "paid_som": float(sales["paid_som"]),
        "cost_som": cost_som,
        "gross_profit": gross_profit,
        "expenses_som": expenses_som,
        "expenses_usd": float(expenses["usd"]),
        "net_profit": net_profit,
        "purchases_som": float(purchases["som"]),
        "new_debts": float(new_debts),
        "low_stock": [dict(r) for r in low_stock],
        "top_products": [dict(r) for r in top_products],
    }


async def get_monthly_report(shop_id: int, year: int, month: int) -> dict:
    from calendar import monthrange
    _, last_day = monthrange(year, month)
    start = date(year, month, 1)
    end = date(year, month, last_day)
    pool = await get_pool()
    async with pool.acquire() as conn:
        sales = await conn.fetchrow(
            """SELECT COUNT(*) as cnt,
               COALESCE(SUM(total_som),0) as total_som,
               COALESCE(SUM(total_usd),0) as total_usd
               FROM sales WHERE shop_id=$1 AND date BETWEEN $2 AND $3""",
            shop_id, start, end
        )
        cost = await conn.fetchval(
            """SELECT COALESCE(SUM(si.qty * si.cost_price_som),0)
               FROM sale_items si JOIN sales s ON s.id=si.sale_id
               WHERE s.shop_id=$1 AND s.date BETWEEN $2 AND $3""",
            shop_id, start, end
        )
        expenses = await conn.fetchrow(
            """SELECT COALESCE(SUM(amount_som),0) as som FROM expenses
               WHERE shop_id=$1 AND date BETWEEN $2 AND $3""",
            shop_id, start, end
        )
        purchases = await conn.fetchrow(
            """SELECT COALESCE(SUM(total_som),0) as som FROM purchases
               WHERE shop_id=$1 AND date BETWEEN $2 AND $3""",
            shop_id, start, end
        )
        top_products = await conn.fetch(
            """SELECT p.name, SUM(si.qty) as qty, SUM(si.qty*si.sell_price_som) as revenue
               FROM sale_items si JOIN sales s ON s.id=si.sale_id JOIN products p ON p.id=si.product_id
               WHERE s.shop_id=$1 AND s.date BETWEEN $2 AND $3
               GROUP BY p.name ORDER BY revenue DESC LIMIT 10""",
            shop_id, start, end
        )
        daily = await conn.fetch(
            """SELECT date,
               COALESCE(SUM(total_som),0) as sales,
               (SELECT COALESCE(SUM(e.amount_som),0) FROM expenses e WHERE e.shop_id=$1 AND e.date=s.date) as exp
               FROM sales s WHERE s.shop_id=$1 AND date BETWEEN $2 AND $3
               GROUP BY date ORDER BY date""",
            shop_id, start, end
        )
        exp_by_cat = await conn.fetch(
            """SELECT category, COALESCE(SUM(amount_som),0) as total FROM expenses
               WHERE shop_id=$1 AND date BETWEEN $2 AND $3 GROUP BY category ORDER BY total DESC""",
            shop_id, start, end
        )

    total_som = float(sales["total_som"])
    cost_som = float(cost)
    expenses_som = float(expenses["som"])
    gross_profit = total_som - cost_som
    net_profit = gross_profit - expenses_som

    return {
        "year": year, "month": month,
        "sales_count": sales["cnt"],
        "total_som": total_som,
        "total_usd": float(sales["total_usd"]),
        "cost_som": cost_som,
        "gross_profit": gross_profit,
        "expenses_som": expenses_som,
        "net_profit": net_profit,
        "purchases_som": float(purchases["som"]),
        "top_products": [dict(r) for r in top_products],
        "daily": [dict(r) for r in daily],
        "exp_by_cat": [dict(r) for r in exp_by_cat],
    }


def format_daily_report(r: dict) -> str:
    txt = (
        f"📊 <b>Kunlik hisobot — {r['date'].strftime('%d.%m.%Y')}</b>\n\n"
        f"🛒 Sotuvlar: {r['sales_count']} ta | {r['total_som']:,.0f} so'm"
    )
    if r["total_usd"]:
        txt += f" | {r['total_usd']:.2f}$"
    txt += (
        f"\n💸 Mahsulot tannarxi: {r['cost_som']:,.0f} so'm"
        f"\n📈 Yalpi foyda: {r['gross_profit']:,.0f} so'm"
        f"\n🏷️ Xarajatlar: {r['expenses_som']:,.0f} so'm"
        f"\n\n💰 <b>SOF FOYDA: {r['net_profit']:,.0f} so'm</b>"
    )
    if r["new_debts"]:
        txt += f"\n💳 Yangi qarzlar: {r['new_debts']:,.0f} so'm"
    if r["purchases_som"]:
        txt += f"\n📦 Kirimlar: {r['purchases_som']:,.0f} so'm"
    if r["top_products"]:
        txt += "\n\n🏆 <b>Eng ko'p sotilgan:</b>\n"
        for i, p in enumerate(r["top_products"], 1):
            txt += f"{i}. {p['name']} — {p['qty']:g} ta | {p['revenue']:,.0f} so'm\n"
    if r["low_stock"]:
        txt += "\n⚠️ <b>Kam qolganlar:</b>\n"
        for p in r["low_stock"]:
            txt += f"• {p['name']}: {p['stock_qty']:g} {p['unit']}\n"
    return txt


def format_monthly_report(r: dict) -> str:
    import calendar
    month_name = [
        "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
        "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"
    ][r["month"] - 1]
    txt = (
        f"📆 <b>Oylik hisobot — {month_name} {r['year']}</b>\n\n"
        f"🛒 Sotuvlar: {r['sales_count']} ta | {r['total_som']:,.0f} so'm\n"
        f"💸 Tannarx: {r['cost_som']:,.0f} so'm\n"
        f"📈 Yalpi foyda: {r['gross_profit']:,.0f} so'm\n"
        f"🏷️ Xarajatlar: {r['expenses_som']:,.0f} so'm\n"
        f"\n💰 <b>SOF FOYDA: {r['net_profit']:,.0f} so'm</b>"
    )
    if r["exp_by_cat"]:
        txt += "\n\n💸 <b>Xarajat turlari:</b>\n"
        for c in r["exp_by_cat"]:
            txt += f"• {c['category']}: {c['total']:,.0f} so'm\n"
    if r["top_products"]:
        txt += "\n🏆 <b>TOP 10 mahsulot:</b>\n"
        for i, p in enumerate(r["top_products"], 1):
            txt += f"{i}. {p['name']} — {p['qty']:g} ta | {p['revenue']:,.0f} so'm\n"
    return txt
