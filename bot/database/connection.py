import asyncpg
from bot.config import DATABASE_URL

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _pool


async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(_SCHEMA)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS shops (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    login VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
-- migrations
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_name='shops' AND column_name='login') THEN
    ALTER TABLE shops ADD COLUMN login VARCHAR(100) UNIQUE;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_name='shops' AND column_name='use_usd') THEN
    ALTER TABLE shops ADD COLUMN use_usd BOOLEAN DEFAULT TRUE;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_name='shops' AND column_name='use_som') THEN
    ALTER TABLE shops ADD COLUMN use_som BOOLEAN DEFAULT TRUE;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS shop_users (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER REFERENCES shops(id) ON DELETE CASCADE,
    telegram_id BIGINT NOT NULL,
    username VARCHAR(255),
    full_name VARCHAR(255),
    role VARCHAR(20) DEFAULT 'staff' CHECK (role IN ('boss', 'staff')),
    is_active BOOLEAN DEFAULT TRUE,
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(shop_id, telegram_id)
);

CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER REFERENCES shops(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    UNIQUE(shop_id, name)
);

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER REFERENCES shops(id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    barcode VARCHAR(100),
    buy_price_som NUMERIC(15,2) DEFAULT 0,
    buy_price_usd NUMERIC(12,4) DEFAULT 0,
    sell_price_som NUMERIC(15,2) DEFAULT 0,
    sell_price_usd NUMERIC(12,4) DEFAULT 0,
    stock_qty NUMERIC(12,3) DEFAULT 0,
    min_stock_qty NUMERIC(12,3) DEFAULT 5,
    unit VARCHAR(50) DEFAULT 'dona',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS suppliers (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER REFERENCES shops(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    debt_som NUMERIC(15,2) DEFAULT 0,
    debt_usd NUMERIC(12,4) DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS purchases (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER REFERENCES shops(id) ON DELETE CASCADE,
    supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
    date DATE DEFAULT CURRENT_DATE,
    total_som NUMERIC(15,2) DEFAULT 0,
    total_usd NUMERIC(12,4) DEFAULT 0,
    paid_som NUMERIC(15,2) DEFAULT 0,
    paid_usd NUMERIC(12,4) DEFAULT 0,
    notes TEXT,
    created_by BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS purchase_items (
    id SERIAL PRIMARY KEY,
    purchase_id INTEGER REFERENCES purchases(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id) ON DELETE RESTRICT,
    qty NUMERIC(12,3) NOT NULL,
    price_som NUMERIC(15,2) DEFAULT 0,
    price_usd NUMERIC(12,4) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER REFERENCES shops(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    telegram_id BIGINT,
    debt_som NUMERIC(15,2) DEFAULT 0,
    debt_usd NUMERIC(12,4) DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sales (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER REFERENCES shops(id) ON DELETE CASCADE,
    customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL,
    date DATE DEFAULT CURRENT_DATE,
    total_som NUMERIC(15,2) DEFAULT 0,
    total_usd NUMERIC(12,4) DEFAULT 0,
    paid_som NUMERIC(15,2) DEFAULT 0,
    paid_usd NUMERIC(12,4) DEFAULT 0,
    discount_som NUMERIC(15,2) DEFAULT 0,
    change_som NUMERIC(15,2) DEFAULT 0,
    notes TEXT,
    created_by BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sale_items (
    id SERIAL PRIMARY KEY,
    sale_id INTEGER REFERENCES sales(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id) ON DELETE RESTRICT,
    qty NUMERIC(12,3) NOT NULL,
    sell_price_som NUMERIC(15,2) DEFAULT 0,
    sell_price_usd NUMERIC(12,4) DEFAULT 0,
    discount_som NUMERIC(15,2) DEFAULT 0,
    cost_price_som NUMERIC(15,2) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS expenses (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER REFERENCES shops(id) ON DELETE CASCADE,
    category VARCHAR(100) DEFAULT 'Boshqa',
    amount_som NUMERIC(15,2) DEFAULT 0,
    amount_usd NUMERIC(12,4) DEFAULT 0,
    description TEXT,
    date DATE DEFAULT CURRENT_DATE,
    created_by BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS debt_payments (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER REFERENCES shops(id) ON DELETE CASCADE,
    payment_type VARCHAR(20) CHECK (payment_type IN ('supplier', 'customer')),
    entity_id INTEGER NOT NULL,
    amount_som NUMERIC(15,2) DEFAULT 0,
    amount_usd NUMERIC(12,4) DEFAULT 0,
    date DATE DEFAULT CURRENT_DATE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS usd_rates (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER REFERENCES shops(id) ON DELETE CASCADE,
    rate NUMERIC(10,2) NOT NULL,
    set_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_reports (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER REFERENCES shops(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    total_sales_som NUMERIC(15,2) DEFAULT 0,
    total_sales_usd NUMERIC(12,4) DEFAULT 0,
    cost_of_goods_som NUMERIC(15,2) DEFAULT 0,
    gross_profit_som NUMERIC(15,2) DEFAULT 0,
    total_expenses_som NUMERIC(15,2) DEFAULT 0,
    net_profit_som NUMERIC(15,2) DEFAULT 0,
    sales_count INTEGER DEFAULT 0,
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(shop_id, date)
);

CREATE TABLE IF NOT EXISTS kassa (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    naxt_som NUMERIC(15,2) DEFAULT 0,
    karta_som NUMERIC(15,2) DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(shop_id)
);

CREATE TABLE IF NOT EXISTS kassa_movements (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    movement_type VARCHAR(20) NOT NULL,
    method VARCHAR(10) DEFAULT 'naxt',
    amount_som NUMERIC(15,2) NOT NULL,
    note TEXT,
    recipient VARCHAR(255),
    created_by BIGINT,
    date DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- migration: sales jadvaliga payment_method ustuni qo'shish
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_name='sales' AND column_name='payment_method') THEN
    ALTER TABLE sales ADD COLUMN payment_method VARCHAR(10) DEFAULT 'naxt';
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_products_shop ON products(shop_id);
CREATE INDEX IF NOT EXISTS idx_products_active ON products(shop_id, is_active);
CREATE INDEX IF NOT EXISTS idx_sales_shop_date ON sales(shop_id, date);
CREATE INDEX IF NOT EXISTS idx_purchases_shop_date ON purchases(shop_id, date);
CREATE INDEX IF NOT EXISTS idx_expenses_shop_date ON expenses(shop_id, date);
CREATE INDEX IF NOT EXISTS idx_shop_users_tg ON shop_users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_shop_users_shop ON shop_users(shop_id);
"""
