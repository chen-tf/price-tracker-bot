import asyncio
import inspect
import logging
import os
from functools import wraps

import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import pt_config
import pt_error
import pt_service
from response.UserAddGoodResponse import UserAddGoodResponse

CLEAR_USER_SUB_GOODS_TEXT = "請點選要刪除的商品"

template_dir = os.path.abspath("templates")

application = None
logger = logging.getLogger("bot")

UNTRACK = range(1)
ADD_GOOD = range(1)


def _is_private_update(update):
    chat, user = update.effective_chat, update.effective_user
    return bool(chat and user and chat.type == "private" and chat.id == user.id)


def check_user_reg(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        for arg in args:
            if isinstance(arg, Update):
                if not _is_private_update(arg):
                    return None
                chat_id = str(arg.message.chat_id)
                user_id = str(arg.message.from_user.id)
                pt_service.ensure_user_registration(user_id, chat_id)
                break
        return await func(*args, **kwargs)

    return wrapper


async def consume_request(request):
    update = telegram.Update.de_json(request.get_json(force=True), get_application().bot)
    await get_application().process_update(update)


def _register_bot_command_handler(application):
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

    application.add_handler(CallbackQueryHandler(clear_callback))

    application.add_handler(CommandHandler("clear", clear))


@check_user_reg
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = f"""
            /my 顯示追蹤清單
            /clearall 清空全部追蹤清單
            /clear 刪除指定追蹤商品
            /add 後貼上momo商品連結可加入追蹤清單
            或是可以直接使用指令選單方便操作
            ====
            """
    await update.message.reply_text(text=inspect.cleandoc(message))


@check_user_reg
async def line(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "LINE Notify 已於 2025/03/31 終止服務，目前透過 Telegram 發送通知。"
    )


@check_user_reg
async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("貼上momo商品連結加入收藏\n輸入 /cancel 後放棄動作")
    return ADD_GOOD


@check_user_reg
async def add_good(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    url = update.message.text
    try:
        response = pt_service.add_user_sub_good(user_id=user_id, url=url)
    except pt_error.Error as e:
        response = UserAddGoodResponse.failure(type(e))
    except Exception:
        response = UserAddGoodResponse.failure(pt_error.Error)
    await update.message.reply_text(text=response.to_message())
    return ConversationHandler.END


@check_user_reg
async def my_good(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    response = pt_service.find_user_sub_goods(user_id)
    await update.message.reply_html(text=response.to_message(), disable_web_page_preview=True)


@check_user_reg
async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_markup = _create_user_sub_goods_buttons(str(update.message.from_user.id))
    await update.message.reply_text(CLEAR_USER_SUB_GOODS_TEXT, reply_markup=reply_markup)


async def clear_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and updates the message text."""
    if not _is_private_update(update):
        return
    query = update.callback_query

    await query.answer()

    if CLEAR_USER_SUB_GOODS_TEXT in query.message.text:
        user_id = str(query.from_user.id)
        clear_response = pt_service.clear_user_sub_goods_by_id(user_id, query.data)
        message = query.message.text + f"\n====\n{clear_response.removed_good_names[0]}\n===="
        reply_markup = _create_user_sub_goods_buttons(user_id)
        await query.edit_message_text(text=message, reply_markup=reply_markup)


def _create_user_sub_goods_buttons(user_id: str) -> InlineKeyboardMarkup:
    keyboard = []
    for element in pt_service.find_user_sub_goods(user_id).user_sub_goods:
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"{element.good_info.name.strip()}", callback_data=f"{element.good_id}"
                )
            ]
        )
    return InlineKeyboardMarkup(keyboard)


@check_user_reg
async def clearall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    response = pt_service.clear_user_sub_goods(user_id, None)
    await update.message.reply_text(text=response.to_message())


@check_user_reg
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
        bot_event_loop.run_until_complete(
            get_application().bot.send_message(chat_id=chat_id, text=msg)
        )
    except:
        logger.error("Send message and catch the exception.", exc_info=True)


def is_blocked_by_user(chat_id):
    try:
        bot_event_loop.run_until_complete(
            get_application().bot.send_chat_action(chat_id=str(chat_id), action=ChatAction.TYPING)
        )
    except telegram.error.Forbidden:
        return True
    except:
        logger.error("Failed to check block user", exc_info=True)
    return False


def get_application():
    global application
    if application is None:
        if not pt_config.BOT_TOKEN:
            raise RuntimeError(
                "BOT_TOKEN must be configured before starting the optional Python bot"
            )
        application = Application.builder().token(pt_config.BOT_TOKEN).build()
        _register_bot_command_handler(application)
    return application
