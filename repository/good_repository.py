from typing import List

from repository.database import Session, with_session
from repository.entity import GoodInfo, GoodInfoState


@with_session
def find_all_by_state(state: GoodInfoState, session: Session = None) -> List[GoodInfo]:
    return session.query(GoodInfo).filter(GoodInfo.state == state).all()
