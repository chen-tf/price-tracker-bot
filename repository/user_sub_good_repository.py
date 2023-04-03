from typing import List, Optional

from sqlalchemy import update

from repository.database import with_session, Session
from repository.entity import UserSubGoodState, UserSubGood


@with_session
def find_all_by_user_id_and_state(user_id: str, user_sub_good_state: UserSubGoodState,
                                  session: Session) -> List[UserSubGood]:
    return (
        session.query(UserSubGood)
        .filter(UserSubGood.user_id == user_id)
        .filter(UserSubGood.state == user_sub_good_state)
        .all()
    )


@with_session
def find_one_by_user_id_and_good_id(user_id: str, good_id: str,
                                    session: Session) -> Optional[UserSubGood]:
    return (
        session.query(UserSubGood)
        .filter(UserSubGood.user_id == user_id)
        .filter(UserSubGood.good_id == good_id)
        .first()
    )


@with_session
def find_all_by_good_id_and_price_greater_than(good_id: str, price: int,
                                               session: Session) -> List[UserSubGood]:
    return (
        session.query(UserSubGood)
        .filter(UserSubGood.price > price)
        .filter(UserSubGood.good_id == good_id)
        .filter(UserSubGood.state == UserSubGoodState.ENABLE)
        .all()
    )


@with_session
def count_by_user_id_and_state(user_id: str, user_sub_good_state: UserSubGoodState,
                               session: Session) -> int:
    return (
        session.query(UserSubGood.id)
        .filter(UserSubGood.user_id == user_id,
                UserSubGood.state == user_sub_good_state)
        .count()
    )


@with_session
def count_by_good_id_and_state(good_id: str, user_sub_good_state: UserSubGoodState,
                               session: Session) -> int:
    return (
        session.query(UserSubGood.id)
        .filter(UserSubGood.good_id == good_id,
                UserSubGood.state == user_sub_good_state)
        .count()
    )


@with_session
def update_notified_by_id_in(ids: List[str], is_notified: bool, session: Session):
    statement = (
        update(UserSubGood)
        .filter(UserSubGood.id.in_(ids))
        .values(is_notified=is_notified)
    )
    session.execute(statement=statement)


@with_session
def update_notified_by_good_id(good_id: str, is_notified: bool, session: Session):
    statement = (
        update(UserSubGood)
        .filter(UserSubGood.good_id == good_id)
        .values(is_notified=is_notified)
    )
    session.execute(statement=statement)
