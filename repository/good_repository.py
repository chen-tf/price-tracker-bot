from typing import List

from repository.database import with_session, Session
from repository.entity import GoodInfoState, GoodInfo


@with_session
def find_all_by_state(state: GoodInfoState, session: Session) -> List[GoodInfo]:
    return session.query(GoodInfo).filter(GoodInfo.state == state).all()
