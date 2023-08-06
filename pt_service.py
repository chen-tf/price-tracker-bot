# coding: utf-8
import logging
import time

import pt_config
import pt_error
import pt_momo
from lotify_client import get_lotify_client
from pt_momo import generate_momo_url_by_good_id
from repository import good_repository, user_sub_good_repository, user_repository, common_repository
from repository.entity import GoodInfoStockState, GoodInfo, GoodInfoState, UserSubGoodState, UserState, User, \
    UserSubGood
from response.ClearSubGoodResponse import ClearSubGoodResponse
from response.MySubGoodsResponse import UserSubGoodsResponse
from response.UserAddGoodResponse import UserAddGoodResponse

logger = logging.getLogger("Service")
lotify_client = get_lotify_client()


def sync_price() -> None:
    logger.info("Price syncer started")
    try:
        count = 1
        for good in good_repository.find_all_by_state(GoodInfoState.ENABLE):
            _price_sync_handler(good)
            count += 1
            time.sleep(1)
            if count >= 900:
                time.sleep(120)
                count = 0
    except Exception as ex:
        logger.error(ex, exc_info=True)
    logger.info("Price syncer finished")


def _price_sync_handler(good_info: GoodInfo) -> None:
    good_id = None
    import pt_bot
    new_good_info = None
    try:
        good_id = good_info.id
        is_exist = _handle_redundant_good_info(good_info)
        if not is_exist:
            logger.debug("%s not exist", good_id)
            return
        new_good_info = pt_momo.find_good_info(good_id=good_id)
        common_repository.merge(new_good_info)
        cheaper_records = []
        if new_good_info.price != good_info.price:
            user_sub_good_repository.update_notified_by_good_id(good_id, False)
            cheaper_records = user_sub_good_repository.find_all_by_good_id_and_price_greater_than(
                price=new_good_info.price, good_id=good_id
            )
        msg = "%s\n目前價格為%s, 低於當初紀錄價格%s\n\n%s"
        success_notified_user_ids = []
        good_page_url = generate_momo_url_by_good_id(good_id)
        for cheaper_record in cheaper_records:
            chat_id = cheaper_record.user.chat_id
            original_price = cheaper_record.price
            format_msg = msg % (
                new_good_info.name,
                new_good_info.price,
                original_price,
                good_page_url,
            )
            pt_bot.send(format_msg, chat_id)
            line_notify_token = cheaper_record.user.line_notify_token
            if line_notify_token:
                try:
                    lotify_client.send_message(line_notify_token, format_msg)
                except Exception as ex:
                    logger.error(ex, exc_info=True)
            success_notified_user_ids.append(cheaper_record.id)
        user_sub_good_repository.update_notified_by_id_in(success_notified_user_ids, True)

        # Notify if good's stock change
        if (
                new_good_info.stock_state == GoodInfoStockState.IN_STOCK
                and good_info.stock_state == GoodInfoStockState.OUT_OF_STOCK
        ):
            logger.info(f"{new_good_info.name} is in stock!")
            follow_good_users = user_repository.find_all_user_by_good_id(good_id)
            for user in follow_good_users:
                pt_bot.send(
                    f"{new_good_info.name}\n目前已經可購買！！！\n\n{good_page_url}",
                    str(user.chat_id),
                )
    except pt_error.GoodNotException:
        if new_good_info is not None:
            new_good_info.state = GoodInfoStockState.NOT_EXIST
            common_repository.merge(new_good_info)
    except pt_error.EmptyPageException:
        logger.error(f"empty page good_id:{good_id}")
    except Exception as ex:
        logger.error(ex, exc_info=True)


def _handle_redundant_good_info(good_info: GoodInfo) -> bool:
    valid_user_sub_goods = user_sub_good_repository.count_by_good_id_and_state(good_info.id, UserSubGoodState.ENABLE)

    if valid_user_sub_goods >= 1:
        return True

    good_info.state = GoodInfoState.DISABLE
    common_repository.merge(good_info)
    return False


def disable_blocked_user_data() -> None:
    import pt_bot
    blocked_users = filter(lambda u: pt_bot.is_blocked_by_user(u.chat_id),
                           user_repository.find_all_by_state(UserState.ENABLE))
    for user in blocked_users:
        _disable_user_and_sub_goods(user)


