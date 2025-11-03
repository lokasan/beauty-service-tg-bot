"""
Общие обработчики
"""
from sqlalchemy.orm import Session
from bot.models import User, UserRole
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__)


def get_db_from_context(context: ContextTypes.DEFAULT_TYPE):
    """Получение сессии БД из контекста"""
    db_func = context.bot_data.get('db_session')
    if callable(db_func):
        return db_func()
    else:
        return db_func


async def get_or_create_user(db: Session, telegram_id: int, username: str = None, full_name: str = None) -> User:
    """Получение или создание пользователя"""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            role=UserRole.CLIENT
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Создан новый пользователь: {telegram_id}")
    else:
        # Обновление данных если изменились
        if username and user.username != username:
            user.username = username
        if full_name and user.full_name != full_name:
            user.full_name = full_name
        db.commit()
    
    return user


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    db = get_db_from_context(context)
    user_data = update.effective_user
    
    # Проверяем, есть ли параметр после /start
    if context.args and len(context.args) > 0:
        start_param = context.args[0]
        
        # Если это возврат после оплаты
        if start_param.startswith("payment_"):
            invoice_id = int(start_param.split("_")[1])
            from bot.models import Invoice
            
            # Получаем чек
            invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
            
            if invoice:
                message_text = (
                    f"💳 Возврат после оплаты\n\n"
                    f"Услуга: {invoice.description}\n"
                    f"Сумма: {invoice.amount:.2f} ₽\n\n"
                    f"Проверяем статус платежа..."
                )
                
                await update.message.reply_text(message_text)
                
                # Проверяем статус платежа
                if invoice.payment_id:
                    from bot.utils.payments import check_payment_status
                    from bot.models import PaymentStatus
                    from datetime import datetime
                    
                    payment_status = check_payment_status(invoice.payment_id)
                    
                    if payment_status == "succeeded":
                        invoice.payment_status = PaymentStatus.SUCCEEDED
                        invoice.paid_at = datetime.utcnow()
                        db.commit()
                        
                        await update.message.reply_text(
                            f"✅ Чек оплачен!\n\n"
                            f"Услуга: {invoice.description}\n"
                            f"Сумма: {invoice.amount:.2f} ₽\n"
                            f"Спасибо за оплату!"
                        )
                    else:
                        await update.message.reply_text(
                            f"⏳ Платеж обрабатывается. Проверьте статус позже."
                        )
            
            # Показываем главное меню после обработки оплаты
            # (продолжаем выполнение)
        
        # Проверка на ссылку мастера (все остальные параметры)
        else:
            # Это запись по ссылке
            from bot.handlers import client
            await client.handle_master_link(update, context)
            return
    
    user = await get_or_create_user(
        db,
        user_data.id,
        user_data.username,
        user_data.full_name
    )
    
    if user.role == UserRole.MASTER:
        # Мастер
        keyboard = [
            [InlineKeyboardButton("📋 Мои услуги", callback_data="master_services")],
            [InlineKeyboardButton("📅 Мои записи", callback_data="master_appointments")],
            [InlineKeyboardButton("⚙️ Настройки", callback_data="master_settings")],
            [InlineKeyboardButton("🔗 Моя ссылка", callback_data="master_link")],
            [InlineKeyboardButton("📝 Записаться к мастеру", callback_data="book_by_link")]
        ]
    else:
        # Обычный пользователь
        keyboard = [
            [InlineKeyboardButton("👤 Стать мастером", callback_data="become_master")],
            [InlineKeyboardButton("📝 Записаться к мастеру", callback_data="book_by_link")],
            [InlineKeyboardButton("📅 Мои записи", callback_data="client_appointments")],
            [InlineKeyboardButton("💬 Обратная связь", callback_data="feedback")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"Привет, {user_data.first_name}! 👋\n\n"
        f"Я помогу вам управлять записями к мастерам.\n\n"
        f"Выберите действие:"
    )
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=reply_markup)
    
    logger.info(f"Команда /start от пользователя {user_data.id}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "📖 Помощь\n\n"
        "Для мастеров:\n"
        "• /start - главное меню\n"
        "• Создайте профиль мастера через меню\n"
        "• Добавьте услуги и настройте расписание\n"
        "• Получите уникальную ссылку для записи клиентов\n\n"
        "Для клиентов:\n"
        "• Перейдите по ссылке мастера\n"
        "• Выберите услугу и удобное время\n"
        "• Получите уведомления о записи\n\n"
        "💬 По вопросам обращайтесь через меню 'Обратная связь'"
    )
    await update.message.reply_text(help_text)


async def feedback_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик обратной связи"""
    query = update.callback_query
    if query:
        await query.answer()
    
    message_text = (
        "💬 Обратная связь\n\n"
        "Пожалуйста, опишите ваше предложение, замечание или проблему:"
    )
    
    context.user_data['waiting_for_feedback'] = True
    
    if query:
        await query.edit_message_text(message_text)
    else:
        await update.message.reply_text(message_text)


async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текста обратной связи"""
    if not context.user_data.get('waiting_for_feedback'):
        return
    
    feedback_text = update.message.text.strip()
    user_data = update.effective_user
    
    if len(feedback_text) < 5:
        await update.message.reply_text(
            "❌ Сообщение слишком короткое. Пожалуйста, опишите подробнее:"
        )
        return
    
    # Сохранение обратной связи в БД
    db = get_db_from_context(context)
    from bot.models import Feedback, User
    
    user = await get_or_create_user(db, user_data.id, user_data.username, user_data.full_name)
    
    feedback = Feedback(
        user_id=user.id,
        message=feedback_text,
        rating=None
    )
    db.add(feedback)
    db.commit()
    
    context.user_data.pop('waiting_for_feedback', None)
    
    keyboard = [
        [InlineKeyboardButton("🏠 Главное меню", callback_data="start_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "✅ Спасибо за вашу обратную связь! Мы обязательно учтем ваше мнение.",
        reply_markup=reply_markup
    )
    
    logger.info(f"Получена обратная связь от пользователя {user_data.id}: {feedback_text[:50]}...")

