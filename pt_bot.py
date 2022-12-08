import logging
import re

import requests
import telegram
from flask import Flask, request, Response
from telegram import ChatAction
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler

import pt_config
import pt_error
import pt_momo
import pt_service
from lotify_client import get_lotify_client
from pt_entity import UserGoodInfo, GoodInfo

updater = Updater(token=pt_config.BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher
bot = telegram.Bot(token=pt_config.BOT_TOKEN)
logger = logging.getLogger('Bot')
lotify_client = get_lotify_client()

UNTRACK = range(1)
ADD_GOOD = range(1)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=pt_config.LOGGING_LEVEL, force=True)
app = Flask(__name__)


# required hook endpoint to get the data from telegram
@app.route('/webhook/' + pt_config.BOT_TOKEN, methods=['POST', 'GET'])
def webhook_handler():
    if request.method == "POST":
        update = telegram.Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
    return Response('OK', status=200)


def _register_bot_command_handler():
    start_handler = CommandHandler('start', start)
    dispatcher.add_handler(start_handler)

    line_handler = CommandHandler('line', line)
    dispatcher.add_handler(line_handler)

    add_good_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add', add)],
        fallbacks=[CommandHandler('cancel', cancel)],
        states={
            UNTRACK: [MessageHandler(Filters.text & (~Filters.command), add_good)],
        },
        run_async=True
    )

    dispatcher.add_handler(add_good_conv_handler)

    my_good_handler = CommandHandler('my', my)
    dispatcher.add_handler(my_good_handler)

    clear_all_my_good_handler = CommandHandler('clearall', clearall)
    dispatcher.add_handler(clear_all_my_good_handler)

    clear_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('clear', clear)],
        fallbacks=[CommandHandler('cancel', cancel)],

        states={
            UNTRACK: [MessageHandler(Filters.text & (~Filters.command), untrack)],
        },
        run_async=True
    )

    dispatcher.add_handler(clear_conv_handler)

    # updater.idle()


def start(update, context):
    user_reg(update)
    msg = '''/my 顯示追蹤清單\n/clearall 清空全部追蹤清單\n/clear 刪除指定追蹤商品\n/add 後貼上momo商品連結可加入追蹤清單\n或是可以直接使用指令選單方便操作'''
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg)


def line(update, context):
    user_reg(update)
    auth_url = lotify_client.get_auth_link(state=update.message.from_user.id)
    msg = f'你專屬的 LINE 通知綁定連結\n{auth_url}'
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg)


def add(update, context):
    user_reg(update)
    update.message.reply_text('貼上momo商品連結加入收藏\n輸入 /cancel 後放棄動作')
    return ADD_GOOD


def user_reg(update):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    pt_service.upsert_user(user_id, chat_id)


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
                                        timeout=(10, 15))
            url = response.url
        r = urlparse(url)
        d = parse_qs(r.query)
        if 'i_code' not in d or len(d['i_code']) < 1:
            raise pt_error.NotValidMomoURL

        # Check the number of user sub goods
        if pt_service.count_user_good_info_sum(user_id) >= pt_config.USER_SUB_GOOD_LIMITED:
            raise pt_error.ExceedLimitedSizeError

        good_id = str(d['i_code'][0])
        good_info = pt_service.get_good_info(good_id=good_id)
        pt_service.add_good_info(good_info)
        user_good_info = UserGoodInfo(user_id=user_id, chat_id=chat_id, good_id=good_id, original_price=good_info.price,
                                      is_notified=False)
        stock_state_string = '可購買'
        if good_info.stock_state == GoodInfo.STOCK_STATE_OUT_OF_STOCK:
            stock_state_string = '缺貨中，請等待上架後通知'
        pt_service.add_user_good_info(user_good_info)
        msg = '成功新增\n商品名稱:%s\n價格:%s\n狀態:%s' % (good_info.name, good_info.price, stock_state_string)
        context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    except pt_error.GoodNotExist:
        context.bot.send_message(chat_id=update.effective_chat.id, text='商品目前無展售或是網頁不存在')
    except pt_error.CrawlerParseError:
        context.bot.send_message(chat_id=update.effective_chat.id, text='商品頁面解析失敗')
    except pt_error.ExceedLimitedSizeError:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='追蹤物品已達%s件' % pt_config.USER_SUB_GOOD_LIMITED)
    except pt_error.NotValidMomoURL:
        context.bot.send_message(chat_id=update.effective_chat.id, text='無效momo商品連結')
    except Exception:
        logger.error("Catch an exception.", exc_info=True)
        context.bot.send_message(chat_id=update.effective_chat.id, text='Something wrong...try again.')
    finally:
        return ConversationHandler.END


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
        my_good[3] = pt_momo.generate_momo_url_by_good_id(good_id)
        msgs = msgs + (msg % tuple(my_good))
    context.bot.send_message(chat_id=update.effective_chat.id, text=msgs)


def clear(update, context):
    update.message.reply_text(text='請輸入想取消收藏的商品名稱 (有包含就可以)\n輸入 /cancel 放棄動作')
    return UNTRACK


def clearall(update, context):
    user_id = str(update.message.from_user.id)
    removed_goods_name = pt_service.clear(user_id, None)
    response_msg = '無可清空的追蹤商品'
    if len(removed_goods_name) > 0:
        response_msg = '已清空以下物品\n'
        for good_name in removed_goods_name:
            response_msg += '====\n%s\n====\n' % good_name
    context.bot.send_message(chat_id=update.effective_chat.id, text=response_msg)


def untrack(update, context):
    user_id = str(update.message.from_user.id)
    good_name = update.message.text
    removed_goods_name = pt_service.clear(user_id, good_name)
    response_msg = '無可清空的追蹤商品'
    if len(removed_goods_name) > 0:
        response_msg = '已清空以下物品\n'
        for good_name in removed_goods_name:
            response_msg += '====\n%s\n====\n' % good_name
    update.message.reply_text(text=response_msg)
    return ConversationHandler.END


def cancel(update, context):
    update.message.reply_text(text='已放棄動作')
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
    except Exception:
        logger.error('Failed to check block user', exc_info=True)
    return False


if __name__ == '__main__':
    _register_bot_command_handler()
    if pt_config.TELEGRAM_BOT_MODE == 'polling':
        updater.start_polling()
    else:
        updater.bot.setWebhook(url=pt_config.WEBHOOK_URL + 'webhook/' + pt_config.BOT_TOKEN)
        app.run('0.0.0.0', pt_config.PORT, False, True)
