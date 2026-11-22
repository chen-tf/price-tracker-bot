import pytest
from sqlalchemy import URL, create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker

from repository import database


def test_repository_session_ownership_commit_rollback_and_cleanup(monkeypatch):
    engine = create_engine("sqlite://")
    factory = scoped_session(sessionmaker(bind=engine))
    monkeypatch.setattr(database, "Session", factory)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE sample (value INTEGER)"))

    @database.with_session
    def write(value, session=None):
        session.execute(text("INSERT INTO sample VALUES (:value)"), {"value": value})
        if value < 0:
            raise ValueError("rollback")

    try:
        write(1)
        assert not factory.registry.has()
        write(2, session=None)
        with pytest.raises(ValueError):
            write(-1)
        assert not factory.registry.has()
        external = sessionmaker(bind=engine)()
        write(3, external)
        external.rollback()
        external.close()
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT value FROM sample ORDER BY value")
            ).scalars().all() == [1, 2]
    finally:
        factory.remove()
        engine.dispose()


def test_database_password_special_characters_survive_url_construction():
    password = "test@:/?#password"
    url = URL.create(
        "postgresql+psycopg2", username="test", password=password, host="localhost", database="test"
    )
    from sqlalchemy.engine import make_url

    assert make_url(url.render_as_string(hide_password=False)).password == password
