"""Read momo's public price API and resolve only explicitly allowed HTTPS hosts."""

import re
from urllib.parse import parse_qs, urljoin, urlsplit

import requests

import pt_config
import pt_error
from repository.entity import GoodInfo, GoodInfoState, GoodInfoStockState

session = requests.Session()
API = "https://www.momoshop.com.tw/api/moecapp/"
ALLOWED_HOSTS = {"momo.dm", "www.momoshop.com.tw", "m.momoshop.com.tw"}


def _validated_url(text):
    matches = re.findall(r"https?://[^\s<>]+", text or "")
    if len(matches) != 1:
        raise pt_error.NotValidMomoURLException
    url = matches[0]
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in ALLOWED_HOSTS
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            raise ValueError("Invalid host")
    except ValueError as error:
        raise pt_error.NotValidMomoURLException from error
    return url, parsed


def _is_sharing_link(url):
    return _validated_url(url)[1].hostname == "momo.dm"


def _parse_good_id_from_url(url):
    _, parsed = _validated_url(url)
    product = re.fullmatch(r"/product/(\d+)/?", parsed.path)
    candidates = [product.group(1)] if product else parse_qs(parsed.query).get("i_code", [])
    if len(candidates) != 1 or not re.fullmatch(r"\d+", candidates[0]):
        raise pt_error.NotValidMomoURLException
    return candidates[0]


def _resolve_sharing_link(url):
    for _ in range(6):
        url, parsed = _validated_url(url)
        if parsed.hostname != "momo.dm":
            return _parse_good_id_from_url(url)
        # Validate each Location before making the next request. Requests' automatic
        # redirects would otherwise allow a trusted short link to reach any host.
        with session.get(
            url,
            headers={"User-Agent": pt_config.USER_AGENT},
            allow_redirects=False,
            timeout=pt_config.MOMO_REQUEST_TIMEOUT,
        ) as response:
            if response.status_code not in (301, 302, 303, 307, 308):
                raise pt_error.NotValidMomoURLException
            location = response.headers.get("Location")
            if not location:
                raise pt_error.NotValidMomoURLException
            url = urljoin(url, location)
    raise pt_error.NotValidMomoURLException


def _api(method, payload):
    with session.post(
        API + method,
        json={**payload, "host": "momoshop"},
        headers={"User-Agent": pt_config.USER_AGENT},
        allow_redirects=False,
        timeout=pt_config.MOMO_REQUEST_TIMEOUT,
    ) as response:
        if response.status_code != 200:
            raise pt_error.EmptyPageException
        data = response.json()
    if data.get("success") is not True:
        raise pt_error.GoodNotException
    return data


def find_good_info(good_id=None, url=None) -> GoodInfo:
    if good_id is None:
        good_id = (
            _resolve_sharing_link(url) if _is_sharing_link(url) else _parse_good_id_from_url(url)
        )
    good_id = str(good_id)
    if not re.fullmatch(r"\d+", good_id):
        raise pt_error.NotValidMomoURLException
    data = _api(
        "getInstantGoodsStatus",
        {
            "columnType": "",
            "priceDescrip": True,
            "implementTypes": ["price"],
            "goodsCodes": [good_id],
        },
    )
    try:
        product = data["rtnGoods"][good_id]
        name = product["goodsName"]
        raw_price = str(product["goodsPriceModel"]["basePrice"]["price"]).replace(",", "")
        if (
            not isinstance(name, str)
            or not name.strip()
            or not re.fullmatch(r"\d+", raw_price)
            or int(raw_price) <= 0
        ):
            raise ValueError("Missing name or price")
        stock = _api(
            "getGoodsRealTimeInfo",
            {"goodsCode": good_id, "fsCode": "", "hour": "", "addressData": {}, "categoryCode": ""},
        )["rtnGoodsData"]["goodsStock"]
        if str(stock) not in {"0", "1"}:
            raise ValueError("Unknown stock")
        return GoodInfo(
            id=good_id,
            name=name,
            price=int(raw_price),
            stock_state=GoodInfoStockState(int(stock)),
            state=GoodInfoState.ENABLE,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise pt_error.CrawlerParseException from error


def generate_momo_url_by_good_id(good_id):
    return pt_config.momo_good_url() + "?i_code=" + str(good_id)
