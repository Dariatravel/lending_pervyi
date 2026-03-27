import logging
import os
from dataclasses import dataclass, field

from telegram import ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


ASK_NAME, ASK_NICHE, ASK_FORMAT, ASK_BUDGET, ASK_CONTACT = range(5)


@dataclass
class LeadForm:
    name: str = ""
    niche: str = ""
    format: str = ""
    budget: str = ""
    contact: str = ""

    def text(self, user_id: int, username: str | None) -> str:
        username_text = f"@{username}" if username else "без username"
        return (
            "Новая заявка на сотрудничество\n\n"
            f"Имя: {self.name}\n"
            f"Ниша/проект: {self.niche}\n"
            f"Формат сотрудничества: {self.format}\n"
            f"Бюджет: {self.budget}\n"
            f"Контакт для связи: {self.contact}\n\n"
            f"Telegram user id: {user_id}\n"
            f"Telegram username: {username_text}"
        )


def get_form(context: ContextTypes.DEFAULT_TYPE) -> LeadForm:
    if "lead_form" not in context.user_data:
        context.user_data["lead_form"] = LeadForm()
    return context.user_data["lead_form"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["lead_form"] = LeadForm()
    await update.message.reply_text(
        "Привет! Это анкета для сотрудничества.\n"
        "Ответь на 5 коротких вопросов.\n\n"
        "1/5 Как тебя зовут?"
    )
    return ASK_NAME


async def ask_niche(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    form = get_form(context)
    form.name = update.message.text.strip()
    await update.message.reply_text("2/5 Какая у тебя ниша или проект?")
    return ASK_NICHE


async def ask_format(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    form = get_form(context)
    form.niche = update.message.text.strip()
    await update.message.reply_text(
        "3/5 Какой формат сотрудничества интересует? "
        "(например: реклама, бартер, интеграция, долгосрочный проект)"
    )
    return ASK_FORMAT


async def ask_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    form = get_form(context)
    form.format = update.message.text.strip()
    await update.message.reply_text("4/5 Какой бюджет или вилка бюджета?")
    return ASK_BUDGET


async def ask_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    form = get_form(context)
    form.budget = update.message.text.strip()
    await update.message.reply_text(
        "5/5 Оставь контакт для связи (телефон, @username, email)."
    )
    return ASK_CONTACT


async def finish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    owner_chat_id = os.getenv("OWNER_CHAT_ID")
    if not owner_chat_id:
        await update.message.reply_text(
            "Ошибка настройки: не найден OWNER_CHAT_ID. Напиши владельцу бота."
        )
        return ConversationHandler.END

    form = get_form(context)
    form.contact = update.message.text.strip()

    await context.bot.send_message(
        chat_id=int(owner_chat_id),
        text=form.text(
            user_id=update.effective_user.id,
            username=update.effective_user.username,
        ),
    )

    await update.message.reply_text(
        "Спасибо! Заявка отправлена. Я скоро вернусь с ответом.",
        reply_markup=ReplyKeyboardRemove(),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Ок, анкету отменили. Если захочешь снова, отправь /start.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


def build_app() -> Application:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")

    app = Application.builder().token(token).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_niche)],
            ASK_NICHE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_format)],
            ASK_FORMAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_budget)],
            ASK_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_contact)],
            ASK_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, finish)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("cancel", cancel))
    return app


if __name__ == "__main__":
    application = build_app()
    application.run_polling(allowed_updates=Update.ALL_TYPES)
