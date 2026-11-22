import asyncio
import importlib
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

from telegram import Update

import app
import pt_bot
import pt_config
from repository.entity import GoodInfo, GoodInfoStockState, UserSubGood
from response.MySubGoodsResponse import UserSubGoodsResponse


def test_importing_app_does_not_start_threads_or_register_a_webhook():
    with (
        patch("threading.Thread.start") as start,
        patch.object(pt_bot, "get_application") as application,
    ):
        importlib.reload(app)
        start.assert_not_called()
        application.assert_not_called()


def test_optional_webhook_requires_secret_and_uses_a_token_free_path(monkeypatch):
    monkeypatch.setattr(pt_config, "WEBHOOK_SECRET", "test-secret")
    client = app.app.test_client()
    with patch.object(pt_bot, "get_application") as application:
        assert client.post("/webhook").status_code == 401
        assert client.get("/webhook").status_code == 405
        assert client.post("/webhook/fake-token").status_code == 404
        assert client.get("/line-subscribe?code=ignored&state=10").status_code == 410
        application.assert_not_called()
    context = MagicMock()
    context.__aenter__ = AsyncMock()
    context.__aexit__ = AsyncMock(return_value=False)
    with (
        patch.object(pt_bot, "get_application", return_value=context),
        patch.object(pt_bot, "consume_request", new_callable=AsyncMock) as consume,
    ):
        assert (
            client.post(
                "/webhook", headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"}, json={}
            ).status_code
            == 200
        )
        consume.assert_awaited_once()


def test_telegram_registration_decorator_remains_async():
    assert inspect.iscoroutinefunction(pt_bot.start)
    update = Update.de_json(
        {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "date": 0,
                "chat": {"id": 10, "type": "private"},
                "from": {"id": 10, "first_name": "Test", "is_bot": False},
                "text": "/start",
            },
        },
        None,
    )
    with (
        patch("pt_service.ensure_user_registration") as registration,
        patch("telegram.Message.reply_text", new_callable=AsyncMock) as reply,
    ):
        asyncio.run(pt_bot.start(update, None))
        registration.assert_called_once_with("10", "10")
        reply.assert_awaited_once()


def test_html_list_escapes_product_names_and_reads_product_stock():
    good = GoodInfo(
        id="123", name="<script>&", price=100, stock_state=GoodInfoStockState.OUT_OF_STOCK
    )
    subscription = UserSubGood(good_id="123", price=100, state=1, good_info=good)
    message = UserSubGoodsResponse([subscription]).to_message()
    assert "&lt;script&gt;&amp;" in message
    assert "缺貨中" in message


def test_group_commands_cannot_register_or_expose_private_lists():
    update = Update.de_json(
        {
            "update_id": 2,
            "message": {
                "message_id": 2,
                "date": 0,
                "chat": {"id": -100, "type": "group", "title": "test"},
                "from": {"id": 10, "first_name": "Test", "is_bot": False},
                "text": "/my",
            },
        },
        None,
    )
    with (
        patch("pt_service.ensure_user_registration") as registration,
        patch("pt_service.find_user_sub_goods") as listing,
    ):
        asyncio.run(pt_bot.my_good(update, None))
        registration.assert_not_called()
        listing.assert_not_called()
