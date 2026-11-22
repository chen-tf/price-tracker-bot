from unittest.mock import MagicMock, patch

import pytest

import pt_error
import pt_momo


@pytest.mark.parametrize(
    "url",
    [
        "http://momo.dm/a",
        "https://momo.dm.evil.test/a",
        "https://evil.test/?x=https://momo.dm/a",
        "https://a:b@momo.dm/a",
        "https://momo.dm:8443/a",
        "https://127.0.0.1/?i_code=123",
        "https://m.momoshop.com.tw/goods.momo?i_code=123&i_code=456",
    ],
)
def test_invalid_product_urls_make_no_network_requests(url):
    with patch.object(pt_momo.session, "get") as get, patch.object(pt_momo.session, "post") as post:
        with pytest.raises(pt_error.NotValidMomoURLException):
            pt_momo.find_good_info(url=url)
        get.assert_not_called()
        post.assert_not_called()


def test_short_link_redirect_cannot_escape_allowlist():
    response = MagicMock(status_code=302, headers={"Location": "https://127.0.0.1/private"})
    with patch.object(pt_momo.session, "get") as get:
        get.return_value.__enter__.return_value = response
        with pytest.raises(pt_error.NotValidMomoURLException):
            pt_momo.find_good_info(url="https://momo.dm/abc")
        assert get.call_count == 1
        assert get.call_args.kwargs["allow_redirects"] is False


def test_live_api_parser_preserves_price_and_stock_contract():
    responses = [
        {
            "success": True,
            "rtnGoods": {
                "123": {"goodsName": "商品", "goodsPriceModel": {"basePrice": {"price": "1,111"}}}
            },
        },
        {"success": True, "rtnGoodsData": {"goodsStock": "1"}},
    ]
    with patch.object(pt_momo.session, "post") as post:
        post.return_value.__enter__.return_value.status_code = 200
        post.return_value.__enter__.return_value.json.side_effect = responses
        good = pt_momo.find_good_info(url="https://www.momoshop.com.tw/product/123")
        assert (good.id, good.price, good.stock_state) == ("123", 1111, 1)
        assert all(
            c.kwargs["headers"]["User-Agent"] == "price-tracker-bot/1.0"
            for c in post.call_args_list
        )
        assert all(c.kwargs["allow_redirects"] is False for c in post.call_args_list)


def test_missing_or_zero_price_never_becomes_a_valid_product():
    with patch.object(
        pt_momo,
        "_api",
        return_value={
            "rtnGoods": {
                "123": {"goodsName": "商品", "goodsPriceModel": {"basePrice": {"price": "0"}}}
            }
        },
    ):
        with pytest.raises(pt_error.CrawlerParseException):
            pt_momo.find_good_info(good_id="123")
