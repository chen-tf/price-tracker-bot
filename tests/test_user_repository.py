from repository import user_repository
from repository.entity import UserState, User, GoodInfo, GoodInfoStockState, GoodInfoState, UserSubGood, \
    UserSubGoodState
from tests.base_pg_testcontainer import BasePGTestContainer


class TestUserRepository(BasePGTestContainer):

    def test_enable_state_users(self):
        self._given_enable_user(user_id="enable-user")
        self._find_all_users_by_enable_state_should_only_contains(user_id="enable-user")

    def test_find_not_exist_user(self):
        self._find_one_user_should_raise_no_result_found(user_id="not-exist")

    def test_find_id_345_user(self):
        self._given_user_with_id(user_id="345")
        self._find_one_user_id_should_be(user_id="345")

    def test_no_user_sub_good_id(self):
        self.assertEqual(len(user_repository.find_all_user_by_good_id(good_id="168", session=self.session)), 0)

    def test_find_user_sub_another_good_id(self):
        self._given_user_sub_good(good_id="another_good")
        self.assertEqual(len(user_repository.find_all_user_by_good_id(good_id="good", session=self.session)), 0)

    def test_find_user_sub_good_id(self):
        self._given_user_sub_good(good_id="good")
        self.assertEqual(len(user_repository.find_all_user_by_good_id(good_id="good", session=self.session)), 1)

    def _given_user_sub_good(self, good_id: str):
        self.session.add(
            GoodInfo(id=good_id, stock_state=GoodInfoStockState.IN_STOCK, state=GoodInfoState.ENABLE))
        user_id = "345"
        self.session.add(User(id=user_id, state=UserState.ENABLE))
        self.session.add(
            UserSubGood(state=UserSubGoodState.ENABLE, good_id=good_id, user_id=user_id))

    def _find_all_users_by_enable_state_should_only_contains(self, user_id: str):
        users = user_repository.find_all_by_state(UserState.ENABLE, self.session)
        assert len(users) == 1 and users[0].id == user_id

    def _given_enable_user(self, user_id: str):
        self.session.add(User(id=user_id, state=UserState.ENABLE))

    def _find_one_user_id_should_be(self, user_id: str):
        self.assertEqual(user_repository.find_one(user_id=user_id, session=self.session).id, user_id)

    def _given_user_with_id(self, user_id):
        self.session.add(User(id=user_id))

    def _find_one_user_should_raise_no_result_found(self, user_id: str):
        self.assertIsNone(user_repository.find_one(user_id=user_id, session=self.session))
