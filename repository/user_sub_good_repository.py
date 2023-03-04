from typing import List

from sqlalchemy import update
from sqlalchemy.orm import Session

from repository import auto_flush, UserSubGood, UserSubGoodState
from repository.database import SessionLocal


def find_all_by_user_id_and_state(user_id: str, user_sub_good_state: UserSubGoodState,
                                  session: Session = SessionLocal()) -> List[UserSubGood]:
    return (
        session.query(UserSubGood)
        .filter(UserSubGood.user_id == user_id)
        .filter(UserSubGood.state == user_sub_good_state)
        .all()
    )


def find_one_by_user_id_and_good_id(user_id: str, good_id: str,
                                    session: Session = SessionLocal()) -> UserSubGood:
    return (
        session.query(UserSubGood)
        .filter(UserSubGood.user_id == user_id)
        .filter(UserSubGood.good_id == good_id)
        .one()
    )


def find_all_by_good_id_and_price_greater_than(good_id: str, price: int,
                                               session: Session = SessionLocal()) -> List[UserSubGood]:
    return (
        session.query(UserSubGood)
        .filter(UserSubGood.price > price)
        .filter(UserSubGood.good_id == good_id)
        .filter(UserSubGood.state == UserSubGoodState.ENABLE)
        .all()
    )


@auto_flush
def save(user_sub_good: UserSubGood, session=SessionLocal()):
    session.merge(user_sub_good)


def count_by_user_id_and_state(user_id: str, user_sub_good_state: UserSubGoodState,
                               session: Session = SessionLocal()) -> int:
    return (
        session.query(UserSubGood.id)
        .filter(UserSubGood.user_id == user_id,
                UserSubGood.state == user_sub_good_state)
        .count()
    )


def count_by_good_id_and_state(good_id: str, user_sub_good_state: UserSubGoodState,
                               session: Session = SessionLocal()) -> int:
    return (
        session.query(UserSubGood.id)
        .filter(UserSubGood.good_id == good_id,
                UserSubGood.state == user_sub_good_state)
        .count()
    )


@auto_flush
def update_notified_by_id_in(ids: List[str], is_notified: bool, session: Session = SessionLocal()):
    statement = (
        update(UserSubGood)
        .filter(UserSubGood.id.in_(ids))
        .values(is_notified=is_notified)
    )
    session.execute(statement=statement)


@auto_flush
def update_notified_by_good_id(good_id: str, is_notified: bool, session: Session = SessionLocal()):
    statement = (
        update(UserSubGood)
        .filter(UserSubGood.good_id == good_id)
        .values(is_notified=is_notified)
    )
    session.execute(statement=statement)
