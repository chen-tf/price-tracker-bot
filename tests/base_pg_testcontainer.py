from unittest import TestCase

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer

from repository.database import Base


class BasePGTestContainer(TestCase):
    container: PostgresContainer = None
    SessionLocal: sessionmaker
    session: Session = None

    def setUp(self) -> None:
        super().setUp()
        self.session = type(self).SessionLocal()

    def tearDown(self) -> None:
        super().tearDown()
        self.session.rollback()
        self.session.close()

    @classmethod
    def setUpClass(cls):
        cls.container = PostgresContainer("postgres:18")
        cls.container.start()
        engine = create_engine(cls.container.get_connection_url())
        cls.engine = engine
        cls.SessionLocal = sessionmaker(bind=engine)
        Base.metadata.create_all(bind=engine)

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        cls.container.stop()
