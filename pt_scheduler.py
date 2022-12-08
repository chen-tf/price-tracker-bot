import logging
import threading
import time

import schedule

import pt_config
import pt_scheduler
import pt_service

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=pt_config.LOGGING_LEVEL, force=True)
logger = logging.getLogger('App')
if __name__ == '__main__':
    threading.Thread(target=pt_scheduler.my_job).start()
    logger.debug('Momo price tracker bot started.')


def my_job():
    schedule.every(pt_config.PERIOD_HOUR).hours.do(pt_service.sync_price)
    schedule.every(pt_config.PERIOD_HOUR).hours.do(pt_service.disable_not_active_user_sub_good)
    while True:
        schedule.run_pending()
        time.sleep(2)
