import os
import asyncio
import logging

from aiohttp import web
from aiogram.types import Update

# Reuse the existing Games Vault Shop bot, catalog and handlers.
# Importing gamesvaultshop.py does NOT start polling because its main()
# is protected by if __name__ == "__main__".
from gamesvaultshop import bot, dp


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

PORT = int(os.getenv("PORT", "10000"))
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
WEBHOOK_PATH = "/telegram/webhook"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")


async def health(request: web.Request) -> web.Response:
    return web.Response(text="Games Vault Shop is running")


async def webhook(request: web.Request) -> web.Response:
    if WEBHOOK_SECRET:
        received_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if received_secret != WEBHOOK_SECRET:
            return web.Response(status=403, text="Forbidden")

    try:
        data = await request.json()
        update = Update.model_validate(data)
        await dp.feed_update(bot, update)
        return web.Response(text="OK")
    except Exception:
        logging.exception("Webhook update processing failed")
        return web.Response(status=500, text="Internal Server Error")


async def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    app.router.add_post(WEBHOOK_PATH, webhook)

    webhook_url = WEBHOOK_URL or (
        f"{RENDER_EXTERNAL_URL}{WEBHOOK_PATH}" if RENDER_EXTERNAL_URL else ""
    )

    if not webhook_url:
        raise RuntimeError(
            "WEBHOOK_URL или RENDER_EXTERNAL_URL не задан. "
            "Для Render добавь RENDER_EXTERNAL_URL, например https://your-service.onrender.com."
        )

    logging.info("Setting Telegram webhook: %s", webhook_url)

    webhook_kwargs = {"url": webhook_url, "drop_pending_updates": True}
    if WEBHOOK_SECRET:
        webhook_kwargs["secret_token"] = WEBHOOK_SECRET

    await bot.set_webhook(**webhook_kwargs)

    logging.info("Telegram webhook is active")
    return app


async def main() -> None:
    logging.info("Games Vault Shop webhook bot starting...")

    app = await create_app()
    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    logging.info("HTTP server started on 0.0.0.0:%s", PORT)

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await runner.cleanup()
        await bot.delete_webhook(drop_pending_updates=False)
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
