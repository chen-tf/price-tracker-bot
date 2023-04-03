from unittest import TestCase

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from testcontainers.postgres import PostgresContainer

from repository.database import Base


class BasePGTestContainer(TestCase):
    container: PostgresContainer = None
    SessionLocal: sessionmaker = None
    session: Session = None

    def setUp(self) -> None:
        super().setUp()
        self.session = self.SessionLocal()

    def tearDown(self) -> None:
        super().tearDown()
        if self.session.is_active:
            self.session.close()

    @classmethod
    def setUpClass(cls):
        cls.container = PostgresContainer("postgres:14").with_bind_ports(5432, 16888)
        cls.container.start()
        engine = create_engine(cls.container.get_connection_url())
        cls.SessionLocal = sessionmaker(bind=engine)
        Base.metadata.create_all(bind=engine)

    @classmethod
    def tearDownClass(cls):
        cls.container.stop()
