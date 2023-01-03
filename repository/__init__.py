import functools
from typing import List

from sqlalchemy import and_
from sqlalchemy.dialects.postgresql import insert

from repository.database import Session
from repository.models import User, UserSubGood


def auto_commit(func):
    @functools.wraps(func)
    def wrapper(*args):
        _db = Session()
        try:
            result = func(*args, db=_db)

            # if insert、update and delete will commit the transaction
            if _db.new or _db.dirty or _db.deleted:
                _db.commit()
        except Exception:
            _db.rollback()
            raise
        finally:
            _db.close()
        return result

    return wrapper


@auto_commit
def get_users(_skip: int = 0, _limit: int = 100, **kwargs) -> List[User]:
    _db = kwargs["db"]
    return _db.query(User).offset(_skip).limit(_limit).all()


@auto_commit
def upsert_user(user_id: str, chat_id: str, **kwargs):
    _db = kwargs["db"]
    insert_stmt = insert(User).values(id=user_id, chat_id=chat_id, state=1)
    do_update_stmt = insert_stmt.on_conflict_do_update(
        index_elements=[User.id],
        set_=dict(
            chat_id=insert_stmt.excluded.chat_id, state=insert_stmt.excluded.state
        ),
    )
    _db.execute(do_update_stmt)
    _db.commit()


@auto_commit
def find_user_by_good_id(good_id: str, **kwargs):
    _db = kwargs["db"]
    return (
        _db.query(User.chat_id)
        .join(UserSubGood, and_(User.id == UserSubGood.user_id, User.state == 1))
        .filter(UserSubGood.good_id == good_id)
        .all()
    )
