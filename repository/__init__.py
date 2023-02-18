import functools
from typing import List

from sqlalchemy import and_
from sqlalchemy.orm import Session

from repository.database import SessionLocal
from repository.models import User, UserSubGood, GoodInfo


def auto_commit(func):
    @functools.wraps(func)
    def wrapper(*args):
        session: Session = SessionLocal()
        try:
            result = func(*args, session=session)
            # if insert、update and delete will commit the transaction
            if session.new or session.dirty or session.deleted:
                session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        return result

    return wrapper


@auto_commit
def get_users(_skip: int = 0, _limit: int = 100, **kwargs) -> List[User]:
    session: Session = kwargs["session"]
    return session.query(User).offset(_skip).limit(_limit).all()


@auto_commit
def upsert_user(user_id: str, chat_id: str, **kwargs):
    session: Session = kwargs["session"]
    data = User(id=user_id, chat_id=chat_id, state=1)
    session.merge(data)
    session.commit()


@auto_commit
def find_user_by_good_id(good_id: str, **kwargs):
    session: Session = kwargs["session"]
    return (
        session.query(User.chat_id)
        .join(UserSubGood, and_(User.id == UserSubGood.user_id, User.state == 1))
        .filter(UserSubGood.good_id == good_id)
        .all()
    )


@auto_commit
def add_good_info(good_info, **kwargs):
    session: Session = kwargs["session"]
    data = GoodInfo(
        id=good_info.good_id,
        name=good_info.name,
        price=good_info.price,
        stock_state=good_info.stock_state,
    )
    session.merge(data)


# @auto_commit
# def insert_user(**kwargs):
#     session: Session = kwargs["session"]
#     data = User(id="1234", chat_id="12", state=1)
#     session.add(data)
#
#
# @auto_commit
# def update_user(**kwargs):
#     session: Session = kwargs["session"]
#     user = session.query(User).filter(User.id == "1234").first()
#     user.state = 0
#
#
# @auto_commit
# def delete_user(**kwargs):
#     session: Session = kwargs["session"]
#     user = session.query(User).filter(User.id == "1234").first()
#     session.delete(user)
