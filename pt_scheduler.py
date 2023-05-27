import logging

import pt_service

logger = logging.getLogger("Scheduler")

if __name__ == "__main__":
    logger.info("Momo price tracker scheduler started.")
    pt_service.sync_price()
    pt_service.disable_blocked_user_data()
    logger.info("Momo price tracker scheduler finished.")
