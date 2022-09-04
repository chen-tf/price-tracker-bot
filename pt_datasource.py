import logging

import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

import pt_config

psycopg2.extras.register_uuid()
pool = ThreadedConnectionPool(2, 4, host=pt_config.DB_HOST, database=pt_config.DB_NAME, user=pt_config.DB_USER,
                              password=pt_config.DB_PASSWORD)
logging.info("Connection Pool established")


def get_pool():
    return pool
