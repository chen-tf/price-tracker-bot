import functools
from typing import List

from sqlalchemy import and_

from repository.database import Session
from repository.models import User, UserSubGood


def auto_commit(func):
    @functools.wraps(func)
    def wrapper(*args):
        db = Session()
        try:
            result = func(*args, db=db)
            # if insert、update and delete will commit the transaction
            if db.new or db.dirty or db.deleted:
                db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        return result

    return wrapper


@auto_commit
def get_users(_skip: int = 0, _limit: int = 100, **kwargs) -> List[User]:
    db = kwargs["db"]
    return db.query(User).offset(_skip).limit(_limit).all()


@auto_commit
def upsert_user(user_id: str, chat_id: str, **kwargs):
    db = kwargs["db"]
    data = User(id=user_id, chat_id=chat_id, state=1)
    db.merge(data)


@auto_commit
def find_user_by_good_id(good_id: str, **kwargs):
    db = kwargs["db"]
    return (
        db.query(User.chat_id)
        .join(UserSubGood, and_(User.id == UserSubGood.user_id, User.state == 1))
        .filter(UserSubGood.good_id == good_id)
        .all()
    )
