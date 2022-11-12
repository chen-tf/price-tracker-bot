import os

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, '.env')
load_dotenv(dotenv_path=env_path, verbose=True)

TELEGRAM_BOT_MODE = os.getenv('TELEGRAM_BOT_MODE', 'polling')
BOT_TOKEN = os.getenv('BOT_TOKEN')
MOMO_URL = 'https://m.momoshop.com.tw/'
MOMO_GOOD_URI = 'goods.momo'
USER_AGENT = 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:90.0) Gecko/20100101 Firefox/90.0'

WEBHOOK_URL = os.getenv('WEBHOOK_URL')

USER_SUB_GOOD_LIMITED = 11

DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')

LOGGING_LEVEL = os.getenv('LOGGING_LEVEL')
PERIOD_HOUR = int(os.getenv('PERIOD_HOUR', 2))

MOMO_REQUEST_TIMEOUT = 20

LINE_NOTIFY_REDIRECT_URL = os.getenv('LINE_NOTIFY_REDIRECT_URL')
LINE_NOTIFY_CLIENT_ID = os.getenv('LINE_NOTIFY_CLIENT_ID')
LINE_NOTIFY_CLIENT_SECRET = os.getenv('LINE_NOTIFY_CLIENT_SECRET')

PORT = int(os.getenv('PORT', 8080))


def momo_good_url():
    return MOMO_URL + MOMO_GOOD_URI
