import asyncio
import logging
import os
import threading

from flask import Flask, Response, render_template, request

import pt_bot
import pt_config
import pt_service
from lotify_client import get_lotify_client

template_dir = os.path.abspath("templates")

lotify_client = get_lotify_client()

logger = logging.getLogger("app")

app = Flask(__name__, template_folder=template_dir)

telegram_event_loop = asyncio.new_event_loop()


@app.route("/", methods=["GET"])
def index():
    # health check
    return Response("OK", status=200)


@app.route("/line-subscribe", methods=["GET"])
def subscribe():
    args = request.args
    code = args["code"]
    user_id = args["state"]
    access_token = lotify_client.get_access_token(code=code)
    pt_service.update_user_line_token(user_id=user_id, line_notify_token=access_token)
    return render_template("success.html")


# required hook endpoint to get the data from telegram
@app.route("/webhook/" + pt_config.BOT_TOKEN, methods=["POST", "GET"])
def webhook_handler():
    logger.info(f"Before webhook_handler {request=}")
    if request.method == "POST":
        asyncio.set_event_loop(telegram_event_loop)
        telegram_event_loop.run_until_complete(pt_bot.consume_request(request))
    logger.info(f"After webhook_handler {request=}")
    return Response("OK", status=200)


class FlaskAppThread(threading.Thread):
    def run(self) -> None:
        run_web_app()


def run_web_app():
    port = int(os.environ.get("PORT", "8443"))
    app.run("127.0.0.1", port)


class TelegramBotThread(threading.Thread):
    def run(self) -> None:
        async def run_bot():
            await pt_bot.application.bot.set_webhook(url=pt_config.WEBHOOK_URL + "webhook/" + pt_config.BOT_TOKEN)
            async with pt_bot.application:
                await pt_bot.application.initialize()
                await pt_bot.application.start()
                while True:
                    dummy = 1

        asyncio.run(run_bot())


if __name__ == "__main__":
    if pt_config.TELEGRAM_BOT_MODE == "polling":
        flask_app_thread = FlaskAppThread()
        flask_app_thread.start()
        pt_bot.application.run_polling()
    else:
        TelegramBotThread().start()
        run_web_app()
