import logging
import os
import re

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path=env_path, verbose=True)

TELEGRAM_BOT_MODE = os.getenv("TELEGRAM_BOT_MODE", "polling")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MOMO_URL = "https://m.momoshop.com.tw/"
MOMO_GOOD_URI = "goods.momo"
USER_AGENT = "price-tracker-bot/1.0"

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

USER_SUB_GOOD_LIMITED = 20

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT", 5432)

LOGGING_LEVEL = os.getenv("LOGGING_LEVEL")
PERIOD_HOUR = int(os.getenv("PERIOD_HOUR", 2))

MOMO_REQUEST_TIMEOUT = 6


PORT = int(os.getenv("PORT", 8080))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=LOGGING_LEVEL,
    force=True,
)


def momo_good_url():
    return MOMO_URL + MOMO_GOOD_URI


class TokenRedactingFormatter(logging.Formatter):
    """Redact credentials after rendering messages, arguments and tracebacks."""

    def format(self, record):
        rendered = super().format(record)
        if BOT_TOKEN:
            rendered = rendered.replace(BOT_TOKEN, "[REDACTED]")
        return re.sub(r"(api\.telegram\.org/bot)[^/\s\"']+", r"\1[REDACTED]", rendered)


for handler in logging.getLogger().handlers:
    handler.setFormatter(
        TokenRedactingFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
for name in ("httpx", "httpcore"):
    logging.getLogger(name).setLevel(logging.WARNING)
