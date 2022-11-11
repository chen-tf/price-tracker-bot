import os

from flask import Flask, request, render_template

import pt_config
from lotify_client import get_lotify_client

template_dir = os.path.abspath('Templates')
app = Flask(__name__, template_folder=template_dir)
lotify_client = get_lotify_client()


@app.route("/line-subscribe", methods=['GET'])
def subscribe():
    args = request.args
    code = args['code']
    user_id = args['state']
    access_token = lotify_client.get_access_token(code=code)
    import pt_service
    pt_service.update_user_line_token(user_id=user_id, line_notify_token=access_token)
    return render_template('success.html')


def start():
    app.run('0.0.0.0', pt_config.PORT, False, True)
