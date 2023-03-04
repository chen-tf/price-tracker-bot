import inspect
import logging
import os

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
import pt_service
from lotify_client import get_lotify_client

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
    user_id = str(update.message.from_user.id)
    url = update.message.text
    response = pt_service.add_user_sub_good(user_id=user_id, url=url)
    context.bot.send_message(chat_id=update.effective_chat.id, text=response.to_message())
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
