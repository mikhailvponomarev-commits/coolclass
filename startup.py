import asyncio
import os

from aiogram import Bot

TOKEN = os.getenv("BOT_TOKEN")
PUBLIC_URL = (os.getenv("PUBLIC_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")
# Telegram accepts only A-Z/a-z/0-9/_/- in webhook secret tokens.
# Force one known-good value so an invalid Render environment variable cannot break startup.
WEBHOOK_SECRET = "CoolClassQuiz2026"
os.environ["WEBHOOK_SECRET"] = WEBHOOK_SECRET

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not PUBLIC_URL:
    raise RuntimeError("PUBLIC_URL/RENDER_EXTERNAL_URL is not set")

async def configure_webhook():
    bot = Bot(TOKEN)
    try:
        me = await bot.get_me()
        print(f"Telegram bot: @{me.username} ({me.id})", flush=True)
        webhook_url = f"{PUBLIC_URL}/webhook"
        await bot.set_webhook(webhook_url, secret_token=WEBHOOK_SECRET, drop_pending_updates=False)
        info = await bot.get_webhook_info()
        print(f"Webhook set: {info.url}", flush=True)
        print(f"Pending updates: {info.pending_update_count}", flush=True)
        if info.last_error_message:
            print(f"Telegram webhook last error: {info.last_error_message}", flush=True)
    finally:
        await bot.session.close()

asyncio.run(configure_webhook())
os.execv("/usr/local/bin/python", ["python", "quiz_bot.py"])
