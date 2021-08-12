import logging
import threading
import time

import schedule

import App
import Bot
import PTConfig
import Service

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=PTConfig.LOGGING_LEVEL, force=True)
logger = logging.getLogger('App')
if __name__ == '__main__':
    t = threading.Thread(target=App.my_job)
    t.start()
    logger.debug('Momo price tracker bot started.')
    Bot.run()


def my_job():
    schedule.every(1).hours.do(Service.sync_price)
    while True:
        schedule.run_pending()
        time.sleep(2)
