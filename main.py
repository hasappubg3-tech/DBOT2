import os
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROUP_CHAT_ID = int(os.environ.get("GROUP_CHAT_ID", "0"))

user_topic_map: dict[int, int] = {}
topic_user_map: dict[int, int] = {}

WELCOME_MESSAGE = (
    "أهلا صديقنا 😊\n\n"
    "اكتب طلبك هنا (اي ملزمة او ملخص او ملف معين تريد ينضاف للبوت)\n"
    "وراح يتم اضافته ان شاء الله 😇"
)

REQUEST_RECEIVED = "حسناً صديقنا…تم ارسال طلبك للمشرفين وسوف يتم الرد باسرع وقت 😇"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME_MESSAGE)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📋 قائمة الأوامر:\n\n/start - بدء المحادثة\n/help - المساعدة\n/myid - معرفة رقمك"
    )


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"🆔 رقمك: `{chat_id}`", parse_mode="Markdown")


async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg:
        return

    user = update.effective_user
    chat_id = update.effective_chat.id

    if GROUP_CHAT_ID == 0:
        logger.error("GROUP_CHAT_ID is not set!")
        return

    if chat_id not in user_topic_map:
        user_name = user.full_name if user else "مجهول"
        username_part = f" (@{user.username})" if user and user.username else ""
        topic_name = f"{user_name}{username_part}"

        try:
            topic = await context.bot.create_forum_topic(
                chat_id=GROUP_CHAT_ID,
                name=topic_name,
            )
            topic_id = topic.message_thread_id
            user_topic_map[chat_id] = topic_id
            topic_user_map[topic_id] = chat_id

            await context.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                message_thread_id=topic_id,
                text=(
                    f"👤 مستخدم جديد\n"
                    f"الاسم: {user_name}{username_part}\n"
                    f"الرقم: `{chat_id}`"
                ),
                parse_mode="Markdown",
            )
            logger.info(f"Created topic {topic_id} for user {chat_id} ({topic_name})")
        except Exception as e:
            logger.error(f"Failed to create topic for user {chat_id}: {e}")
            return

        await msg.reply_text(REQUEST_RECEIVED)

    topic_id = user_topic_map[chat_id]

    try:
        await context.bot.copy_message(
            chat_id=GROUP_CHAT_ID,
            message_thread_id=topic_id,
            from_chat_id=chat_id,
            message_id=msg.message_id,
        )
        logger.info(f"Copied message from user {chat_id} to topic {topic_id}")
    except Exception as e:
        logger.error(f"Failed to forward message from user {chat_id} to topic {topic_id}: {e}")


async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg:
        return

    if not msg.message_thread_id:
        return

    if msg.from_user and msg.from_user.is_bot:
        return

    topic_id = msg.message_thread_id

    if topic_id not in topic_user_map:
        logger.warning(f"No user mapped to topic {topic_id}, ignoring.")
        return

    target_user_id = topic_user_map[topic_id]

    try:
        await context.bot.copy_message(
            chat_id=target_user_id,
            from_chat_id=GROUP_CHAT_ID,
            message_id=msg.message_id,
        )
        logger.info(f"Sent reply from topic {topic_id} to user {target_user_id}")
    except Exception as e:
        logger.error(f"Failed to send reply to user {target_user_id}: {e}")
        try:
            await msg.reply_text(f"❌ فشل الإرسال للمستخدم\nالسبب: {e}")
        except Exception:
            pass


def main() -> None:
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set")
    if GROUP_CHAT_ID == 0:
        raise ValueError("GROUP_CHAT_ID is not set — please set it in environment variables")

    logger.info(f"Bot starting. GROUP_CHAT_ID={GROUP_CHAT_ID}")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("myid", myid))

    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & ~filters.COMMAND,
            handle_user_message,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Chat(GROUP_CHAT_ID) & ~filters.COMMAND,
            handle_group_message,
        )
    )

    logger.info("Bot started with polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
