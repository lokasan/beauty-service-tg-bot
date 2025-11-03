"""
Обработчики для работы с чеками и оплатами
"""
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from bot.models import Invoice, Appointment, AppointmentStatus, PaymentStatus, User
from bot.utils.telegram_helpers import safe_edit_message_text
from bot.handlers.common import get_db_from_context
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def create_invoice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выставление чека для завершенной записи"""
    query = update.callback_query
    await query.answer()
    
    db = get_db_from_context(context)
    user_data = update.effective_user
    
    # Извлекаем ID записи из callback_data
    appointment_id = int(query.data.split("_")[-1])
    
    # Получаем запись
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    
    if not appointment:
        await safe_edit_message_text(query, "Ошибка: запись не найдена")
        return
    
    # Проверяем, что пользователь - мастер этой записи
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    if not user or not user.master_profile or user.master_profile.id != appointment.master_id:
        await safe_edit_message_text(query, "Ошибка: у вас нет доступа к этой записи")
        return
    
    # Проверяем, что запись завершена
    if appointment.status != AppointmentStatus.COMPLETED:
        await safe_edit_message_text(query, "Ошибка: запись еще не завершена")
        return
    
    # Проверяем, не создан ли уже чек
    existing_invoice = db.query(Invoice).filter(Invoice.appointment_id == appointment_id).first()
    if existing_invoice:
        await safe_edit_message_text(query, "Чек уже был выставлен для этой записи")
        return
    
    # Получаем стоимость услуги
    service = appointment.service
    amount = service.price
    
    # Создаем чек
    # FreedomPay KG работает с KGS, но сохраняем оригинальную сумму в базе
    invoice = Invoice(
        appointment_id=appointment_id,
        master_id=appointment.master_id,
        client_id=appointment.client_id,
        amount=amount,
        currency="KGS",  # FreedomPay KG использует KGS
        description=f"{service.name} - {appointment.start_time.strftime('%d.%m.%Y %H:%M')}",
        payment_status=PaymentStatus.PENDING
    )
    
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    
    # Предлагаем выбрать метод оплаты
    keyboard = [
        [
            InlineKeyboardButton("💳 Карта", callback_data=f"payment_method_card_{invoice.id}"),
            InlineKeyboardButton("📱 СБП", callback_data=f"payment_method_sbp_{invoice.id}")
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data="master_appointments")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        f"💳 Чек выставлен\n\n"
        f"Запись: {service.name}\n"
        f"Дата: {appointment.start_time.strftime('%d.%m.%Y %H:%M')}\n"
        f"Клиент: {appointment.client_name or appointment.client.full_name}\n"
        f"Сумма: {amount:.2f} ₽\n\n"
        f"Выберите метод оплаты:"
    )
    
    await safe_edit_message_text(query, message, reply_markup=reply_markup)


async def payment_method_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создание платежа с выбранным методом оплаты через Telegram Bot Payments"""
    query = update.callback_query
    await query.answer()
    
    db = get_db_from_context(context)
    
    # Извлекаем метод оплаты и ID чека
    parts = query.data.split("_")
    payment_method = parts[2]  # card или sbp (не используется для Telegram Payments)
    invoice_id = int(parts[3])
    
    # Получаем чек
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    
    if not invoice:
        await safe_edit_message_text(query, "Ошибка: чек не найден")
        return
    
    # Проверяем, что платеж еще не создан
    if invoice.payment_id:
        await safe_edit_message_text(query, "Платеж уже был создан для этого чека")
        return
    
    # Проверяем настройку Telegram Payment Provider Token
    from bot.config import TELEGRAM_PAYMENT_PROVIDER_TOKEN
    
    if not TELEGRAM_PAYMENT_PROVIDER_TOKEN:
        await safe_edit_message_text(
            query,
            "Ошибка: платежная система не настроена. Обратитесь к администратору."
        )
        return
    
    # Сохраняем invoice_id как payment_id для отслеживания
    invoice.payment_id = str(invoice_id)
    invoice.payment_method = payment_method
    invoice.payment_status = PaymentStatus.PENDING
    db.commit()
    
    # Отправляем счет клиенту через Telegram Bot Payments
    from telegram import LabeledPrice
    
    client = invoice.client
    try:
        # FreedomPay KG работает с валютой KGS (киргизский сом)
        # Формируем список цен (Telegram требует массив LabeledPrice)
        # Сумма должна быть в тийинах (1 KGS = 100 тийинов), как и копейки в рублях
        prices = [
            LabeledPrice(
                label=invoice.description[:64],  # Максимум 64 символа
                amount=int(invoice.amount * 100)  # Сумма в тийинах (1 KGS = 100 тийинов)
            )
        ]
        
        # Отправляем счет клиенту через sendInvoice
        await context.bot.send_invoice(
            chat_id=client.telegram_id,
            title=invoice.description[:32],  # Название счета (макс 32 символа)
            description=invoice.description[:255],  # Описание (макс 255 символов)
            payload=str(invoice_id),  # Уникальный идентификатор (invoice_id)
            provider_token=TELEGRAM_PAYMENT_PROVIDER_TOKEN,
            currency="KGS",  # Валюта KGS для FreedomPay KG
            prices=prices,
            start_parameter=f"invoice_{invoice_id}",  # Уникальный параметр для deep linking
            is_flexible=False  # Не гибкая цена
        )
        
        # Обновляем сообщение для мастера
        success_message = (
            f"✅ Счет отправлен клиенту\n\n"
            f"Услуга: {invoice.description}\n"
            f"Сумма: {invoice.amount:.2f} ₽\n\n"
            f"Клиенту отправлен счет на оплату через Telegram."
        )
        
        keyboard = [
            [InlineKeyboardButton("◀️ Мои записи", callback_data="master_appointments")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await safe_edit_message_text(query, success_message, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Ошибка отправки счета клиенту: {e}")
        await safe_edit_message_text(
            query,
            f"Ошибка отправки счета клиенту: {str(e)}\n\n"
            f"Проверьте настройки Telegram Payment Provider Token."
        )


async def pay_invoice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопки оплаты чека"""
    query = update.callback_query
    await query.answer()
    
    db = get_db_from_context(context)
    
    # Извлекаем ID чека
    invoice_id = int(query.data.split("_")[-1])
    
    # Получаем чек
    invoice_obj = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    
    if not invoice_obj:
        await safe_edit_message_text(query, "Ошибка: чек не найден")
        return
    
    # Проверяем, что чек принадлежит текущему пользователю
    user_data = update.effective_user
    user = db.query(User).filter(User.telegram_id == user_data.id).first()
    
    if not user or user.id != invoice_obj.client_id:
        await safe_edit_message_text(query, "Ошибка: у вас нет доступа к этому чеку")
        return
    
    # Проверяем статус платежа
    if invoice_obj.payment_status == PaymentStatus.SUCCEEDED:
        await safe_edit_message_text(query, "✅ Чек уже оплачен")
        return
    
    if not invoice_obj.payment_id:
        await safe_edit_message_text(query, "Ошибка: платеж не создан")
        return
    
    # Проверяем наличие ссылки на оплату
    if not invoice_obj.payment_url:
        await safe_edit_message_text(query, "Ошибка: ссылка на оплату не найдена")
        return
    
    # Отправляем ссылку на оплату
    message_text = (
        f"💳 Оплата чека\n\n"
        f"Услуга: {invoice_obj.description}\n"
        f"Сумма: {invoice_obj.amount:.2f} ₽\n\n"
        f"Перейдите по ссылке для оплаты:"
    )
    
    keyboard = [
        [InlineKeyboardButton("💳 Оплатить", url=invoice_obj.payment_url)],
        [InlineKeyboardButton("🔄 Проверить статус", callback_data=f"check_payment_{invoice_obj.id}")],
        [InlineKeyboardButton("◀️ Мои записи", callback_data="client_appointments")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await safe_edit_message_text(query, message_text, reply_markup=reply_markup)


async def check_payment_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка статуса платежа"""
    query = update.callback_query
    await query.answer()
    
    db = get_db_from_context(context)
    
    # Извлекаем ID чека
    invoice_id = int(query.data.split("_")[-1])
    
    # Получаем чек
    invoice_obj = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    
    if not invoice_obj:
        await safe_edit_message_text(query, "Ошибка: чек не найден")
        return
    
    # Проверяем статус платежа
    if invoice_obj.payment_status == PaymentStatus.SUCCEEDED:
        await safe_edit_message_text(
            query,
            f"✅ Чек оплачен!\n\n"
            f"Услуга: {invoice_obj.description}\n"
            f"Сумма: {invoice_obj.amount:.2f} ₽\n"
            f"Дата оплаты: {invoice_obj.paid_at.strftime('%d.%m.%Y %H:%M') if invoice_obj.paid_at else 'Не указана'}"
        )
    elif invoice_obj.payment_status == PaymentStatus.PENDING:
        await safe_edit_message_text(
            query,
            f"⏳ Платеж ожидает оплаты\n\n"
            f"Услуга: {invoice_obj.description}\n"
            f"Сумма: {invoice_obj.amount:.2f} ₽\n\n"
            f"Счет отправлен через Telegram."
        )
    else:
        await safe_edit_message_text(
            query,
            f"❌ Статус платежа: {invoice_obj.payment_status.value}\n\n"
            f"Попробуйте оплатить снова."
        )


async def pre_checkout_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик PreCheckoutQuery - подтверждение платежа перед оплатой"""
    query = update.pre_checkout_query
    db = get_db_from_context(context)
    
    try:
        logger.info(f"Получен PreCheckoutQuery: payload={query.invoice_payload}, amount={query.total_amount}, currency={query.currency}")
        
        # Извлекаем invoice_id из payload
        invoice_id = int(query.invoice_payload)
        
        # Получаем чек
        invoice_obj = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        
        if not invoice_obj:
            logger.error(f"Чек {invoice_id} не найден для PreCheckoutQuery")
            await query.answer(ok=False, error_message="Чек не найден")
            return
        
        # Проверяем, что чек еще не оплачен
        if invoice_obj.payment_status == PaymentStatus.SUCCEEDED:
            logger.warning(f"Чек {invoice_id} уже оплачен")
            await query.answer(ok=False, error_message="Чек уже оплачен")
            return
        
        # Проверяем сумму (в тийинах для KGS)
        # Допускаем небольшую погрешность для округления (до 1 тийина)
        expected_amount = int(invoice_obj.amount * 100)  # В тийинах (1 KGS = 100 тийинов)
        actual_amount = query.total_amount
        
        logger.info(f"Сравнение сумм для чека {invoice_id}: ожидается {expected_amount} тийинов ({invoice_obj.amount} KGS), получено {actual_amount} тийинов")
        
        # Допускаем разницу в 1 тийин из-за округления
        amount_diff = abs(expected_amount - actual_amount)
        if amount_diff > 1:
            logger.warning(
                f"Неверная сумма для чека {invoice_id}: "
                f"ожидается {expected_amount} тийинов ({invoice_obj.amount} KGS), "
                f"получено {actual_amount} тийинов (разница: {amount_diff})"
            )
            await query.answer(
                ok=False,
                error_message=f"Неверная сумма. Ожидается {invoice_obj.amount:.2f} KGS"
            )
            return
        
        # Проверяем валюту (допускаем KGS, даже если в базе другая)
        if query.currency != "KGS":
            logger.warning(
                f"Неверная валюта для чека {invoice_id}: "
                f"ожидается KGS, получено {query.currency}"
            )
            await query.answer(
                ok=False,
                error_message="Неверная валюта. Ожидается KGS"
            )
            return
        
        # Подтверждаем платеж (Telegram требует ответ в течение 10 секунд)
        await query.answer(ok=True)
        logger.info(f"✓ PreCheckoutQuery подтвержден для чека {invoice_id}, сумма {actual_amount} тийинов ({actual_amount/100:.2f} KGS)")
        
    except ValueError as e:
        logger.error(f"Неверный формат invoice_payload в PreCheckoutQuery: {query.invoice_payload}, ошибка: {e}")
        await query.answer(ok=False, error_message="Неверный формат чека")
    except Exception as e:
        logger.error(f"Ошибка обработки PreCheckoutQuery: {e}", exc_info=True)
        await query.answer(ok=False, error_message="Ошибка обработки платежа")


async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик успешной оплаты через Telegram Bot Payments"""
    payment = update.message.successful_payment
    db = get_db_from_context(context)
    
    try:
        logger.info(
            f"Получен successful_payment: payload={payment.invoice_payload}, "
            f"amount={payment.total_amount}, currency={payment.currency}"
        )
        
        # Извлекаем invoice_id из payload
        invoice_id = int(payment.invoice_payload)
        
        # Получаем чек
        invoice_obj = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        
        if not invoice_obj:
            logger.error(f"Чек {invoice_id} не найден для успешного платежа")
            return
        
        # Обновляем статус платежа
        invoice_obj.payment_status = PaymentStatus.SUCCEEDED
        invoice_obj.paid_at = datetime.utcnow()
        invoice_obj.payment_method = payment.currency  # Сохраняем валюту
        db.commit()
        
        logger.info(f"✓ Чек {invoice_id} успешно оплачен через Telegram Bot Payments")
        
        # Уведомляем клиента
        client = invoice_obj.client
        try:
            await context.bot.send_message(
                chat_id=client.telegram_id,
                text=(
                    f"✅ Платеж успешно завершен!\n\n"
                    f"Услуга: {invoice_obj.description}\n"
                    f"Сумма: {invoice_obj.amount:.2f} {invoice_obj.currency}\n"
                    f"Спасибо за оплату!"
                )
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления клиенту: {e}")
        
        # Уведомляем мастера
        try:
            master_user = invoice_obj.master_profile.user
            await context.bot.send_message(
                chat_id=master_user.telegram_id,
                text=(
                    f"✅ Чек оплачен!\n\n"
                    f"Услуга: {invoice_obj.description}\n"
                    f"Клиент: {invoice_obj.client.full_name}\n"
                    f"Сумма: {invoice_obj.amount:.2f} {invoice_obj.currency}\n"
                    f"Дата оплаты: {invoice_obj.paid_at.strftime('%d.%m.%Y %H:%M')}"
                )
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления мастеру: {e}")
        
    except ValueError as e:
        logger.error(f"Неверный формат invoice_payload: {payment.invoice_payload}, ошибка: {e}")
    except Exception as e:
        logger.error(f"Ошибка обработки успешного платежа: {e}", exc_info=True)


async def payment_error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок оплаты (если они приходят через сообщения)"""
    if update.message:
        # Логируем все сообщения связанные с оплатой
        if update.message.successful_payment:
            logger.info("Получено сообщение с successful_payment")
        elif hasattr(update.message, 'invoice'):
            logger.info(f"Получено сообщение с invoice: {update.message.invoice}")
        
        # Проверяем текст сообщения на ошибки
        if update.message.text:
            text_lower = update.message.text.lower()
            if "payment failed" in text_lower or "ошибка" in text_lower or "failed" in text_lower:
                logger.warning(f"⚠️ Обнаружено сообщение об ошибке оплаты: {update.message.text}")
        
    logger.debug(f"Update received: {update.update_id}, message: {update.message.text if update.message else 'No message'}")

