import logging

import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

import pt_config

psycopg2.extras.register_uuid()
pool = ThreadedConnectionPool(
    1,
    8,
    host=pt_config.DB_HOST,
    port=pt_config.DB_PORT,
    database=pt_config.DB_NAME,
    user=pt_config.DB_USER,
    password=pt_config.DB_PASSWORD,
    connect_timeout=3,
    keepalives=1,
    keepalives_idle=5,
    keepalives_interval=2,
    keepalives_count=2,
)
logging.info("Connection Pool established")


def get_pool():
    return pool
