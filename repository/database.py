from contextlib import contextmanager
from functools import wraps
from inspect import signature
from typing import ContextManager

import sqlalchemy.orm
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

import pt_config

eng = create_engine(
    URL.create(
        "postgresql+psycopg2",
        username=pt_config.DB_USER,
        password=pt_config.DB_PASSWORD,
        host=pt_config.DB_HOST,
        port=int(pt_config.DB_PORT),
        database=pt_config.DB_NAME,
    ),
    pool_size=20,
    max_overflow=0,
    pool_pre_ping=True,
    pool_recycle=1200,
)
Session = scoped_session(sessionmaker(bind=eng, expire_on_commit=False))
Base = declarative_base()


@contextmanager
def session_scope() -> ContextManager[sqlalchemy.orm.Session]:
    """
    Using ContextManager return value hint to solve the issue
    PyCharm doesn't infer types when using contextlib.contextmanager decorator
    Reference：https://youtrack.jetbrains.com/issue/PY-36444
    """
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        Session.remove()


def with_session(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        bound = signature(func).bind_partial(*args, **kwargs)
        if bound.arguments.get("session") is not None:
            return func(*args, **kwargs)
        with session_scope() as session:
            bound.arguments["session"] = session
            return func(*bound.args, **bound.kwargs)

    return wrapper
