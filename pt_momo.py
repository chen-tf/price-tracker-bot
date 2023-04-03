import logging
import random
import time

import requests
from bs4 import BeautifulSoup

import pt_config
import pt_error
from repository.entity import GoodInfoStockState, GoodInfo, GoodInfoState

logger = logging.getLogger("momo")


def find_good_info(good_id=None) -> GoodInfo:
    logger.info(f"查詢商品資訊, good_id:{good_id}")
    response = _get_good_info_from_momo(i_code=good_id)

    if not response:
        raise pt_error.EmptyPageException

    soup = BeautifulSoup(response, "html.parser")
    try:
        if soup.find("meta", property="og:title") is None:
            raise pt_error.GoodNotException
        good_name = soup.find("meta", property="og:title")["content"]
        price = _format_price(soup.find("meta", property="product:price:amount")["content"])
        stock_state_str = soup.find("meta", property="product:availability")["content"]
        if stock_state_str == "in stock":
            stock_state = GoodInfoStockState.IN_STOCK
        else:
            stock_state = GoodInfoStockState.OUT_OF_STOCK
        logger.info(f"""
        商品名稱：{good_name}
        價格：{price}
        狀態：{stock_state_str}""")
    except pt_error.GoodNotException as e:
        raise e
    except Exception:
        logger.error(f"Parse good_info and catch an exception. good_id:{good_id}", exc_info=True)
        raise pt_error.CrawlerParseException
    return GoodInfo(id=good_id, name=good_name, price=price, stock_state=stock_state, state=GoodInfoState.ENABLE)


def _format_price(price):
    return int(str(price).strip().replace(",", ""))


def _get_good_info_from_momo(i_code=None):
    time.sleep(round(random.uniform(0, 1), 2))
    result = None
    try:
        params = {"i_code": i_code}
        response = requests.get(
            pt_config.momo_good_url(),
            params=params,
            headers={"user-agent": pt_config.USER_AGENT,
                     "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
                               "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                     "accept-encoding": "gzip, deflate, br",
                     "accept-language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                     "referer": "https://m.momoshop.com.tw/main.momo"},
            timeout=pt_config.MOMO_REQUEST_TIMEOUT,
        )
        result = response.text
    except requests.exceptions.ReadTimeout:
        logger.error(f"ReadTimeout i_code:{i_code}")
    return result


def generate_momo_url_by_good_id(good_id):
    return (pt_config.MOMO_URL + pt_config.MOMO_GOOD_URI + "?i_code=%s") % str(good_id)
