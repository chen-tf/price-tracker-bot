"""Optional local Python interface. Production runs on Cloudflare Workers."""

import asyncio
import hmac
import threading

from flask import Flask, Response, request

import pt_bot
import pt_config

app = Flask(__name__)
telegram_event_loop = asyncio.new_event_loop()
telegram_lock = threading.Lock()


@app.get("/")
def index():
    return Response("OK", status=200)


@app.get("/line-subscribe")
def subscribe():
    return Response("LINE Notify ended on 2025-03-31.", status=410)


@app.post("/webhook")
def webhook_handler():
    secret = pt_config.WEBHOOK_SECRET
    supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not secret or not hmac.compare_digest(supplied, secret):
        return Response("Unauthorized", status=401)

    async def consume():
        async with pt_bot.get_application():
            await pt_bot.consume_request(request)

    # Flask can serve concurrent requests; the shared Telegram loop is serialized.
    with telegram_lock:
        telegram_event_loop.run_until_complete(consume())
    return Response("OK", status=200)


if __name__ == "__main__":
    if pt_config.TELEGRAM_BOT_MODE == "polling":
        pt_bot.get_application().run_polling()
    else:
        # Webhook registration is an explicit operator action, never an import side effect.
        app.run("127.0.0.1", pt_config.PORT)
