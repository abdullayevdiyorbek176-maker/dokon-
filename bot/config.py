import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

_db_url = os.getenv("DATABASE_URL", "")
# Railway postgres:// → asyncpg postgresql:// formatiga o'girish
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)
DATABASE_URL: str = _db_url

ADMIN_IDS: list = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
USD_RATE: float = float(os.getenv("USD_RATE", "12700"))
REPORT_HOUR: int = int(os.getenv("REPORT_HOUR", "22"))
REPORT_MINUTE: int = int(os.getenv("REPORT_MINUTE", "0"))
