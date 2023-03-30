from repository import good_repository, GoodInfoState, GoodInfo
from repository.models import GoodInfoStockState
from tests.base_pg_testcontainer import BasePGTestContainer


class TestGoodRepository(BasePGTestContainer):

    def test_enable_state_goods(self):
        self._given_enable_good(good_id="enable-good")
        self._find_all_goods_by_enable_state_should_only_contains(good_id="enable-good")

    def _find_all_goods_by_enable_state_should_only_contains(self, good_id: str):
        goods = good_repository.find_all_by_state(GoodInfoState.ENABLE, self.session)
        assert len(goods) == 1 and goods[0].id == good_id

    def _given_enable_good(self, good_id: str):
        self.session.merge(
            GoodInfo(id=good_id, state=GoodInfoState.ENABLE, stock_state=GoodInfoStockState.IN_STOCK))
