# coding: utf-8
import logging
from typing import List

import pt_error
import pt_momo
import pt_repository
import repository
from lotify_client import get_lotify_client
from pt_entity import GoodInfo
from pt_momo import generate_momo_url_by_good_id
from repository import UserSubGood

logger = logging.getLogger("Service")
lotify_client = get_lotify_client()


def sync_price():
    logger.info("Price syncer started")
    try:
        pt_repository.find_all_good(_price_sync_handler)
    except Exception as ex:
        logger.error(ex, exc_info=True)
    logger.info("Price syncer finished")


def _price_sync_handler(good_info):
    good_id = None
    import pt_bot

    try:
        good_id = good_info.good_id
        is_exist = pt_repository.disable_redundant_good_info(good_info.good_id)
        if not is_exist:
            logger.debug("%s not exist", good_id)
            return
        new_good_info = pt_momo.find_good_info(good_id=good_id)
        repository.add_good_info(new_good_info)
        cheaper_records = []
        if new_good_info.price != good_info.price:
            pt_repository.reset_higher_user_sub(good_id)
            cheaper_records = pt_repository.find_user_sub_goods_price_higher(
                new_good_info.price, good_id
            )
        msg = "%s\n目前價格為%s, 低於當初紀錄價格%s\n\n%s"
        success_notified = []
        good_page_url = generate_momo_url_by_good_id(good_id)
        for cheaper_record in cheaper_records:
            chat_id = cheaper_record[3]
            original_price = cheaper_record[2]
            format_msg = msg % (
                new_good_info.name,
                new_good_info.price,
                original_price,
                good_page_url,
            )
            pt_bot.send(format_msg, chat_id)
            line_notify_token = cheaper_record[4]
            if line_notify_token:
                try:
                    lotify_client.send_message(line_notify_token, format_msg)
                except Exception as ex:
                    logger.error(ex, exc_info=True)
            success_notified.append(cheaper_record[0])
        pt_repository.mark_is_notified_by_id(success_notified)

        # Notify if good's stock change
        if (
                new_good_info.stock_state == GoodInfo.STOCK_STATE_IN_STOCK
                and good_info.stock_state == GoodInfo.STOCK_STATE_OUT_OF_STOCK
        ):
            logger.info("%s is in stock!", new_good_info.name)
            follow_good_chat_ids = pt_repository.find_user_by_good_id(good_id)
            msg = "%s\n目前已經可購買！！！\n\n%s"
            for follow_good_chat_id in follow_good_chat_ids:
                pt_bot.send(
                    msg % (new_good_info.name, good_page_url),
                    str(follow_good_chat_id[0]),
                )
    except pt_error.GoodNotExist:
        pt_repository.update_good_stock_state(good_id, GoodInfo.STOCK_STATE_NOT_EXIST)
    except Exception as ex:
        logger.error(ex, exc_info=True)


def disable_not_active_user_sub_good():
    try:
        pt_repository.find_all_active_user(_disable_not_active_user_sub_good_handler)
    except Exception as ex:
        logger.error(ex, exc_info=True)


def _disable_not_active_user_sub_good_handler(record):
    user_id = str(record[0])
    chat_id = str(record[1])
    import pt_bot

    if pt_bot.is_blocked_by_user(chat_id):
        pt_repository.disable_user_and_user_sub_goods(user_id)


def update_user_line_token(user_id, line_notify_token):
    return repository.update_user_line_token(user_id, line_notify_token)


def find_user_sub_goods(user_id) -> List[UserSubGood]:
    return repository.find_user_sub_goods(user_id)


def clear(user_id, good_name):
    user_sub_goods = repository.find_user_sub_goods(user_id)
    if good_name is not None:
        user_sub_goods = [user_sub_good for user_sub_good in user_sub_goods if
                          good_name in user_sub_good.good_info.name]

    if len(user_sub_goods) == 0:
        return []

    repository.user_unsubscribe_goods(user_sub_goods)
    return [user_sub_good.good_info.name for user_sub_good in user_sub_goods]


def count_user_good_info_sum(user_id):
    return repository.count_user_sub_goods(user_id)


def upsert_user(user_id, chat_id):
    return repository.upsert_user(user_id, chat_id)


def get_good_info(good_id):
    return pt_momo.find_good_info(good_id)


def add_good_info(good_info):
    return repository.add_good_info(good_info)


def add_user_good_info(user_good_info):
    return pt_repository.add_user_good_info(user_good_info)
