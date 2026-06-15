import io
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from bot.database.connection import get_pool

MONTHS_UZ = ["Yanvar","Fevral","Mart","Aprel","May","Iyun",
              "Iyul","Avgust","Sentabr","Oktabr","Noyabr","Dekabr"]

_styles = getSampleStyleSheet()
_title_style = ParagraphStyle("Title", parent=_styles["Heading1"], fontSize=16, spaceAfter=12)
_h2_style = ParagraphStyle("H2", parent=_styles["Heading2"], fontSize=12, spaceAfter=8)
_normal = _styles["Normal"]

_TABLE_HEADER = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E5FA3")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0F4FF")]),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
])


def _fmt(v: float) -> str:
    return f"{v:,.0f}"


async def generate_daily_pdf(shop_id: int, report_date: date) -> bytes:
    pool = await get_pool()
    async with pool.acquire() as conn:
        shop = await conn.fetchrow("SELECT name FROM shops WHERE id=$1", shop_id)
        sales_rows = await conn.fetch(
            """SELECT s.total_som, s.paid_som, COALESCE(c.name,'Naqd') as cust,
               (SELECT COALESCE(SUM(si.qty*si.cost_price_som),0) FROM sale_items si WHERE si.sale_id=s.id) as cost
               FROM sales s LEFT JOIN customers c ON c.id=s.customer_id
               WHERE s.shop_id=$1 AND s.date=$2 ORDER BY s.created_at""",
            shop_id, report_date
        )
        expenses = await conn.fetch(
            "SELECT category, amount_som, description FROM expenses WHERE shop_id=$1 AND date=$2",
            shop_id, report_date
        )
        top = await conn.fetch(
            """SELECT p.name, SUM(si.qty) as qty, SUM(si.qty*si.sell_price_som) as rev
               FROM sale_items si JOIN sales s ON s.id=si.sale_id JOIN products p ON p.id=si.product_id
               WHERE s.shop_id=$1 AND s.date=$2 GROUP BY p.name ORDER BY rev DESC LIMIT 8""",
            shop_id, report_date
        )
        low = await conn.fetch(
            """SELECT name, stock_qty, unit FROM products
               WHERE shop_id=$1 AND is_active=TRUE AND stock_qty <= min_stock_qty ORDER BY stock_qty""",
            shop_id
        )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm,
                            topMargin=2*cm, bottomMargin=1.5*cm)
    story = []
    story.append(Paragraph(f"{shop['name']}", _title_style))
    story.append(Paragraph(f"Kunlik hisobot — {report_date.strftime('%d.%m.%Y')}", _h2_style))
    story.append(Spacer(1, 0.3*cm))

    total_sales = sum(float(r["total_som"]) for r in sales_rows)
    total_cost = sum(float(r["cost"]) for r in sales_rows)
    total_paid = sum(float(r["paid_som"]) for r in sales_rows)
    total_exp = sum(float(r["amount_som"]) for r in expenses)
    gross = total_sales - total_cost
    net = gross - total_exp

    summary_data = [
        ["Ko'rsatkich", "Miqdor (so'm)"],
        ["Jami sotuv", _fmt(total_sales)],
        ["Mahsulot tannarxi", _fmt(total_cost)],
        ["Yalpi foyda", _fmt(gross)],
        ["Xarajatlar", _fmt(total_exp)],
        ["SOF FOYDA", _fmt(net)],
        ["Qarzlar", _fmt(total_sales - total_paid)],
    ]
    t = Table(summary_data, colWidths=[8*cm, 7*cm])
    t.setStyle(TableStyle([
        *_TABLE_HEADER._cmds,
        ("FONTNAME", (0, 6), (-1, 6), "Helvetica-Bold"),
        ("BACKGROUND", (0, 6), (-1, 6), colors.HexColor("#E8F5E9")),
        ("FONTSIZE", (0, 6), (-1, 6), 11),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5*cm))

    if sales_rows:
        story.append(Paragraph("Sotuvlar", _h2_style))
        data = [["#", "Mijoz", "Jami (so'm)", "To'landi", "Qarz"]]
        for i, s in enumerate(sales_rows, 1):
            debt = float(s["total_som"]) - float(s["paid_som"])
            data.append([i, s["cust"], _fmt(float(s["total_som"])), _fmt(float(s["paid_som"])), _fmt(debt)])
        t2 = Table(data, colWidths=[1*cm, 6*cm, 4*cm, 4*cm, 4*cm])
        t2.setStyle(_TABLE_HEADER)
        story.append(t2)
        story.append(Spacer(1, 0.5*cm))

    if top:
        story.append(Paragraph("Eng ko'p sotilgan mahsulotlar", _h2_style))
        data = [["Mahsulot", "Miqdor", "Summa (so'm)"]]
        for p in top:
            data.append([p["name"], f"{p['qty']:g}", _fmt(float(p["rev"]))])
        t3 = Table(data, colWidths=[9*cm, 3*cm, 7*cm])
        t3.setStyle(_TABLE_HEADER)
        story.append(t3)

    if low:
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph("⚠️ Kam qolgan mahsulotlar", _h2_style))
        data = [["Mahsulot", "Qoldiq", "Birlik"]]
        for p in low:
            data.append([p["name"], f"{p['stock_qty']:g}", p["unit"]])
        t4 = Table(data, colWidths=[10*cm, 4*cm, 5*cm])
        t4.setStyle(_TABLE_HEADER)
        story.append(t4)

    doc.build(story)
    buf.seek(0)
    return buf.read()


