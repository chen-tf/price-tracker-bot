import logging
import threading
import time

import schedule
from flask import Flask, Response

import pt_config
import pt_scheduler
import pt_service

logger = logging.getLogger('Scheduler')
app = Flask(__name__)


@app.route('/', methods=['GET'])
def index():
    # health check
    return Response('OK', status=200)


def my_job():
    schedule.every(pt_config.PERIOD_HOUR).hours.do(pt_service.sync_price)
    schedule.every(pt_config.PERIOD_HOUR).hours.do(pt_service.disable_not_active_user_sub_good)
    while True:
        schedule.run_pending()
        time.sleep(2)


threading.Thread(target=pt_scheduler.my_job).start()
logger.info('Momo price tracker scheduler started.')
