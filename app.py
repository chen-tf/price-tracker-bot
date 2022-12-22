import logging
import os

import telegram
from flask import Flask, request, Response, render_template

import pt_bot
import pt_config
import pt_service
from lotify_client import get_lotify_client

template_dir = os.path.abspath('Templates')

lotify_client = get_lotify_client()

logger = logging.getLogger('app')

UNTRACK = range(1)
ADD_GOOD = range(1)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=pt_config.LOGGING_LEVEL, force=True)

app = Flask(__name__, template_folder=template_dir)


@app.route('/', methods=['GET'])
def index():
    # health check
    return 'ok', 200


@app.route("/line-subscribe", methods=['GET'])
def subscribe():
    args = request.args
    code = args['code']
    user_id = args['state']
    access_token = lotify_client.get_access_token(code=code)
    pt_service.update_user_line_token(user_id=user_id, line_notify_token=access_token)
    return render_template('success.html')


# required hook endpoint to get the data from telegram
@app.route('/webhook/' + pt_config.BOT_TOKEN, methods=['POST', 'GET'])
def webhook_handler():
    if request.method == "POST":
        update = telegram.Update.de_json(request.get_json(force=True), pt_bot.bot)
        pt_bot.telegram_dispatcher.process_update(update)
    return Response('OK', status=200)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8443'))
    app.run('127.0.0.1', port)