async def generate_monthly_pdf(shop_id: int, year: int, month: int) -> bytes:
    from calendar import monthrange
    _, last_day = monthrange(year, month)
    start = date(year, month, 1)
    end = date(year, month, last_day)
    pool = await get_pool()
    async with pool.acquire() as conn:
        shop = await conn.fetchrow("SELECT name FROM shops WHERE id=$1", shop_id)
        daily = await conn.fetch(
            """SELECT s.date,
               COALESCE(SUM(s.total_som),0) as sales,
               (SELECT COALESCE(SUM(e.amount_som),0) FROM expenses e WHERE e.shop_id=$1 AND e.date=s.date) as exp,
               COALESCE(SUM(si.qty*si.cost_price_som),0) as cost
               FROM sales s JOIN sale_items si ON si.sale_id=s.id
               WHERE s.shop_id=$1 AND s.date BETWEEN $2 AND $3
               GROUP BY s.date ORDER BY s.date""",
            shop_id, start, end
        )
        exp_cat = await conn.fetch(
            """SELECT category, SUM(amount_som) as total FROM expenses
               WHERE shop_id=$1 AND date BETWEEN $2 AND $3 GROUP BY category ORDER BY total DESC""",
            shop_id, start, end
        )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm,
                            topMargin=2*cm, bottomMargin=1.5*cm)
    story = []
    story.append(Paragraph(f"{shop['name']}", _title_style))
    story.append(Paragraph(f"Oylik hisobot — {MONTHS_UZ[month-1]} {year}", _h2_style))

    total_s = sum(float(r["sales"]) for r in daily)
    total_c = sum(float(r["cost"]) for r in daily)
    total_e = sum(float(r["exp"]) for r in daily)
    gross = total_s - total_c
    net = gross - total_e

    summary = [
        ["Ko'rsatkich", "Miqdor (so'm)"],
        ["Jami sotuv", _fmt(total_s)],
        ["Tannarx", _fmt(total_c)],
        ["Yalpi foyda", _fmt(gross)],
        ["Xarajatlar", _fmt(total_e)],
        ["SOF FOYDA", _fmt(net)],
    ]
    t = Table(summary, colWidths=[8*cm, 7*cm])
    t.setStyle(TableStyle([
        *_TABLE_HEADER._cmds,
        ("FONTNAME", (0, 5), (-1, 5), "Helvetica-Bold"),
        ("BACKGROUND", (0, 5), (-1, 5), colors.HexColor("#E8F5E9")),
        ("FONTSIZE", (0, 5), (-1, 5), 11),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5*cm))

    if daily:
        story.append(Paragraph("Kunlik ko'rsatkichlar", _h2_style))
        data = [["Sana", "Sotuv", "Tannarx", "Xarajat", "Sof foyda"]]
        for d in daily:
            s = float(d["sales"]); c = float(d["cost"]); e = float(d["exp"])
            data.append([str(d["date"]), _fmt(s), _fmt(c), _fmt(e), _fmt(s-c-e)])
        t2 = Table(data, colWidths=[3*cm, 4*cm, 4*cm, 4*cm, 4*cm])
        t2.setStyle(_TABLE_HEADER)
        story.append(t2)

    if exp_cat:
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph("Xarajat turlari", _h2_style))
        data = [["Tur", "Jami (so'm)"]]
        for ec in exp_cat:
            data.append([ec["category"], _fmt(float(ec["total"]))])
        t3 = Table(data, colWidths=[10*cm, 9*cm])
        t3.setStyle(_TABLE_HEADER)
        story.append(t3)

    doc.build(story)
    buf.seek(0)
    return buf.read()
