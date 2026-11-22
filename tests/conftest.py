"""Tests always use synthetic configuration, never the developer's .env file."""

import os

os.environ.update(
    {
        "PYTHON_DOTENV_DISABLED": "1",
        "BOT_TOKEN": "123456789:fake-test-token-for-offline-tests",
        "DB_HOST": "localhost",
        "DB_NAME": "test",
        "DB_USER": "test",
        "DB_PASSWORD": "test",
        "DB_PORT": "5432",
    }
)
