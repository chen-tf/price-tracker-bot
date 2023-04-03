# coding: utf-8
import logging
import re
from urllib.parse import urlparse, parse_qs

import requests

import pt_config
import pt_error
import pt_momo
from lotify_client import get_lotify_client
from pt_momo import generate_momo_url_by_good_id
from repository import good_repository, user_sub_good_repository, user_repository
from repository.common_repository import merge
from repository.entity import GoodInfoStockState, GoodInfo, GoodInfoState, UserSubGoodState, UserState, User, \
    UserSubGood
from response.ClearSubGoodResponse import ClearSubGoodResponse
from response.MySubGoodsResponse import UserSubGoodsResponse
from response.UserAddGoodResponse import UserAddGoodResponse

logger = logging.getLogger("Service")
lotify_client = get_lotify_client()


def sync_price():
    logger.info("Price syncer started")
    try:
        for good in good_repository.find_all_by_state(GoodInfoState.ENABLE):
            _price_sync_handler(good)
    except Exception as ex:
        logger.error(ex, exc_info=True)
    logger.info("Price syncer finished")


def _price_sync_handler(good_info: GoodInfo):
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
        merge(new_good_info)
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
            logger.info("%s is in stock!", new_good_info.name)
            follow_good_chat_ids = user_repository.find_all_user_by_good_id(good_id)
            msg = "%s\n目前已經可購買！！！\n\n%s"
            for follow_good_chat_id in follow_good_chat_ids:
                pt_bot.send(
                    msg % (new_good_info.name, good_page_url),
                    str(follow_good_chat_id),
                )
    except pt_error.GoodNotExist:
        if new_good_info is not None:
            new_good_info.state = GoodInfoStockState.NOT_EXIST
            merge(new_good_info)
    except pt_error.EmptyPageError:
        logger.error(f"empty page good_id:{good_id}")
    except Exception as ex:
        logger.error(ex, exc_info=True)


def _handle_redundant_good_info(good_info: GoodInfo):
    valid_user_sub_goods = user_sub_good_repository.count_by_good_id_and_state(good_info.id, UserSubGoodState.ENABLE)

    if valid_user_sub_goods >= 1:
        return True

    good_info.state = GoodInfoState.DISABLE
    merge(good_info)
    return False


def disable_not_active_user_sub_good():
    try:
        for user in user_repository.find_all_by_state(UserState.ENABLE):
            _disable_not_active_user_sub_good_handler(user)
    except Exception as ex:
        logger.error(ex, exc_info=True)


def _disable_not_active_user_sub_good_handler(user: User):
    import pt_bot

    if pt_bot.is_blocked_by_user(user.chat_id):
        user.state = UserState.DISABLE
        merge(user)
        user_sub_goods = user_sub_good_repository.find_all_by_user_id_and_state(user.id, UserSubGoodState.ENABLE)
        for user_sub_good in user_sub_goods:
            user_sub_good.state = UserSubGoodState.DISABLE
            merge(user_sub_good)


def update_user_line_token(user_id, line_notify_token):
    user = user_repository.find_one(user_id)
    user.line_notify_token = line_notify_token
    merge(user)


def find_user_sub_goods(user_id) -> UserSubGoodsResponse:
    user_sub_goods = user_sub_good_repository.find_all_by_user_id_and_state(user_id, UserSubGoodState.ENABLE)
    return UserSubGoodsResponse(user_sub_goods)


def clear(user_id, good_name) -> ClearSubGoodResponse:
    user_sub_goods = user_sub_good_repository.find_all_by_user_id_and_state(user_id, UserSubGoodState.ENABLE)
    if good_name is not None:
        user_sub_goods = [user_sub_good for user_sub_good in user_sub_goods if
                          good_name in user_sub_good.good_info.name]

    if len(user_sub_goods) == 0:
        return ClearSubGoodResponse()

    for user_sub_good in user_sub_goods:
        user_sub_good.state = UserSubGoodState.DISABLE
        merge(user_sub_good)

    removed_good_names = [user_sub_good.good_info.name for user_sub_good in user_sub_goods]
    return ClearSubGoodResponse(removed_good_names)


def count_user_good_info_sum(user_id):
    return user_sub_good_repository.count_by_user_id_and_state(user_id, UserSubGoodState.ENABLE)


def reg_user(user_id, chat_id):
    user = user_repository.find_one(user_id)
    if user:
        user.state = UserState.ENABLE
    else:
        user = User(id=user_id, chat_id=chat_id, state=UserState.ENABLE)
    merge(user)


def get_good_info(good_id) -> GoodInfo:
    return pt_momo.find_good_info(good_id)


def add_user_sub_good(user_id: str, url: str) -> UserAddGoodResponse:
    if user_sub_good_repository.count_by_user_id_and_state(user_id,
                                                           UserSubGoodState.ENABLE) \
            >= pt_config.USER_SUB_GOOD_LIMITED:
        return UserAddGoodResponse.error(pt_error.ExceedLimitedSizeError)

    good_id = _parse_good_id_from_url(url)
    if good_id is None:
        return UserAddGoodResponse.error(pt_error.NotValidMomoURL)

    try:
        good_info = merge(pt_momo.find_good_info(good_id))
    except pt_error.Error as error:
        return UserAddGoodResponse.error(error)
    except Exception:
        return UserAddGoodResponse.error(pt_error.Error)

    user_sub_good = UserSubGood(
        user_id=user_id,
        good_id=good_id,
        price=good_info.price,
        is_notified=False,
        state=UserSubGoodState.ENABLE
    )
    exist_record = user_sub_good_repository.find_one_by_user_id_and_good_id(user_id=user_sub_good.user_id,
                                                                            good_id=user_sub_good.good_id)
    if exist_record:
        exist_record.price = user_sub_good.price
        exist_record.is_notified = user_sub_good.is_notified
        exist_record.state = user_sub_good.state
        user_sub_good = merge(exist_record)
    else:
        user_sub_good = merge(user_sub_good)
    return UserAddGoodResponse.success(user_sub_good=user_sub_good)


def _parse_good_id_from_url(url: str):
    good_id = None
    try:
        if "https://momo.dm" in url:
            match = re.search("https.*momo.dm.*", url)
            response = requests.request(
                "GET",
                match.group(0),
                headers={"user-agent": pt_config.USER_AGENT},
                timeout=(10, 15),
            )
            url = response.url
        result = urlparse(url)
        query = parse_qs(result.query)
        if "i_code" in query and len(query["i_code"]) >= 1:
            good_id = str(query["i_code"][0])
    finally:
        return good_id
