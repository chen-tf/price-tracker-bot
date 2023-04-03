from sqlalchemy.orm import Session

from repository.database import with_session


@with_session
def merge(entity, session: Session):
    merged_entity = session.merge(entity)
    session.flush()
    session.refresh(merged_entity)
    return merged_entity
