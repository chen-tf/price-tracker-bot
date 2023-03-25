import uuid
from unittest import TestCase

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from testcontainers.postgres import PostgresContainer

from repository import good_repository, GoodInfoState, GoodInfo
from repository.database import Base
from repository.models import GoodInfoStockState


class GoodRepositoryTest(TestCase):
    container: PostgresContainer = None
    SessionLocal: sessionmaker = None
    session: Session = None

    def setUp(self) -> None:
        self.session = self.SessionLocal()
        super().setUp()

    def tearDown(self) -> None:
        self.session.close()
        super().tearDown()

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

    def test_enable_state_goods(self):
        self.given_good_with_state(GoodInfoState.ENABLE)
        self.given_good_with_state(GoodInfoState.DISABLE)
        self.find_all_by_state_should_only_contains_enable_state_goods()

    def find_all_by_state_should_only_contains_enable_state_goods(self):
        assert len(good_repository.find_all_by_state(GoodInfoState.ENABLE, self.session)) == 1

    def given_good_with_state(self, state):
        self.session.merge(
            GoodInfo(id=str(uuid.uuid4()), state=state, stock_state=GoodInfoStockState.IN_STOCK))
