import logging

import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

import PTConfig

psycopg2.extras.register_uuid()
pool = ThreadedConnectionPool(2, 10, host=PTConfig.DB_HOST, database=PTConfig.DB_NAME, user=PTConfig.DB_USER,
                              password=PTConfig.DB_PASSWORD)
logging.info("Connection Pool established")


def get_pool():
    return pool
