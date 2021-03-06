import logging
import re

import requests
import telegram
from telegram import ChatAction
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler

import pt_config
import pt_error
import pt_service
from pt_entity import UserGoodInfo, GoodInfo
from pt_service import get_good_info, add_good_info, add_user_good_info, upsert_user

updater = Updater(token=pt_config.BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher
bot = telegram.Bot(token=pt_config.BOT_TOKEN)
logger = logging.getLogger('Bot')

UNTRACK = range(1)
ADD_GOOD = range(1)

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

    add_good_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add', add)],
        fallbacks=[CommandHandler('cancel', cancel)],

        states={
            UNTRACK: [MessageHandler(Filters.text & (~Filters.command), add_good)],
        },
    )

    bot_dispatcher.add_handler(add_good_conv_handler)

    my_good_handler = CommandHandler('my', my)
    bot_dispatcher.add_handler(my_good_handler)

    clear_all_my_good_handler = CommandHandler('clearall', clearall)
    bot_dispatcher.add_handler(clear_all_my_good_handler)

    clear_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('clear', clear)],
        fallbacks=[CommandHandler('cancel', cancel)],

        states={
            UNTRACK: [MessageHandler(Filters.text & (~Filters.command), untrack)],
        },
    )

    bot_dispatcher.add_handler(clear_conv_handler)

    bot_updater.idle()


def start(update, context):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    upsert_user(user_id, chat_id)
    msg = '''/my ??????????????????\n/clearall ????????????????????????\n/clear ????????????????????????\n/add ?????????momo?????????????????????????????????\n????????????????????????????????????????????????'''
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg)


def add(update, context):
    update.message.reply_text('??????momo????????????????????????\n?????? /cancel ???????????????')
    return ADD_GOOD


def add_good(update, context):
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
        stock_state_string = '?????????'
        if good_info.stock_state == GoodInfo.STOCK_STATE_OUT_OF_STOCK:
            stock_state_string = '????????????????????????????????????'
        add_user_good_info(user_good_info)
        msg = '????????????\n????????????:%s\n??????:%s\n??????:%s' % (good_info.name, good_info.price, stock_state_string)
        context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    except pt_error.GoodNotExist:
        context.bot.send_message(chat_id=update.effective_chat.id, text='??????????????????????????????????????????')
    except pt_error.CrawlerParseError:
        context.bot.send_message(chat_id=update.effective_chat.id, text='????????????????????????')
    except pt_error.ExceedLimitedSizeError:
        context.bot.send_message(chat_id=update.effective_chat.id, text='??????????????????%s???' % pt_config.USER_SUB_GOOD_LIMITED)
    except pt_error.NotValidMomoURL:
        context.bot.send_message(chat_id=update.effective_chat.id, text='??????momo????????????')
    except Exception as e:
        logger.error("Catch an exception.", exc_info=True)
        context.bot.send_message(chat_id=update.effective_chat.id, text='Something wrong...try again.')
    finally:
        return ConversationHandler.END


def my(update, context):
    user_id = str(update.message.from_user.id)
    my_goods = pt_service.find_user_sub_goods(user_id)
    if len(my_goods) == 0:
        context.bot.send_message(chat_id=update.effective_chat.id, text='??????????????????')
        return
    msg = '====\n????????????:%s\n????????????:%s\n??????:%s\n%s\n====\n'
    msgs = '????????????\n'
    for my_good in my_goods:
        my_good = list(my_good)
        stock_state_string = '?????????'
        if my_good[2] == GoodInfo.STOCK_STATE_OUT_OF_STOCK:
            stock_state_string = '????????????????????????????????????'
        elif my_good[2] == GoodInfo.STOCK_STATE_NOT_EXIST:
            stock_state_string = '??????????????????????????????????????????'
        my_good[2] = stock_state_string
        good_id = my_good[3]
        my_good[3] = pt_service.generate_momo_url_by_good_id(good_id)
        msgs = msgs + (msg % tuple(my_good))
    context.bot.send_message(chat_id=update.effective_chat.id, text=msgs)


def clear(update, context):
    update.message.reply_text(text='??????????????????????????????????????? (??????????????????)\n?????? /cancel ????????????')
    return UNTRACK


def clearall(update, context):
    user_id = str(update.message.from_user.id)
    removed_goods_name = pt_service.clear(user_id, None)
    response_msg = '???????????????????????????'
    if len(removed_goods_name) > 0:
        response_msg = '?????????????????????\n'
        for good_name in removed_goods_name:
            response_msg += '====\n%s\n====\n' % good_name
    context.bot.send_message(chat_id=update.effective_chat.id, text=response_msg)


def untrack(update, context):
    user_id = str(update.message.from_user.id)
    good_name = update.message.text
    removed_goods_name = pt_service.clear(user_id, good_name)
    response_msg = '???????????????????????????'
    if len(removed_goods_name) > 0:
        response_msg = '?????????????????????\n'
        for good_name in removed_goods_name:
            response_msg += '====\n%s\n====\n' % good_name
    update.message.reply_text(text=response_msg)
    return ConversationHandler.END


def cancel(update, context):
    update.message.reply_text(text='???????????????')
    return ConversationHandler.END


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
