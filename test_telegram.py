import os
import asyncio
from telegram_notifier import notifier

async def test():
    if notifier.enabled:
        print("✅ Telegram is configured!")
        await notifier.send_message("🎉 <b>Test Message</b>\n\nYour bot is working!")
    else:
        print("❌ Telegram not configured. Check your credentials.")

if __name__ == "__main__":
    asyncio.run(test())