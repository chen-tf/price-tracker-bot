import asyncio
import inspect
import logging
import os

import telegram
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    Application, ContextTypes, filters, )

import pt_config
import pt_error
import pt_service
from lotify_client import get_lotify_client
from response.UserAddGoodResponse import UserAddGoodResponse

template_dir = os.path.abspath("templates")

lotify_client = get_lotify_client()

application = Application.builder().token(pt_config.BOT_TOKEN).build()
logger = logging.getLogger("bot")

UNTRACK = range(1)
ADD_GOOD = range(1)


def check_user_reg(func):
    def wrapper(*args, **kwargs):
        for arg in args:
            if isinstance(arg, Update):
                chat_id = str(arg.message.chat_id)
                user_id = str(arg.message.from_user.id)
                pt_service.ensure_user_registration(user_id, chat_id)
                break
        return func(*args, **kwargs)

    return wrapper


async def consume_request(request):
    update = telegram.Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)


def _register_bot_command_handler():
    start_handler = CommandHandler("start", start)
    application.add_handler(start_handler)

    line_handler = CommandHandler("line", line)
    application.add_handler(line_handler)

    add_good_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add", add)],
        fallbacks=[CommandHandler("cancel", cancel)],
        states={
            UNTRACK: [MessageHandler(filters.TEXT & (~filters.COMMAND), add_good)],
        },
    )

    application.add_handler(add_good_conv_handler)

    my_good_handler = CommandHandler("my", my_good)
    application.add_handler(my_good_handler)

    clear_all_my_good_handler = CommandHandler("clearall", clearall)
    application.add_handler(clear_all_my_good_handler)

    clear_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("clear", clear)],
        fallbacks=[CommandHandler("cancel", cancel)],
        states={
            UNTRACK: [MessageHandler(filters.TEXT & (~filters.COMMAND), untrack)],
        },
    )

    application.add_handler(clear_conv_handler)


@check_user_reg
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = f'''
            /my 顯示追蹤清單
            /clearall 清空全部追蹤清單
            /clear 刪除指定追蹤商品
            /add 後貼上momo商品連結可加入追蹤清單
            或是可以直接使用指令選單方便操作
            ====
            '''
    await update.message.reply_text(text=inspect.cleandoc(message))


@check_user_reg
async def line(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth_url = lotify_client.get_auth_link(state=update.message.from_user.id)
    msg = inspect.cleandoc(f"""
    你專屬的 LINE 通知綁定連結
    => 為確保綁定流程正常，請複製連結後在手機瀏覽器開啟
    {auth_url}
    """)
    await update.message.reply_text(text=msg)


@check_user_reg
async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("貼上momo商品連結加入收藏\n輸入 /cancel 後放棄動作")
    return ADD_GOOD


async def add_good(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    url = update.message.text
    try:
        response = pt_service.add_user_sub_good(user_id=user_id, url=url)
    except pt_error.Error as e:
        response = UserAddGoodResponse.error(type(e))
    except Exception:
        response = UserAddGoodResponse.error(pt_error.Error)
    await update.message.reply_text(text=response.to_message())
    return ConversationHandler.END


@check_user_reg
async def my_good(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    response = pt_service.find_user_sub_goods(user_id)
    await update.message.reply_html(text=response.to_message(), disable_web_page_preview=True)


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(text="請輸入想取消收藏的商品名稱 (有包含就可以)\n輸入 /cancel 放棄動作")
    return UNTRACK


async def clearall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    response = pt_service.clear_user_sub_goods(user_id, None)
    await update.message.reply_text(text=response.to_message())


async def untrack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    good_name = update.message.text
    response = pt_service.clear_user_sub_goods(user_id, good_name)
    await update.message.reply_text(text=response.to_message())
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(text="已放棄動作")
    return ConversationHandler.END


bot_event_loop = asyncio.new_event_loop()


def send(msg, chat_id):
    if is_blocked_by_user(chat_id):
        return
    try:
        bot_event_loop.run_until_complete(application.bot.sendMessage(chat_id=chat_id, text=msg))
    except:
        logger.error("Send message and catch the exception.", exc_info=True)


def is_blocked_by_user(chat_id):
    try:
        bot_event_loop.run_until_complete(
            application.bot.send_chat_action(chat_id=str(chat_id), action=ChatAction.TYPING))
    except telegram.error.Forbidden:
        return True
    except:
        logger.error("Failed to check block user", exc_info=True)
    return False


_register_bot_command_handler()
