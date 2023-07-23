from typing import List, Optional

from repository.database import with_session, Session
from repository.entity import User, UserState, UserSubGood, UserSubGoodState


@with_session
def find_one(user_id: str, session: Session) -> Optional[User]:
    return session.query(User).filter(User.id == user_id).first()


@with_session
def find_all_by_state(state: UserState, session: Session) -> List[User]:
    return session.query(User).filter(User.state == state).all()


@with_session
def find_all_user_by_good_id(good_id: str, session: Session) -> List[User]:
    return (
        session.query(User)
        .join(UserSubGood)
        .filter(User.state == UserState.ENABLE)
        .filter(UserSubGood.state == UserSubGoodState.ENABLE)
        .filter(UserSubGood.good_id == good_id)
        .all()
    )