def _disable_user_and_sub_goods(user):
    user.state = UserState.DISABLE
    common_repository.merge(user)
    user_sub_goods = user_sub_good_repository.find_all_by_user_id_and_state(user.id, UserSubGoodState.ENABLE)
    for user_sub_good in user_sub_goods:
        user_sub_good.state = UserSubGoodState.DISABLE
        common_repository.merge(user_sub_good)


def update_user_line_token(user_id: str, line_notify_token: str) -> None:
    user = user_repository.find_one(user_id)
    user.line_notify_token = line_notify_token
    common_repository.merge(user)


def find_user_sub_goods(user_id: str) -> UserSubGoodsResponse:
    user_sub_goods = user_sub_good_repository.find_all_by_user_id_and_state(user_id, UserSubGoodState.ENABLE)
    return UserSubGoodsResponse(user_sub_goods)


def clear_user_sub_goods(user_id: str, good_name: str = None) -> ClearSubGoodResponse:
    user_sub_goods = _find_user_sub_goods_contains_name(user_id, good_name)

    for user_sub_good in user_sub_goods:
        user_sub_good.state = UserSubGoodState.DISABLE
        common_repository.merge(user_sub_good)

    removed_good_names = [user_sub_good.good_info.name for user_sub_good in user_sub_goods]
    return ClearSubGoodResponse(removed_good_names)


def clear_user_sub_goods_by_id(user_id: str, good_id: str) -> ClearSubGoodResponse:
    user_sub_good = user_sub_good_repository.find_one_by_user_id_and_good_id(user_id, good_id)
    user_sub_good.state = UserSubGoodState.DISABLE
    common_repository.merge(user_sub_good)
    removed_good_names = [user_sub_good.good_info.name]
    return ClearSubGoodResponse(removed_good_names)


def _find_user_sub_goods_contains_name(user_id, good_name):
    user_sub_goods = user_sub_good_repository.find_all_by_user_id_and_state(user_id, UserSubGoodState.ENABLE)
    not_clear_all = good_name is not None
    if not_clear_all:
        user_sub_goods = [user_sub_good for user_sub_good in user_sub_goods if
                          good_name in user_sub_good.good_info.name]
    return user_sub_goods


def ensure_user_registration(user_id: str, chat_id: str) -> None:
    user = user_repository.find_one(user_id)
    if user:
        user.state = UserState.ENABLE
    else:
        user = User(id=user_id, chat_id=chat_id, state=UserState.ENABLE)
    common_repository.merge(user)


def add_user_sub_good(user_id: str, url: str) -> UserAddGoodResponse:
    _ensure_user_maximum_sub_goods(user_id)
    good_info = pt_momo.find_good_info(url=url)
    good_info = common_repository.merge(good_info)
    return UserAddGoodResponse.success(user_sub_good=_upsert_user_sub_good(good_info, user_id))


def _ensure_user_maximum_sub_goods(user_id: str) -> None:
    if user_sub_good_repository.count_by_user_id_and_state(user_id,
                                                           UserSubGoodState.ENABLE) \
            >= pt_config.USER_SUB_GOOD_LIMITED:
        raise pt_error.ExceedLimitedSizeException


def _upsert_user_sub_good(good_info: GoodInfo, user_id: str) -> UserSubGood:
    user_sub_good = _create_user_sub_good(good_info, user_id)
    exist_record = user_sub_good_repository.find_one_by_user_id_and_good_id(user_id=user_sub_good.user_id,
                                                                            good_id=user_sub_good.good_id)
    if exist_record:
        _update_existing_sub_good(exist_record, user_sub_good)
        return common_repository.merge(exist_record)
    else:
        return common_repository.merge(user_sub_good)


def _update_existing_sub_good(exist_record: UserSubGood, user_sub_good: UserSubGood) -> None:
    exist_record.price = user_sub_good.price
    exist_record.is_notified = user_sub_good.is_notified
    exist_record.state = user_sub_good.state


def _create_user_sub_good(good_info: GoodInfo, user_id: str) -> UserSubGood:
    return UserSubGood(
        user_id=user_id,
        good_id=good_info.id,
        price=good_info.price,
        is_notified=False,
        state=UserSubGoodState.ENABLE
    )
