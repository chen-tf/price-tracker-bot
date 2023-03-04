from typing import List

from sqlalchemy.orm import Session

from repository import GoodInfo, auto_flush, GoodInfoState
from repository.database import SessionLocal


@auto_flush
def save(good_info: GoodInfo, session: Session = SessionLocal()):
    session.merge(good_info)


def find_all_by_state(state: GoodInfoState, session: Session = SessionLocal()) -> List[GoodInfo]:
    return session.query(GoodInfo).filter(GoodInfo.state == state).all()
