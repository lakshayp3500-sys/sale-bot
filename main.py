"""
main.py — Bot entry point.

* aiogram 3.x polling
* aiohttp web server   → /ping + /health
* Self-ping every 5 min to prevent Render free tier sleep
* Order expiry loop every 60 seconds
"""

import asyncio
import logging
import sys

import aiohttp
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_IDS, PORT, RENDER_EXTERNAL_URL
from database import init_db
from order_manager import expire_orders
from handlers import start, buy, orders, admin, support

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ── SELF-PING ─────────────────────────────────────────────────────────────────

async def self_ping():
    """Ping /ping every 5 minutes → prevents Render free tier sleep."""
    if not RENDER_EXTERNAL_URL:
        logger.info("RENDER_EXTERNAL_URL not set — self-ping disabled.")
        return

    url = f"{RENDER_EXTERNAL_URL.rstrip('/')}/ping"
    await asyncio.sleep(60)          # 1 min warm-up
    while True:
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    logger.info(f"Self-ping {resp.status}")
        except Exception as e:
            logger.warning(f"Self-ping failed: {e}")
        await asyncio.sleep(300)     # every 5 min


# ── ORDER EXPIRY LOOP ─────────────────────────────────────────────────────────

async def expiry_loop(bot: Bot):
    """Expire old pending orders and notify users every 60 seconds."""
    while True:
        await asyncio.sleep(60)
        try:
            for order in expire_orders():
                try:
                    await bot.send_message(
                        order["user_id"],
                        f"⌛ <b>Order Expired</b>\n\n"
                        f"🆔 Order <code>#{order['id']}</code> has expired "
                        f"because payment was not received in time.\n\n"
                        f"You can place a new order anytime 👇",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Expiry loop error: {e}")


# ── WEB SERVER ────────────────────────────────────────────────────────────────

async def ping_handler(request: web.Request) -> web.Response:
    return web.Response(text="pong")


async def health_handler(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


# ── MAIN ──────────────────────────────────────────────────────────────────────

async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set!")
        sys.exit(1)

    if not ADMIN_IDS:
        logger.warning("ADMIN_IDS is empty — admin panel will be inaccessible.")

    try:
        init_db()
        logger.info("Database ready.")
    except Exception as e:
        logger.error(f"DB init failed: {e}")
        sys.exit(1)

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Register all routers in priority order
    dp.include_router(start.router)
    dp.include_router(buy.router)
    dp.include_router(orders.router)
    dp.include_router(support.router)
    dp.include_router(admin.router)

    # Start web server
    app = web.Application()
    app.router.add_get("/ping",   ping_handler)
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    logger.info(f"Web server on port {PORT}")

    # Background tasks
    asyncio.create_task(self_ping())
    asyncio.create_task(expiry_loop(bot))

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Polling started.")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await runner.cleanup()
        await dp.storage.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped.")
