import functools
from typing import List

from sqlalchemy import update
from sqlalchemy.orm import Session

from repository.database import SessionLocal
from repository.models import User, UserSubGood, GoodInfo, UserSubGoodState, UserState, GoodInfoState


def auto_flush(func):
    @functools.wraps(func)
    def wrapper(*args):
        session: Session = SessionLocal()
        try:
            result = func(*args, session=session)
            # if insert、update and delete will commit the transaction
            if session.new or session.dirty or session.deleted:
                session.flush()
        finally:
            session.close()
        return result

    return wrapper


@auto_flush
def upsert_user(user_id: str, chat_id: str, **kwargs):
    session: Session = kwargs["session"]
    data = User(id=user_id, chat_id=chat_id, state=UserState.ENABLE)
    session.merge(data)


@auto_flush
def update_user_line_token(user_id: str, line_token: str, **kwargs):
    session: Session = kwargs["session"]
    statement = (
        update(User)
        .where(User.id == user_id)
        .values(line_notify_token=line_token)
    )
    session.execute(statement=statement)


@auto_flush
def add_good_info(good_info, **kwargs):
    session: Session = kwargs["session"]
    data = GoodInfo(
        id=good_info.good_id,
        name=good_info.name,
        price=good_info.price,
        stock_state=good_info.stock_state,
        state=GoodInfoState.ENABLE
    )
    session.merge(data)


@auto_flush
def find_user_sub_goods(user_id: str, **kwargs) -> List[UserSubGood]:
    session: Session = kwargs["session"]
    return (
        session.query(UserSubGood)
        .filter(UserSubGood.user_id == user_id)
        .filter(UserSubGood.state == UserSubGoodState.ENABLE)
        .all()
    )


@auto_flush
def user_unsubscribe_goods(user_sub_goods: List[UserSubGood], **kwargs):
    session: Session = kwargs["session"]
    sub_good_ids = [user_sub_good.id for user_sub_good in user_sub_goods]
    statement = (
        update(UserSubGood)
        .where(UserSubGood.id.in_(sub_good_ids))
        .values(state=UserSubGoodState.DISABLE)
    )
    session.execute(statement=statement)


@auto_flush
def count_user_sub_goods(user_id: str, **kwargs) -> int:
    session: Session = kwargs["session"]
    return (
        session.query(UserSubGood.id)
        .where(UserSubGood.user_id == str(user_id),
               UserSubGood.state == UserSubGoodState.ENABLE)
        .count()
    )
