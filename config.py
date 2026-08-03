"""config.py — Load all environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_IDS: list[int] = [
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
]

UPI_ID: str      = os.getenv("UPI_ID", "example@upi")
SHOP_NAME: str   = os.getenv("SHOP_NAME", "VoucherStore")
BOT_NAME: str    = os.getenv("BOT_NAME", "VoucherBot")

DATABASE_URL: str | None = os.getenv("DATABASE_URL")   # None → use SQLite

PORT: int                = int(os.getenv("PORT", "8000"))
RENDER_EXTERNAL_URL: str = os.getenv("RENDER_EXTERNAL_URL", "")

ORDER_EXPIRY_MINUTES: int = int(os.getenv("ORDER_EXPIRY_MINUTES", "10"))
