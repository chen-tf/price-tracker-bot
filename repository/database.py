from contextlib import contextmanager
from functools import wraps
from typing import ContextManager

import sqlalchemy.orm
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, scoped_session

import pt_config

eng = create_engine(
    f"postgresql://{pt_config.DB_USER}:{pt_config.DB_PASSWORD}@"
    f"{pt_config.DB_HOST}:{pt_config.DB_PORT}/{pt_config.DB_NAME}",
    pool_size=20,
    max_overflow=0,
    pool_pre_ping=True
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
        session.close()


def with_session(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        session = None
        for arg in args:
            if isinstance(arg, sqlalchemy.orm.Session):
                session = arg
        if 'session' not in kwargs and session is None:
            session = Session()
            kwargs['session'] = session
            try:
                result = func(*args, **kwargs)
                session.commit()
                return result
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        else:
            return func(*args, **kwargs)

    return wrapper
