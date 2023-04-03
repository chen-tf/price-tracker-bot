from sqlalchemy.orm import Session

from repository.database import with_session


@with_session
def merge(entity, session: Session):
    session.merge(entity)
    session.flush()
    return entity
