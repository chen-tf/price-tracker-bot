import logging
import os

from flask import Flask, Response, render_template, request

import pt_bot
import pt_config
import pt_service
from lotify_client import get_lotify_client

template_dir = os.path.abspath("templates")

lotify_client = get_lotify_client()

logger = logging.getLogger("app")

app = Flask(__name__, template_folder=template_dir)


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
    if request.method == "POST":
        pt_bot.consume_request(request)
    return Response("OK", status=200)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8443"))
    app.run("127.0.0.1", port)
