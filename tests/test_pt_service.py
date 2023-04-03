from unittest import TestCase, mock
from unittest.mock import patch

import pytest

import pt_config
import pt_service
from pt_error import ExceedLimitedSizeException
from repository.entity import GoodInfo, UserSubGood, UserSubGoodState


class TestAddUserSubGood(TestCase):

    def setUp(self) -> None:
        self.fake_count_by_user_id_and_state = \
            patch('repository.user_sub_good_repository.count_by_user_id_and_state').start()
        self.fake_find_one_by_user_id_and_good_id = \
            patch('repository.user_sub_good_repository.find_one_by_user_id_and_good_id').start()
        self.fake_find_good_info = patch('pt_momo.find_good_info').start()
        self.fake_merge = patch('repository.common_repository.merge').start()
        self.fake_merge.side_effect = lambda x: x

    def tearDown(self) -> None:
        mock.patch.stopall()

    def test_exceed_maximum_sub_goods(self):
        """
        Test that adding a new sub good exceeds the maximum allowed sub goods raises an exception.
        """
        self._given_user_exceed_maximum_sub_goods()

        with pytest.raises(ExceedLimitedSizeException):
            pt_service.add_user_sub_good(user_id='dummy', url='dummy')

    def test_non_existent_sub_goods(self):
        """
        Test that adding a new sub good that does not exist creates a new UserSubGood object.
        """
        self._given_user_less_than_maximum_sub_goods()
        self.fake_find_good_info.return_value = GoodInfo(id='good123', price=168)
        self.fake_find_one_by_user_id_and_good_id.return_value = None

        actual = pt_service.add_user_sub_good(user_id='user-test', url='dummy')

        self.assertEqual(actual.user_sub_good.good_id, 'good123')
        self.assertEqual(actual.user_sub_good.user_id, 'user-test')
        self.assertEqual(actual.user_sub_good.price, 168)

    def test_existing_sub_goods(self):
        """
        Test that adding a new sub good that existing update the existing UserSubGood object.
        """
        self._given_user_less_than_maximum_sub_goods()
        self.fake_find_good_info.return_value = GoodInfo(price=168)
        self.fake_find_one_by_user_id_and_good_id.return_value = UserSubGood(state=UserSubGoodState.DISABLE,
                                                                             price=66)

        actual = pt_service.add_user_sub_good(user_id='user-test', url='dummy')

        self.assertEqual(actual.user_sub_good.price, 168)
        self.assertEqual(actual.user_sub_good.state, UserSubGoodState.ENABLE)

    def _given_user_exceed_maximum_sub_goods(self):
        self.fake_count_by_user_id_and_state.return_value = pt_config.USER_SUB_GOOD_LIMITED

    def _given_user_less_than_maximum_sub_goods(self):
        self.fake_count_by_user_id_and_state.return_value = pt_config.USER_SUB_GOOD_LIMITED - 1
