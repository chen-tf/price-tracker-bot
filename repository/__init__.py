from functools import wraps

from repository.database import SessionLocal
from repository.models import User, UserSubGood, GoodInfo, UserSubGoodState, UserState, GoodInfoState


def auto_flush(func):
    @wraps(func)
    def wrapper(*args):
        session = SessionLocal()
        try:
            result = func(*args, session=session)
            # if insert、update and delete will commit the transaction
            if session.new or session.dirty or session.deleted:
                session.flush()
        finally:
            session.close()
        return result

    return wrapper
