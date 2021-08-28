import logging
import re

import requests
import telegram
from telegram import ChatAction
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

import pt_config
import pt_error
import pt_service
from pt_entity import UserGoodInfo, GoodInfo
from pt_service import get_good_info, add_good_info, add_user_good_info, upsert_user

updater = Updater(token=pt_config.BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher
bot = telegram.Bot(token=pt_config.BOT_TOKEN)
logger = logging.getLogger('Bot')


def run():
    bot_dispatcher = None
    if pt_config.TELEGRAM_BOT_MODE == 'polling':
        bot_updater = Updater(token=pt_config.BOT_TOKEN, use_context=True)
        bot_dispatcher = bot_updater.dispatcher
        bot_updater.start_polling()
    else:
        import os
        port = int(os.environ.get('PORT', '8443'))
        bot_updater = Updater(pt_config.BOT_TOKEN)

        bot_updater.start_webhook(listen="0.0.0.0",
                                  port=port,
                                  url_path=pt_config.BOT_TOKEN,
                                  webhook_url=pt_config.WEBHOOK_URL + pt_config.BOT_TOKEN)
        bot_dispatcher = bot_updater.dispatcher

    # add handlers
    start_handler = CommandHandler('start', start)
    bot_dispatcher.add_handler(start_handler)

    echo_handler = MessageHandler(Filters.text & (~Filters.command), auto_add_good)
    bot_dispatcher.add_handler(echo_handler)

    my_good_handler = CommandHandler('my', my)
    bot_dispatcher.add_handler(my_good_handler)

    clear_good_handler = CommandHandler('clear', clear)
    bot_dispatcher.add_handler(clear_good_handler)

    bot_updater.idle()


def start(update, context):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    upsert_user(user_id, chat_id)
    msg = '''/my 顯示追蹤清單\n/clear 清空追蹤清單\n直接貼上momo商品連結可加入追蹤清單'''
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg)


def auto_add_good(update, context):
    from urllib.parse import urlparse
    from urllib.parse import parse_qs
    try:
        chat_id = update.message.chat_id
        user_id = update.message.from_user.id
        # Verify momo url
        url = update.message.text
        if 'https://momo.dm' in url:
            match = re.search('https.*momo.dm.*', url)
            response = requests.request("GET", match.group(0), headers={'user-agent': pt_config.USER_AGENT},
                                        timeout=pt_config.MOMO_REQUEST_TIMEOUT)
            url = response.url
        r = urlparse(url)
        d = parse_qs(r.query)
        if 'i_code' not in d or len(d['i_code']) < 1:
            raise pt_error.NotValidMomoURL

        # Check the number of user sub goods
        if pt_service.count_user_good_info_sum(user_id) >= pt_config.USER_SUB_GOOD_LIMITED:
            raise pt_error.ExceedLimitedSizeError

        good_id = str(d['i_code'][0])
        good_info = get_good_info(good_id=good_id)
        add_good_info(good_info)
        user_good_info = UserGoodInfo(user_id=user_id, chat_id=chat_id, good_id=good_id, original_price=good_info.price,
                                      is_notified=False)
        stock_state_string = '可購買'
        if good_info.stock_state == GoodInfo.STOCK_STATE_OUT_OF_STOCK:
            stock_state_string = '缺貨中，請等待上架後通知'
        add_user_good_info(user_good_info)
        msg = '成功新增\n商品名稱:%s\n價格:%s\n狀態:%s' % (good_info.name, good_info.price, stock_state_string)
        context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    except pt_error.GoodNotExist:
        context.bot.send_message(chat_id=update.effective_chat.id, text='商品目前無展售或是網頁不存在')
    except pt_error.CrawlerParseError:
        context.bot.send_message(chat_id=update.effective_chat.id, text='商品頁面解析失敗')
    except pt_error.ExceedLimitedSizeError:
        context.bot.send_message(chat_id=update.effective_chat.id, text='追蹤物品已達%s件' % pt_config.USER_SUB_GOOD_LIMITED)
    except pt_error.NotValidMomoURL:
        context.bot.send_message(chat_id=update.effective_chat.id, text='無效momo商品連結')
    except Exception as e:
        logger.error("Catch an exception.", exc_info=True)
        context.bot.send_message(chat_id=update.effective_chat.id, text='Something wrong...try again.')


def my(update, context):
    user_id = str(update.message.from_user.id)
    my_goods = pt_service.find_user_sub_goods(user_id)
    if len(my_goods) == 0:
        context.bot.send_message(chat_id=update.effective_chat.id, text='尚未追蹤商品')
        return
    msg = '====\n商品名稱:%s\n追蹤價格:%s\n狀態:%s\n%s\n====\n'
    msgs = '追蹤清單\n'
    for my_good in my_goods:
        my_good = list(my_good)
        stock_state_string = '可購買'
        if my_good[2] == GoodInfo.STOCK_STATE_OUT_OF_STOCK:
            stock_state_string = '缺貨中，請等待上架後通知'
        elif my_good[2] == GoodInfo.STOCK_STATE_NOT_EXIST:
            stock_state_string = '商品目前無展售或是網頁不存在'
        my_good[2] = stock_state_string
        good_id = my_good[3]
        my_good[3] = pt_service.generate_momo_url_by_good_id(good_id)
        msgs = msgs + (msg % tuple(my_good))
    context.bot.send_message(chat_id=update.effective_chat.id, text=msgs)


def clear(update, context):
    user_id = str(update.message.from_user.id)
    good_name = None
    if len(context.args) > 1:
        good_name = context.args[1]
    removed_goods_name = pt_service.clear(user_id, good_name)
    response_msg = '無可清空的追蹤商品'
    if len(removed_goods_name) > 0:
        response_msg = '已清空以下物品\n'
        for good_name in removed_goods_name:
            response_msg += '====\n%s\n====\n' % good_name
    context.bot.send_message(chat_id=update.effective_chat.id, text=response_msg)


def send(msg, chat_id):
    if is_blocked_by_user(chat_id):
        return
    try:
        bot.sendMessage(chat_id=chat_id, text=msg)
    except:
        logger.error('Send message and catch the exception.', exc_info=True)


def is_blocked_by_user(chat_id):
    try:
        bot.send_chat_action(chat_id=str(chat_id), action=ChatAction.TYPING)
    except telegram.error.Unauthorized as e:
        if e.message == 'Forbidden: bot was blocked by the user':
            return True
    return False
