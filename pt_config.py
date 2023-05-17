import logging
import os

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path=env_path, verbose=True)

TELEGRAM_BOT_MODE = os.getenv("TELEGRAM_BOT_MODE", "polling")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MOMO_URL = "https://m.momoshop.com.tw/"
MOMO_GOOD_URI = "goods.momo"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
TEMP_MOMO_GOOD_URL = "https://f85e-114-34-80-107.ngrok-free.app/good"

WEBHOOK_URL = os.getenv("WEBHOOK_URL")

USER_SUB_GOOD_LIMITED = 11

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT", 5432)

LOGGING_LEVEL = os.getenv("LOGGING_LEVEL")
PERIOD_HOUR = int(os.getenv("PERIOD_HOUR", 2))

MOMO_REQUEST_TIMEOUT = 6

LINE_NOTIFY_REDIRECT_URL = os.getenv("LINE_NOTIFY_REDIRECT_URL")
LINE_NOTIFY_CLIENT_ID = os.getenv("LINE_NOTIFY_CLIENT_ID")
LINE_NOTIFY_CLIENT_SECRET = os.getenv("LINE_NOTIFY_CLIENT_SECRET")

PORT = int(os.getenv("PORT", 8080))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=LOGGING_LEVEL,
    force=True,
)


def momo_good_url():
    return MOMO_URL + MOMO_GOOD_URI
