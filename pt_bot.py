import inspect
import logging
import os
import re

import requests
import telegram
from telegram import ChatAction, Update
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    Filters,
    MessageHandler,
    Updater,
)

import pt_config
import pt_error
import pt_service
from lotify_client import get_lotify_client
from repository import UserSubGood, UserSubGoodState
from repository.models import GoodInfoStockState

template_dir = os.path.abspath("Templates")

lotify_client = get_lotify_client()

telegram_updater = Updater(token=pt_config.BOT_TOKEN, use_context=True)
telegram_dispatcher = telegram_updater.dispatcher
bot = telegram.Bot(token=pt_config.BOT_TOKEN)
logger = logging.getLogger("bot")

UNTRACK = range(1)
ADD_GOOD = range(1)


def check_user_reg(func):
    def wrapper(*args, **kwargs):
        for arg in args:
            if isinstance(arg, Update):
                chat_id = str(arg.message.chat_id)
                user_id = str(arg.message.from_user.id)
                pt_service.reg_user(user_id, chat_id)
                break
        return func(*args, **kwargs)

    return wrapper


def consume_request(request):
    update = telegram.Update.de_json(request.get_json(force=True), bot)
    telegram_dispatcher.process_update(update)


def _register_bot_command_handler():
    start_handler = CommandHandler("start", start)
    telegram_dispatcher.add_handler(start_handler)

    line_handler = CommandHandler("line", line)
    telegram_dispatcher.add_handler(line_handler)

    add_good_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add", add)],
        fallbacks=[CommandHandler("cancel", cancel)],
        states={
            UNTRACK: [MessageHandler(Filters.text & (~Filters.command), add_good)],
        },
    )

    telegram_dispatcher.add_handler(add_good_conv_handler)

    my_good_handler = CommandHandler("my", my_good)
    telegram_dispatcher.add_handler(my_good_handler)

    clear_all_my_good_handler = CommandHandler("clearall", clearall)
    telegram_dispatcher.add_handler(clear_all_my_good_handler)

    clear_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("clear", clear)],
        fallbacks=[CommandHandler("cancel", cancel)],
        states={
            UNTRACK: [MessageHandler(Filters.text & (~Filters.command), untrack)],
        },
    )

    telegram_dispatcher.add_handler(clear_conv_handler)


@check_user_reg
def start(update, context):
    message = f'''
            /my 顯示追蹤清單
            /clearall 清空全部追蹤清單
            /clear 刪除指定追蹤商品
            /add 後貼上momo商品連結可加入追蹤清單
            或是可以直接使用指令選單方便操作
            ====
            '''
    context.bot.send_message(chat_id=update.effective_chat.id, text=inspect.cleandoc(message))


@check_user_reg
def line(update, context):
    auth_url = lotify_client.get_auth_link(state=update.message.from_user.id)
    msg = f"你專屬的 LINE 通知綁定連結\n{auth_url}"
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg)


@check_user_reg
def add(update, context):
    update.message.reply_text("貼上momo商品連結加入收藏\n輸入 /cancel 後放棄動作")
    return ADD_GOOD


def add_good(update, context):
    from urllib.parse import parse_qs, urlparse

    try:
        user_id = str(update.message.from_user.id)
        # Verify momo url
        url = update.message.text
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
        if "i_code" not in query or len(query["i_code"]) < 1:
            raise pt_error.NotValidMomoURL

        # Check the number of user sub goods
        if pt_service.count_user_good_info_sum(user_id) >= pt_config.USER_SUB_GOOD_LIMITED:
            raise pt_error.ExceedLimitedSizeError

        good_id = str(query["i_code"][0])
        good_info = pt_service.get_good_info(good_id=good_id)
        pt_service.add_good_info(good_info)
        user_sub_good = UserSubGood(
            user_id=user_id,
            good_id=good_id,
            price=good_info.price,
            is_notified=False,
            state=UserSubGoodState.ENABLE
        )
        stock_state_string = "可購買"
        if good_info.stock_state == GoodInfoStockState.OUT_OF_STOCK:
            stock_state_string = "缺貨中，請等待上架後通知"
        pt_service.add_user_good_info(user_sub_good)
        msg = f"成功新增\n商品名稱:{good_info.name}\n價格:{good_info.price}\n狀態:{stock_state_string}"
        context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    except pt_error.GoodNotExist:
        context.bot.send_message(chat_id=update.effective_chat.id, text="商品目前無展售或是網頁不存在")
    except pt_error.CrawlerParseError or pt_error.EmptyPageError:
        context.bot.send_message(chat_id=update.effective_chat.id, text="商品頁面解析失敗")
    except pt_error.ExceedLimitedSizeError:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"追蹤物品已達{pt_config.USER_SUB_GOOD_LIMITED}件",
        )
    except pt_error.NotValidMomoURL:
        context.bot.send_message(chat_id=update.effective_chat.id, text="無效momo商品連結")
    except Exception:
        logger.error("Catch an exception.", exc_info=True)
        context.bot.send_message(
            chat_id=update.effective_chat.id, text="Something wrong...try again."
        )

    return ConversationHandler.END


@check_user_reg
def my_good(update, context):
    user_id = str(update.message.from_user.id)
    response = pt_service.find_user_sub_goods(user_id)
    context.bot.send_message(chat_id=update.effective_chat.id, text=response.to_message())


def clear(update, context):
    update.message.reply_text(text="請輸入想取消收藏的商品名稱 (有包含就可以)\n輸入 /cancel 放棄動作")
    return UNTRACK


def clearall(update, context):
    user_id = str(update.message.from_user.id)
    response = pt_service.clear(user_id, None)
    context.bot.send_message(chat_id=update.effective_chat.id, text=response.to_message())


def untrack(update, context):
    user_id = str(update.message.from_user.id)
    good_name = update.message.text
    response = pt_service.clear(user_id, good_name)
    update.message.reply_text(text=response.to_message())
    return ConversationHandler.END


def cancel(update, context):
    update.message.reply_text(text="已放棄動作")
    return ConversationHandler.END


def send(msg, chat_id):
    if is_blocked_by_user(chat_id):
        return
    try:
        bot.sendMessage(chat_id=chat_id, text=msg)
    except:
        logger.error("Send message and catch the exception.", exc_info=True)


def is_blocked_by_user(chat_id):
    try:
        bot.send_chat_action(chat_id=str(chat_id), action=ChatAction.TYPING)
    except telegram.error.Unauthorized as ex:
        if ex.message == "Forbidden: bot was blocked by the user":
            return True
    except:
        logger.error("Failed to check block user", exc_info=True)
    return False


_register_bot_command_handler()
if pt_config.TELEGRAM_BOT_MODE == "polling":
    telegram_updater.start_polling()
else:
    telegram_updater.bot.setWebhook(url=pt_config.WEBHOOK_URL + "webhook/" + pt_config.BOT_TOKEN)
