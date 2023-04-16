import logging
import random
import re
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

import pt_config
import pt_error
from repository.entity import GoodInfoStockState, GoodInfo, GoodInfoState

logger = logging.getLogger("momo")
session = requests.Session()
session.mount('https://', requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10))


def find_good_info(good_id=None, url: str = None) -> GoodInfo:
    if url is not None:
        good_id = _parse_good_id_from_url(url)

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


def generate_momo_url_by_good_id(good_id):
    return (pt_config.MOMO_URL + pt_config.MOMO_GOOD_URI + "?i_code=%s") % str(good_id)


def _parse_good_id_from_url(url: str):
    good_id = None
    try:
        if "https://momo.dm" in url:
            match = re.search("https.*momo.dm.*", url)
            response = session.get(
                match.group(0),
                headers={"user-agent": pt_config.USER_AGENT},
                timeout=(10, 15),
            )
            url = response.url
        result = urlparse(url)
        good_id = re.search(r'i_code=(\d+)', result.query).group(1)
    finally:
        if good_id is None:
            raise pt_error.NotValidMomoURLException
        return good_id


def _format_price(price):
    return int(str(price).strip().replace(",", ""))


def _get_good_info_from_momo(i_code=None):
    time.sleep(round(random.uniform(0, 1), 2))
    result = None
    try:
        params = {"i_code": i_code}
        response = session.get(
            "https://c47b-114-34-80-107.ngrok-free.app/good",
            params=params,
            headers={
                'authority': 'm.momoshop.com.tw',
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'accept-language': 'zh-TW,zh;q=0.9',
                'sec-ch-ua': '"Chromium";v="112", "Google Chrome";v="112", "Not:A-Brand";v="99"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"macOS"',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'none',
                'sec-fetch-user': '?1',
                'upgrade-insecure-requests': '1',
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36',
            },
            timeout=pt_config.MOMO_REQUEST_TIMEOUT,
        )
        result = response.text
    except requests.exceptions.ReadTimeout:
        logger.error(f"ReadTimeout i_code:{i_code}")
    return result
