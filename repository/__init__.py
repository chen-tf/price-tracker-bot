import functools
from typing import List

from sqlalchemy import and_

from repository.database import Session
from repository.models import User, UserSubGood


def auto_close_or_rollback(func):
    @functools.wraps(func)
    def wrapper(*args):
        session = Session()
        try:
            result = func(*args, session=session)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        return result

    return wrapper


@auto_close_or_rollback
def get_users(_skip: int = 0, _limit: int = 100, **kwargs) -> List[User]:
    session = kwargs["session"]
    return session.query(User).offset(_skip).limit(_limit).all()


@auto_close_or_rollback
def upsert_user(user_id: str, chat_id: str, **kwargs):
    session = kwargs["session"]
    data = User(id=user_id, chat_id=chat_id, state=1)
    session.merge(data)


@auto_close_or_rollback
def find_user_by_good_id(good_id: str, **kwargs):
    session = kwargs["session"]
    return (
        session.query(User.chat_id)
        .join(UserSubGood, and_(User.id == UserSubGood.user_id, User.state == 1))
        .filter(UserSubGood.good_id == good_id)
        .all()
    )
