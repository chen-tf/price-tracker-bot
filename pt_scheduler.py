import logging
import time

import schedule

import pt_config
import pt_service

logger = logging.getLogger("Scheduler")

if __name__ == "__main__":
    logger.info("Momo price tracker scheduler started.")
    pt_service.sync_price()
    schedule.every(pt_config.PERIOD_HOUR).hours.do(pt_service.sync_price)
    schedule.every(pt_config.PERIOD_HOUR).hours.do(pt_service.disable_not_active_user_sub_good)
    while True:
        schedule.run_pending()
        time.sleep(2)
