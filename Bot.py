import logging
import re

import requests
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

import Service
import PTConfig
import PTError
from Entity import UserGoodInfo
from Service import get_good_info, add_good_info, add_user_good_info, upsert_user

updater = Updater(token=PTConfig.BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
bot = telegram.Bot(token=PTConfig.BOT_TOKEN)


def run():
    bot_dispatcher = None
    if PTConfig.TELEGRAM_BOT_MODE == 'polling':
        bot_updater = Updater(token=PTConfig.BOT_TOKEN, use_context=True)
        bot_dispatcher = bot_updater.dispatcher
        bot_updater.start_polling()
    else:
        import os
        port = int(os.environ.get('PORT', '8443'))
        bot_updater = Updater(PTConfig.BOT_TOKEN)

        bot_updater.start_webhook(listen="0.0.0.0",
                                  port=port,
                                  url_path=PTConfig.BOT_TOKEN,
                                  webhook_url="https://momo-price-tracker.herokuapp.com/" + PTConfig.BOT_TOKEN)
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
    print('Bot Start')
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    upsert_user(user_id, chat_id)
    msg = '''/my 顯示追蹤清單\n/clear 清空追蹤清單\n直接貼上momo商品連結可加入追蹤清單'''
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg)


def auto_add_good(update, context):
    from urllib.parse import urlparse
    from urllib.parse import parse_qs
    try:
        url = update.message.text
        if 'https://momo.dm' in url:
            match = re.search('https.*momo.dm.*', url)
            response = requests.request("GET", match.group(0), headers=Service.basic_headers)
            url = response.url
        r = urlparse(url)
        d = parse_qs(r.query)
        good_id = str(d['i_code'][0])
        good_info = get_good_info(good_id)
        add_good_info(good_info)
        chat_id = update.message.chat_id
        user_id = update.message.from_user.id
        user_good_info = UserGoodInfo(user_id=user_id, chat_id=chat_id, good_id=good_id, original_price=good_info.price,
                                      is_notified=False)

        try:
            add_user_good_info(user_good_info)
            msg = '成功新增\n商品名稱:%s\n價格:%s' % (good_info.name, good_info.price)
            context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        except PTError.ExceedLimitedSizeError:
            context.bot.send_message(chat_id=update.effective_chat.id, text='追蹤物品已達11件')
    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=update.effective_chat.id, text='無效momo商品連結')


def my(update, context):
    user_id = str(update.message.from_user.id)
    my_goods = Service.find_user_sub_goods(user_id)
    if len(my_goods) == 0:
        context.bot.send_message(chat_id=update.effective_chat.id, text='尚未追蹤商品')
        return
    msg = '====\n商品名稱:%s\n追蹤價格:%s\n====\n'
    msgs = '追蹤清單\n'
    for my_good in my_goods:
        msgs = msgs + (msg % my_good)
    context.bot.send_message(chat_id=update.effective_chat.id, text=msgs)


def clear(update, context):
    user_id = str(update.message.from_user.id)
    Service.clear(user_id)
    context.bot.send_message(chat_id=update.effective_chat.id, text='已清空追蹤清單')


def send(msg, chat_id):
    bot.sendMessage(chat_id=chat_id, text=msg)
